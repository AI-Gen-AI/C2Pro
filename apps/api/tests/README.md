# C2Pro Test Suite Documentation

This document provides comprehensive instructions for running the C2Pro test suite.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL client (optional, for debugging)

## Test Database Setup

### Automated Setup (Recommended)

Run the automated setup script:

**Windows:**
```cmd
.\infrastructure\scripts\setup-test-db.bat
```

**Linux/macOS:**
```bash
chmod +x infrastructure/scripts/setup-test-db.sh
./infrastructure/scripts/setup-test-db.sh
```

### Manual Setup

1. Start the test database container:
```bash
docker-compose -f docker-compose.test.yml up -d
```

2. Wait for the database to be ready (check with `docker ps`)

3. The database will be available at:
   - Host: `localhost`
   - Port: `5433`
   - Database: `c2pro_test`
   - User: `nonsuperuser`
   - Password: `test`

## Running Tests

### Environment Configuration

Set the `DATABASE_URL` environment variable before running tests:

```bash
export DATABASE_URL="postgresql://nonsuperuser:test@localhost:5433/c2pro_test"
```

**Windows (PowerShell):**
```powershell
$env:DATABASE_URL="postgresql://nonsuperuser:test@localhost:5433/c2pro_test"
```

### Running All Tests

```bash
cd apps/api
pytest
```

### Running Specific Test Suites

**E2E Security Tests:**
```bash
pytest tests/e2e/security/ -v -m "e2e and security"
```

**Unit Tests:**
```bash
pytest tests/unit/ -v -m "unit"
```

**Integration Tests:**
```bash
pytest tests/integration/ -v -m "integration"
```

### Running a Single Test

```bash
pytest tests/e2e/security/test_multi_tenant_isolation.py::test_001_tenant_a_cannot_read_tenant_b_project -v
```

## Test Configuration

### pytest.ini Options

The test configuration is defined in `pyproject.toml`:

- `asyncio_mode = "auto"` - Automatically detects async tests
- Test markers are defined for categorization (`e2e`, `integration`, `unit`, `security`, `ai`, etc.)

### Test Fixtures

Key fixtures are defined in `tests/conftest.py`:

- `test_engine` - Async database engine for tests
- `test_session_factory` - Session factory for database operations
- `db` - Database session for individual tests
- `client` - Async HTTP client for API testing
- `generate_token` - JWT token generator for authentication testing

## Known Issues & Fixes

### 1. Windows Async Event Loop Issues

**Issue:** `ConnectionResetError` or `ConnectionDoesNotExistError` on Windows

**Fix:** The test configuration automatically applies `WindowsSelectorEventLoopPolicy` on Windows (configured in `tests/conftest.py`).

### 2. Bcrypt Version Compatibility

**Issue:** `ValueError: password cannot be longer than 72 bytes`

**Fix:** The project uses `bcrypt==4.3.0` which is compatible with `passlib==1.7.4`. Do NOT upgrade to bcrypt 5.x.

**Lock the version:**
```bash
pip install 'bcrypt<5.0,>=4.0'
```

### 3. Pgbouncer / Supabase Connection Pooler

**Issue:** `DuplicatePreparedStatementError` when using Supabase Connection Pooler

**Fix:** Add `statement_cache_size=0` to database connect_args (already configured in `tests/conftest.py` and `src/core/database.py`).

## Test Database Maintenance

### Reset Test Database

```bash
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d
```

### View Database Logs

```bash
docker logs c2pro-postgres-test
```

### Connect to Test Database

```bash
docker exec -it c2pro-postgres-test psql -U nonsuperuser -d c2pro_test
```

## CI/CD Integration

For CI/CD pipelines, use the following approach:

```yaml
# Example GitHub Actions workflow
- name: Start Test Database
  run: docker-compose -f docker-compose.test.yml up -d

- name: Wait for Database
  run: sleep 5

- name: Run Tests
  env:
    DATABASE_URL: postgresql://nonsuperuser:test@localhost:5433/c2pro_test
  run: |
    cd apps/api
    pytest tests/ -v --cov=src --cov-report=xml

- name: Stop Test Database
  run: docker-compose -f docker-compose.test.yml down -v
```

## Test Coverage

To generate coverage reports:

```bash
cd apps/api
pytest --cov=src --cov-report=html --cov-report=term
```

View the HTML report:
```bash
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
xdg-open htmlcov/index.html # Linux
```

## Troubleshooting

### Tests Hang or Timeout

1. Check if the database is running: `docker ps | grep c2pro-postgres-test`
2. Verify database connectivity: `docker exec c2pro-postgres-test psql -U nonsuperuser -d c2pro_test -c "SELECT 1;"`
3. Check for orphaned connections: Restart the test database

### Import Errors

Ensure you're in the correct directory and have installed dependencies:
```bash
cd apps/api
pip install -r requirements.txt
```

### Database Schema Issues

If tests fail due to missing tables, ensure migrations have run:
```bash
export DATABASE_URL="postgresql://nonsuperuser:test@localhost:5433/c2pro_test"
alembic upgrade head
```

## Contact

For issues or questions about the test suite, please:
1. Check this documentation first
2. Review existing tests in the `tests/` directory
3. Create an issue in the project repository
