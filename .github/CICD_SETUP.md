# C2Pro CI/CD Setup

## Overview

This repository uses GitHub Actions for continuous integration and testing. All tests run automatically on Linux runners, avoiding Windows-specific compatibility issues.

## Workflows

### 1. E2E Security Tests (`e2e-security-tests.yml`)

**Purpose**: Validates multi-tenant isolation security (TS-E2E-SEC-TNT-001)

**Triggers**:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch

**What it tests**:
- 11 multi-tenant isolation scenarios
- Cross-tenant data access prevention
- JWT authentication and authorization
- Concurrent request isolation
- Inactive tenant blocking

**Runtime**: ~2-3 minutes

**Test Command**:
```bash
pytest tests/e2e/security/test_multi_tenant_isolation.py \
  -v -m "e2e and security" \
  --cov=src/projects --cov=src/core/auth
```

---

### 2. Full Test Suite (`tests.yml`)

**Purpose**: Comprehensive testing across all layers

**Jobs**:

#### a) Unit Tests
- Runs on Python 3.11 and 3.12 matrix
- Tests: `tests/unit/`
- No external dependencies required
- Runtime: ~30 seconds

#### b) Integration Tests
- Requires PostgreSQL + Redis
- Tests: `tests/integration/`
- Validates database operations
- Runtime: ~1-2 minutes

#### c) E2E Security Tests
- Full security test suite
- Tests: `tests/e2e/security/`
- Includes coverage reports
- Runtime: ~2-3 minutes

#### d) Test Summary
- Aggregates all test results
- Publishes unified test report
- Shows pass/fail statistics

**Total Runtime**: ~5-7 minutes

---

## Environment Variables

All workflows use these test environment variables:

```yaml
DATABASE_URL: postgresql://nonsuperuser:test@localhost:5433/c2pro_test
ENVIRONMENT: test
DEBUG: "true"
JWT_SECRET_KEY: test-secret-key-min-32-chars-required-for-testing-purposes-only
JWT_ALGORITHM: HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES: "60"
SUPABASE_URL: https://test.supabase.co
SUPABASE_ANON_KEY: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.mock
SUPABASE_SERVICE_ROLE_KEY: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.mock.service
ANTHROPIC_API_KEY: sk-ant-test-mock-key
REDIS_URL: redis://localhost:6379/0
```

**Note**: These are test-only values. Production secrets are stored in GitHub Secrets.

---

## Services

Workflows use GitHub Actions services for dependencies:

### PostgreSQL
```yaml
# Started via docker-compose.test.yml
docker-compose -f docker-compose.test.yml up -d
```

Configuration:
- Image: `postgres:15-alpine`
- Port: `5433` (to avoid conflicts with default 5432)
- Database: `c2pro_test`
- User: `nonsuperuser` / Password: `test`

### Redis
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

---

## Artifacts

All workflows upload test artifacts:

### Test Results
- **Name**: `*-test-results`
- **Format**: JUnit XML
- **Retention**: 30 days
- **Use**: Test history, failure analysis

### Coverage Reports
- **Name**: `*-coverage`
- **Format**: Coverage.xml (Cobertura)
- **Retention**: 30 days
- **Use**: Coverage tracking, PR comments

---

## Pull Request Integration

### Automated Checks

Every PR runs:
1. ✅ All unit tests (Python 3.11 + 3.12)
2. ✅ All integration tests
3. ✅ All E2E security tests
4. ✅ Coverage report generation
5. ✅ Test result summary

### PR Comments

The workflow automatically comments on PRs with:
- Coverage percentage
- Coverage delta vs base branch
- Files with coverage changes
- Minimum coverage warnings

### Merge Requirements

To merge a PR, all checks must pass:
- [ ] Unit tests: PASSED
- [ ] Integration tests: PASSED
- [ ] E2E security tests: PASSED
- [ ] Coverage: ≥60% (orange), ≥80% (green)

---

## Manual Trigger

You can manually run workflows:

1. Go to **Actions** tab
2. Select workflow (e.g., "E2E Security Tests")
3. Click **Run workflow**
4. Select branch
5. Click **Run workflow**

---

## Local Testing

### Run tests locally (Linux/Mac/WSL2):

