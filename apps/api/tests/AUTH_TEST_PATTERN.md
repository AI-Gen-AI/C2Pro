# Authentication Test Pattern

**Part of TASK-BCK-030**: Set up authenticated test fixtures for HITL resume tests (GREEN phase)

This document describes the standard pattern for testing authenticated API endpoints in C2Pro.

---

## Overview

Many API endpoints require JWT authentication. The `authenticated_client` fixture provides an easy way to test these endpoints without manually managing tokens in each test.

## Basic Usage

### Using authenticated_client Fixture

```python
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_protected_endpoint(authenticated_client: AsyncClient):
    """Test a protected endpoint that requires authentication."""
    response = await authenticated_client.get("/api/v1/protected/resource")
    assert response.status_code == 200
```

### Using client Fixture (Unauthenticated)

For endpoints that do NOT require authentication:

```python
async def test_public_endpoint(client: AsyncClient):
    """Test a public endpoint that does not require authentication."""
    response = await client.get("/api/v1/public/health")
    assert response.status_code == 200
```

---

## How It Works

The `authenticated_client` fixture (defined in `conftest.py`) does three things:

1. **Creates a test user**: Uses the `test_user` and `test_tenant` fixtures
2. **Generates a JWT token**: Uses the `generate_token` fixture with the test user's credentials
3. **Adds Authorization header**: Automatically includes `Authorization: Bearer <token>` in all requests

### Fixture Definition

```python
@pytest_asyncio.fixture
async def authenticated_client(
    app,
    db: AsyncSession,
    test_user: User,
    generate_token: Callable,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates an authenticated HTTP client for testing protected API endpoints.
    """
    # Generate JWT token for test_user
    token = generate_token(
        user_id=test_user.id,
        tenant_id=test_user.tenant_id,
        email=test_user.email,
        role=test_user.role.value,
    )

    # Create client with Authorization header
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as test_client:
        yield test_client
```

---

## Advanced Usage

### Testing with Different Users

If you need to test with a different user (e.g., testing tenant isolation):

```python
async def test_tenant_isolation(
    app, db, test_user_2, generate_token: Callable
):
    """Test that users can't access other tenants' resources."""
    # Create authenticated client for test_user_2
    token = generate_token(
        user_id=test_user_2.id,
        tenant_id=test_user_2.tenant_id,
        email=test_user_2.email,
        role=test_user_2.role.value,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        # This should fail due to tenant isolation
        response = await client.get(f"/api/v1/tenants/{test_user.tenant_id}/projects")
        assert response.status_code == 403
```

### Testing with Invalid/Expired Tokens

```python
async def test_expired_token_rejected(client: AsyncClient, generate_token):
    """Test that expired tokens are rejected."""
    # Generate an expired token (expires in -3600 seconds = 1 hour ago)
    expired_token = generate_token(expires_delta_seconds=-3600)

    response = await client.get(
        "/api/v1/protected/resource",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
```

### Testing with Different Roles

```python
async def test_admin_only_endpoint(app, db, generate_token):
    """Test that only admins can access admin endpoints."""
    # Create a non-admin token
    user_token = generate_token(role="user")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {user_token}"},
    ) as client:
        response = await client.post("/api/v1/admin/settings")
        assert response.status_code == 403  # Forbidden
```

---

## Migration Guide

### Converting Existing Tests

**Before (RED phase - no auth)**:
```python
async def test_resume_endpoint(client: AsyncClient, test_review_item):
    response = await client.post(
        f"/api/v1/hitl/resume/{test_review_item.id}",
        json={"decision": "approve"}
    )
    assert response.status_code == 200
```

**After (GREEN phase - with auth)**:
```python
async def test_resume_endpoint(authenticated_client: AsyncClient, test_review_item):
    response = await authenticated_client.post(
        f"/api/v1/hitl/resume/{test_review_item.id}",
        json={"decision": "approve"}
    )
    assert response.status_code == 200
```

**Changes required**:
1. Replace `client: AsyncClient` → `authenticated_client: AsyncClient` in parameter list
2. Replace `await client.` → `await authenticated_client.` in test body

---

## Available Fixtures

| Fixture | Purpose | Returns |
|---------|---------|---------|
| `client` | Unauthenticated HTTP client | `AsyncClient` |
| `authenticated_client` | Authenticated HTTP client (uses `test_user`) | `AsyncClient` |
| `test_user` | Test user in `test_tenant` | `User` |
| `test_tenant` | Test tenant | `Tenant` |
| `generate_token` | Factory to create JWT tokens with custom claims | `Callable` |

---

## Examples

### Example 1: HITL Resume Endpoint (TASK-BCK-024 + TASK-BCK-030)

```python
async def test_approval_resumes_workflow(
    authenticated_client: AsyncClient,
    test_review_item,
    db
):
    """Approving a review item should resume the workflow."""
    response = await authenticated_client.post(
        f"/api/v1/hitl/resume/{test_review_item.id}",
        json={
            "decision": "approve",
            "feedback": "Stakeholders confirmed"
        }
    )
    assert response.status_code == 200

    # Verify review status updated
    data = response.json()
    assert data["status"] == "resumed"
```

### Example 2: Testing Authorization Failure

```python
async def test_unauthorized_access_rejected(client: AsyncClient):
    """Requests without authentication should be rejected."""
    # Use unauthenticated client (no Authorization header)
    response = await client.get("/api/v1/protected/resource")
    assert response.status_code == 401
```

### Example 3: Testing Tenant Isolation

```python
async def test_cannot_access_other_tenant_data(
    authenticated_client: AsyncClient,
    test_tenant_2
):
    """Users cannot access resources from other tenants."""
    # authenticated_client uses test_user (from test_tenant)
    # Try to access resource from test_tenant_2
    response = await authenticated_client.get(
        f"/api/v1/tenants/{test_tenant_2.id}/projects"
    )
    # Should fail due to RLS (Row Level Security) tenant isolation
    assert response.status_code in [403, 404]
```

---

## Test Coverage Requirements

Per TASK-BCK-030 requirements:

- ✅ Authenticated AsyncClient fixture created
- ✅ JWT token generation helper integrated
- ✅ All 21+ HITL resume endpoint tests use auth fixtures
- ✅ Tests transition from RED → GREEN phase
- ✅ Documentation provided for future HITL tests

---

## Related Files

- `apps/api/tests/conftest.py` - Authentication fixtures
- `apps/api/tests/modules/integration/test_hitl_resume_endpoint.py` - Example usage (TASK-BCK-024)
- `apps/api/src/core/auth/` - Authentication implementation

---

## References

- **TASK-BCK-024**: Implement HITL workflow resume mechanism after approval
- **TASK-BCK-030**: Set up authenticated test fixtures for HITL resume tests (GREEN phase)
- **Suite ID**: TS-INT-HITL-RESUME-001

---

*Last Updated*: 2026-04-06
*Author*: Backend Team
*Status*: ✅ Complete
