# C2.6 — Platform Operator Authorization Boundary

**Canonical C2Pro specification** · Status: `READY_FOR_MASTER_REVIEW` · Base `32eba943` **Specification only — no production code modified, C2.6 not implemented.**

> **NAMING CORRECTION (MASTER, binding).** The source design (`/srv/c2pro/sessions/evidence/c3-platform-operator/claude-opus-c3-platform-operator-spec.md`) labels this slice "C3". That is wrong: canonical sequencing reserves **C3** for the ordinary-runtime non-owner / `NOBYPASSRLS` cutover. This authorization slice is **C2.6**; its deferred audit successor is **C2.6.1**; `INV-C3-ORG` → **`INV-C26-ORG`**.

**MASTER decisions M1–M22 are binding and enforced at:** M1 §5, §8/G-series, §13/N01, §19/I1 · M2 §6.1/OS4, §8/G1, §14/AC3 · M3 §6.1/OS2, §8/G2 · M4 §3/SO2, §5/IR4, §19/I2 · M5 §6.2, §6.3 · M6 §7.1/AUTH-M2–M3, §8 · M7 §5.2 · M8 §5/IR3, §7.1/AUTH-M5, §7.2 · M9 §10 · M10 §8.1, §9 · M11–M13 §9 · M14 §15.4 · M15 §15.4 · M16 §9/F2, §15.4 · M17 §12 · M18 §12.1, §18 · M19 §5.4, §17/NG3 · M20 §5.4, §19/I1 · M21–M22 §1.3, §15.2, §15.3, §14/AC16, §17/NG11.

> **SUPERSESSION (MASTER, binding, Resolution 5).** The source design's deployment steps that created a persistent admin LOGIN and configured `ADMIN_OPS_DATABASE_URL` as part of the *same* slice deployment (source D-4 / D-5) are **SUPERSEDED and non-canonical**. Canonical sequencing is: **C2.5 CLOSED → C2.6 authorization boundary implementation + acceptance → separate MASTER-controlled admin capability enablement → C3 ordinary-runtime non-owner / `NOBYPASSRLS` cutover.** Capability enablement is never part of the C2.6 slice (§15.3).

> **FIX2 REVISION (binding).** This revision reconciles an independent Codex review (2 CRITICAL + 3 IMPORTANT, all accepted). It adds: the persistent-credential vs disposable-harness distinction (§1.3, §15.2); the **platform-route authentication mode** that keeps platform requests out of tenant context (§7.1, §8, §11); the dual anti-provisioning guard with a **deny-only** integrity lookup (§10); a gate order coherent with the real middleware baseline (§8); and the supersession note above.

> **FIX3 REVISION (binding).** This revision reconciles a targeted Codex re-review (0 CRITICAL, 2 IMPORTANT, 2 MINOR, all accepted). It: (1) replaces prefix-based/ambiguous platform-route classification with an explicit `(method, normalized_path)` registry scoped to the exact routes in `src.admin.adapters.http.router` only, and adds structural tests keeping it separated from the structurally distinct tenant-scoped `src.core.dlq.router` (§7.1, §11, §13.3 S09–S13); (2) requires the C2.6 disposable harness to extend/reuse the lifecycle, ownership-tracking, and teardown machinery of `apps/api/scripts/c25_admin_ops_gate.py` rather than reimplement it, preserving any pre-existing cluster-global `c2pro_admin_ops` role (§1.3 B, §13.5 H01–H02, §15.2); (3) corrects the baseline live tenant/user-resolution call that platform mode must bypass from the unused `_get_tenant_for_clerk_user` to the actually-invoked `_get_clerk_user_record` (§7.1, §11, §13.3 S06); and (4) states the `PLATFORM_OPERATOR_USER_IDS` grammar as plain comma-separated only, never CSV/JSON (§6.2, §11). All FIX2 decisions are unchanged.

> **FIX4 REVISION (binding, route registry only).** MASTER independently verified baseline runtime truth: `src.main` mounts `src.admin.adapters.http.router` as `dlq_admin_router` (`main.py:311`); the legacy `src.core.dlq.router` still exists in source but is **NOT mounted**; both modules happen to declare equivalent method/path templates. Codex therefore found a valid **specification** contradiction, but **not** a current runtime route collision. FIX4 corrects the framing accordingly: the registry keeps its explicit method + normalized-route-template model, but is now defined against the **ACTIVE MOUNTED** application route set — every registered identity **MUST resolve to exactly one mounted route**, and that route **MUST be the cross-tenant admin router** (§7.1, S10). The legacy module **may exist** provided it **remains unmounted** (S11); its declaring the same template is **not** a violation and requires no code change. If any second route with the same method/template becomes mounted, structural CI **MUST fail** (S12, proven RED). No router-provenance runtime authorization is introduced (provenance is a CI-time assertion only), no public API path changes, and no `/platform/dlq` namespace is created. All FIX2 and FIX3 decisions are preserved.

## 1. STATUS / PREDECESSOR / SUCCESSOR

```
C2.5  database capability boundary      — CLOSED (PR #604, merged)
  ↓
C2.6  platform-operator authorization   — THIS SPECIFICATION
  ↓
C3    ordinary-runtime non-owner / NOBYPASSRLS cutover
```

**Inherited state at base `32eba943`:** C2.5/PR604 CLOSED and unchanged by C2.6; `ADMIN_OPS_DATABASE_URL` **ABSENT** from every persistent runtime environment; no persistent restricted admin runtime LOGIN exists; the cross-tenant capability is therefore **fail-closed** (`503`) today.

### 1.3 C2.6 merge does NOT enable the cross-tenant database capability

> **Normative.** Merging C2.6 closes an authorization gap; it does **not** turn on the cross-tenant capability. `/admin/dlq` therefore returns `403` to unauthorized callers and `503` to authorized operators, in production, post-merge, **by design**.

The prohibition applies to **persistent credentials**, not to test resources. The two categories are disjoint and must never be conflated (M21, M22).

**A. Persistent / runtime credentials — HELD until separate MASTER-controlled enablement.** Until C2.6 acceptance (§14) completes *and* a separate MASTER-controlled enablement operation is authorized: `ADMIN_OPS_DATABASE_URL` **MUST remain absent from every persistent application runtime environment** (API and worker process environments, deployment manifests, secret stores, `.env` files, CI environment configuration); **no persistent restricted admin LOGIN** may be created, granted, or configured for API/worker use; and **no staging or production runtime may exercise the capability through a persistent DSN**.

**B. Disposable security harness — REQUIRED for C2.6 acceptance.** C2.6's harness **MUST extend/reuse — never reimplement — the lifecycle, ownership-tracking, and teardown machinery already proven in `apps/api/scripts/c25_admin_ops_gate.py`.** Inside the test harness only, it stands up: an isolated **disposable PostgreSQL database**; a **synthetic restricted LOGIN**; a **temporary `ADMIN_OPS_DATABASE_URL`-equivalent test DSN**; and **real cross-tenant positive and negative database capability tests**, which are **RE-RUN from the gate script, not duplicated** (§13.5, H01). The gate script's existing ownership-tracking behavior is binding here: a **pre-existing cluster-global `c2pro_admin_ops` capability role MUST be preserved** — C2.6 **MUST NOT** drop it merely because its tests ran; it is dropped **only if the disposable fixture itself created it**, with ownership explicitly tracked exactly as the gate script already does. The synthetic restricted LOGIN, any disposable DB/resources C2.6 itself created, and temporary DSN/config state are **always destroyed at harness teardown — on both success and failure** (proven by H02); none of it is ever **written into application environment configuration**, and none of it is **"enablement"**. C2.5's capability/grant/RLS proofs remain authoritative and are **RE-RUN, not reimplemented or duplicated**; C2.6-specific real-database coverage focuses on the **HTTP identity/authz integration** with that already-proven capability boundary. The real-database RED and positive tests (§13.2, §13.5) are **REQUIRED**, not optional — a mock-only acceptance is rejected.

## 2. PROBLEM STATEMENT

C2.5 established a minimal database capability boundary for cross-tenant DLQ administration: the `c2pro_admin_ops` role (NOLOGIN / NOSUPERUSER / NOBYPASSRLS / NOCREATEROLE / non-owner) with column-exact grants on `dlq_failed_tasks`, reachable only through a dedicated LOGIN supplied via `ADMIN_OPS_DATABASE_URL` and re-verified against `pg_catalog` on every session acquisition.

That boundary is fronted by one HTTP gate, `require_admin_user` (`apps/api/src/admin/adapters/http/router.py:157`), whose only test is `current_user.role == UserRole.ADMIN`. `UserRole.ADMIN` is *"Administrador del tenant"* (`apps/api/src/core/auth/models.py:53`), assigned unconditionally to the first user of any tenant created via the unauthenticated `POST /api/v1/auth/register`, which sits in `TenantIsolationMiddleware.PUBLIC_PATHS`.

**Consequence:** any member of the public can self-issue an identity satisfying the only authorization gate in front of a cross-tenant capability. The gap is **pre-existing** (TS-BCK-042-001; `require_admin_user` is untouched by PR604) and so was not a PR604 merge blocker — but it is a hard blocker on ever setting `ADMIN_OPS_DATABASE_URL` where real customer data lives. C2.6 closes it.

## 3. SECURITY OBJECTIVE

