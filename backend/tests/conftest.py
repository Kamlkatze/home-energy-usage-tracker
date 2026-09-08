"""
Test configuration and fixtures for the energy tracker backend.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models.base import Base

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def engine():
    """Create fresh SQLAlchemy engine for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh database session for each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
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