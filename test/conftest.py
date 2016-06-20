import os

import aiopg.sa
import asyncio
import pytest

from sqlalchemy import create_engine

from cryptography.fernet import Fernet
from glotpod.ident import load_config, init_app
from glotpod.ident.model import metadata, users, services
from webtest_aiohttp import TestApp as WebtestApp


class ModelFixture:
    # Helper class to modify a database model
    def __init__(self, conn):
        self.conn = conn

    def add_user(self, **args):
        return self.conn.execute(
            users.insert().values(**args).returning(users.c.id)
        ).scalar()

    def add_github_info(self, **args):
        args['sv_name'] = 'gh'
        return self.add_service_info(**args)

    def add_facebook_info(self, **args):
        args['sv_name'] = 'fb'
        return self.add_service_info(**args)

    def add_service_info(self, **args):
        return self.conn.execute(
            services.insert().values(**args).returning(
                services.c.sv_name,
                services.c.user_id
            )
        ).fetchone()


@pytest.fixture(scope="session")
def dbengine(config):
    cfg = config['database']['postgres']
    connect_url = 'postgresql://{user}:{password}' \
                  '@{host}:{port}/{database}'.format(**cfg)

    engine = create_engine(connect_url)
    metadata.drop_all(engine) # remove traces of any old data
    return engine


@pytest.fixture(scope="session")
def dbconn(dbengine):
    return dbengine.connect()


@pytest.yield_fixture
def model(dbconn, dbengine):
    metadata.create_all(dbengine)
    yield ModelFixture(dbconn)
    metadata.drop_all(dbengine)


@pytest.fixture(scope="session")
def config():
    cfg = load_config()
    dbcfg = cfg.setdefault('database', {}).setdefault('postgres', {})

    dbcfg.setdefault('user', 'postgres')
    dbcfg.setdefault('password', '')
    dbcfg.setdefault('host', 'localhost'),
    dbcfg.setdefault('port', '5432')
    dbcfg.setdefault('database', 'glotpod.ident')

    for var in os.environ:
        if var.startswith('IDENT_TEST_POSTGRES_'):
            key = var[len('IDENT_TEST_POSTGRES_'):].lower()
            dbcfg[key] = os.environ[var]

    return cfg


@pytest.fixture
def fernet(config):
    return Fernet(config['database']['encryption_key'])


@pytest.yield_fixture(scope="session")
def app(config):
    event_loop = asyncio.get_event_loop()
    app = init_app([], loop=event_loop)
    app['config'] = config
    app['db_engine'] = event_loop.run_until_complete(
        aiopg.sa.create_engine(loop=event_loop, minsize=10, **config['database']['postgres'])
    )
    yield app
    app['db_engine'].close()
    event_loop.run_until_complete(app['db_engine'].wait_closed())
    event_loop.run_until_complete(app.shutdown())


@pytest.fixture
def client(app):
    return WebtestApp(app)
