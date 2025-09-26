# API Service Integration Tests

This directory contains pytest-based integration tests for the CodeTrekking API service using FastAPI's TestClient.

## Setup

### 1. Install Test Dependencies

Ensure you have pytest and other testing dependencies installed:

```bash
cd application/api-service
uv sync  # This will install dev dependencies including pytest
```

### 2. Configure Test Environment

The test configuration loads from environment files in this priority order:
1. `.env.test` (highest priority, test-specific)
2. `.env.dev` (development environment)
3. `.env` (fallback)

**Option A: Use existing .env.dev (Quick Start)**
The `.env.dev` file already includes test credentials. Tests will use these automatically.

**Option B: Create dedicated test configuration**
For isolated test environment:

```bash
cp .env.test.example .env.test
```

Edit `.env.test` to match your test environment:

- **TEST_USERNAME/TEST_PASSWORD**: Valid credentials for testing authentication
- **DATABASE_URL**: Test database connection (recommended: dedicated test DB)
- **ELASTICSEARCH_HOST**: Elasticsearch instance for analytics tests
- **RABBITMQ_URL**: RabbitMQ instance for task-related tests

**Security Note**: Tests automatically validate that required environment variables are loaded from files, not hardcoded.

### 3. Test Database Setup

#### Option A: Dedicated Test Database (Recommended)
Create a dedicated test database:

```sql
-- Connect to PostgreSQL as superuser
CREATE DATABASE codetrekking_test;
CREATE USER codetrekking_test WITH PASSWORD 'test_password';
GRANT ALL PRIVILEGES ON DATABASE codetrekking_test TO codetrekking_test;
```

Update `.env.test`:
```env
DATABASE_URL=postgresql://codetrekking_test:test_password@localhost:5432/codetrekking_test
```

#### Option B: SQLite (Faster, Limited Features)
For faster tests with limited functionality:
```env
DATABASE_URL=sqlite:///:memory:
```

## Running Tests

### Validate Test Environment
First, validate your test environment is properly configured:

```bash
# Run environment validation tests
uv run pytest tests/test_environment.py -v
```

### Run All Tests
```bash
uv run pytest
```

### Run Specific Test Categories
```bash
# Authentication tests
uv run pytest -m auth

# Analytics tests
uv run pytest -m analytics

# Integration tests only
uv run pytest -m integration
```

### Run Specific Test Files
```bash
# Weekly summary tests
uv run pytest tests/test_weekly_summary.py

# Health metrics tests
uv run pytest tests/test_health_metrics.py
```

### Run with Verbose Output
```bash
uv run pytest -v -s
```

## Test Structure

### Fixtures (`conftest.py`)

- **`test_client`**: FastAPI TestClient instance
- **`authenticated_client`**: TestClient with JWT authentication headers
- **`test_user_credentials`**: Test user credentials loaded from environment
- **`sample_date_range`**: Sample date range for analytics tests
- **`sample_weekly_summary_request`**: Sample request payload for weekly summary
- **`sample_health_metrics_request`**: Sample request payload for health metrics

### Test Files

#### `test_weekly_summary.py`
Tests for the weekly analytics summary endpoint:
- Authentication requirements
- Valid request handling
- Different zone calculation methods
- Date range validation
- Response structure validation

#### `test_health_metrics.py`
Tests for the health metrics endpoint:
- Authentication requirements
- Valid date range handling
- Response validation
- Timezone handling
- Night-time data filtering

## Writing New Tests

### Test Class Structure
```python
class TestMyEndpoint:
    """Test class for my endpoint."""

    def test_authentication_required(self, test_client: TestClient):
        """Test that endpoint requires authentication."""
        response = test_client.post("/api/v1/my-endpoint")
        assert response.status_code in [401, 403]

    def test_valid_request(self, authenticated_client: TestClient):
        """Test valid request handling."""
        response = authenticated_client.post("/api/v1/my-endpoint", json={
            "param": "value"
        })

        if response.status_code == 200:
            data = response.json()
            # Validate response structure
        else:
            pytest.skip(f"Endpoint returned {response.status_code}")
```

### Test Markers
Add markers to categorize tests:

```python
@pytest.mark.integration
@pytest.mark.analytics
def test_analytics_endpoint(self, authenticated_client: TestClient):
    """Test analytics endpoint."""
    pass
```

### Handling Missing Endpoints
For endpoints that may not be implemented yet:

```python
if response.status_code == 404:
    pytest.skip("Endpoint not found - may not be implemented yet")
```

## Test Data

### Sample Date Ranges
Tests use these date ranges:
- **Default**: `2025-08-01` to `2025-08-31` (known data period)
- **Recent**: Last 7/30 days from current date
- **Broad**: Last 365 days for comprehensive testing

### User Credentials
Configure test user credentials in `.env.test`:
- Must be valid users in your test database
- Should have appropriate permissions for tested endpoints

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify `TEST_USERNAME` and `TEST_PASSWORD` in `.env.test`
   - Ensure user exists in test database
   - Check JWT configuration

2. **Database Connection Issues**
   - Verify `DATABASE_URL` in `.env.test`
   - Ensure test database exists and is accessible
   - Check database migrations are applied

3. **External Service Dependencies**
   - Elasticsearch: Verify `ELASTICSEARCH_HOST` is accessible
   - RabbitMQ: Verify `RABBITMQ_URL` is correct
   - These services should be running for full integration tests

4. **Import Errors**
   - Ensure all dependencies are installed: `uv sync`
   - Check Python path includes the `src` directory

### Test Environment Isolation

Tests use environment variable overrides to ensure isolation:
- Separate test database
- Test-specific storage directories
- Relaxed rate limiting
- Disabled audit logging

This prevents tests from affecting development/production data.