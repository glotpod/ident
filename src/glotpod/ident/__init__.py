import logging

import toml

from logging.handlers import MemoryHandler
from os import environ

from aiohttp import web
from aiopg.sa import create_engine

from glotpod.ident import handlers, notifications


def load_config():
    defaults = {
        'database': {}
    }

    if 'IDENT_SETTINGS' in environ:
        with open(environ['IDENT_SETTINGS']) as fh:
            text = fh.read()
            defaults.update(toml.loads(text))

    return defaults


def configure_logging(log, level=logging.INFO):
    log.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    memory_handler = MemoryHandler(10, target=stream_handler)

    log.addHandler(memory_handler)


async def db_pool_middleware_factory(app, handler):
    # This middleware adds a postgres connection pool to every request.
    # It doesn't actually acquire a database connection however; handlers
    # must do that themselves. The simplest was is using an async with
    # block::
    #
    #   async with request['db_pool'] as conn:
    #       do_something_with(conn)
    #

    # Create a connection pool on the first request
    if 'db_engine' not in app:
        default_args = {'database': 'glotpod.ident', 'user': 'postgres'}
        args = app['config'].get('database', {}).get('postgres', default_args)

        app['log'].info("Creating pooled database connections.")
        app['db_engine'] = await create_engine(**args)

        async def cleanup(app):
            app['log'].info("Disposing pooled database connections.")
            app['db_engine'].close()
            await app['db_engine'].wait_closed()

        app.on_shutdown.append(cleanup)

    async def middleware_handler(request):
        request['db_pool'] = app['db_engine']
        return await handler(request)

    return middleware_handler


async def logging_middleware_factory(app, handler):
    # This middleware emits messages to the application log, *and* it
    # sets up logging.

    # If the application doesn't have a log, create it
    if 'log' not in app:
        app['log'] = logging.getLogger(__name__)
        configure_logging(app['log'])

    async def middleware_handler(request):
        log = app['log']

        log.info("request: %s %r", request.method, request.path_qs)
        log.debug("this request is being passed to: %s", handler)

        request_log = "%s.%s".format(__name__, handler.__name__)
        log.debug("setting request log: %s", request_log)
        request['log'] = logging.getLogger(request_log)

        try:
            res = await handler(request)

        except Exception as e:
            if isinstance(e, web.HTTPException):
                log.debug("request handling succeeded.")
                log.info("response: %s %s (<unknown> bytes)",
                         e.status, e.reason)
            else:
                log.exception("request handling failed.")

            raise

        else:
            log.debug("request handling succeeded.")
            log.info("response: %s %s (<unknown> bytes)",
                     res.status, res.reason)
            return res

    return middleware_handler


async def subscribers_middleware_factory(app, handler):
    # This middleware sends events to the notifications micro-service
    if 'subscribers' not in app:
        app['subscribers'] = sender = notifications.Sender(app.loop)

        async def cleanup(app):
            await sender.cleanup()

        app.on_shutdown.append(cleanup)

    return handler


def init_app(_, *, loop=None):
    """Initialise the application object, to be served by aiohttp."""
    middlewares = [db_pool_middleware_factory,
                   subscribers_middleware_factory, logging_middleware_factory]

    app = web.Application(loop=loop, middlewares=middlewares)
    app['config'] = load_config()

    app.router.add_route('*', '/', handlers.AllUsers, name='user-list')
    app.router.add_route('*', '/{id}', handlers.User, name='user')

    return app


app = init_app([])