```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Run E2E security tests
cd apps/api
DATABASE_URL="postgresql://nonsuperuser:test@localhost:5433/c2pro_test" \
  python -m pytest tests/e2e/security/test_multi_tenant_isolation.py -v

# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Run tests locally (Windows):

**Option 1: Use WSL2** (Recommended)
```bash
wsl
cd /mnt/c/Users/esus_/Documents/AI/ZTWQ/c2pro
# Follow Linux commands above
```

**Option 2: Skip database tests**
```powershell
cd apps\api
python -m pytest tests\unit\ -v
```

**Option 3: Wait for CI**
```bash
# Just commit and push, CI will run tests
git add .
git commit -m "test: verify changes"
git push
# Check GitHub Actions tab for results
```

---

## Monitoring

### View Workflow Status

**Badge in README**: Shows latest main branch status
```markdown
[![Tests](https://github.com/USERNAME/c2pro/actions/workflows/tests.yml/badge.svg)](...)
```

**Actions Tab**: Full history and logs
- https://github.com/USERNAME/c2pro/actions

**Per-Commit Status**: Check icon next to commit
- ✅ Green check = all passed
- ❌ Red X = failures
- 🟡 Yellow dot = in progress

### Debugging Failures

1. **Click on failed workflow**
2. **Expand failed job**
3. **View logs** for specific step
4. **Download artifacts** for detailed reports

Common debugging steps:
```yaml
- name: Database logs on failure
  if: failure()
  run: docker logs c2pro-postgres-test --tail 100
```

---

## Optimization Tips

### Caching

Workflows use pip caching to speed up installs:
```yaml
- uses: actions/setup-python@v5
  with:
    cache: 'pip'
    cache-dependency-path: apps/api/requirements.txt
```

**Effect**: Reduces dependency installation from ~60s to ~10s

### Parallel Execution

The `tests.yml` workflow runs jobs in parallel:
- Unit tests (Py 3.11)
- Unit tests (Py 3.12)
- Integration tests
- E2E security tests

**Effect**: Total time ≈ slowest job (~3 min) instead of sum (~7 min)

### Docker Layer Caching

PostgreSQL image is cached by GitHub:
```bash
docker-compose -f docker-compose.test.yml up -d
```

**Effect**: Database start time ~5s instead of ~30s

---

## Cost

**GitHub Actions Minutes**:
- **Public repos**: ✅ Unlimited free
- **Private repos**: 2000 free minutes/month

**Current usage per workflow run**:
- E2E Security Tests: ~3 minutes
- Full Test Suite: ~7 minutes

**Estimated monthly usage** (assuming 50 commits/month):
- E2E: 50 × 3 = 150 minutes
- Full: 50 × 7 = 350 minutes
- **Total**: 500 minutes/month (~25% of free tier)

---

## Troubleshooting

### Tests fail in CI but pass locally

**Cause**: Linux vs Windows environment differences

**Solution**: Run tests in WSL2 to match CI environment
```bash
wsl
cd /mnt/c/path/to/c2pro
docker-compose -f docker-compose.test.yml up -d
cd apps/api && pytest tests/e2e/security/ -v
```

### Database connection errors

**Symptoms**:
```
FATAL: password authentication failed
connection refused
```

**Solutions**:
1. Check `docker-compose.test.yml` is starting correctly
2. Verify `infrastructure/database/test-init/01-setup.sql` exists
3. Increase wait time: `sleep 10` → `sleep 15`

### Coverage not updating

**Cause**: Coverage report not being generated

**Solution**: Ensure pytest-cov is installed
```yaml
- name: Install dependencies
  run: |
    pip install -r requirements.txt
    pip install pytest-cov  # Add this
```

### Workflow not triggering

**Check**:
1. Workflow file syntax (YAML indentation)
2. Branch name matches trigger (`main` vs `master`)
3. Workflow file in correct location (`.github/workflows/`)

**Validate locally**:
```bash
# Install actionlint
brew install actionlint  # Mac
# OR
sudo apt install actionlint  # Linux

# Validate workflow
actionlint .github/workflows/*.yml
```

---

## Next Steps

### Add More Tests

Add new test files to appropriate directories:
- `tests/unit/` - Fast, isolated tests
- `tests/integration/` - Database/API tests
- `tests/e2e/` - Full user flows

Tests are auto-discovered by pytest.

### Add Coverage Requirements

Enforce minimum coverage in workflows:
```yaml
- name: Check coverage
  run: |
    pytest --cov=src --cov-fail-under=80
```

### Add Security Scanning

Add Bandit for security linting:
```yaml
- name: Security scan
  run: |
    pip install bandit
    bandit -r apps/api/src/
```

### Add Performance Tests

Add locust or pytest-benchmark for performance:
```yaml
- name: Performance tests
  run: |
    pytest tests/performance/ --benchmark-only
```

---

## References

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Docker Compose](https://docs.docker.com/compose/)

---

**Last Updated**: 2026-02-07
**Maintained By**: C2Pro Development Team
