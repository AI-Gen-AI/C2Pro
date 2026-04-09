# Follow-up Ticket: Remove Dormant ORM Fallback Paths

> **Governance Note:** This ticket defines scope and acceptance criteria. Active execution status must be tracked in `C2PRO_MASTER_BACKLOG.md`.

## Ticket

- **ID**: `FOLLOWUP-AUTH-BOOTSTRAP-FALLBACK-REMOVAL`
- **Status**: ✅ COMPLETED (TASK-BCK-018)
- **Priority**: P2
- **Owner**: Team Alpha (Sentinel)
- **Completed**: 2026-04-07

## Goal

Add explicit emergency override mechanism for ORM fallback instead of completely removing fallback paths.

## Implementation (Option 3: Safe-Mode Flag)

Instead of removing ORM fallback entirely, added an explicit emergency override flag:

### New Configuration

```bash
# EMERGENCY ONLY: Set to true only during outages to restore access
AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY=false
```

### Changes Made

1. **Config (`src/config.py`)**:
   - Added `auth_bootstrap_allow_fallback_emergency: bool = False` setting
   - Description: "EMERGENCY ONLY: Allow ORM fallback if SQL bootstrap fails. Set to true only during outages to restore access."

2. **Bootstrap Lookup (`src/core/auth/bootstrap_lookup.py`)**:
   - `is_bootstrap_fallback_allowed()` now returns `settings.auth_bootstrap_allow_fallback_emergency`
   - Normal production operation: Always returns `False` (SQL-only)
   - Only returns `True` when `AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY=true` is explicitly set
   - ORM fallback paths preserved but only activated by explicit emergency flag

3. **Tests (`tests/auth/test_auth_dependencies.py`)**:
   - Updated tests to use new `auth_bootstrap_allow_fallback_emergency` setting instead of `auth_bootstrap_fallback_mode`
   - `test_bootstrap_fallback_mode_blocks_production`: Verifies default blocks fallback
   - `test_bootstrap_fallback_mode_allows_emergency_override`: Verifies emergency flag enables fallback

4. **Tests (`tests/security/test_fail_closed_auth_bootstrap_smoke.py`)**:
   - Updated to use new setting

### Why This Approach

- **Safe**: Production uses SQL-only by default; ORM fallback only when explicitly enabled
- **Reversible**: During outage, set `AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY=true` to restore access
- **Auditable**: Telemetry logs when emergency fallback is used (`orm_fallback_emergency` resolution path)
- **Minimal Risk**: No dormant code removed; just made opt-in

## Acceptance Criteria

- [x] `is_bootstrap_fallback_allowed()` returns `False` by default
- [x] `AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY=true` enables ORM fallback
- [x] All auth bootstrap and tenant isolation tests pass
- [x] Telemetry emits correct resolution path for emergency fallback

## Usage During Outage

If `auth_bootstrap.*` SQL functions fail:

1. Set `AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY=true`
2. Restart application
3. System will use ORM fallback to access users/tenants
4. After outage resolved, set back to `false`