**Primary:** cross-tenant administrative capabilities are reachable only by an identity C2Pro itself provisioned as a platform operator, where the privilege decision is made by **server-side configuration** and never by an assertion carried inside the credential.

- **SO1** No self-issuable identity (registration, customer Clerk org, tenant-mapped API key) can satisfy the gate.
- **SO2** Privilege provenance is server-side config compared against verified identity; tokens assert identity only.
- **SO3** Absent or misconfigured operator config denies — never falls back, skips, or widens.
- **SO4** Authorization state and capability-availability state are never conflated; capability state is not disclosable to unauthorized callers.
- **SO5** Every C2.5 database invariant survives C2.6 unchanged.
- **SO6** Operator actions are individually attributable.

**Non-objective:** C2.6 neither strengthens nor weakens the C2.5 database boundary. It is an authorization slice only.

## 4. TRUST BOUNDARIES

**Normative boundary:** *an identity crosses the platform-operator boundary if and only if it is a verified principal of the operator identity provider **and** the server's own configuration names it as an operator. Nothing the credential says about its own privilege level is an input.*

```
UNTRUSTED for cross-tenant capability
  anonymous · self-registered tenant admin (UserRole.ADMIN) · customer Clerk org member ·
  customer org_role "admin" · tenant-mapped integration API key · any token-borne
  privilege claim (e.g. platform_operator=true)
      ║  C2.6 BOUNDARY (§8 gate sequence)
      ▼
TRUSTED for cross-tenant DLQ capability
  verified operator-IdP principal whose org_id equals the server-configured
  PLATFORM_OPERATOR_ORG_ID (and, when the allowlist is configured, is named by it)
      ║  C2.5 BOUNDARY (unchanged, PR604)
      ▼
  ADMIN_OPS_DATABASE_URL LOGIN, member of c2pro_admin_ops; SELECT +
  UPDATE(retry_count, status, updated_at, next_retry_at) on dlq_failed_tasks only
```

**Assets behind the boundary.** Cross-tenant *read* of `dlq_failed_tasks`: `payload_json` (customer document ids, analysis parameters), `error_message`, `error_traceback` (may embed customer data), `tenant_id`, plus failure-volume patterns that are themselves competitive intelligence. Cross-tenant *mutation*: forcing or suppressing reprocessing of another tenant's failed work — driving rows to `exhausted` (denial of retry) or re-triggering paid AI analysis against another tenant's budget.

**Not owned by C2.6:** theft of `ADMIN_OPS_DATABASE_URL` (secret management); compromise of a genuine operator's IdP account (IdP MFA/SSO); the C2.5 database boundary (PR604); PR604 lifecycle defects under separate review.

## 5. PRINCIPAL MODEL

| Principal | Type | Provenance | Self-issuable | Tenant context | Cross-tenant capability |
|---|---|---|---|---|---|
| Tenant user / admin | `src.core.auth.models.User` | local HS256 JWT, or customer Clerk org | **Yes** (public registration) | own tenant, bound to RLS GUC | **Never** |
| Platform operator | `PlatformOperator` (new) | operator Clerk org, pinned server-side | No | **none** | Yes — sole holder |
| Machine / service | `ServicePrincipal` (**not in C2.6**) | dedicated service credential | No | none | Deferred (§5.4) |

**5.2 Type separation is normative (M7).** `PlatformOperator` **MUST** be a distinct frozen type; it **MUST NOT** be `User`, a subclass of `User`, or carry a `tenant_id`. This makes tier drift a type error rather than a review omission.

```python
@dataclass(frozen=True)
class PlatformOperator:
    operator_id: str                       # immutable IdP user id ("user_...")
    org_id: str                            # the pinned operator org
    email: str | None                      # attribution only, never authz input
    auth_tier: Literal["platform_operator"]
```

### 5.3 Identity resolution rules

- **IR1** Operator identity is resolved **exclusively** from the verified operator-IdP token. The gate **MUST NOT** query `users` or `tenants` to **establish** operator status. The single permitted database read is the **deny-only** integrity lookup at G5 (§10 E2), which runs *after* identity is already established and can only ever **deny** — never grant, never supply identity.
- **IR2** The operator key is the **immutable IdP user id** (`user_...`). Email **MUST NOT** be an authorization input anywhere (mutable; attacker-choosable under some IdP configurations).
- **IR3 (residual tenant identity, M8)** A staff IdP account may already have a `users` row. On the **current baseline** `TenantIsolationMiddleware` would resolve it and populate `request.state.tenant_id` (verified: `tenant_isolation.py:154`). Under C2.6 a platform-scoped route **MUST NOT** reach that resolution path at all (§7.1). Any residual tenant_id **MUST NOT** be an authorization input, **MUST NOT** be bound as the operator's tenant context, and **MUST NOT** appear as the actor's tenant in operator audit events. **An operator request that has entered tenant context is a fail-closed defect** (§19/I15).
- **IR4** Token-borne privilege assertions (`org_public_metadata`, `org_role`, custom claims such as `platform_operator`) are **NOT** authorization inputs (M4). `org_role` may be logged; it must not gate.

**5.4 Cross-tier invariant; machine tier deferred (M19, M20).**

> No dependency function, principal type, or database credential is shared between tiers. A tier is **never** obtained by adding a flag, role, or claim to a lower tier's principal.

No machine consumer of the cross-tenant DLQ capability exists today and C2.6 builds none. A future one **MUST** use a distinct dependency and principal type (`require_platform_service(scope)` / `ServicePrincipal`, never the operator gate); be constrained at the **network layer** (internal-only route or mTLS), not by secret possession alone; receive a capability **strictly narrower** than a human operator and **read-only by default** (e.g. a read-only DLQ list for a monitoring probe); and **MUST NOT** be satisfiable by `settings.integration_api_keys`, which maps an API key to a `tenant_id` (`apps/api/src/core/security/__init__.py:133`) and therefore manufactures exactly the tenant context this boundary forbids.

## 6. CONFIGURATION CONTRACT

### 6.1 `PLATFORM_OPERATOR_ORG_ID` — MANDATORY (M2)

It *is* the authorization boundary; unset means closed, not open.

- **OS1** Type `str | None`, default `None`, env alias `PLATFORM_OPERATOR_ORG_ID`, sourced through `Settings` (`apps/api/src/config.py`).
- **OS2** Comparison is **exact, full-string, case-sensitive equality** against the verified token's `org_id` (M3). No prefix, suffix, substring, normalisation, trimming beyond config load, wildcard, or regex.
- **OS3** Exactly **one** operator organization is supported. A list-valued form is out of scope.
- **OS4** Unset, empty, or whitespace-only ⇒ **every** caller denied `403`, including a genuine operator; log `platform_operator_unconfigured` at ERROR. **No** fallback to `UserRole.ADMIN`, to `org_role`, to allow, or to any other identity source.
- **OS5** The value is a configuration **identifier**, not a secret. It may appear in server logs; it **MUST NOT** appear in any client-facing response body or header.
- **OS6** **No** computed/derived convenience property that could resolve to a non-configured value (contrast the deliberate no-fallback style of `admin_ops_database_url`, `config.py:102`).
- **OS7** Value changes take effect on process restart; not hot-reloaded. Operator *membership* changes require no deploy.

**Why the pin, not the claim.** Membership is managed in the IdP and takes effect on the member's next token refresh, with no deploy; privilege is defined by this server-side pin. The split gives fast revocation without ever letting a credential assert its own tier (SO2).

### 6.2 `PLATFORM_OPERATOR_USER_IDS` — optional narrowing (M5)

The C2.6 posture **MUST NOT** depend on the allowlist being configured. With it empty, C2.6 is complete and its acceptance criteria fully satisfiable.

- **AL1** Type `list[str]`, default `[]`, env alias `PLATFORM_OPERATOR_USER_IDS`. **Grammar (binding): `PLATFORM_OPERATOR_USER_IDS` is a comma-separated list of immutable Clerk user IDs — not CSV/JSON, not JSON.** The parser mirrors the existing repository comma-separated list pattern (`config.py:633`, `budget_alert_admin_emails`: split on `,`, trim surrounding whitespace per entry, drop empty entries after trimming). **JSON parsing is NOT introduced for this setting.**
- **AL2** **Empty ⇒ no narrowing.** Org-pin membership alone authorizes. Unset or an empty/whitespace-only list is a valid, supported production configuration.
- **AL3** **Non-empty ⇒ narrowing applies.** The verified `user_id` must be a member, compared by **exact, case-sensitive** string equality; a non-member operator-org principal is denied `403`. The allowlist can only ever *reduce* the authorized set — never authorize a principal that failed the org pin.
- **AL4** Entries are **immutable IdP user ids** (`user_...`). Emails, display names, org roles are invalid; a malformed entry or a value not of the expected id shape fails according to the existing config validation contract (fail fast at startup), the same way other malformed `Settings` values do.
- **AL5** Evaluated **after** the org pin (§8: G2 before G3), so denial reasons stay attributable to the correct cause.
- **AL6** Intended uses: bootstrap narrowing during initial enablement; emergency kill-switch. **Not** the routine offboarding mechanism — IdP org membership removal is.
- **AL7** If a future slice makes the allowlist mandatory it becomes a *required narrowing constraint* — even then not a "factor". Out of C2.6 scope.

