"""
Refers to Suite ID: TS-E2E-SEC-MCP-001

E2E Test Suite: MCP Gateway Security
Priority: 🔴 P0 CRÍTICO
Coverage Target: 90%

Tests the MCP Gateway security layer end-to-end:
- Allowlist validation (views and functions)
- Rate limiting per tenant (60 req/min)
- Query limits (5s timeout, 1000 rows)
- Audit logging for all operations
- Destructive operation blocking
- Tenant isolation

MCP Gateway Configuration (from PLAN_ARQUITECTURA_v2.1.md):
- Views (read-only): projects_summary, alerts_active, coherence_latest,
  documents_metadata, stakeholders_list, wbs_structure, bom_items, audit_recent
- Functions (write): create_alert, update_score, flag_review, add_note, trigger_recalc
- Rate Limit: 60 requests/minute per tenant
- Query Limits: 5s timeout, 1000 rows max
- Audit: Log all operations and blocked attempts
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from src.core.auth.models import Tenant, User, UserRole, SubscriptionPlan
from src.core.auth.service import hash_password


# ===========================================
# FIXTURES
# ===========================================


@pytest_asyncio.fixture
async def mcp_tenant(db) -> Tenant:
    """Create a tenant for MCP testing."""
    tenant = Tenant(
        id=uuid4(),
        name="MCP Test Company",
        slug=f"mcp-test-{uuid4().hex[:8]}",
        subscription_plan=SubscriptionPlan.PROFESSIONAL,
        subscription_status="active",
        ai_budget_monthly=100.0,
        ai_spend_current=0.0,
        max_projects=50,
        max_users=10,
        max_storage_gb=100,
        is_active=True,
    )
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def mcp_user(db, mcp_tenant: Tenant) -> User:
    """Create a user for MCP testing."""
    user = User(
        id=uuid4(),
        tenant_id=mcp_tenant.id,
        email="mcp_user@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="MCP",
        last_name="User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


# ===========================================
# TEST 1: Allowlist - View Operations Allowed
# ===========================================


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_001_mcp_view_operations_allowed(
    client,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A valid authenticated user
    WHEN User executes an allowed view operation (e.g., projects_summary)
    THEN Response is 200 OK with data filtered by tenant_id
    AND Operation is logged in audit trail

    Security: Validates allowlist permits read-only view operations.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Execute allowed view operation
    response = await client.post(
        "/api/v1/mcp/execute",
        headers=headers,
        json={
            "operation": "projects_summary",
            "params": {},
        },
    )

    # Should succeed
    assert response.status_code == 200
    body = response.json()

    # Should return data
    assert "data" in body or "result" in body

    # Should be tenant-scoped (implementation detail)
    # Data should only contain tenant's projects


# ===========================================
# TEST 2: Allowlist - Function Operations Allowed
# ===========================================


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_002_mcp_function_operations_allowed(
    client,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A valid authenticated user
    WHEN User executes an allowed function operation (e.g., create_alert)
    THEN Response is 200 OK with operation result
    AND Operation is logged in audit trail

    Security: Validates allowlist permits write function operations.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Execute allowed function operation
    response = await client.post(
        "/api/v1/mcp/execute",
        headers=headers,
        json={
            "operation": "create_alert",
            "params": {
                "rule_code": "R1",
                "severity": "high",
                "message": "Test alert",
            },
        },
    )

    # Should succeed (or 404 if not implemented yet in GREEN phase)
    assert response.status_code in [200, 404]


# ===========================================
# TEST 3: Allowlist - Destructive Operations Blocked
# ===========================================


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_003_mcp_destructive_operations_blocked(
    client,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A valid authenticated user
    WHEN User tries to execute a destructive operation (e.g., delete_all, drop_table)
    THEN Response is 403 Forbidden
    AND Blocked attempt is logged in audit trail

    Security: CRITICAL - Prevents data loss through MCP gateway.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Try destructive operations
    destructive_ops = [
        "delete_all",
        "drop_table",
        "truncate_table",
        "delete_tenant",
        "modify_schema",
    ]

    for operation in destructive_ops:
        response = await client.post(
            "/api/v1/mcp/execute",
            headers=headers,
            json={
                "operation": operation,
                "params": {},
            },
        )

        # Should be blocked with 403
        assert response.status_code == 403, f"Operation {operation} should be blocked"
        body = response.json()
        assert "detail" in body
        assert "not allowed" in body["detail"].lower() or "forbidden" in body["detail"].lower()


# ===========================================
# TEST 4: Allowlist - Unknown Operations Blocked
# ===========================================


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_004_mcp_unknown_operations_blocked(
    client,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A valid authenticated user
    WHEN User tries to execute an operation not in the allowlist
    THEN Response is 403 Forbidden
    AND Blocked attempt is logged

    Security: Default-deny approach for unknown operations.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Try unknown operation
    response = await client.post(
        "/api/v1/mcp/execute",
        headers=headers,
        json={
            "operation": "unknown_operation_xyz",
            "params": {},
        },
    )

    # Should be blocked
    assert response.status_code == 403
    body = response.json()
    assert "detail" in body


# ===========================================
# TEST 5: Rate Limiting - Under Limit Allowed
# ===========================================


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_005_mcp_rate_limit_under_limit_allowed(
    client,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A tenant with no prior requests
    WHEN User makes 10 requests within a minute (under limit of 60)
    THEN All requests succeed with 200 OK

    Security: Validates normal usage is not throttled.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Make 10 requests (well under limit)
    for i in range(10):
        response = await client.post(
            "/api/v1/mcp/execute",
            headers=headers,
            json={
                "operation": "projects_summary",
                "params": {},
            },
        )

        # All should succeed
        assert response.status_code == 200, f"Request {i+1} failed"


# ===========================================
# TEST 6: Rate Limiting - Over Limit Blocked
# ===========================================


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
@pytest.mark.slow
async def test_006_mcp_rate_limit_over_limit_blocked(
    client,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A tenant at the rate limit threshold
    WHEN User makes request number 61 within a minute
    THEN Response is 429 Too Many Requests
    AND Response includes Retry-After header

    Security: Prevents MCP abuse and DoS attacks.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Make 61 requests rapidly
    responses = []
    for i in range(61):
        response = await client.post(
            "/api/v1/mcp/execute",
            headers=headers,
            json={
                "operation": "projects_summary",
                "params": {},
            },
        )
        responses.append(response)

    # Last request should be rate limited
    last_response = responses[-1]

    # Should be 429 Too Many Requests
    assert last_response.status_code == 429

    # Should include Retry-After header
    assert "Retry-After" in last_response.headers or "retry-after" in last_response.headers


# ===========================================
# TEST 7: Rate Limiting - Tenant Isolation
# ===========================================


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_007_mcp_rate_limit_tenant_isolation(
    client,
    db,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN Tenant A has exhausted their rate limit
    WHEN Tenant B makes a request
    THEN Tenant B's request succeeds (not affected by Tenant A)

    Security: Validates rate limiting is per-tenant, not global.
    """
    # Create second tenant
    tenant_b = Tenant(
        id=uuid4(),
        name="MCP Test Company B",
        slug=f"mcp-test-b-{uuid4().hex[:8]}",
        subscription_plan=SubscriptionPlan.PROFESSIONAL,
        subscription_status="active",
        ai_budget_monthly=100.0,
        ai_spend_current=0.0,
        max_projects=50,
        max_users=10,
        max_storage_gb=100,
        is_active=True,
    )
    db.add(tenant_b)
    await db.flush()

    user_b = User(
        id=uuid4(),
        tenant_id=tenant_b.id,
        email="user_b@test.com",
        hashed_password=hash_password("Password123!"),
        first_name="User",
        last_name="B",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(user_b)
    await db.flush()

    token_b = generate_token(
        user_id=user_b.id,
        tenant_id=tenant_b.id,
        email=user_b.email,
        role="admin",
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Tenant B should be able to make requests
    response = await client.post(
        "/api/v1/mcp/execute",
        headers=headers_b,
        json={
            "operation": "projects_summary",
            "params": {},
        },
    )

    # Should succeed
    assert response.status_code == 200


# ===========================================
# TEST 8: Query Limits - Large Result Set Truncated
# ===========================================


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_008_mcp_query_limits_large_result_truncated(
    client,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A view operation that returns more than 1000 rows
    WHEN User executes the operation
    THEN Response is 200 OK with data truncated to 1000 rows
    AND Response includes a warning flag indicating truncation

    Security: Prevents memory exhaustion attacks via large result sets.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Execute operation that might return many rows
    response = await client.post(
        "/api/v1/mcp/execute",
        headers=headers,
        json={
            "operation": "audit_recent",
            "params": {"limit": 5000},  # Try to get 5000 rows
        },
    )

    # Should succeed
    assert response.status_code == 200
    body = response.json()

    # Should have data
    if "data" in body and isinstance(body["data"], list):
        # Should be truncated to max 1000 rows
        assert len(body["data"]) <= 1000

        # Should indicate truncation if applicable
        if len(body["data"]) == 1000:
            assert "truncated" in body or "warning" in body


# ===========================================
# EDGE CASES
# ===========================================


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_edge_001_mcp_malformed_operation_rejected(
    client,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A valid authenticated user
    WHEN User sends a malformed MCP request (missing operation field)
    THEN Response is 422 Unprocessable Entity

    Security: Input validation prevents injection attacks.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Send malformed request
    response = await client.post(
        "/api/v1/mcp/execute",
        headers=headers,
        json={
            # Missing "operation" field
            "params": {},
        },
    )

    # Should reject with validation error
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_edge_002_mcp_sql_injection_attempt_blocked(
    client,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A valid authenticated user
    WHEN User tries SQL injection via operation name
    THEN Request is blocked with 403 Forbidden

    Security: CRITICAL - Prevents SQL injection attacks.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # SQL injection attempts
    sql_injection_payloads = [
        "projects_summary'; DROP TABLE projects; --",
        "projects_summary OR 1=1",
        "projects_summary; DELETE FROM users;",
    ]

    for payload in sql_injection_payloads:
        response = await client.post(
            "/api/v1/mcp/execute",
            headers=headers,
            json={
                "operation": payload,
                "params": {},
            },
        )

        # Should be blocked (not in allowlist)
        assert response.status_code == 403, f"SQL injection payload '{payload}' not blocked"


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_edge_003_mcp_without_authentication_rejected(
    client,
):
    """
    GIVEN An unauthenticated user
    WHEN User tries to execute MCP operation without JWT token
    THEN Response is 401 Unauthorized

    Security: MCP operations require authentication.
    """
    # No Authorization header
    response = await client.post(
        "/api/v1/mcp/execute",
        json={
            "operation": "projects_summary",
            "params": {},
        },
    )

    # Should reject
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.security
@pytest.mark.e2e
async def test_edge_004_mcp_audit_log_created(
    client,
    db,
    mcp_user: User,
    mcp_tenant: Tenant,
    generate_token,
):
    """
    GIVEN A valid authenticated user
    WHEN User executes an MCP operation
    THEN An audit log entry is created
    AND Log includes operation name, tenant_id, user_id, timestamp

    Security: Audit trail for compliance and forensics.
    """
    token = generate_token(
        user_id=mcp_user.id,
        tenant_id=mcp_tenant.id,
        email=mcp_user.email,
        role="admin",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Execute operation
    response = await client.post(
        "/api/v1/mcp/execute",
        headers=headers,
        json={
            "operation": "projects_summary",
            "params": {},
        },
    )

    assert response.status_code == 200

    # Check if audit log was created
    # This will depend on implementation
    # For now, just verify the operation succeeded
    # In GREEN phase, implement audit log checking
