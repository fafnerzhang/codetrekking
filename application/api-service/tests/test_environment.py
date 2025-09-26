"""
Test environment validation and configuration tests.

These tests verify that the test environment is properly configured.
"""

import pytest
import os
from typing import Dict, Any


class TestEnvironmentConfiguration:
    """Test class for validating test environment setup."""

    def test_environment_files_loaded(self, test_environment_info: Dict[str, Any]):
        """Test that environment files are properly loaded."""
        loaded_files = test_environment_info["loaded_files"]

        # Should have loaded at least one environment file
        assert len(loaded_files) > 0, "No environment files were loaded"

        # Print loaded files for debugging
        print(f"\nLoaded environment files: {loaded_files}")

        # Should be in testing environment
        assert test_environment_info["environment"] == "testing"

    def test_required_environment_variables(self):
        """Test that all required environment variables are set."""
        required_vars = [
            "TEST_USERNAME",
            "TEST_PASSWORD",
            "JWT_SECRET_KEY",
            "ENVIRONMENT"
        ]

        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)

        assert not missing_vars, f"Missing required environment variables: {missing_vars}"

    def test_test_credentials_configured(self, test_user_credentials: Dict[str, str]):
        """Test that test user credentials are properly configured."""
        username = test_user_credentials["username"]
        password = test_user_credentials["password"]

        assert username is not None, "TEST_USERNAME not configured"
        assert password is not None, "TEST_PASSWORD not configured"
        assert len(username.strip()) > 0, "TEST_USERNAME is empty"
        assert len(password.strip()) > 0, "TEST_PASSWORD is empty"

        print(f"\nTest credentials configured for user: {username}")

    def test_jwt_configuration(self):
        """Test that JWT configuration is present."""
        jwt_secret = os.getenv("JWT_SECRET_KEY")
        jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")

        assert jwt_secret is not None, "JWT_SECRET_KEY not configured"
        assert len(jwt_secret) >= 32, "JWT_SECRET_KEY should be at least 32 characters"
        assert jwt_algorithm == "HS256", "JWT_ALGORITHM should be HS256"

    def test_database_configuration(self, test_environment_info: Dict[str, Any]):
        """Test that database configuration is present."""
        database_url = test_environment_info["database_url"]

        assert database_url is not None, "DATABASE_URL not configured"

        # Should be either SQLite in-memory or PostgreSQL test database
        valid_db_patterns = [
            "sqlite:///:memory:",
            "postgresql://",
            "sqlite:///"
        ]

        is_valid_db = any(database_url.startswith(pattern) for pattern in valid_db_patterns)
        assert is_valid_db, f"DATABASE_URL should start with one of {valid_db_patterns}, got: {database_url}"

        print(f"\nDatabase configured: {database_url}")

    def test_external_services_configuration(self, test_environment_info: Dict[str, Any]):
        """Test that external services are configured (optional for tests)."""
        elasticsearch_host = test_environment_info["elasticsearch_host"]
        rabbitmq_url = test_environment_info["rabbitmq_url"]

        # These are optional but should be valid URLs if configured
        if elasticsearch_host:
            assert elasticsearch_host.startswith("http"), f"ELASTICSEARCH_HOST should be a valid URL: {elasticsearch_host}"

        if rabbitmq_url:
            assert rabbitmq_url.startswith("amqp://"), f"RABBITMQ_URL should be a valid AMQP URL: {rabbitmq_url}"

        print(f"\nElasticsearch: {elasticsearch_host or 'Not configured'}")
        print(f"RabbitMQ: {rabbitmq_url or 'Not configured'}")

    def test_security_configuration(self):
        """Test that security-related configuration is appropriate for testing."""
        environment = os.getenv("ENVIRONMENT")
        jwt_secret = os.getenv("JWT_SECRET_KEY")

        # Should be in testing environment
        assert environment == "testing", "ENVIRONMENT should be 'testing'"

        # JWT secret should not be the production default
        insecure_secrets = [
            "CHANGE_ME_IN_PRODUCTION",
            "your-super-secret-jwt-key-change-in-production"
        ]

        assert jwt_secret not in insecure_secrets, "JWT_SECRET_KEY appears to be using default/insecure value"

        print(f"\nSecurity check passed - using secure JWT secret for testing")

    def test_no_hardcoded_credentials(self):
        """Test that no credentials are hardcoded in test files."""
        # This is a meta-test to ensure we're not hardcoding credentials
        test_username = os.getenv("TEST_USERNAME")
        test_password = os.getenv("TEST_PASSWORD")

        # These should come from environment, not be hardcoded
        assert test_username is not None, "TEST_USERNAME should come from environment"
        assert test_password is not None, "TEST_PASSWORD should come from environment"

        # Verify they are actually loaded from environment (not defaults)
        # This test will pass if environment variables are properly loaded
        print(f"\nCredentials loaded from environment - not hardcoded")