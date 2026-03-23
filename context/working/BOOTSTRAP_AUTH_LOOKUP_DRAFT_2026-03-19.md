# Bootstrap Auth Lookup Draft

Date: 2026-03-19
Status: Draft
Purpose: Define exact SQL bootstrap functions and Python call sites required before fail-closed RLS can be rolled out on `tenants` and `users`.

## Goal

Move pre-tenant authentication and identity resolution off direct table reads that depend on permissive RLS.

This draft assumes:

- normal application reads continue to use `app.current_tenant`
- `tenants` and `users` will become fail-closed
- bootstrap identity lookups must still work before tenant context exists

## SQL Design

### Schema

Create a dedicated schema for bootstrap lookups:

```sql
CREATE SCHEMA IF NOT EXISTS auth_bootstrap;
REVOKE ALL ON SCHEMA auth_bootstrap FROM PUBLIC;
```

### Function 1: Tenant lookup by tenant id

Use for local JWT validation in middleware.

```sql
CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_tenant_by_id(
    p_tenant_id uuid
)
RETURNS TABLE (
    tenant_id uuid,
    is_active boolean,
    clerk_org_id text
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT
        t.id,
        t.is_active,
        t.clerk_org_id
    FROM public.tenants t
    WHERE t.id = p_tenant_id
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION auth_bootstrap.lookup_tenant_by_id(uuid) FROM PUBLIC;
```

### Function 2: Tenant lookup by Clerk org id

Use for Clerk org resolution.

```sql
CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_tenant_by_clerk_org_id(
    p_clerk_org_id text
)
RETURNS TABLE (
    tenant_id uuid,
    tenant_name text,
    is_active boolean
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT
        t.id,
        t.name::text,
        t.is_active
    FROM public.tenants t
    WHERE t.clerk_org_id = p_clerk_org_id
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION auth_bootstrap.lookup_tenant_by_clerk_org_id(text) FROM PUBLIC;
```

### Function 3: Personal tenant lookup by name

Use for Clerk users without organizations.

```sql
CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_personal_tenant_by_name(
    p_name text
)
RETURNS TABLE (
    tenant_id uuid,
    tenant_name text,
    is_active boolean
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT
        t.id,
        t.name::text,
        t.is_active
    FROM public.tenants t
    WHERE t.name = p_name
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION auth_bootstrap.lookup_personal_tenant_by_name(text) FROM PUBLIC;
```

### Function 4: User lookup by email

Use for public register/login bootstrap reads.

```sql
CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_user_by_email(
    p_email text
)
RETURNS TABLE (
    user_id uuid,
    tenant_id uuid,
    email text,
    hashed_password text,
    is_active boolean,
    role text,
    clerk_user_id text
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT
        u.id,
        u.tenant_id,
        u.email::text,
        u.hashed_password::text,
        u.is_active,
        u.role::text,
        u.clerk_user_id
    FROM public.users u
    WHERE lower(u.email) = lower(p_email)
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION auth_bootstrap.lookup_user_by_email(text) FROM PUBLIC;
```

### Function 5: User lookup by Clerk user id

Use for Clerk-authenticated request bootstrap.

```sql
CREATE OR REPLACE FUNCTION auth_bootstrap.lookup_user_by_clerk_user_id(
    p_clerk_user_id text
)
RETURNS TABLE (
    user_id uuid,
    tenant_id uuid,
    email text,
    is_active boolean
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT
        u.id,
        u.tenant_id,
        u.email::text,
        u.is_active
    FROM public.users u
    WHERE u.clerk_user_id = p_clerk_user_id
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION auth_bootstrap.lookup_user_by_clerk_user_id(text) FROM PUBLIC;
```

## Optional Write Helpers

These should only be added if direct ORM writes on `tenants` and `users` become blocked under `FORCE RLS`.

```sql
CREATE OR REPLACE FUNCTION auth_bootstrap.create_tenant_for_clerk_org(
    p_name text,
    p_clerk_org_id text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_tenant_id uuid;
BEGIN
    INSERT INTO public.tenants (
        id,
        name,
        clerk_org_id,
        is_active
    )
    VALUES (
        gen_random_uuid(),
        p_name,
        p_clerk_org_id,
        true
    )
    RETURNING id INTO v_tenant_id;

    RETURN v_tenant_id;
END;
$$;

REVOKE ALL ON FUNCTION auth_bootstrap.create_tenant_for_clerk_org(text, text) FROM PUBLIC;
```

Equivalent write helpers can be added for:

- `create_personal_tenant`
- `create_clerk_user`
- `move_clerk_user_to_tenant`

## Python Integration Points

### New module

Add a small adapter module, for example:

- `apps/api/src/core/auth/bootstrap_lookup.py`

Recommended responsibilities:

- call the `auth_bootstrap.*` SQL functions
- return typed DTOs, not ORM models
- remain the only bootstrap bypass path in application code

### Suggested DTOs

```python
from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class BootstrapTenantRecord:
    tenant_id: UUID
    is_active: bool
    clerk_org_id: str | None = None
    tenant_name: str | None = None


@dataclass(slots=True)
class BootstrapUserRecord:
    user_id: UUID
    tenant_id: UUID
    email: str
    is_active: bool
    hashed_password: str | None = None
    role: str | None = None
    clerk_user_id: str | None = None
```

### Suggested Python functions

```python
async def lookup_tenant_by_id(db: AsyncSession, tenant_id: UUID) -> BootstrapTenantRecord | None: ...
async def lookup_tenant_by_clerk_org_id(db: AsyncSession, clerk_org_id: str) -> BootstrapTenantRecord | None: ...
async def lookup_personal_tenant_by_name(db: AsyncSession, name: str) -> BootstrapTenantRecord | None: ...
async def lookup_user_by_email(db: AsyncSession, email: str) -> BootstrapUserRecord | None: ...
async def lookup_user_by_clerk_user_id(db: AsyncSession, clerk_user_id: str) -> BootstrapUserRecord | None: ...
```

## Exact Call-Site Switches

### 1. `TenantIsolationMiddleware._get_tenant_for_clerk_user()`

Current file:

- `apps/api/src/core/middleware/tenant_isolation.py`

Current query:

```python
select(User.tenant_id).where(User.clerk_user_id == clerk_user_id)
```

Replace with:

```python
record = await lookup_user_by_clerk_user_id(session, clerk_user_id)
return record.tenant_id if record else None
```

### 2. `TenantIsolationMiddleware._validate_tenant_exists()`

Current file:

- `apps/api/src/core/middleware/tenant_isolation.py`

Current query:

```python
select(Tenant).where(Tenant.id == tenant_id)
```

Replace with:

```python
record = await lookup_tenant_by_id(session, tenant_id)
return bool(record and record.is_active)
```

### 3. `get_user_by_email()` used by register/login

Current file:

- `apps/api/src/core/auth/service.py`

Current query:

```python
select(User).where(User.email == email)
```

Change:

- keep the ORM version for tenant-bound internal flows if still needed
- add a bootstrap-safe variant for public auth

Suggested split:

```python
async def get_user_by_email_bootstrap(db: AsyncSession, email: str) -> BootstrapUserRecord | None: ...
```

Then switch:

- `AuthService.register()`
- `AuthService.login()`

to use the bootstrap variant

### 4. `_provision_clerk_user()` tenant lookup by Clerk org id

Current file:

- `apps/api/src/core/auth/dependencies.py`

Current query:

```python
select(Tenant).where(Tenant.clerk_org_id == clerk_org_id)
```

Replace lookup with:

```python
tenant_record = await lookup_tenant_by_clerk_org_id(db, clerk_org_id)
```

### 5. `_provision_clerk_user()` personal tenant lookup

Current file:

- `apps/api/src/core/auth/dependencies.py`

Current query:

```python
select(Tenant).where(Tenant.name == personal_tenant_name)
```

Replace lookup with:

```python
tenant_record = await lookup_personal_tenant_by_name(db, personal_tenant_name)
```

### 6. `_provision_clerk_user()` existing user lookup by Clerk user id

Current file:

- `apps/api/src/core/auth/dependencies.py`

Current query:

```python
select(User).where(User.clerk_user_id == clerk_user_id)
```

Replace lookup with:

```python
user_record = await lookup_user_by_clerk_user_id(db, clerk_user_id)
```

## Rollout Notes

### Phase 1

Implement read-only bootstrap functions and switch the lookup call sites.

### Phase 2

Run auth smoke tests:

- local JWT login
- local JWT register
- Clerk-authenticated request for existing user
- Clerk first-login auto-provisioning

### Phase 3

Apply fail-closed policy migration only after the above pass against a database with `FORCE RLS`.

## Open Decisions

- Whether bootstrap writes should also move into `SECURITY DEFINER` functions or continue through ORM with a dedicated non-RLS path
- Whether personal-tenant bootstrap should keep using generated names or move to a more stable key
- Whether `email` should remain globally unique or become tenant-scoped in auth bootstrap logic
