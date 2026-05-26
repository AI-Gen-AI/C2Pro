# ECOA v2 Hotfix and Cutover — Design Spec

**Status**: Draft → for review
**Date**: 2026-05-25
**Owner**: Coherence Score™ workstream
**Trademark scope**: Coherence Score™ is C2Pro's registered differentiator. Any change to authoritative output is trademark-critical.
**Source ADR**: `docs/architecture/decisions/009-coherence-score-v2-evidence-aware.md` (also present, malformed, at `worktrees/sentry-perf/w5b-benchmarks/docs/architecture/adr/ADR-009-`)
**Prior PR**: #146 — ECOA v2 Phase 1 (compatibility) + Phase 2 (shadow mode)

---

## 1. Problem Statement

A diagnostics call on a 2-document, SCOPE-only project returned `overall_score=15` with five categories `state="unassessed"` and `score_reason="assessed_clean"`. The value is mathematically a `mean × coverage_ratio` collapse that ADR-009 §1 P1 explicitly forbids. The bug has two causal paths:

| # | Path | File:line | ADR-009 violation |
|---|------|-----------|--------------------|
| 1 | v1 engine produces `15` instead of `null` | `apps/api/src/coherence/scoring.py:397-400` | §1 P1, §14 |
| 2 | v1→v2 adapter echoes v1's bad number with hardcoded `active_weight=1.0` | `apps/api/src/coherence/adapters/v1_to_v2.py:65-96` | §14 stability rule |

Flipping `coherence_v2_enabled=True` today does **not** fix it because the only v2 surface visible to clients is `DashboardSummary.categories_v2`, populated by the broken adapter. The correct aggregator (`apps/api/src/coherence/services/v2/aggregator_v2.py:77-85`) implements §14 but is unreachable from any authoritative HTTP path.

A third, latent issue: `EnrichedCoherenceResult.overall_score` is declared `float` non-nullable (`apps/api/src/coherence/models.py:264-268`) despite a docstring claiming nullability. `CoherenceResult.overall_score` is already `float | None` (`models.py:228-231`), but the diagnostics endpoint returns the enriched model.

---

## 2. Current vs Target State

| Concern | Current | Target |
|---|---|---|
| v1 partial-coverage score | `mean × coverage_ratio` (forbidden) | `None` with `score_reason="insufficient_active_weight"` when `active_weight < 0.35` |
| `score_reason` propagation | Lost between scoring → router → dashboard | Carried end-to-end through `EnrichedCoherenceResult` and `DashboardSummary` |
| `overall_score` typing | `float` non-nullable on enriched model | `float \| None` on both `CoherenceResult` and `EnrichedCoherenceResult` |
| v1→v2 adapter | Hardcodes `active_weight=1.0`, ignores nulls | Classifies null sub_scores as `INSUFFICIENT_EVIDENCE`, computes real `active_weight`, applies §14 |
| Authoritative engine | v1 (`scoring.py`) | v2 (`aggregator_v2.py`) behind tenant flag, after canary |
| Frontend null handling | Mixed — `?? 0` patterns persist outside DashboardClient | Uniform null-safe rendering per ADR-009 §18 |
| `score_version` coverage | Inconsistent: `"v0_flag_based"`, `"v1_exponential_decay"`, `"coherence-v2"` | Canonical 2-value enum: `"coherence-v1"`, `"coherence-v2"` |
| Cache namespacing | Ad-hoc `f"coherence:..."` keys | `cache_keys.key()` with versioned prefixes; flag-flip invalidation |
| Telemetry | Shadow MAE only | `coherence.v2_path_used`, `coherence.v1_v2_score_delta`, plus shadow events |

---

## 3. Contract Changes (DTO Field-by-Field)

### 3.1 `EnrichedCoherenceResult` (`apps/api/src/coherence/models.py:255-331`)

| Field | Current | Target | Notes |
|---|---|---|---|
| `overall_score` | `float`, `ge=0.0, le=100.0` (line 264-268) | `float \| None`, `ge=0.0, le=100.0` | Aligns with `CoherenceResult` and ADR-009 §14 |
| `score_version` | `default="v0_flag_based"` (line 282-285) | `Literal["coherence-v1", "coherence-v2"]`, no default; required | Phase F |
| `score_reason` | optional str | optional str (no change) | Already exists; now actually populated |
| `score_missing_dimensions` | optional list[str] | unchanged | Populate from `ScoringDiagnostics.missing_dimensions` |

### 3.2 `CoherenceResult` (`models.py:215-252`)

| Field | Change |
|---|---|
| `overall_score` | Already `float \| None` — no change |
| `score_version` | `default="v0_flag_based"` → `Literal["coherence-v1", "coherence-v2"]`, required |

### 3.3 `DashboardSummary` (`models.py:334-354`)

