"""
Test configuration and fixtures for the energy tracker backend.
"""
import os
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import AuthSession, User
from app.models.base import Base
from app.models.user import UserRole
from app.security import generate_session_token, hash_password, hash_session_token

# Default admin account used by the `client` fixture (all business
# endpoints require authentication since the global route guard).
TEST_ADMIN_USERNAME = "testadmin"
TEST_ADMIN_PASSWORD = "test admin fixture password"
# Hash is computed once per test session (Argon2 is deliberately slow).
TEST_ADMIN_PASSWORD_HASH = hash_password(TEST_ADMIN_PASSWORD)

# Tests MUST run against PostgreSQL: the tariff_periods EXCLUDE constraint
# (overlap prevention) and daterange/btree_gist have no SQLite equivalent,
# so overlap tests would silently not be enforced on SQLite.
# The default points at the dedicated test DB from docker-compose.dev.yml
# (db-test service, energy_tracker_test on port 5433). Override with
# TEST_DATABASE_URL if needed - note that tests requiring the EXCLUDE
# constraint will FAIL (not pass silently) on SQLite.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/energy_tracker_test"
)

@pytest.fixture(scope="session")
def engine():
    """Create SQLAlchemy engine for test session."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {},
        poolclass=StaticPool if "sqlite" in TEST_DATABASE_URL else None,
    )
    
    # Create tables using alembic for PostgreSQL, direct creation for SQLite
    if "sqlite" in TEST_DATABASE_URL:
        Base.metadata.create_all(bind=engine)
    else:
        # For PostgreSQL, we should use alembic to create schema
        # This ensures migrations are tested too
        # Set DATABASE_URL environment variable for alembic
        original_db_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = TEST_DATABASE_URL
        
        try:
            from alembic.config import Config

            from alembic import command
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
            command.upgrade(alembic_cfg, "head")
        finally:
            # Restore original DATABASE_URL if it existed
            if original_db_url is not None:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)
    
    yield engine
    
    if "sqlite" in TEST_DATABASE_URL:
        Base.metadata.drop_all(bind=engine)
    else:
        # Clean up PostgreSQL database
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE;"))
            conn.execute(text("CREATE SCHEMA public;"))
            conn.commit()

@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh database session for each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    # Clean up all data before test starts
    if "postgresql" in TEST_DATABASE_URL:
        session.execute(text("""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' RESTART IDENTITY CASCADE';
                END LOOP;
            END $$;
        """))
        session.commit()
    else:
        # For SQLite, delete all data
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()

def _override_get_db(db_session):
    def override():
        try:
            yield db_session
        finally:
            pass

    return override


def _create_test_admin_with_session(db_session) -> str:
    """Create the test admin plus a valid AuthSession row directly in the
    database (fast: no Argon2 verification per test) and return the
    raw session token for the cookie."""
    user = User(
        username=TEST_ADMIN_USERNAME,
        password_hash=TEST_ADMIN_PASSWORD_HASH,
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    token = generate_session_token()
    db_session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(UTC) + timedelta(hours=2),
            last_used_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    return token


@pytest.fixture(scope="function")
def client(db_session):
    """Authenticated TestClient: logged in as TEST_ADMIN via a session
    cookie, so the ~240 business endpoint tests keep working under the
    global route guard without individual changes."""
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    token = _create_test_admin_with_session(db_session)
    with TestClient(app) as test_client:
        test_client.cookies.set(settings.SESSION_COOKIE_NAME, token)
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def anon_client(db_session):
    """Unauthenticated TestClient (no session cookie) for tests that
    verify 401 behaviour of protected endpoints."""
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def sample_meter_data():
    """Sample meter data for testing.

    Note: no "unit" field - the unit is derived server-side from
    meter_type and a client-supplied unit is rejected with 422.
    """
    return {
        "meter_type": "gas",
        "label": "Main Gas Meter",
    }

@pytest.fixture
def sample_reading_data():
    """Sample reading data for testing."""
    return {
        "meter_id": 1,
        "value": "1234.56",
        "reading_date": "2024-01-15",
        "note": "Monthly reading"
    }

@pytest.fixture
def sample_advance_payment_data():
    """Sample advance payment data for testing."""
    return {
        "category": "gas",
        "meter_id": 1,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "monthly_amount": "120.00"
    }


@pytest.fixture
def sample_tariff_period_data():
    """Sample tariff period data for testing."""
    return {
        "meter_id": 1,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "price_per_unit": "0.35490",
        "base_fee_monthly": "12.50"
    }
