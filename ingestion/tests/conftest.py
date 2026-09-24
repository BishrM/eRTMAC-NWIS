"""DB fixtures for loader tests. Reuses the same nwis_test Postgres/PostGIS
database as backend/tests (docker compose must be up) so no second test
database needs to be created."""

import sqlalchemy as sa
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ingestion import _backend_path  # noqa: F401
from app.config import settings
from app.db.base import Base
from app import models  # noqa: F401

TEST_DB_NAME = f"{settings.postgres_db}_test"


def _url(dbname: str) -> str:
    return (
        f"postgresql+psycopg2://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{dbname}"
    )


@pytest.fixture(scope="session")
def test_engine():
    admin_engine = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            sa.text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar_one_or_none()
        if not exists:
            conn.execute(sa.text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()

    engine = create_engine(_url(TEST_DB_NAME), future=True)
    with engine.connect() as conn:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, future=True)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
