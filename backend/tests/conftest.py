"""
Test configuration and fixtures for the energy tracker backend.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models.base import Base

# Use PostgreSQL test database if available, fallback to SQLite for local testing
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite:///:memory:"
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

@pytest.fixture(scope="function")
def client(db_session):
    """Create a TestClient with overridden database dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def sample_meter_data():
    """Sample meter data for testing."""
    return {
        "meter_type": "electricity",
        "label": "Main Electricity Meter",
        "unit": "kWh"
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
def sample_tariff_period_data():
    """Sample tariff period data for testing."""
    return {
        "meter_id": 1,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
        "price_per_unit": "0.35490",
        "base_fee_monthly": "12.50"
    }
