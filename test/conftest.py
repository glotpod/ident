import asyncio
import os
import uuid

import aioamqp
import msgpack
import pytest

from sqlalchemy import create_engine

from phi.common.ident import load_config, IdentService
from phi.common.ident.model import metadata, users, services
from phi.common.ident.handlers import HandlerError


class IdentServiceCaller:
    # Simulate an external call into an identity service
    def __init__(self, loop, ident):
        self.loop = loop
        loop.run_until_complete(ident.setup())
        loop.run_until_complete(self.connect_amqp(ident))
        self.ident = ident

    async def connect_amqp(self, cfg):
        self.transport, self.protocol = await aioamqp.connect(
            **cfg.get('amqp', {}))
        self.channel = await self.protocol.channel()

    async def cleanup(self):
        await self.ident.cleanup()
        await self.protocol.close()
        self.transport.close()

    async def send(self, op, arg, timeout=10):
        # Send a message into the identity service and wait for
        # a response.
        if arg is None:
            payload = b''

        elif isinstance(arg, bytes):
            payload = arg

        else:
            payload = msgpack.packb(arg)

        # Correlation id and routing key
        corr_id = str(uuid.uuid4())
        routing_key = "rpc.user.{}".format(op)

        # Setup a temporary queue to receive our results
        result = await self.channel.queue_declare(
            durable=False, exclusive=True)
        callback_queue = result['queue']

        # Publish the request
        await self.channel.basic_publish(
            exchange_name='amq.topic',
            routing_key=routing_key,
            payload=payload,
            properties=dict(
                correlation_id=corr_id,
                reply_to=callback_queue))

        items = asyncio.Queue()

        # Consume the callback queue
        async def handle_results(channel, body, envelope, properties):
            if properties.correlation_id == corr_id:
                await items.put(msgpack.unpackb(body, encoding='utf-8'))
        await self.channel.basic_consume(handle_results, no_ack=True,
                                         queue_name=callback_queue)

        return await asyncio.wait_for(items.get(), timeout, loop=self.loop)


class TestIdentService(IdentService):
    def __init__(self, config):
        super().__init__(config)
        self.handlers['test'] = self.test
        self.handlers['errors'] = self.errors
        self.handlers['echo'] = self.echo
        self.handlers['bad_data'] = self.bad_data
        self.handlers['value_err'] = self.value_err
        self.handlers['type_err'] = self.type_err
        self.handlers['handler_err'] = self.handler_err

    async def test(self, helpers, **args):
        return args['test']

    async def echo(self, helpers, **args):
        return args

    async def errors(self, helpers, **args):
        return {'foo': bar}

    async def bad_data(self, helpers, **data):
        return pytest

    async def value_err(self, helpers, **data):
        raise ValueError

    async def type_err(self, helpers, **data):
        raise ValueError

    async def handler_err(self, helpers, **data):
        raise HandlerError(data['err'])


class ModelFixture:
    # Helper class to modify a database model
    def __init__(self, ident, engine):
        self.ident = ident
        self.conn = engine.connect()
        self._users = []

    def add_user(self, **args):
        id = self.conn.execute(
            users.insert().values(**args).returning(users.c.id)
        ).scalar()
        self._users.append(id)
        return id

    def add_github_info(self, **args):
        args['sv_name'] = 'gh'
        return self.add_service_info(**args)

    def add_facebook_info(self, **args):
        args['sv_name'] = 'fb'
        return self.add_service_info(**args)

    def add_service_info(self, **args):
        if 'access_token' in args:
            args['access_token'] = self.ident['db_fernet'].encrypt(
                args['access_token'].encode('utf8'))

        return self.conn.execute(
            services.insert().values(**args).returning(
                services.c.sv_name,
                services.c.user_id
            )
        ).fetchone()

    def cleanup(self):
        for id in self._users:
            self.conn.execute(services.delete(services.c.user_id == id))
            self.conn.execute(users.delete(users.c.id == id))

        self._svcs = []
        self._users = []


@pytest.fixture
def dbengine(config):
    cfg = config['database']['postgres']
    connect_url = 'postgresql://{user}:{password}' \
                  '@{host}:{port}/{database}'.format(**cfg)

    engine = create_engine(connect_url)
    return engine


@pytest.yield_fixture
def caller(event_loop, ident):
    # Set up a fake identity service and call into it
    caller = IdentServiceCaller(event_loop, ident)
    yield caller
    event_loop.run_until_complete(caller.cleanup())


@pytest.yield_fixture
def ident(dbengine, config):
    metadata.create_all(bind=dbengine)
    yield TestIdentService(config)
    metadata.drop_all(bind=dbengine)


@pytest.yield_fixture
def model(dbengine, ident):
    m = ModelFixture(ident, dbengine)
    yield m
    m.cleanup()


@pytest.yield_fixture
def amqpchannel(config, event_loop):
    transport, protocol = event_loop.run_until_complete(
        aioamqp.connect(**config.get('amqp', {}))
    )
    channel = event_loop.run_until_complete(protocol.channel())
    yield channel
    event_loop.run_until_complete(protocol.close())
    transport.close()


@pytest.fixture
def config():
    cfg = load_config()
    dbcfg = cfg.setdefault('database', {}).setdefault('postgres', {})

    dbcfg.setdefault('user', 'postgres')
    dbcfg.setdefault('password', '')
    dbcfg.setdefault('host', 'localhost'),
    dbcfg.setdefault('port', '5432')
    dbcfg.setdefault('database', 'phi.common.ident')

    for var in os.environ:
        if var.startswith('PHI_IDENT_TEST_POSTGRES_'):
            key = var[len('PHI_IDENT_TEST_POSTGRES_'):].lower()
            dbcfg[key] = os.environ[var]

    return cfg