| Field | Current | Target |
|---|---|---|
| `global_score` | `int` | `float \| None` (widened per orchestrator decision 2026-05-26, aligns with ADR-009 §5) |
| `coherence_score` | `int` | `float \| None` (widened per orchestrator decision 2026-05-26) |
| `score_version` | `str \| None = None` (line 350) | `Literal["coherence-v1", "coherence-v2"]`, required |
| `score_reason` | already `str \| None` | unchanged |
| `categories_v2` | `CoherenceV2Payload \| None` | unchanged (still additive in Phases A-C; authoritative in D) |

### 3.4 `CoherenceResultORM` (`apps/api/src/coherence/adapters/persistence/models.py:83-87`)

| Concern | Action |
|---|---|
| Enum value `"v1_exponential_decay"` | Rename to `"coherence-v1"` via Alembic (Phase F) |
| Enum value `"v0_flag_based"` | Backfill to `"coherence-v1"`, drop |
| New value `"coherence-v2"` | Add to enum |
| `global_score` column | Allow `NULL` (Alembic migration) |

### 3.5 v2 DTOs (`apps/api/src/coherence/application/dtos/coherence_v2_dtos.py`)

No structural change. `CoherenceV2Payload.version` is already `Literal["coherence-v2"]` (line 83). Confirm that `GlobalV2.status` includes `"insufficient_active_weight"` (line 74 — yes).

---

## 4. State Machine Impact

ADR-009 §13 state machine (`apps/api/src/coherence/domain/category_state_machine.py`) is **untouched** in Phases A-C. Phase D wires `aggregator_v2.py` as authoritative; the state transitions remain as PR #146 shipped them. Phase B fixes a single classification bug in the adapter: null sub_scores must map to `CategoryStatus.INSUFFICIENT_EVIDENCE`, not be silently dropped.

| Transition | Producer | Phase touched |
|---|---|---|
| `PENDING_DOCUMENTS → SCORED` | `category_aggregator.py` | none |
| `PENDING_DOCUMENTS → INSUFFICIENT_EVIDENCE` | adapter (Phase B) + aggregator | B, D |
| `* → CONFLICTING_EVIDENCE` | `conflict_service.py` | none |
| `* → NOT_APPLICABLE` | `evidence_service.py` | none |

---

## 5. `score_version` Registry (Phase F)

Canonical values, **closed enum**:

| Value | Semantics | Producer |
|---|---|---|
| `"coherence-v1"` | Exponential-decay v1 engine with §14 guard applied | `scoring.py` |
| `"coherence-v2"` | ECOA v2 aggregator authoritative | `aggregator_v2.py` |