**6.3 Terminology rule (binding, M5).** The allowlist **MUST NOT** be called a "second factor", "2FA", or "multi-factor". It is not an independent authentication factor; it is an **additional server-side narrowing constraint applied to the same single verified identity**. Approved terms: *narrowing constraint*, *defense-in-depth narrowing*, *operator kill-switch*. Applies to code comments, docstrings, log messages, backlog entries, and runbooks.

## 7. PLATFORM-ROUTE AUTHENTICATION MODE AND `require_platform_operator` CONTRACT

### 7.1 Platform-route authentication mode (authentication layer) — REQUIRED

**Baseline, verified on `32eba943` (authoritative evidence).** `TenantIsolationMiddleware.dispatch` (`tenant_isolation.py:77`) calls `_extract_auth_context` (`:227`), which **first** attempts a local HS256 decode with `settings.jwt_secret_key` (`:198`) and **falls back** to `verify_clerk_token` (`:300`); on the Clerk branch it resolves the internal user record and tenant via `_get_clerk_user_record` (`:318`, returning the `BootstrapUserRecord` whose `tenant_id`/`user_id` are then returned to `dispatch` — the sibling method `_get_tenant_for_clerk_user` at `:371` is dead on this path: it is never called from `_extract_auth_context` and exists only as a standalone helper exercised directly by unit tests), then `dispatch` writes `request.state.tenant_id` (`:154`) and `request.state.user_id` (`:155`) and binds `tenant_id` into the structlog context (`:158`). **For platform routes this behavior is NOT acceptable:** a platform operator would be authenticated through the tenant path, acquire a tenant context, and have `tenant_id` bound into every log line of a cross-tenant action.

To avoid collision with the binding decision register (M1–M22), the MASTER Resolution 4 steps M0–M5 are written **`AUTH-M0`–`AUTH-M5`** throughout this document; their numbering and meaning are unchanged.

C2.6 therefore defines a **platform-route authentication mode**, gated by an explicit **platform-route registry** whose canonical model is **`(method, normalized_path)`** — an exact HTTP-method-plus-path identity, never a path prefix. The initial registry contains only the two exact route identities defined by `src.admin.adapters.http.router` (mounted at `main.py:311` under the v1 prefix): `("GET", "/api/v1/admin/dlq")` and `("POST", "/api/v1/admin/dlq/{dlq_id}/retry")`.

**The registry MUST NOT be implemented, or described, as a prefix match on `/api/v1/admin/dlq`.** A route enters platform mode only through an explicit, individually reviewed `(method, normalized_path)` registry entry — never a prefix heuristic, never inferred.

**Registry resolution is defined against the ACTIVE MOUNTED application route set (binding).** The registry is not a free-standing list of strings compared against request paths in the abstract. Each registered `(method, normalized_path)` identity **MUST resolve to exactly one route in the running application's mounted route table** (`app.routes`) — not zero, not two — and that one mounted route **MUST be the cross-tenant admin implementation** from `src.admin.adapters.http.router`. This **active-route uniqueness** invariant is what makes the exact-identity model sound: an identity that resolves ambiguously, or resolves to something other than the cross-tenant admin router, is a specification violation.

**Legacy `src.core.dlq.router` (clarification, binding).** The legacy tenant-scoped DLQ module `src.core.dlq.router` still exists in source and declares an equivalent method/path template, but it is **NOT mounted**: at base `32eba943` `src.main` includes only `dlq_admin_router` from `src.admin.adapters.http.router` (`main.py:311`). **The mere existence of an unmounted legacy module declaring the same template is NOT a specification violation** — C2.6 neither deletes, moves, nor rewrites it. Two things are binding instead: it **MUST remain unmounted** (S11), and **if any second route carrying a registered method/template ever becomes mounted, the structural CI gate MUST fail** (S10, S12), because registry identities would no longer resolve uniquely.

**No router-provenance runtime authorization.** Provenance — *which module defined the matched route* — is a **structural, CI-time** assertion only (S10). It **MUST NOT** become a request-time authorization input: at runtime AUTH-M0 stays a pure `(method, normalized_path)` match against the registry, with no inspection of the matched route's defining module, endpoint object, or router identity.

**No public API path change.** C2.6 does not rename, move, or re-prefix any route. `/api/v1/admin/dlq` stays exactly as mounted today, and **no `/platform/dlq`** (or equivalent) namespace is introduced.

| Step (MASTER Resolution 4 · M0–M5) | Requirement |
|---|---|
| **AUTH-M0** | **Platform-route classification.** `(request.method, normalized_path)` **exactly** matches an entry in the platform-route registry (§7.1) — never a prefix or substring match on the path. Classification is a pure identity match: it **MUST NOT** inspect the matched route's defining module or router (router provenance is a CI-time structural assertion only, §7.1 / S10). Classification happens before any credential resolution. |
| **AUTH-M1** | **Require Bearer token.** Absent or unparseable ⇒ `401` + `WWW-Authenticate: Bearer` from the authentication layer. |
| **AUTH-M2** | **Reject the local HS256 path** for a platform route (decision M6). A local HS256 token is **not** an accepted platform identity; it is rejected ⇒ `401`. The baseline's HS256-first fall-through **MUST NOT** apply to platform routes. |
| **AUTH-M3** | **Verify the Clerk RS256 token** (`verify_clerk_token`, RS256/JWKS) in the authentication layer. Verification failure, including JWKS unreachable ⇒ `401`. |
| **AUTH-M4** | **Extract** the immutable Clerk subject (`sub`), `org_id`, and verified identity claims (`email_verified` and, for attribution only, `email`). |
| **AUTH-M5** | **Enter platform identity context with NO tenant resolution or binding.** The normal internal-user/tenant resolution path **MUST NOT** be called: no `_get_clerk_user_record` (the actually-invoked baseline lookup, `:318`), no `get_current_user`, no `_provision_clerk_user`. `request.state.tenant_id` **MUST NOT** be populated. `tenant_id` **MUST NOT** be bound into the structlog context. |

**Exposure to the dependency.** The verified Clerk identity is exposed to `require_platform_operator` via `request.state` (or an equivalent **typed** authenticated-context object) — for example `request.state.platform_identity`. The dependency **consumes** this already-verified context; it **MUST NOT** re-verify the token or make a second IdP round-trip, and it **MUST NOT** perform a second tenant lookup to establish identity (§8.2).

**Scope note (not scope expansion).** The middleware change is **inside C2.6 implementation scope**. It is not a product feature: it is the minimum required to make the approved trust boundary expressible on the current repository. Behavior on every **non**-platform route is unchanged (S08, AC18).

### 7.2 `require_platform_operator` contract

**Location:** `apps/api/src/core/auth/platform_operator.py` — new module; the authorization surface of C2.6 lives in this one file (~150 lines), alongside the platform-route authentication mode in the middleware layer (§7.1).

```python
async def require_platform_operator(request: Request) -> PlatformOperator
```

