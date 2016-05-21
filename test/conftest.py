import asyncio
import os
import uuid

import aioamqp
import msgpack
import pytest

from sqlalchemy import create_engine

from cryptography.fernet import Fernet
from phi.common.ident import load_config, init_app, fernet_middleware_factory
from phi.common.ident.model import metadata, users, services
from phi.common.ident.handlers import HandlerError


class ModelFixture:
    # Helper class to modify a database model
    def __init__(self, fernet, engine):
        self.fernet = fernet
        self.conn = engine.connect()
        self._users = []

        # Ensure the database is created
        metadata.create_all(engine)

        # Restart the ID sequence
        self.conn.execute("ALTER SEQUENCE users_id_seq RESTART;");

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
            args['access_token'] = self.fernet.encrypt(
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
def model(dbengine, fernet):
    m = ModelFixture(fernet, dbengine)
    yield m
    m.cleanup()


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


@pytest.fixture
def fernet(config):
    return Fernet(config['database']['encryption_key'])


@pytest.yield_fixture
def app(config, event_loop):
    app = init_app([], loop=event_loop)
    app['config'] = config
    yield app
    event_loop.run_until_complete(app.shutdown())
