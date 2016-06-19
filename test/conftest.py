import asyncio
import os
import uuid

import pytest

from sqlalchemy import create_engine

from cryptography.fernet import Fernet
from glotpod.ident import load_config, init_app, fernet_middleware_factory
from glotpod.ident.model import metadata, users, services


class ModelFixture:
    # Helper class to modify a database model
    def __init__(self, engine):
        self.conn = engine.connect()

        # Ensure the database is created
        metadata.create_all(engine)

        self.engine = engine

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

    def cleanup(self):
        metadata.drop_all(self.engine)


@pytest.fixture
def dbengine(config):
    cfg = config['database']['postgres']
    connect_url = 'postgresql://{user}:{password}' \
                  '@{host}:{port}/{database}'.format(**cfg)

    engine = create_engine(connect_url)
    return engine


@pytest.yield_fixture
def model(dbengine):
    m = ModelFixture(dbengine)
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
    dbcfg.setdefault('database', 'glotpod.ident')

    for var in os.environ:
        if var.startswith('IDENT_TEST_POSTGRES_'):
            key = var[len('IDENT_TEST_POSTGRES_'):].lower()
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
