import asyncio
import logging
import signal
import sys
import traceback

import aioamqp
import msgpack
import toml

from functools import partial
from os import environ

from aiopg.sa import create_engine
from cryptography.fernet import Fernet

from glotpod.ident import handlers


ROUTING_KEY_PREFIX = 'rpc.user.'  # amqp binding key
MAX_RETRY_TIMEOUT = 5 * 60  # 5 minutes


class NotificationSender:
    def __init__(self, channel):
        self.channel = channel

    def __getitem__(self, event):
        return partial(self, "notifications.user.{}".format(event))

    async def __call__(self, routing_key, payload_bytes):
        await self.channel.basic_publish(
            exchange_name='amq.topic',
            routing_key=routing_key,
            payload=payload_bytes
        )


class IdentService(dict):
    _log = logging.getLogger(__name__)

    def __init__(self, cfg):
        self._log.info("Initializing new identity service...")
        super().__init__()

        self.update(cfg)
        self.handlers = {
            'get': handlers.get_user,
            'create': handlers.create_user,
            'patch': handlers.patch_user
        }

        key = cfg.get('database', {}).get('encryption_key')
        if key is None:
            raise ValueError(
                "Configuration value {!r} must be set to a base32 encoded "
                "fernet key".format("database.encryption_key")
            )
        self['db_fernet'] = Fernet(key)

    async def __setup_amqp(self):
        self._log.info("Connecting to AMQP broker.")
        self['transport'], self['protocol'] = await aioamqp.connect(
            **self.get('amqp', {}))
        self['channel'] = await self.protocol.channel()

        self._log.info("Declaring AMQP queues")
        # Declare a queue for all of the events we expect from the application
        # This will be a shared queue so that work isn't duplicated.
        await self.channel.queue_declare('glotpod.rpc/ident', durable=True)
        await self.channel.queue_bind('glotpod.rpc/ident', 'amq.topic',
                                      ROUTING_KEY_PREFIX + '#')

        # Setup basic consumption
        await self.channel.basic_consume(self.handle_request,
                                         queue_name='glotpod.rpc/ident')

        self._log.info("Waiting for events")

    async def __setup_db_conn(self):
        # Connect to postgres
        default_args = {'database': 'glotpod.ident', 'user': 'glotpod.ident'}
        args = self.get('database', {}).get('postgres', default_args)

        self._log.info("Connecting to database server.")

        self['db_engine'] = engine = await create_engine(**args)

    async def setup(self):
        await self.__setup_db_conn()
        await self.__setup_amqp()

        # Additional things we will need
        self['notifications-sender'] = NotificationSender(self.channel)

    async def cleanup(self):
        if 'protocol' in self:
            self._log.info("Disposing AMQP connection.")
            await self.protocol.close()

        if 'transport' in self:
            self.transport.close()

        if 'db_engine' in self:
            self._log.info("Disposing database connections.")
            self['db_engine'].close()
            await self['db_engine'].wait_closed()

    async def handle_request(self, channel, body, envelope, properties):
        key = envelope.routing_key[len(ROUTING_KEY_PREFIX):]
        handler_log = logging.getLogger(
            envelope.routing_key.replace(ROUTING_KEY_PREFIX, __name__))

        self._log.info("Handling remote call to '%s'", key)

        try:
            args = msgpack.unpackb(body, encoding='utf-8')
            handler = self.handlers[key]
        except KeyError:
            self._log.warn("No handler registered for '%s'", key)
            resp = {'error': 'operation_not_found'}
        except:
            self._log.error("Could not decode call with msgpack.")
            self._log.error(body)
            resp = {'error': 'decode_error'}
        else:
            helpers = dict(self)
            helpers['log'] = handler_log
            helpers['notify'] = self['notifications-sender'][key]

            async with self['db_engine'].acquire() as self['db_conn']:
                db_transaction = await self['db_conn'].begin()

                try:
                    resp = {'result': await handler(helpers, **args)}
                    await db_transaction.commit()
                except (KeyError, TypeError, ValueError):
                    self._log.exception("Handler %r did not receive required data",
                                        handler)
                    resp = {'error': 'bad_request'}
                except handlers.HandlerError as e:
                    self._log.exception("Handler %r raised a direct error: %r",
                                        handler, e)
                    resp = dict(e)
                except:
                    self._log.exception("Handler %r failed", handler)
                    resp = {'error': 'invocation_failed'}
                    await db_transaction.rollback()
                finally:
                    await db_transaction.close()
        finally:
            await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)

            if properties.reply_to:
                try:
                    payload = msgpack.packb(resp)
                except:
                    self._log.exception("Could not pack handler response: %r",
                                        resp)
                    payload = msgpack.packb({"error": "invocation_failed"})
                finally:
                    self._log.info("Dispatching response to '%s'",
                                   properties.reply_to)
                    await self.channel.basic_publish(
                        exchange_name='',
                        routing_key=properties.reply_to,
                        payload=payload,
                        properties={
                            'correlation_id': properties.correlation_id
                        },
                    )

    @property
    def channel(self):
        return self.get('channel')

    @property
    def protocol(self):
        return self.get('protocol')

    @property
    def transport(self):
        return self.get('transport')


def load_config():
    defaults = {
        'database': {},
        'amqp': {}
    }

    if 'GLOTPOD_IDENT_SETTINGS' in environ:
        with open(environ['GLOTPOD_IDENT_SETTINGS']) as fh:
            text = fh.read()
            defaults.update(toml.loads(text))

    return defaults


def main(argv=None):
    loop = asyncio.get_event_loop()

    config = load_config()
    ident = IdentService(config)

    if sys.platform != 'win32':
        loop.add_signal_handler(signal.SIGINT, loop.stop)
        loop.add_signal_handler(signal.SIGTERM, loop.stop)

    closed_connections = []

    def health_check():
        ident._log.debug("Checking held connections.")

        if not ident['protocol'].is_open:
            closed_connections.append(True)
            loop.stop()

        if ident['db_conn'].closed:
            closed_connections.append(True)
            loop.stop()

        loop.call_later(5, health_check)

    try:
        loop.run_until_complete(ident.setup())
        loop.call_soon(health_check)
        loop.run_forever()
    except:
        traceback.print_exc()
        sys.exit(129)
    else:
        if closed_connections:
            sys.exit(129)
    finally:
        ident._log.info("Cleaning up.")
        loop.run_until_complete(ident.cleanup())
        loop.close()
        ident._log.info("Exit.")