Deprecated values to migrate: `"v0_flag_based"` (legacy), `"v1_exponential_decay"` (PR #146). Both → `"coherence-v1"`.

Surfaces required to carry `score_version`:

| Surface | File | Today | Target |
|---|---|---|---|
| ORM | `apps/api/src/coherence/adapters/persistence/models.py:83-87` | enum with 2 legacy values | enum `{"coherence-v1","coherence-v2"}` |
| Pydantic (3 models) | `models.py:241, 282, 350` | mixed defaults | `Literal[…]` required |
| Graph nodes | `coherence/graph/nodes.py:876`, `graph/graph.py:253, 302` | hardcoded `"v1_exponential_decay"` | constant import |
| Telemetry | `tests/unit/core/observability/test_coherence_tracing.py:107` | `"v1"` | `"coherence-v1"` |
| Shadow logs | `services/v2/shadow_runner.py:115` | echoes input | emit both v1 and v2 versions explicitly |
| CSV/PDF/JSON export | `apps/web/components/coherence/DashboardClient.tsx:235-269` (PDF/XLS) | absent | include `score_version` column |
| Cache keys | (new) `cache_keys.py` | n/a | embedded as namespace prefix |
| OpenAPI | generated | mixed | enum on every coherence response |
| CI contract test | `apps/api/tests/contract/test_score_version_required.py` (new) | n/a | fail if any `*Coherence*`/`*Dashboard*` Pydantic model lacks `score_version` |

---

## 6. Cache Key Registry (Phase G)

New module `apps/api/src/coherence/cache_keys.py` exposes a single function:

```python
def key(
    *,
    namespace: Literal["dashboard", "diagnostics", "aggregate", "export"],
    version: Literal["coherence-v1", "coherence-v2"],
    tenant_id: UUID,
    project_id: UUID,
    suffix: str | None = None,
) -> str
```

Returned format: `coherence:{version}:{namespace}:{tenant_id}:{project_id}[:{suffix}]`.

Lint rule (Phase G): ruff custom check or grep CI step bans `f"coherence:` literals in production code outside `cache_keys.py`.

Invalidation triggers (handler in `apps/api/src/coherence/cache_invalidation.py`):

| Event | Action |
|---|---|
| `coherence_v2_enabled` flag flipped for tenant T | `SCAN/UNLINK coherence:coherence-v1:*:T:*` AND `coherence:coherence-v2:*:T:*` |
| New `CoherenceResult` persisted for project P, tenant T | `UNLINK coherence:*:*:T:P*` |
| Deploy of Phase A | one-shot script `apps/api/scripts/invalidate_coherence_cache.py` — `UNLINK coherence:*` |

---

## 7. Telemetry Events

| Event | Tags | Emit point | Phase |
|---|---|---|---|
| `coherence.v2_path_used` | `tenant_id`, `path` ∈ {`v1_only`, `v2_shadow`, `v2_authoritative`}, `score_version` | router after computing authoritative result | D |
| `coherence.v1_v2_score_delta` | `tenant_id`, `delta_abs`, `delta_signed`, `v1_status`, `v2_status` | `ShadowRunner.emit` (extend) | D |
| `coherence.shadow.delta` | existing | unchanged | already shipped (PR #146) |
| `coherence.score_reason_emitted` | `tenant_id`, `score_reason`, `score_version` | router for any `overall_score is None` response | A |
| `coherence.cache_invalidated` | `tenant_id`, `trigger`, `keys_unlinked` | invalidation handler | G |

---

## 8. Rollout / Canary Criteria (Phase D)

**Prerequisite**: Phases A, B, C, F, G merged to `main`; shadow MAE ≤ 5 over a rolling 7-day window; no Sentry errors tagged `coherence.shadow.*` in last 48h.

| Step | Tenant population | Duration | Auto-block guards |
|---|---|---|---|
| Canary 1 | 10% of tenants by hashed `tenant_id` | 24h | Shadow MAE > 15 → revert; `coherence.v2_path_used{path=v2_authoritative}` error rate > 0.5% → revert |
| Canary 2 | 50% | 24h | same as above + p95 latency regression > 30% |
| Canary 3 | 100% | 24h burn-in | same |
| GA | flag default → True | — | manual sign-off |

The per-tenant flag mechanism is **TBD pending Phase D.0 audit** (read-only). Candidates: existing `feature_*` Pydantic settings (global only — insufficient), Clerk org metadata, a new `tenant_settings` table, or a config service. Audit must conclude before D.1 design.

---

## 9. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Returning `null` `overall_score` breaks downstream consumers (web, exports, MCP) | HIGH | Phase C ships before Phase A's flag flip; OpenAPI bump; contract tests |
| R2 | Renaming `v1_exponential_decay → coherence-v1` breaks external integrations | MEDIUM | Internal-only enum; bump OpenAPI minor; deprecation note in CHANGELOG |
| R3 | Cache namespace change orphans warm keys → cold-cache p95 spike | MEDIUM | One-shot purge script + warmup background job at deploy |
| R4 | Per-tenant flag missing → blast radius is global | HIGH | D.0 audit is gate; if no mechanism exists, design `tenant_settings` table before D.1 |
| R5 | Shadow MAE threshold (15) too lax — wrong scores ship | HIGH | Auto-block AND human sign-off; canary measures both MAE and direction (signed delta) |
| R6 | Trademark exposure if `Coherence Score™` returns a misleading scalar | CRITICAL | Phase A returns `null` not a number; UI states reason explicitly (§18) |
| R7 | Frontend `?? 0` patterns hidden in less-trafficked routes | MEDIUM | Phase C grep-based CI guard on `apps/web/**/coherence*` |

---

## 10. Open Questions for Orchestrator

**Resolved 2026-05-26 by orchestrator:**
1. ✅ **Per-tenant flag**: extend existing `Tenant.settings: JSONB` (alerts pattern at `apps/api/src/alerts/adapters/persistence/tenant_repository.py`). Extract shared `apps/api/src/core/feature_flags/tenant_flags_service.py` to avoid duplication. `config.py:319` "Per-tenant override is deferred" comment is the removal seam.
2. ✅ **Type widening**: `DashboardSummary.global_score`, `.coherence_score` → `float | None` (not `int | None`). Internal-breaking minor OpenAPI bump.
3. ✅ **score_version backfill**: blind backfill of NULL and `"v0_flag_based"` → `"coherence-v1"`. Both legacy values are mathematically v1; no row inspection needed.
4. ✅ **OpenAPI bump**: minor.
5. ✅ **MCP audit**: grep before Phase A merges; tdd-guide must verify zero consumers of `DashboardSummary.coherence_score` / `.overall_score` as non-nullable.

---

## 11. References

- ADR-009 — Coherence Score v2 evidence-aware: `docs/architecture/decisions/009-coherence-score-v2-evidence-aware.md`
- PR #146 — ECOA v2 Phase 1+2 (compatibility + shadow mode)
- Bug repro: `POST /api/v1/coherence/evaluate/diagnostics` on project with 2 docs, SCOPE-only assessed
- Suite IDs already in use: `TS-UA-COH-V2-*`, `TS-INT-DB-COH-001`
