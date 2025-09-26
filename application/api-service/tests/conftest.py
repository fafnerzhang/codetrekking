"""
Pytest configuration and fixtures for API service integration tests.
"""

import os
import pytest
from typing import Dict, Any, Generator
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch

# Load environment files in order of priority
def load_test_environment():
    """Load test environment configuration from .env files."""
    from dotenv import load_dotenv

    api_service_dir = Path(__file__).parent.parent

    # Load in order: .env.test > .env.dev > .env (if exists)
    env_files = [
        api_service_dir / ".env.test",
        api_service_dir / ".env.dev",
        api_service_dir / ".env"
    ]

    loaded_files = []
    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file)
            loaded_files.append(str(env_file))

    # Override with testing environment settings
    test_env_overrides = {
        "ENVIRONMENT": "testing",
        "LOG_LEVEL": "WARNING",
    }

    # Set testing environment overrides
    for key, value in test_env_overrides.items():
        os.environ[key] = value

    # Set defaults only if not already set
    default_test_env = {
        "DATABASE_URL": "sqlite:///:memory:",
    }

    for key, value in default_test_env.items():
        if key not in os.environ:
            os.environ[key] = value

    return loaded_files


def validate_test_environment():
    """Validate that required test environment variables are set."""
    required_vars = {
        "TEST_USERNAME": "Test username for authentication",
        "TEST_PASSWORD": "Test password for authentication",
        "JWT_SECRET_KEY": "JWT secret key for token generation"
    }

    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var} ({description})")

    if missing_vars:
        raise ValueError(
            f"Missing required test environment variables:\n" +
            "\n".join(f"  - {var}" for var in missing_vars) +
            f"\n\nPlease configure these in .env.test or .env.dev"
        )


# Load environment configuration
loaded_env_files = load_test_environment()

# Validate required variables are present
try:
    validate_test_environment()
except ValueError as e:
    pytest.exit(f"Test environment configuration error:\n{e}", returncode=1)


@pytest.fixture(scope="session")
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI application."""
    # Mock the database and external dependencies during startup
    with patch("src.database.init_database"), \
         patch("src.database.check_database_connection", return_value=True), \
         patch("peakflow_tasks.api.TaskManager"):

        from src.main import app

        with TestClient(app) as client:
            yield client


@pytest.fixture(scope="session")
def test_user_credentials() -> Dict[str, str]:
    """Test user credentials loaded from environment variables."""
    return {
        "username": os.getenv("TEST_USERNAME"),
        "password": os.getenv("TEST_PASSWORD"),
        "base_url": os.getenv("TEST_BASE_URL", "http://testserver")
    }


@pytest.fixture(scope="session")
def test_environment_info() -> Dict[str, Any]:
    """Information about the loaded test environment."""
    return {
        "loaded_files": loaded_env_files,
        "environment": os.getenv("ENVIRONMENT"),
        "database_url": os.getenv("DATABASE_URL"),
        "jwt_configured": bool(os.getenv("JWT_SECRET_KEY")),
        "elasticsearch_host": os.getenv("ELASTICSEARCH_HOST"),
        "rabbitmq_url": os.getenv("RABBITMQ_URL")
    }


@pytest.fixture(scope="function")
def authenticated_client(test_client: TestClient, test_user_credentials: Dict[str, str]) -> Generator[TestClient, None, None]:
    """Create an authenticated test client with JWT token."""
    # Login to get access token
    login_response = test_client.post("/api/v1/auth/login", json={
        "username": test_user_credentials["username"],
        "password": test_user_credentials["password"]
    })

    if login_response.status_code == 200:
        token_data = login_response.json()
        access_token = token_data.get("access_token")

        if access_token:
            # Set authorization header for the client
            test_client.headers.update({
                "Authorization": f"Bearer {access_token}"
            })

    yield test_client

    # Cleanup - remove auth header
    if "Authorization" in test_client.headers:
        del test_client.headers["Authorization"]


@pytest.fixture(scope="function")
def sample_date_range() -> Dict[str, str]:
    """Sample date range for testing analytics endpoints."""
    return {
        "start_date": "2025-08-01",
        "end_date": "2025-08-31"
    }


@pytest.fixture(scope="function")
def sample_weekly_summary_request(sample_date_range: Dict[str, str]) -> Dict[str, Any]:
    """Sample weekly summary request payload."""
    return {
        "start_date": sample_date_range["start_date"],
        "end_date": sample_date_range["end_date"],
        "power_zone_method": "steve_palladino",
        "pace_zone_method": "joe_friel_running",
        "heart_rate_zone_method": "joe_friel"
    }


@pytest.fixture(scope="function")
def sample_health_metrics_request(sample_date_range: Dict[str, str]) -> Dict[str, Any]:
    """Sample health metrics request payload."""
    return {
        "start_date": sample_date_range["start_date"],
        "end_date": sample_date_range["end_date"]
    }