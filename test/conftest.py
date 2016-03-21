import pytest

from unittest.mock import MagicMock

from sqlalchemy import create_engine


@pytest.fixture
def dbmock():
    return MagicMock()


@pytest.fixture
def dbengine(dbmock):
    engine = create_engine('postgresql://', echo=True, strategy='mock',
                           executor=dbmock)
    return engine