| Clause | Contract |
|---|---|
| **Purpose** | Sole authorization gate for cross-tenant administrative capabilities. |
| **Preconditions** | The request was classified platform-scoped and authenticated by the platform-route authentication mode (§7.1 AUTH-M0–AUTH-M5). A token-less, HS256, or unverifiable request was already rejected `401` **before** this function runs. |
| **Inputs** | The **already-verified** platform identity context from §7.1 (immutable Clerk `sub`, `org_id`, `email_verified`), and `Settings.platform_operator_org_id` / `Settings.platform_operator_user_ids`. **No other input is authorization-relevant.** |
| **Forbidden inputs** | `User.role` / `UserRole` (any value) · `request.state.tenant_id` (IR3, M8) · `org_role` / `is_org_admin` · **`org_public_metadata`** (never, for any purpose, including the integrity check — §10 E2) · any privilege-asserting custom claim · any `users`/`tenants` read used to **establish** identity or **grant** status (IR1) · `settings.environment` (F2) · request headers other than `Authorization`. |
| **Permitted database read** | Exactly one: the **deny-only** operator-org/customer-tenant integrity lookup at G5 (§10 E2). It is narrowly scoped, read-only, runs only after identity is established, and can only **deny**. |
| **Returns** | `PlatformOperator` on success (§5.2). |
| **Raises** | `HTTPException(403)` — identity proven but not an operator, **including** the unconfigured case (M12). **Never** `503` (capability availability is not this function's concern, M10). It does **not** raise `401`: identity-not-proven is handled by the authentication layer (§7.1, M11). |
| **Side effects** | Exactly one structured audit event per invocation — `platform_operator_granted` or `platform_operator_denied{reason}` (§12) — plus the G7 log binding of `platform_operator_id`/`org_id` **without** `tenant_id`. No DB writes. No population of `request.state.tenant_id`. |
| **Purity** | Deterministic given (verified identity context, settings, integrity-lookup result). No caching of authorization decisions across requests. |
| **Auth path** | Clerk RS256 identity **only** (M6), verified upstream at AUTH-M3. The local HS256 path is not an accepted platform identity path and there is no fall-through between paths. The dependency performs **no** re-verification and **no** additional IdP round-trip. |
| **Usage** | Declared as a router-level dependency; injected as a parameter only where the handler needs operator attributes for audit. |

## 8. EXACT AUTHORIZATION ORDER

Order is **load-bearing and normative**; implementations MUST NOT short-circuit differently. It is split across two layers to stay coherent with the real baseline: the **authentication layer** proves identity (AUTH-M0–AUTH-M5, §7.1), then the **authorization dependency** decides privilege (G1–G7), and only then is **capability availability** consulted (G8–G9).

**Authentication layer — `AUTH-M0`–`AUTH-M5` (§7.1).** AUTH-M0 platform-route classification · AUTH-M1 require Bearer ⇒ else `401` · AUTH-M2 reject local HS256 for platform routes ⇒ `401` · AUTH-M3 verify Clerk RS256 ⇒ else `401` · AUTH-M4 extract immutable `sub` / `org_id` / verified claims · AUTH-M5 enter platform identity context with **no** tenant resolution and **no** tenant binding.

**Authorization dependency — `require_platform_operator`:**

| Gate | Check | Failure |
|---|---|---|
| **G1** | `settings.platform_operator_org_id` configured and non-empty (M2) | `403`, log ERROR `platform_operator_unconfigured` |
| **G2** | verified Clerk `org_id == settings.platform_operator_org_id` — exact, full-string, case-sensitive (OS2, M3) | `403`, log WARN with presented `org_id` |
| **G3** | Optional allowlist narrowing on the **immutable Clerk user id**: if `platform_operator_user_ids` non-empty, `sub ∈ list` (AL3) | `403`, log WARN with `user_id` |
| **G4** | `email_verified` is true, where the claim's provenance is itself verified (§9.5) | `403`, log WARN `{reason=email_unverified}` |
| **G5** | **Deny-only** operator-org / customer-tenant integrity check (§10 E2) | `403` + high-severity security event `platform_operator_org_is_tenant` |
| **G6** | Construct the distinct `PlatformOperator` (§5.2) | — |
| **G7** | Bind `platform_operator_id` + `org_id` into the structured logging context **without** `tenant_id`; emit `platform_operator_granted` | — |
| **G8** | *(downstream, PR604, unchanged)* **Only now** check admin capability availability — `ADMIN_OPS_DATABASE_URL` configured and admin-ops DB reachable; surfaced by `DLQAdminOpsAdapter._admin_session` (`router.py:58`) | — |
| **G9** | Capability unavailable | `503` |

**8.1 Ordering rationale — authz before capability (decision M10).** AUTH-M0–AUTH-M5 and G1–G7 are **fully** evaluated before any capability-availability concern (G8–G9), so PR604's `503` is reachable **only** by an authenticated, authorized operator. **An unauthorized caller must never learn whether `ADMIN_OPS_DATABASE_URL` exists** (SO4, N13). Reordering G8 ahead of G1–G7 — e.g. as an early "is this feature on?" check — is a **specification violation**, not an optimisation.

**8.2 No duplicate verification.** G1 (a pure configuration read) precedes every identity-dependent gate, so an unconfigured deployment denies without consulting the identity context further. Token verification happens **once**, at AUTH-M3 in the authentication layer; the dependency consumes that result. Re-verifying the token inside the dependency, or issuing a second IdP round-trip, is a specification violation. Likewise the dependency performs **no** tenant lookup to establish identity — the only database read it may make is the deny-only G5 integrity check.

**8.3 Deviation from the source ordering.** The source design placed the first JWT verification inside the dependency and numbered the middleware step `G0`. On this repository the middleware already authenticates every non-public request, so that description was incoherent with the baseline. The canonical order above replaces it: `G0` no longer exists, and the old `G2`–`G7` are renumbered `G1`–`G5`.

## 9. FAILURE SEMANTICS

**401** — *"you have not proven who you are"* (M11). **403** — *"you are known; you are not a platform operator"* (M12). **503** — *"you are a platform operator; the capability is unavailable"* (M13). Three codes, three meanings, no overlap.

**§9.1 `401` — handled entirely by the authentication layer (§7.1).** Emitted via `TenantIsolationMiddleware._unauthorized_response` (`tenant_isolation.py:69`) with `WWW-Authenticate: Bearer` for: a token-less or unparseable request (AUTH-M1); **a local HS256 token presented to a platform route** (AUTH-M2); and a Clerk RS256 verification failure including JWKS unreachable (AUTH-M3). `require_platform_operator` never raises `401`. **Rule F-401:** an authentication failure is **never** reported as `503`; conflating them would leak capability state to unauthenticated callers.

**§9.2 `403` — every authorization denial, without exception:** G1 config unset, G2 org mismatch, G3 allowlist exclusion, G4 unverified email, G5 operator-org-is-tenant. **Rule F-403-BODY:** the response body is **generic and identical** across all `403` causes (`{"detail": "Not authorized"}`) — no reason codes, no config state, no indication of which gate failed, no echo of the presented `org_id`, **and no signal whatsoever about whether the admin capability is configured**. All diagnostic detail goes to structured logs only.

### 9.3 Normative matrix

| Condition | Code | Log |
|---|---|---|
| No / unparseable credential | 401 (AUTH-M1) | WARN `authentication_failed` (auth layer) |
| **Local HS256 token on a platform route**, any role including `admin` | **401** (AUTH-M2) | WARN `platform_route_local_jwt_rejected` |
| Clerk RS256 verification fails, JWKS unreachable | 401 (AUTH-M3) | WARN `platform_route_identity_unverified` |
| `PLATFORM_OPERATOR_ORG_ID` unset or empty | **403** (G1) | **ERROR** `platform_operator_unconfigured` |
| Token carries no `org_id` | 403 (G2) | WARN `{reason=no_org}` |
| `org_id` mismatch (incl. prefix/case variants) | 403 (G2) | WARN `{reason=org_mismatch, presented_org_id}` |
| Allowlist non-empty, principal not listed | 403 (G3) | WARN `{reason=not_allowlisted, user_id}` |
| `email_verified` false | 403 (G4) | WARN `{reason=email_unverified}` |
| Operator org resolves to a customer tenant | 403 (G5) | **ERROR / high-severity** `platform_operator_org_is_tenant` |
| Authz passed, `ADMIN_OPS_DATABASE_URL` unset | 503 (G9) | WARN `admin_ops_session_unavailable` |
| Authz passed, admin-ops DB unreachable | 503 (G9) | WARN `admin_ops_session_unavailable` |

### 9.4 Fail-closed rules

- **F1** Absence of configuration is a **deny**, never a skip and never a fallback.
- **F2** **No environment-conditional relaxation** (M16): no `if settings.environment != "production"` branch may exist anywhere in the operator path. The pre-existing `tenant_validation_bypassed_for_tests` pattern (`tenant_isolation.py:441`) **MUST NOT** be replicated here.
- **F3** No warn-only, shadow, or dual-accept mode (M14, M15).
- **F4** No caching of a granted authorization decision across requests.
- **F5** An exception raised anywhere inside the gate — or inside the G5 integrity lookup — results in denial, never a pass-through.
- **F6** A platform request that has acquired tenant context (populated `request.state.tenant_id`, a bound `tenant_id` log field, or a resolved internal user record) is a **fail-closed defect**: deny and alert. Tenant context is never "harmless extra state" on a platform route.

**9.5 `email_verified` provenance.** G4 consumes `email_verified` only from the **verified** Clerk token claims extracted at AUTH-M4 — never from a user-supplied header, body, query parameter, or an unverified copy of the claim. Where the deployment's IdP configuration cannot establish the claim's provenance, G4 denies. Email itself remains attribution-only and is never an authorization input (IR2).

## 10. OPERATOR-ORG ANTI-TENANT INVARIANT (M9)

**Hazard.** `_provision_clerk_user` (`apps/api/src/core/auth/dependencies.py:92`) auto-creates a **tenant** for any `clerk_org_id` it has not seen (`create_bootstrap_tenant`, `dependencies.py:118`). Left unmodified, the operator org would be auto-provisioned as a customer tenant on first operator login and its members would become tenant principals — re-creating the exact operator/tenant-admin confusion C2.6 exists to eliminate.

> **INV-C26-ORG (normative):** the organization identified by `PLATFORM_OPERATOR_ORG_ID` MUST NEVER be provisioned as, mapped to, or resolvable to a customer tenant. No `tenants` row may carry `clerk_org_id == PLATFORM_OPERATOR_ORG_ID`, and no operator token may resolve to a tenant context.

Two **independent** enforcement points are mandatory (Resolution 3). Neither alone is sufficient, and neither may be traded for the other.

**E1 — source guard in `_provision_clerk_user` (prevention).** When `clerk_org_id` **exactly equals** `PLATFORM_OPERATOR_ORG_ID`, the tenant path **MUST refuse** tenant/user bootstrap; it **MUST NOT** look up or create a customer tenant for that operator org; and it **MUST fail closed with an explicit, controlled auth/bootstrap error** — never a silent skip, never a `None` that a caller might treat as "not provisioned yet" and retry into creation. The guard sits at the top of the org branch, **before** `lookup_tenant_by_clerk_org_id` (`dependencies.py:114`). This protects operator identities that accidentally hit a normal tenant-scoped route: they are refused rather than quietly turned into tenant principals.

**E2 — deny-only integrity check in `require_platform_operator` (detection, G5).** **After** operator identity has already been established from verified Clerk identity + the server-side org pin (+ optional allowlist), perform one narrowly scoped, **read-only** lookup: *is `PLATFORM_OPERATOR_ORG_ID` mapped as a customer tenant?* If mapped ⇒ **DENY** `403` and emit a high-severity security event. If not mapped ⇒ continue.

| E2 property | Rule |
|---|---|
| Direction | **DENY-ONLY.** The lookup can only subtract authorization. It **MUST NEVER** grant, confirm, or contribute to operator status. |
| Ordering | Runs **after** G1–G4, never before. A caller who failed the org pin is already denied and never reaches it. |
| Scope | One narrow read-only tenant-mapping query. Not a user lookup, not a role read, not a `get_current_user` call. |
| Claim source | **`org_public_metadata` MUST NOT be used** for this check, and MUST NOT participate in authorization in any way (M4, IR4). The check consults server-side tenant mapping only. |
| Failure | A raised exception denies (F5). |

**Forbidden-input clarification (binding).** Tenant records, `UserRole`, and customer user rows may **never GRANT** platform-operator authorization. The single tenant-mapping lookup at E2 is permitted **solely** as a deny-only integrity invariant.

E1 must be deployed **before** the operator org is first used (§15.1), or a single operator login creates the tenant the invariant forbids. If a `tenants` row already maps to the chosen operator org, that org **MUST NOT** be used — choose a fresh organization; do not delete or repurpose the tenant row. G5 is a **misconfiguration alarm**, not a routine denial: it should never fire in a healthy deployment and warrants alerting.

## 11. ROUTER AND MIDDLEWARE INTEGRATION

| Action | Path | Change |
|---|---|---|
| **NEW** | `apps/api/src/core/auth/platform_operator.py` | `PlatformOperator`, `require_platform_operator` (G1–G7), internal denial-reason enum, the deny-only G5 integrity lookup. |
| **EDIT** | `apps/api/src/core/middleware/tenant_isolation.py` | **Platform-route authentication mode (§7.1), C2.6 scope.** Classify platform-scoped routes (AUTH-M0) **before** `_extract_auth_context`; for those routes reject the local HS256 path (AUTH-M2, vs. the baseline HS256-first fall-through at `:198`), verify Clerk RS256 only (AUTH-M3, `:300`), **skip** `_get_clerk_user_record` (`:318`, the actually-invoked baseline lookup on the Clerk branch), and **do not** set `request.state.tenant_id` (`:154`) or bind `tenant_id` into structlog (`:158`). Expose the verified platform identity as typed context. **Non-platform routes keep their current behavior byte-for-byte** (S08). High-blast-radius file — requires the explicit behavior-preserving check per `.claude/rules/agents.md`. |
| **NEW/EDIT** | platform-scoped route registry (e.g. `apps/api/src/core/middleware/tenant_isolation.py` or a small constants module) | Explicit set of `(method, normalized_path)` tuples, initially exactly `{("GET", "/api/v1/admin/dlq"), ("POST", "/api/v1/admin/dlq/{dlq_id}/retry")}`. Each identity **MUST resolve to exactly one** mounted route in `app.routes`, and that route **MUST be** the `src.admin.adapters.http.router` implementation (§7.1, active-route uniqueness). Explicit registration only — never a prefix heuristic, never inferred, and **never a runtime router-provenance check**. No public API path is renamed, moved, or re-prefixed. |
| **EDIT** | `apps/api/src/config.py` | `platform_operator_org_id: str \| None = None`; `platform_operator_user_ids: list[str] = []` (comma-separated validator mirroring the pattern at `config.py:633` — trim, drop empties; **not** CSV/JSON). Deny-by-default; **no** fallback property. |
| **EDIT** | `apps/api/src/admin/adapters/http/router.py` | Router deps → `[Depends(security_scheme), Depends(require_platform_operator)]` (`router.py:172`); `retry_dlq_entry` takes `PlatformOperator` (`router.py:206`); audit per §12.2; **delete `require_admin_user`** (`router.py:157`, its only consumer); drop `get_current_user`/`User`/`UserRole` imports. Adapter internals and `get_admin_ops_session` usage **unchanged**. |
| **EDIT** | `apps/api/src/core/auth/dependencies.py` | `_provision_clerk_user`: operator-org guard (§10 E1) — refuse bootstrap and raise an explicit controlled error, before `lookup_tenant_by_clerk_org_id` (`:114`). Surgical. |
| **NEW** | `apps/api/tests/security/test_c26_platform_operator_boundary.py` | §13 N/P cases. |
| **NEW** | `apps/api/tests/unit/admin/test_admin_router_authz_structure.py` | §13 S cases. |
| **NEW** | `apps/api/tests/security/test_c26_platform_route_auth_mode.py` | §13 platform-route authentication-mode cases (N17, N18, P07, P08, S06, S08). |
| **NEW** | `apps/api/tests/security/test_c26_admin_ops_disposable_harness.py` | §13.5 disposable-harness cases (H01–H03), extending/importing the lifecycle of `apps/api/scripts/c25_admin_ops_gate.py` (never reimplemented): synthetic DB, restricted LOGIN, temporary DSN, ownership-tracked preservation of any pre-existing `c2pro_admin_ops` role, HTTP-layer cross-tenant proofs, teardown proof. |
| **NEW** | `apps/api/tests/security/test_c26_admin_ops_authz_boundary.py` | Successor to the reviewer-local `test_c25_admin_ops_authz_boundary.py`, which documented the permissive behavior and is **not present on base `32eba943`**. Must assert denial, not acceptance. |
| **EDIT** | `docs/api/openapi.yaml` | Regenerate via `make openapi` — generated artifact, never hand-edited. |
| **EDIT** | `C2PRO_MASTER_BACKLOG.md`, `backlogs/BCK_BACKEND.md` | **Reconciler role only**, separate `docs(backlog)` PR, never bundled into the code PR. |

**Explicitly NOT touched:** `apps/api/src/core/database.py` · `apps/api/alembic/versions/20260907_0001_c25_admin_ops_dlq.py` · `apps/api/scripts/admin_ops_bootstrap.py` · `apps/api/scripts/c25_admin_ops_gate.py` (unmodified — its lifecycle/ownership/teardown functions are **reused/imported** by the new C2.6 disposable-harness test per §1.3 B, and its capability/grant/RLS proofs are **re-run, not reimplemented**). C2.6 introduces **no** Alembic migration and **no** persistent environment-configuration change (AC16).

> **Revised from the source design.** `tenant_isolation.py` was previously listed as untouched and its modification as a non-goal. The Codex review established that the baseline middleware resolves tenant context for every authenticated request, so the approved trust boundary is **unimplementable** without the §7.1 change. The middleware edit is therefore in scope, strictly bounded to platform-scoped-route handling.

> ⚠ **Implementer trap (verified on base).** Both `apps/api/src/core/security.py` and `apps/api/src/core/security/__init__.py` exist; `importlib` resolves `src.core.security` to the **package** `__init__.py` — the flat module is dead, shadowed code. Operator logic added to `core/security.py` would never execute. Pre-existing debt, out of C2.6 scope to fix, but it will silently swallow an edit.

## 12. LOGGING / AUDIT BOUNDARY

**12.1 Hard constraint (drives M17 / M18).** The operator audit record **cannot** be written through `get_admin_ops_session()`: `c2pro_admin_ops` holds privileges on `dlq_failed_tasks` **only** (migration `20260907_0001`), so any write to `audit_logs` from that session fails with `InsufficientPrivilege` — correctly. Additionally `AuditLogORM.tenant_id` is `NOT NULL` (`apps/api/src/core/security/adapters/persistence/models.py:26`), so a tenant-less platform action has no valid home in the tenant-scoped audit table. **Therefore C2.6 uses structured logging only.** Forcing platform actions into `audit_logs` — by inventing a synthetic tenant or relaxing the `NOT NULL` — is explicitly rejected; persistent platform audit is C2.6.1 (§18).

### 12.2 Event contract

| Event | When | Required fields |
|---|---|---|
| `platform_operator_granted` | G7 | `operator_id`, `org_id`, `path`, `method` — **never** `tenant_id` |
| `platform_operator_denied` | any 403 from the dependency | `reason`, `path`, plus `presented_org_id` / `user_id` where known |
| `platform_route_local_jwt_rejected` | AUTH-M2 (auth layer) | `path` — no token material |
| `platform_route_identity_unverified` | AUTH-M3 (auth layer) | `path`, failure class only |
| `platform_operator_unconfigured` | G1 (ERROR) | `path` |
| `platform_operator_org_is_tenant` | G5 (**high-severity security event**) | `org_id` |
| `platform_operator_dlq_retry` | successful retry | `operator_id`, `org_id`, `dlq_id`, **`target_tenant_id`** (affected row's tenant, read post-fetch) |

### 12.3 Logging rules

- **LG1** Actor attribution is always `operator_id` + `org_id`. **Never** a shared or anonymous operator identity.
- **LG2** For mutations, tenant attribution is the **target row's** `tenant_id`, never the caller's (IR3).
- **LG3** Log `email` for attribution only; never an authorization input (IR2).
- **LG4** Never log the admin-ops DSN, bearer tokens, or token fragments. The exception-class-only discipline in `init_admin_ops_db` (`core/database.py`) is the reference pattern.
- **LG5** `payload_json` / `error_traceback` contents from cross-tenant rows **MUST NOT** be written to application logs — that re-exports customer data outside the boundary.
- **LG6** Denial reasons exist in logs only; never in response bodies (F-403-BODY).
- **LG7** The existing `admin_dlq_retry` log (`router.py:210`) emits caller `admin_id`/`tenant_id`; it is replaced by `platform_operator_dlq_retry` per §12.2.
- **LG8** The structured-logging context of a platform request **MUST NOT** contain `tenant_id` — not as a value, not as an explicit `None`, not inherited from the baseline `bind_contextvars` call (`tenant_isolation.py:158`). G7 binds `platform_operator_id` + `org_id` instead. Asserted by P08.
- **LG9** The G5 high-severity security event and the denial-rate signal are alerting inputs, not merely archival log lines (§18).

## 13. RED-FIRST TEST MATRIX

All `N*` negatives are written and **must fail RED** against the current permissive gate before `platform_operator.py` is wired, then pass GREEN after. `S*` structural tests are the permanent anti-regression layer.

> **Disposable-harness rule (M21, M22; §1.3 B).** Cases needing an admin-ops DSN (N01, N15, P01–P04, H01, and AC1/AC4/AC5) run against a **disposable** PostgreSQL database with a **synthetic** restricted LOGIN and a **temporary** `ADMIN_OPS_DATABASE_URL`-equivalent test DSN, provisioned and torn down by **extending the lifecycle/ownership/teardown machinery of `apps/api/scripts/c25_admin_ops_gate.py`** — never a parallel, reimplemented disposable-DB lifecycle. These real-database tests are **REQUIRED** — a mock-only acceptance is rejected. They are **not enablement**: nothing is written to application environment configuration, any pre-existing cluster-global `c2pro_admin_ops` role is preserved unless the fixture itself created it (ownership tracked exactly as the gate script already does), and the persistent-credential hold of §1.3 A is unaffected.

### 13.1 Negative — authorization denials

| ID | Given | When | Then |
|---|---|---|---|
| N01 | Self-registered `UserRole.ADMIN` holding a **customer Clerk org** identity, harness admin-ops DSN configured | GET `/api/v1/admin/dlq` | **403** at G2 — denial from authz, not capability absence |
| N01b | Self-registered `UserRole.ADMIN` holding a **local HS256** token, harness admin-ops DSN configured | GET `/api/v1/admin/dlq` | **401** at AUTH-M2 — the credential is not a platform identity at all. Either way the capability is never reached (AC1) |
| N02 | `UserRole.ADMIN` of a second unrelated tenant (both credential types) | GET `/api/v1/admin/dlq` | denied — 403 (customer Clerk) / 401 (local HS256) |
| N03 | Customer Clerk org member, `org_role in ("admin","org:admin")` | GET `/admin/dlq` | 403 |
| N04 | Valid operator-org token, `PLATFORM_OPERATOR_ORG_ID` unset | GET `/admin/dlq` | 403 + ERROR `platform_operator_unconfigured` |
| N05 | `org_id` prefix/substring near-match (`org_abc` vs `org_abcdef`) | GET | 403 |
| N06 | `org_id` case variation | GET | 403 |
| N07 | Allowlist non-empty, operator-org member not listed | GET | 403 |
| N08 | `email_verified` false | GET | 403 |
| N09 | No `Authorization` header | GET | **401** + `WWW-Authenticate: Bearer` (GREEN today) |
| N10 | Operator-IdP verification raises (JWKS unreachable) | GET | **401**, no fallback path |
| N11 | Local HS256 token with forged `platform_operator: true` claim | GET | **401** — rejected as a platform identity at AUTH-M2; a forged claim is never a privilege source (revised from the source's 403, which assumed the HS256 path reached the gate) |
| N12 | Operator org resolves to a provisioned tenant | GET | 403 + ERROR `platform_operator_org_is_tenant` |
| N13 | Unauthorized caller, run twice: harness DSN **configured**, then **absent** | GET | **identical 403** both times (never 503) — the caller cannot learn whether `ADMIN_OPS_DATABASE_URL` exists |
| N14 | Any 403 above | inspect body | generic body, no reason code / config detail |
| N15 | `UserRole.ADMIN` (both credential types) | POST `/api/v1/admin/dlq/{id}/retry` | denied (403 / 401 per N01–N01b); target row **unmodified**, verified in the disposable DB |
| N16 | Operator-org token | POST to a tenant-scoped endpoint | operator status confers nothing there; the E1 guard refuses operator-org bootstrap with an explicit controlled error (N19) rather than minting a tenant principal |
| N17 | **Local HS256 JWT** (any role, incl. `admin`), platform route | GET `/api/v1/admin/dlq` | **401** at the authentication layer (AUTH-M2) — not 403, not a tenant-authenticated request |
| N18 | Clerk token of a **customer** org, platform route | GET `/api/v1/admin/dlq` | 403; and `request.state.tenant_id` **absent** — a denied platform request still never enters tenant context |
| N19 | Operator-org Clerk identity hits a **normal tenant-scoped bootstrap** path | any tenant route | denied by E1 with an explicit controlled error **before** any tenant lookup or creation; **no** `tenants` row created |
| N20 | Operator-org token, pin set, **no** tenant maps to the operator org, but the integrity lookup is forced to return a match | GET | 403 — and the inverse: with the pin **unset** or mismatched, a G5 "no conflict" result **cannot** grant access (deny-only, §10 E2) |

### 13.2 Positive

| ID | Given | When | Then |
|---|---|---|---|
| P01 | Operator-org member, pin set, harness DSN set | GET `/admin/dlq` | 200; results span ≥ 2 distinct `tenant_id`s |
| P02 | Same | POST retry on another tenant's row | 200; only `retry_count`, `status`, `updated_at`, `next_retry_at` change; `tenant_id`, `payload_json` untouched (verified against the DB) |
| P03 | Operator, pin set, `ADMIN_OPS_DATABASE_URL` **unset** | GET | **503** — proving 503 is reachable only post-authz |
| P04 | Successful retry | inspect logs | `platform_operator_dlq_retry` carries `operator_id`, `org_id`, `dlq_id`, target `tenant_id` |
| P05 | Allowlist configured **and** principal listed | GET | 200 |
| P06 | Operator whose IdP account has a residual `users` row with a tenant | GET | 200; no tenant GUC bound; audit shows no caller tenant (IR3) |
| P07 | Operator-org Clerk JWT, platform route | GET | 200; `request.state.tenant_id` is **absent** (never set), and the normal internal-user/tenant resolution path was **not** invoked |
| P08 | Same | inspect the request's structured log context | **no** `tenant_id` key at all; `platform_operator_id` + `org_id` present (LG8, G7) |
| P09 | Operator-org Clerk JWT | GET | Clerk verification occurs **once**; the dependency issues **no** second IdP round-trip and **no** identity-establishing tenant lookup (§8.2) |

### 13.3 Structural / anti-regression (permanent)

- **S01** `require_admin_user` and any `UserRole`-based check are **absent** from the `/admin/dlq` dependency tree (introspect `router.dependencies` + each route's dependant graph). Fails CI if re-added.
- **S02** **Every** route under the `/admin/dlq` prefix depends on `require_platform_operator` — catches a future endpoint that forgets the gate.
- **S03** No `settings.environment`-conditional branch exists in `platform_operator.py` (grep-style guard, mirroring `tests/unit/test_backend_ci_guards.py`).
- **S04** `PlatformOperator` exposes no `tenant_id` attribute and is not a `User` subclass.
- **S05** `_provision_clerk_user` contains the operator-org guard and is exercised with `clerk_org_id == PLATFORM_OPERATOR_ORG_ID`, asserting an explicit controlled error and that **no** `tenants` row is created.
- **S06** The platform-route path does **not** reach `_get_clerk_user_record` (the actually-invoked baseline lookup on the Clerk branch, `:318`), `get_current_user`, or `_provision_clerk_user` (assert via patch/spy that they are never called on a platform request).
- **S07** **CI guard:** no persistent environment configuration in the repository — deployment manifests, `.env*` templates, CI workflow env blocks — defines `ADMIN_OPS_DATABASE_URL`, and no bootstrap invocation creating a persistent restricted LOGIN is wired into startup or deploy (AC16, M21/M22). Harness-local fixtures are exempt by construction: they never touch these files.
- **S08** **Non-platform routes are unaffected:** for a representative tenant-scoped route, Clerk and local-HS256 authentication, `request.state.tenant_id` population, and the `tenant_id` log binding behave exactly as on base `32eba943`.
- **S09** **Exact identities, never a prefix.** The platform-route registry is a set of exact `(method, normalized_path)` tuples, asserted by **set equality** against the mounted platform routes — never a prefix or superset match. A registry implemented as, or reducible to, a string-prefix check on `/api/v1/admin/dlq` fails this test. A request whose path merely shares a prefix with a registered entry, but whose own `(method, normalized_path)` is not a registry entry, does **not** enter platform mode.
- **S10** **Active-route uniqueness: each registered identity resolves to exactly one mounted route, and that route is the cross-tenant admin implementation.** Introspect the running application's mounted route table (`app.routes`): for every registry entry, **exactly one** mounted route matches that `(method, normalized_path)` — not zero, not two — and its endpoint resolves to the `src.admin.adapters.http.router` implementation. Zero matches (registry drift, or the route renamed/unmounted) and ≥ 2 matches (ambiguous mount) **both fail**. This provenance check is **CI-time only** and must have no request-time counterpart (§7.1).
- **S11** **Legacy tenant DLQ router is not mounted.** No route in `app.routes` resolves to an endpoint defined by `src.core.dlq.router`. Its continued **existence in source is explicitly not a violation** (§7.1) and is not asserted against — C2.6 neither deletes nor modifies that module; only its **unmounted** status is asserted.
- **S12** **A conflicting second mount fails CI — proven RED, not assumed.** Against a fixture application that additionally mounts a second route carrying a registered `(method, normalized_path)` (mounting `src.core.dlq.router` under the v1 prefix is the natural fixture), the S10 uniqueness assertion **MUST fail**. The test asserts that failure, so the guard is proven to actually fire. Tenant-scoped DLQ routes are never reached through the platform-route authentication mode in any case: if that router is ever legitimately mounted, it must first be given a non-colliding route identity, and it retains its own tenant authorization (`require_admin` + `CurrentTenantId`, populated `request.state.tenant_id`), which C2.6 leaves untouched.
- **S13** **Unregistered admin route fails closed.** A route added under `src.admin.adapters.http.router` (or any future admin-domain router) that depends on `require_platform_operator` but has **no** matching entry in the platform-route registry fails the structural gate: such a route would reach the authorization dependency without having passed through the platform-route authentication mode, violating the dependency's stated preconditions (§7.2).

### 13.4 Unchanged-invariant re-runs (C2.6 must not weaken C2.5)

- **X01** `apps/api/scripts/c25_admin_ops_gate.py` — unchanged, green in CI.
- **X02** `tests/security/test_c25_admin_ops_dlq.py`, `test_c25_admin_ops_lifecycle.py`, `test_c25_admin_ops_partial_setup.py` — unchanged, green.
- **X03** `git diff` shows **no** change to `core/database.py` or the C2.5 migration.

### 13.5 Disposable harness — real database capability proofs (REQUIRED)

- **H01** The harness **extends/imports `apps/api/scripts/c25_admin_ops_gate.py`** to provision an isolated disposable PostgreSQL database and a **synthetic** restricted LOGIN member of the `c2pro_admin_ops` capability role (creating the role only if it does not already exist, per the gate script's existing ownership-tracking logic — a pre-existing role is preserved untouched), and exports a **temporary** `ADMIN_OPS_DATABASE_URL`-equivalent DSN to the app under test. The gate script's already-authoritative capability/grant/RLS proofs — an authorized login can `SELECT` across ≥ 2 tenants and `UPDATE` only the granted columns, while `INSERT`/`DELETE` on `dlq_failed_tasks`, `UPDATE` of a non-granted column (`tenant_id`, `payload_json`), and any access to another table (e.g. `audit_logs`) raise `InsufficientPrivilege`, and the synthetic LOGIN is NOSUPERUSER / NOBYPASSRLS / NOCREATEROLE / non-owner per `pg_catalog` — are **RE-RUN (X01), not reimplemented**. C2.6-specific coverage layered on top is the **HTTP identity/authz integration**: an authorized platform operator reaches `GET /api/v1/admin/dlq` and `POST .../retry` end-to-end against this disposable database, listing across ≥ 2 tenants and retrying another tenant's row (P01, P02).
- **H02** **Teardown proof, reusing the gate script's ownership-tracked drop logic, run on both success and failure:** after the harness completes, the synthetic LOGIN, the temporary DSN, and the disposable database are all **removed** — asserted, not assumed. The `c2pro_admin_ops` capability role is dropped **only if the fixture itself created it**; a **pre-existing** cluster-global `c2pro_admin_ops` role **MUST be preserved**, never dropped merely because C2.6's tests ran. No synthetic credential survives the test session, and none was ever written to application environment configuration.
- **H03** **Persistent-runtime proof:** with the harness **not** running, the application's persistent runtime configuration resolves `ADMIN_OPS_DATABASE_URL` to **absent**, an authorized operator receives `503` (P03), and no restricted LOGIN is configured for API/worker use (complements S07).

## 14. ACCEPTANCE CRITERIA

| ID | Criterion |
|---|---|
| AC1 | A self-registered `UserRole.ADMIN` is denied on every `/admin/dlq` route **with the harness admin-ops DSN configured** — `403` at G2 for a customer-Clerk identity, `401` at AUTH-M2 for a local HS256 credential — and in no case reaches the capability, proven by executing tests against a real database (N01, N01b, N15). |
| AC2 | `UserRole` does not appear in the `/admin/dlq` authorization path — and cannot, since no internal user record is resolved for a platform request; enforced structurally in CI (S01, S06). |
| AC3 | With `PLATFORM_OPERATOR_ORG_ID` unset, every caller including a genuine operator receives 403 (N04). |
| AC4 | A pinned-org operator lists across ≥ 2 tenants and retries a row belonging to a tenant they could not otherwise reach (P01, P02). |
| AC5 | An operator retry mutates only the four granted columns, verified **against the disposable database**, not a mock; forbidden operations are proven to fail (P02, H01). |
| AC6 | No 403 body discloses configuration state or denial reason; all reasons present in structured logs (N14, LG6). |
| AC7 | All C2.5 invariants hold: gate green, C2.5 suites green, `core/database.py` and the migration unmodified (X01–X03). |
| AC8 | Every route under `/admin/dlq`, including any future one, is covered by the operator gate, expressed as exact `(method, normalized_path)` registry membership rather than a path prefix; **every registered identity resolves to exactly one mounted route and that route is the cross-tenant admin implementation**; the legacy `src.core.dlq.router` remains unmounted; and a conflicting second mount makes the structural gate fail (S02, S09–S13). No public API path is changed. |
| AC9 | Audit events carry `operator_id` + `org_id`; retry additionally carries the **target** row's `tenant_id` (P04). |
| AC10 | No environment-conditional bypass exists in the operator path (S03). |
| AC11 | Operator and tenant identities are distinct types; `PlatformOperator` exposes no `tenant_id` (S04). |
| AC12 | The operator org is never provisioned as a tenant — prevention (E1) and detection (E2) both tested (S05, N12). |
| AC13 | C2.6 deploys safely with **both** operator settings unset: 403 to all callers, no startup failure, no behavior change to any tenant-scoped endpoint. |
| AC14 | Documented, tested runbook for operator onboarding/offboarding via IdP org membership, including token-TTL propagation delay. |
| AC15 | 401/403/503 semantics match §9.3 exactly, including N13 (403 not 503 for unauthorized callers when the capability is also unconfigured). |
| AC16 | The merged C2.6 branch introduces **no** `ADMIN_OPS_DATABASE_URL` value in any **persistent** environment configuration and **no** persistent restricted LOGIN creation/enablement in any bootstrap invocation; disposable-harness fixtures are explicitly exempt and provably torn down (M21, M22; S07, H02, H03). |
| AC17 | **Platform requests never enter tenant context:** a platform-route request never invokes the internal user/tenant resolution path, never populates `request.state.tenant_id`, and never carries `tenant_id` in its log context — proven by executing tests (S06, P07, P08, LG8). |
| AC18 | **Non-platform routes are unchanged:** tenant-scoped authentication, tenant binding, and logging behave exactly as on base `32eba943` (S08). |
| AC19 | **A local HS256 JWT presented to a platform route is rejected `401`** at the authentication layer — never authenticated as a tenant principal, never merely 403 (N17, AUTH-M2). |
| AC20 | **The G5 integrity lookup is deny-only:** it is proven incapable of granting operator status, and `org_public_metadata` is absent from the authorization path entirely (N20, §10 E2). |
| AC21 | **Dual anti-provisioning guard:** E1 refuses operator-org bootstrap with an explicit controlled error before any tenant lookup or creation, and E2 independently denies a contaminated operator org (N19, S05, N12). |

## 15. DEPLOYMENT ORDERING

> **THE ORDERING RULE:** `PLATFORM_OPERATOR_ORG_ID` MUST be set **before** `ADMIN_OPS_DATABASE_URL`, in every environment, without exception. The window in which the admin-ops credential is live while operator gating is unconfigured is precisely the exposure this slice exists to prevent. **Authorization first, capability second.**

### 15.1 Phase A — the C2.6 slice (this specification)

Phase A configures **authorization only**. No persistent capability credential is created at any step.

| Step | Action | Expected state |
|---|---|---|
| **D-1** | Merge C2.6 code (gate + platform-route authentication mode). Both operator settings unset; `ADMIN_OPS_DATABASE_URL` absent from all persistent runtimes; no persistent LOGIN. | `/admin/dlq` → 403 for everyone. Safe in production immediately; no configuration required (AC13). Non-platform routes unchanged (AC18). |
| **D-2** | Create the operator IdP organization; enforce MFA/SSO; add staff; record `org_id`. Confirm the org has **no** existing `tenants` row (§10). | Operator org exists; E1 already deployed at D-1, so first login creates no tenant. |
| **D-3** | **Staging:** set `PLATFORM_OPERATOR_ORG_ID` (+ bootstrap allowlist, AL6). Run the full negative suite. | Operators reach authz; endpoint still 503 (DSN absent) — that post-authz 503 is itself the expected signal (P03). |
| **D-4** | **Production:** set `PLATFORM_OPERATOR_ORG_ID` (+ bootstrap allowlist). Re-run the negative suite against production. | Gate live in production: 503 for authorized operators, 403 for everyone else. |
| **D-5** | Verification. | `platform_operator_denied` events appear for ordinary traffic (gate live and being probed); `platform_operator_granted` events map 1:1 to known staff. **C2.6 acceptance (§14) complete.** |

**15.2 Disposable harness during Phase A (permitted, required).** Throughout Phase A the acceptance suite stands up a disposable database, a synthetic restricted LOGIN, and a temporary DSN inside the harness — by **extending `apps/api/scripts/c25_admin_ops_gate.py`'s existing lifecycle/ownership/teardown machinery**, never a separate reimplementation — and tears them down on both success and failure (§13.5 H01–H03), **preserving any pre-existing cluster-global `c2pro_admin_ops` role** exactly as the gate script already does. This is **not** enablement and does not relax §1.3 A: no persistent runtime acquires a capability credential at any point in Phase A.

**15.3 Phase B — persistent capability enablement: OUT OF C2.6 SCOPE (M21, M22).** `ADMIN_OPS_DATABASE_URL` and the persistent restricted admin LOGIN remain **absent from every persistent runtime through the whole of Phase A**. Only after D-5 completes, and only under a separate MASTER-authorized enablement operation, may an environment run `admin_ops_bootstrap.py` with an owner DSN, create the persistent LOGIN member, set `ADMIN_OPS_DATABASE_URL`, and re-run `c25_admin_ops_gate.py` plus the positive suite — staging first, then production. That operation is specified and approved separately; **merging C2.6 does not authorize it.** The source design's D-4/D-5 steps, which performed this inside the same slice deployment, are superseded and non-canonical.

### 15.4 Prohibited transition patterns (M14, M15, M16)

- **No warn-only mode** (log-what-would-be-denied while still allowing). For an authorization boundary that mode **is** the vulnerability, and it keeps the confirmed finding exploitable for its duration.
- **No dual-accept window** (accept `UserRole.ADMIN` *or* operator identity).
- **No feature flag** gating the gate itself. C2.6 is a hard cutover, safe precisely because `/admin/dlq` returns 503 to every caller in production today, so there is no working consumer to break.

## 16. ROLLBACK ORDERING

| Step | Action | Result |
|---|---|---|
| **R-1** | Unset `ADMIN_OPS_DATABASE_URL`; restart. *(No-op until Phase B has run — under §1.3 A it is already absent.)* | Capability off; 503 for authorized operators. Tenant isolation unaffected. |
| **R-2** | Unset `PLATFORM_OPERATOR_ORG_ID`; restart. | Gate closed for everyone; 403. Platform-route authentication mode still active: platform requests still acquire no tenant context. |
| **R-3** | *(only if C2.6 code itself is faulty)* revert the C2.6 code PR. | Returns to the pre-C2.6 permissive gate **and** restores baseline tenant-context resolution on `/admin/dlq` — **therefore R-1 MUST have completed first**, or the confirmed finding is live again. |

**Invariant:** capability is withdrawn before authorization is withdrawn. Reverting C2.6 code while `ADMIN_OPS_DATABASE_URL` remains set re-opens cross-tenant access to every self-registered tenant admin. **R-3 without R-1 is a forbidden operation.**

**Blast radius.** Rollback at any step affects only `/admin/dlq`, which has no production consumer today. No tenant-scoped endpoint, RLS policy, migration, or database role is touched by C2.6 or its rollback; C2.6 introduces no Alembic migration, so there is no `downgrade()` to run.

**Break-glass.** If the operator IdP is unavailable, the recovery path is a **DBA action using the owner credential**, deliberately **not** an application code path. Building an emergency HTTP bypass is prohibited — it would reintroduce the fail-open this design exists to prevent (F2, F3).

## 17. NON-GOALS

| ID | Non-goal |
|---|---|
| NG1 | Modifying the C2.5 database boundary — role properties, grants, policies, `get_admin_ops_session` validation, bootstrap, or gate script. |
| NG2 | Persistent platform audit storage (→ C2.6.1, §18). |
| NG3 | Machine/internal-service authorization (§5.4, M19). |
| NG4 | Extending platform-operator gating to endpoints beyond `/admin/dlq`. |
| NG5 | Multi-org or hierarchical operator roles (viewer/approver tiers). Exactly one operator org, one capability (OS3). |
| NG6 | Replacing or reforming tenant-level `UserRole` semantics for tenant-scoped endpoints. |
| NG7 | Fixing the shadowed `core/security.py` module (documented hazard only, §11). |
| NG8 | Any change to `TenantIsolationMiddleware` **beyond** the platform-scoped-route handling of §7.1. Non-platform-route authentication, tenant resolution, tenant binding, and logging are untouched (S08, AC18). *(Revised: the source design's blanket non-goal was incompatible with the approved trust boundary.)* |
| NG9 | Provisioning automation for the operator org (a runbook, not code). |
| NG10 | Addressing PR604 lifecycle defects under separate review. |
| NG11 | Enabling `ADMIN_OPS_DATABASE_URL` or creating a **persistent** restricted runtime LOGIN (M21, M22 — separate MASTER-controlled operation, §15.3). Disposable-harness resources are **not** covered by this non-goal and are required (§13.5). |
| NG12 | Anything belonging to **C3**, the ordinary-runtime non-owner / `NOBYPASSRLS` cutover. |

## 18. DEFERRED C2.6.1 SCOPE

**`platform_audit_log` — persistent platform-action audit.**

| Aspect | Requirement |
|---|---|
| Driver | `audit_logs.tenant_id` is `NOT NULL` and tenant-scoped; `c2pro_admin_ops` has no privileges on it (§12.1). Platform actions have no valid home there. |
| Design | Dedicated table **outside** tenant RLS, owned by neither `c2pro_app` nor `c2pro_admin_ops`; written through the ordinary runtime session, never the admin-ops session. |
| Columns | `operator_id`, `org_id`, `action`, `target_tenant_id` (nullable — a cross-tenant list has no single target), `target_resource_id`, `created_at`, optional hash chain mirroring `AuditLogORM.event_hash` / `previous_hash`. |
| Constraint | **MUST NOT** bind the operator's residual tenant context when writing (IR3). |
| Also in scope | Retention policy; whether cross-tenant **list** operations are persisted or remain log-only; alerting on `platform_operator_org_is_tenant` and on denial-rate anomalies. |
| Rejected | Relaxing `audit_logs.tenant_id` to nullable, or inventing a synthetic "platform tenant" to reuse the tenant-scoped table. |

**Also deferred:** mandatory-allowlist mode (AL7); machine/service tier (§5.4); extension of operator gating to future cross-tenant capabilities.

## 19. PERMANENT SECURITY INVARIANTS

Must never regress — in C2.6 or any successor (C2.6.1, C3, beyond):

| ID | Invariant |
|---|---|
| **I1** | Tenant-scoped privilege — `UserRole.ADMIN`, customer `org_role` admin, or any tenant-mapped API key (`integration_api_keys`) — is **NEVER** sufficient for a cross-tenant capability. |
| **I2** | A token **NEVER** asserts its own privilege tier. Privilege is decided by server-side configuration compared against verified identity. |
| **I3** | Absence of configuration is a **DENY**, never a skip, fallback, or widened gate. |
| **I4** | No environment-conditional authorization bypass exists, in any environment. |
| **I5** | Authorization is evaluated **before** capability availability; capability state is never disclosable to an unauthorized caller. |
| **I6** | An operator request **NEVER** carries a tenant GUC; any `tenant_id` needed is derived from the target row, never from the caller. |
| **I7** | The three identity tiers share no dependency function, principal type, or database credential. |
| **I8** | The C2.5 database boundary is unweakened: `c2pro_admin_ops` remains NOLOGIN / NOSUPERUSER / NOBYPASSRLS / NOCREATEROLE / non-owner, grants confined to `dlq_failed_tasks` SELECT + UPDATE(`retry_count`, `status`, `updated_at`, `next_retry_at`); per-session catalog re-verification remains mandatory. |
| **I9** | Cross-tenant admin capability is reachable **only** through the dedicated `ADMIN_OPS_DATABASE_URL` credential — never `DATABASE_URL`, never an owner credential. |
| **I10** | Role/capability provisioning never happens at application runtime; it remains an owner/bootstrap responsibility. |
| **I11** | Every route under a cross-tenant admin prefix carries the operator gate — enforced structurally, not by convention. |
| **I12** | Operator actions are individually attributable: `operator_id` + `org_id` on every event; no shared or anonymous operator identity. |
| **I13** | The operator organization is never provisioned as, mapped to, or resolvable to a customer tenant (`INV-C26-ORG`). |
| **I14** | Authentication failure is never reported as `503`; capability unavailability is never reported as `403`. |
| **I15** | A platform-scoped request **NEVER** enters tenant context: no internal user/tenant resolution, no `request.state.tenant_id`, no `tenant_id` in its log context. Any occurrence is a fail-closed defect, not cosmetic drift. |
| **I16** | A local HS256 credential is **NEVER** an accepted platform identity; on a platform route it is rejected at the authentication layer as identity-not-proven. |
| **I17** | Any tenant/customer-record read in the platform authorization path is **deny-only**. No database read may ever grant, confirm, or supply platform-operator status, and `org_public_metadata` never participates in authorization. |
| **I18** | Persistent capability credentials (`ADMIN_OPS_DATABASE_URL`, persistent restricted LOGIN) are created only by an explicit MASTER-controlled enablement operation, never as a side effect of a code merge. Disposable harness resources are isolated, unconfigured in any runtime, and destroyed at teardown. |

`C26_SPEC_STATUS=READY_FOR_MASTER_REVIEW`

*Specification only. No production code modified. C2.6 not implemented. C2.6 merge does not enable the cross-tenant database capability (§1.3).*
