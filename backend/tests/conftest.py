"""Test fixtures.

Tests run against a real Postgres/PostGIS instance (the docker-compose
`postgres` service) using a separate `<POSTGRES_DB>_test` database, since
GeoAlchemy2/PostGIS geometry types have no SQLite equivalent. This means
the docker-compose stack must be up (`docker compose up -d`) to run tests.
"""

import uuid

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.base import Base
from app.deps import get_db
from app.main import app
from app import models  # noqa: F401  (registers all models on Base.metadata)

TEST_DB_NAME = f"{settings.postgres_db}_test"


def _admin_url(dbname: str) -> str:
    return (
        f"postgresql+psycopg2://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{dbname}"
    )


@pytest.fixture(scope="session")
def test_engine():
    # Connect to the default 'postgres' maintenance DB to (re)create the test DB.
    admin_engine = create_engine(_admin_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            sa.text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DB_NAME},
        ).scalar_one_or_none()
        if not exists:
            conn.execute(sa.text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()

    engine = create_engine(_admin_url(TEST_DB_NAME), future=True)
    with engine.connect() as conn:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine) -> Session:
    """A DB session bound to a per-test transaction that is always rolled back."""
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, future=True)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def make_well(db_session: Session):
    """Factory for a clearly-labeled demo Well row."""
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    from app.models.well import Well

    def _make(**overrides):
        defaults = dict(
            well_id=f"DEMO-{uuid.uuid4().hex[:8]}",
            name="Demo Test Well",
            operator="Demo Operator",
            field="Demo Field",
            country="Norway",
            location=from_shape(Point(2.34, 58.44), srid=4326),  # ~Volve area
            water_depth_m=80.0,
            total_depth_md_m=3500.0,
            total_depth_tvd_m=3000.0,
            formation="Hugin",
            source="demo",
        )
        defaults.update(overrides)
        well = Well(**defaults)
        db_session.add(well)
        db_session.commit()
        db_session.refresh(well)
        return well

    return _make


@pytest.fixture()
def make_wellbore(db_session: Session):
    """Factory for a Wellbore under a given Well, optionally with a real
    LineString trajectory (a list of (lon, lat) points)."""
    from geoalchemy2.shape import from_shape
    from shapely.geometry import LineString

    from app.models.wellbore import Wellbore

    def _make(well, trajectory_points: list[tuple[float, float]] | None = None, **overrides):
        defaults = dict(
            well_id=well.id,
            name=overrides.pop("name", f"{well.well_id} (demo bore)"),
            source=well.source,
        )
        if trajectory_points is not None:
            defaults["trajectory"] = from_shape(LineString(trajectory_points), srid=4326)
        defaults.update(overrides)
        wellbore = Wellbore(**defaults)
        db_session.add(wellbore)
        db_session.commit()
        db_session.refresh(wellbore)
        return wellbore

    return _make
