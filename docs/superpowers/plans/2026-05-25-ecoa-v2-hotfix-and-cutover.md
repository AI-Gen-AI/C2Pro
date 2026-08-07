# ECOA v2 Hotfix and Cutover — Execution Plan

**Date**: 2026-05-25
**Spec**: `docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md`
**Method**: TDD (RED → GREEN → REFACTOR) per phase, with code-reviewer dispatch before any merge.

---

## Phase Overview

| ID | Phase | Top-level Task | PRs (est.) | Depends on |
|---|---|---|---|---|
| A | v1 hotfix (§14 + reason propagation) | `TASK-COH-V2-HOTFIX-001` | 1 | — |
| B | v1→v2 adapter partial-coverage fix | `TASK-COH-V2-ADAPTER-002` | (in A's PR) | A |
| C | Frontend null-safe rendering | `TASK-COH-V2-FRONTEND-003` | 1 | A (contract change) |
| D | v2 authoritative behind tenant flag | `TASK-COH-V2-CUTOVER-004` | 2-3 | A, B, C, F, G |
| E | Docs cleanup + OpenAPI | `TASK-COH-V2-DOCS-005` | 1 | A merged |
| F | Mandatory `score_version` everywhere | `TASK-COH-V2-VERSIONING-006` | 2 (api + web) | A |
| G | Cache namespace + invalidation | `TASK-COH-V2-CACHING-007` | 1 | F (uses version) |

### Dependency Graph

```
A ──┬──► C ──┐
    ├──► F ──┴──► G ──► D
    └──► E
B is shipped inside A's PR.
```

---

## Phase A — v1 Hotfix (`TASK-COH-V2-HOTFIX-001`)

### A.1 TDD test list (RED first)

| Test ID | File | What it asserts |
|---|---|---|
| TS-UA-COH-SCORING-014 | `apps/api/tests/coherence/test_scoring_min_active_weight.py` (new) | SCOPE-only (weight 0.20) → `score=None`, `reason="insufficient_active_weight"` |
| TS-UA-COH-SCORING-015 | same | SCOPE+BUDGET (weight 0.20+0.30=0.50 ≥ 0.35) → numeric score, `reason=None` |
| TS-UA-COH-SCORING-016 | same | No findings, all 6 assessed → numeric, `reason=None` (not `"assessed_clean"` with mass collapse) |
| TS-UA-COH-SCORING-017 | same | `poor_extraction_quality=True` → `None`, `reason="insufficient_evidence"` (unchanged) |
| TS-UA-COH-ROUTER-021 | `apps/api/tests/coherence/test_router_score_reason_propagation.py` (new) | `EnrichedCoherenceResult.score_reason` survives router → response |
| TS-UA-COH-ROUTER-022 | same | `DashboardSummary.score_reason` = upstream reason, `coherence_score=None` |
| TS-UA-COH-MODEL-031 | `apps/api/tests/coherence/test_enriched_overall_score_nullable.py` (new) | `EnrichedCoherenceResult(overall_score=None, …)` validates |
| TS-INT-COH-DIAG-001 | `apps/api/tests/integration/coherence/test_diagnostics_partial_coverage.py` (new) | Repro of the user's bug: 2 docs SCOPE-only → 200 OK, `overall_score=None`, `score_reason="insufficient_active_weight"` |

### A.2 Implementation diff outline

| File:line | Change |
|---|---|
| `apps/api/src/coherence/scoring.py:397-400` | Replace `mean × coverage_ratio` with §14 guard: compute `active_weight` from `DEFAULT_CATEGORY_WEIGHTS`; if `< MIN_ACTIVE_WEIGHT` → `score=None`, `reason="insufficient_active_weight"`. Otherwise weighted mean over assessed categories (no coverage multiplier). |
| `apps/api/src/coherence/scoring.py:407-428` | `ScoringDiagnostics` carries `reason` already; ensure `"assessed_clean"` is only returned when **all 6** assessed AND no findings, not when partial. |
| `apps/api/src/coherence/models.py:264-268` | `overall_score: float` → `float \| None`; relax `Field` constraints to allow None. |
| `apps/api/src/coherence/models.py:343-344` | `global_score: int` → `int \| None`; `coherence_score: int` → `int \| None`. |
| `apps/api/src/coherence/router.py:511-525` | When `enriched_result.overall_score is None`, persist `global_score=None`. |
| `apps/api/src/coherence/router.py:708-725` | Propagate `score_reason` from ORM through `DashboardSummary` (already wired at line 719 — verify). |
| `apps/api/src/coherence/router.py` (new emit) | Emit `coherence.score_reason_emitted` event when score is None. |

### A.3 Code-reviewer checklist

- [ ] No `mean × coverage_ratio` arithmetic anywhere in `scoring.py`
- [ ] `MIN_ACTIVE_WEIGHT` imported from `domain/v2_constants.py` (single source of truth)
- [ ] No `?? 0` / `or 0` / `if x else 0` on score values in router
- [ ] `score_reason` and `score_missing_dimensions` flow end-to-end (verified by integration test)
- [ ] No mutation; all DTOs constructed via constructor or `model_copy`
- [ ] Existing tests in `tests/coherence/test_scoring.py` updated, not deleted

### A.4 Acceptance criteria

- [ ] All 8 new tests GREEN
- [ ] `pytest apps/api/tests/coherence/ -x` GREEN
- [ ] `pytest apps/api/tests/integration/coherence/ -x` GREEN
- [ ] Repro request returns `overall_score=null, score_reason="insufficient_active_weight"`
- [ ] No change to `score_version` value yet (Phase F handles rename)

---

## Phase B — v1→v2 Adapter Partial-Coverage Fix (`TASK-COH-V2-ADAPTER-002`)

Shipped in the same PR as Phase A.

### B.1 TDD test list

| Test ID | File | Asserts |
|---|---|---|
| TS-UA-COH-V2-ADAPT-010 | `apps/api/tests/coherence/test_v1_to_v2_adapter.py` (extend) | sub_scores `{SCOPE: 90, others: None}` → 5 categories `INSUFFICIENT_EVIDENCE`, 1 `SCORED`, `active_weight ≈ 0.20`, `global.coherence_score=None`, `status="insufficient_active_weight"` |
| TS-UA-COH-V2-ADAPT-011 | same | sub_scores all numeric → unchanged behavior (`scored`, weight 1.0) |
| TS-UA-COH-V2-ADAPT-012 | same | sub_scores `{SCOPE: 90, BUDGET: 80, others: None}` → `active_weight ≈ 0.50`, status `"partial"`, score = weighted mean |

### B.2 Implementation diff outline

| File:line | Change |
|---|---|
| `apps/api/src/coherence/adapters/v1_to_v2.py:65-96` | Replace hardcoded `active_weight=1.0`. Iterate over `DEFAULT_CATEGORY_WEIGHTS`: numeric sub_score → `CategoryV2(status=SCORED)`; null → `CategoryV2(status=INSUFFICIENT_EVIDENCE, coherence_score=None)`. Sum weights of scored. Apply §14 guard. Reuse `GlobalAggregatorV2` if straightforward; otherwise inline the §14 math (avoid circular import). |

### B.3 Code-reviewer checklist

- [ ] Adapter computes `active_weight` from real per-category weights, not 1.0
- [ ] `CategoryStatus.INSUFFICIENT_EVIDENCE` used for null sub_scores
- [ ] `MIN_ACTIVE_WEIGHT` import (single SoT)
- [ ] Doctring updated; Suite ID referenced
- [ ] No regression in existing test `test_v1_to_v2_adapter.py`

### B.4 Acceptance

- [ ] 3 new tests GREEN
- [ ] When orchestrator-level flag `coherence_v2_enabled=True` over a SCOPE-only project, `DashboardSummary.categories_v2.global.coherence_score is None`

---

## Phase C — Frontend Null-Safe Rendering (`TASK-COH-V2-FRONTEND-003`)

### C.1 TDD test list

| Test ID | File | Asserts |
|---|---|---|
| TS-UW-COH-DASH-021 | `apps/web/components/coherence/DashboardClient.test.tsx` (extend) | `coherence_score=null` → `<CoherenceEmptyState>` renders, no gauge |
| TS-UW-COH-DASH-022 | same | export PDF / XLS write `—` not `0` for null score |
| TS-UW-COH-DASH-023 | same | `sub_scores={SCOPE: 90, BUDGET: null, …}` → BreakdownChart renders BUDGET as muted/null bar, no NaN |
| TS-UW-COH-EMPTY-011 | `apps/web/components/coherence/CoherenceEmptyState.test.tsx` (extend) | `reason="insufficient_active_weight"` → renders specific copy citing ADR-009 §14 |
| TS-UW-COH-CARD-001 | `apps/web/src/components/coherence/ScoreVersionBadge.tsx` (test new) | Renders `coherence-v1` / `coherence-v2` only; throws on unknown |
| TS-E2E-COH-001 | `apps/web/e2e/coherence-partial-coverage.spec.ts` (new Playwright) | Upload 1 doc → dashboard shows empty state, no `15`, no `0` |

### C.2 Implementation outline

| File:line | Change |
|---|---|
| `apps/web/components/coherence/DashboardClient.tsx:111-117` | `buildDashboardRows` must keep null `score` (do not filter or coerce); rows render `—` for null |
| `apps/web/components/coherence/DashboardClient.tsx:136-145` | `barData`/`radarData` typed `score: number \| null`; child charts must accept null |
| `apps/web/components/coherence/DashboardClient.tsx:147-149` | `catEntries` sort: nulls last, no `a - b` coercion |
| `apps/web/components/coherence/DashboardClient.tsx:180-182` | PDF row: render `score ?? "—"`, not raw |
| `apps/web/components/coherence/DashboardClient.tsx:239-253` | XLS cells: use `String` type when null |
| `apps/web/components/coherence/BreakdownChart.tsx` | Accept null bars (filter or render as muted/striped); contract test |
| `apps/web/components/coherence/RadarView.tsx` | Same — handle null axis values |
| `apps/web/components/coherence/ScoreCard.tsx` | Already nullable? — verify; if not, add `score: number \| null` |
| `apps/web/lib/api/contracts.ts` | `DashboardSummary.coherence_score: number \| null`; `global_score: number \| null`; `sub_scores: Record<string, number \| null>`; `score_version: 'coherence-v1' \| 'coherence-v2'` |
| (existing, extend) `apps/web/src/components/coherence/ScoreVersionBadge.tsx` | Confirm existing component handles canonical 2-value enum; if not, update |
| CI guard | grep for `\?\? 0\b` / `\|\| 0\b` / `Number\(` under `apps/web/**/coherence*` — fail build |

### C.3 Code-reviewer checklist

- [ ] No `?? 0`, `|| 0`, `Number(x) || 0` on score paths
- [ ] All chart components accept `number | null`
- [ ] Empty state uses exact copy from ADR-009 §18
- [ ] No UI flag; this is the new default
- [ ] `console.log` absent

### C.4 Acceptance

- [ ] Vitest GREEN
- [ ] Playwright e2e GREEN
- [ ] Visual diff: empty state appears for partial-coverage projects
- [ ] No `0` rendered for null scores anywhere

---

## Phase D — v2 Authoritative Behind Tenant Flag (`TASK-COH-V2-CUTOVER-004`)

### D.0 READ-ONLY AUDIT (gate)

Spawn one investigation task (sub-task `TASK-COH-V2-CUTOVER-004.0`):

- Search `apps/api/src/**` and `core/**` for: `tenant_settings`, `per_tenant`, `feature_flag`, `unleash`, `launchdarkly`, `flagsmith`, `posthog.*feature_flag`, `org_metadata`, Clerk org-level metadata.
- Inspect `core/middleware/clerk_auth.py` for tenant metadata surfaces.
- Output: 1-page memo (added to backlog inline per `DOCUMENTATION_STRUCTURE.md`) — does a per-tenant flag mechanism exist? If not, propose `tenant_settings` table.

**Do not proceed to D.1 until audit signed off by orchestrator.**

### D.1 TDD test list

| Test ID | File | Asserts |
|---|---|---|
| TS-UA-COH-CUTOVER-001 | `apps/api/tests/coherence/test_v2_authoritative_path.py` (new) | Tenant T with flag ON → router returns v2-computed score; v1 not in response |
| TS-UA-COH-CUTOVER-002 | same | Tenant T flag OFF → v1 path unchanged |
| TS-UA-COH-CUTOVER-003 | same | Tenant T flag ON, project SCOPE-only → `coherence_score=None`, `score_version="coherence-v2"`, `score_reason="insufficient_active_weight"` |
| TS-UA-COH-CUTOVER-004 | `apps/api/tests/coherence/test_telemetry_v2_path.py` (new) | `coherence.v2_path_used` emitted with correct tags |
| TS-UA-COH-CUTOVER-005 | same | `coherence.v1_v2_score_delta` emitted in shadow mode |
| TS-INT-COH-CUTOVER-001 | integration | Per-tenant flag flip → next request uses new path |

### D.2 Implementation outline

| File:line | Change |
|---|---|
| `apps/api/src/coherence/router.py:736-756` | Replace global flag check with per-tenant lookup. New helper `coherence_v2_enabled_for_tenant(tenant_id) -> bool`. |
| (new) `apps/api/src/coherence/feature_flags.py` | Wrapper around chosen mechanism from D.0 audit |
| `apps/api/src/coherence/services/v2/orchestrator.py` | Wire as authoritative path when flag ON; result type must conform to existing `DashboardSummary` contract (categories_v2 + top-level scores filled from v2) |
| Telemetry emission | New events per spec §7 |
| Canary rollout | Flag setter script; documented in PR description |

### D.3 Code-reviewer checklist

- [ ] Tenant flag check uses central helper; no `getattr(settings, …)` scattered
- [ ] Both `categories_v2` AND top-level `coherence_score` populated from v2 when authoritative
- [ ] `score_version="coherence-v2"` set deterministically
- [ ] Telemetry tags include `tenant_id` (hashed/uuid only — no PII)
- [ ] Shadow comparison still runs in parallel during canary (instrumentation only)
- [ ] Rollback plan documented in PR

### D.4 Canary acceptance gate

| Metric | Threshold | Window |
|---|---|---|
| Shadow MAE | ≤ 15 | rolling 24h |
| Error rate `coherence.v2_path_used{path=v2_authoritative}` | < 0.5% | 24h |
| p95 latency regression | < 30% | 24h |
| Sentry events tagged `coherence.*` | 0 P1 | 24h |

Auto-block via deploy-pipeline hook reading these metrics; manual sign-off at GA.

---

## Phase E — Docs (`TASK-COH-V2-DOCS-005`)

### E.1 Actions

| Task | File | Action |
|---|---|---|
| Rename ADR | `worktrees/sentry-perf/w5b-benchmarks/docs/architecture/adr/ADR-009-` | `git mv` → `ADR-009-evidence-oriented-coherence-orchestration.md` |
| Status flip | `docs/architecture/decisions/ADR-009-evidence-oriented-coherence-orchestration.md` | `Status: Proposed` → `Status: Accepted` with date |
| OpenAPI | `docs/api/openapi.yaml` | regenerate via `make openapi` after Phase A merged |
| Codemap | `docs/codemaps/coherence.md` (if exists) or update `CLAUDE.md` "Active Analysis Pipeline" | reference new cache_keys module, score_version enum |
| CHANGELOG | root `CHANGELOG.md` | entries for A/B/C/F/G |

### E.2 Acceptance

- [ ] `make openapi` clean diff committed
- [ ] ADR status Accepted with revision history line
- [ ] No new task-specific .md files (per `.claude/rules/DOCUMENTATION_STRUCTURE.md`)

---

## Phase F — Mandatory `score_version` (`TASK-COH-V2-VERSIONING-006`)

### F.1 TDD test list

| Test ID | File | Asserts |
|---|---|---|
| TS-CONTRACT-COH-VERSION-001 | `apps/api/tests/contract/test_score_version_required.py` (new) | Walks all Pydantic models in `src.coherence.**` whose name contains `Coherence` or `Dashboard`; asserts `score_version` field exists and is `Literal["coherence-v1","coherence-v2"]` |
| TS-UA-COH-VERSION-010 | `apps/api/tests/coherence/test_score_version_canonical.py` (new) | `CoherenceResult(score_version="v0_flag_based")` raises `ValidationError` |
| TS-INT-COH-MIGRATE-001 | `apps/api/tests/integration/coherence/test_alembic_score_version_rename.py` (new) | Upgrade then downgrade migration is idempotent; old rows backfilled to `coherence-v1` |

### F.2 Implementation outline

| File:line | Change |
|---|---|
| `apps/api/src/coherence/models.py:241-244, 282-285, 350` | `score_version: Literal["coherence-v1","coherence-v2"]`, required |
| `apps/api/src/coherence/application/dtos/coherence_dtos.py:61` | same |
| `apps/api/src/coherence/adapters/persistence/models.py:83-87` | Alembic migration adds `"coherence-v2"`, renames `"v1_exponential_decay"` → `"coherence-v1"`, drops `"v0_flag_based"` (after backfill) |
| `apps/api/alembic/versions/20260526_0001_coherence_score_version_canonical.py` (new) | Backfill all NULL or `"v0_flag_based"` → `"coherence-v1"`; rename enum values |
| `apps/api/src/coherence/graph/nodes.py:876` | `"v1_exponential_decay"` → `"coherence-v1"` |
| `apps/api/src/coherence/graph/graph.py:253, 302` | same |
| `apps/api/src/coherence/services/v2/shadow_runner.py:115` | emit both v1 and v2 versions explicitly, not echo |
| `apps/api/tests/coherence/*.py` (multiple) | replace `"v1_exponential_decay"` → `"coherence-v1"` |
| `apps/api/tests/integration/document_flow/*.py` | same |
| `apps/api/tests/unit/core/observability/test_coherence_tracing.py:107` | `"v1"` → `"coherence-v1"` |
| `apps/web/lib/api/contracts.ts` | `score_version: 'coherence-v1' \| 'coherence-v2'` |
| `apps/web/src/components/coherence/ScoreVersionBadge.tsx` | confirm/extend existing component |
| Export formats — `DashboardClient.tsx:198-227, 242-256` | Add "Score version" row to PDF + XLS |

### F.3 Code-reviewer checklist

- [ ] Single canonical constant `SCORE_VERSION_V1 = "coherence-v1"`, `SCORE_VERSION_V2 = "coherence-v2"` in `domain/v2_constants.py`
- [ ] No string literals `"v1_exponential_decay"`, `"v0_flag_based"`, `"v1"` survive in `src/`
- [ ] Contract test fails RED before fix, GREEN after
- [ ] Alembic up + down both tested

### F.4 Acceptance

- [ ] CI contract test enforces presence
- [ ] All surfaces in spec §5 carry the value
- [ ] DB migration applied on staging clean

---

## Phase G — Cache Namespace + Invalidation (`TASK-COH-V2-CACHING-007`)

### G.1 TDD test list

| Test ID | File | Asserts |
|---|---|---|
| TS-UA-COH-CACHE-001 | `apps/api/tests/coherence/test_cache_keys.py` (new) | `key(namespace="dashboard", version="coherence-v1", tenant_id=T, project_id=P)` returns `f"coherence:coherence-v1:dashboard:{T}:{P}"` |
| TS-UA-COH-CACHE-002 | same | suffix appended correctly; unknown namespace raises |
| TS-CI-COH-CACHE-001 | `apps/api/tests/ci/test_no_adhoc_coherence_keys.py` (new) | Greps `apps/api/src/**` for `f"coherence:` outside `cache_keys.py` — must find 0 matches |
| TS-INT-COH-CACHE-FLIP-001 | `apps/api/tests/integration/coherence/test_flag_toggle_cache_invalidation.py` (new) | Flip flag for tenant T → `UNLINK coherence:*:*:T:*` executed; subsequent request recomputes |
| TS-INT-COH-CACHE-INVAL-001 | same file | New `CoherenceResult` for project P, tenant T → only T's keys invalidated, other tenants untouched |

### G.2 Implementation outline

| File | Change |
|---|---|
| `apps/api/src/coherence/cache_keys.py` (new) | Sole producer of cache keys; `key()` function as per spec §6 |
| `apps/api/src/coherence/cache_invalidation.py` (new) | Event handler `on_flag_flip`, `on_result_persisted`, `on_deploy` |
| `apps/api/src/coherence/router.py` (multiple sites) | Replace inline `f"coherence:..."` (audit grep first; if none, the system uses higher-level helpers — confirm) |
| `apps/api/src/core/cache.py` (or similar) | Wire event subscriptions |
| `apps/api/scripts/invalidate_coherence_cache.py` (new) | One-shot purge via `SCAN + UNLINK coherence:*`; safe to run multiple times |
| CI: ruff custom rule OR `.github/workflows/lint.yml` grep step | Ban `f"coherence:` in `apps/api/src/` outside `cache_keys.py` |

### G.3 Code-reviewer checklist

- [ ] All cache reads/writes go through `cache_keys.key()`
- [ ] `UNLINK` (non-blocking) used, not `DEL`
- [ ] Telemetry: `coherence.cache_invalidated` emitted with counts
- [ ] Invalidation handler is idempotent
- [ ] One-shot purge script has dry-run mode

### G.4 Acceptance

- [ ] 5 tests GREEN
- [ ] CI ban check enforced
- [ ] Staging dry-run of purge script logs key count and exits clean

---

---

## Phase D — Operational Canary Playbook

### D.5 Per-tenant flag management

**SQL (direct DB — emergency use only):**
```sql
-- Enable v2 for a specific tenant
UPDATE tenants
SET settings = jsonb_set(
    COALESCE(settings, '{}'),
    '{feature_flags,coherence_v2_enabled}',
    'true'
)
WHERE id = '<UUID>';

-- Disable v2 for a specific tenant (rollback)
UPDATE tenants
SET settings = jsonb_set(
    COALESCE(settings, '{}'),
    '{feature_flags,coherence_v2_enabled}',
    'false'
)
WHERE id = '<UUID>';

-- Verify current flag state for all tenants
SELECT id, settings->'feature_flags'->'coherence_v2_enabled' AS v2_flag
FROM tenants
ORDER BY id;
```

**API (preferred — triggers cache invalidation automatically):**
If a settings endpoint exists for the tenant admin surface, prefer that path
because `TenantFlagsService.set_flag` automatically invalidates the coherence
cache via `cache_invalidation.on_flag_flip` after commit.

### D.6 Canary rollout stages

Flip the `coherence_v2_enabled` flag one cohort at a time.  Allow ≥24 hours
between stages to collect shadow delta data.

| Day | Action | Scope |
|-----|--------|-------|
| D+0 | Enable v2 for internal / test tenants | ~5 tenants |
| D+1 | Review `coherence.shadow.delta` + `coherence.v1_v2_score_delta` logs; MAE ≤ 15 required to proceed | — |
| D+2 | Enable v2 for 10% of production tenants | 10% |
| D+3 | Review MAE; if ≤ 15, expand to 50% | 50% |
| D+5 | Full rollout — enable for all tenants | 100% |
| D+7 | Post-rollout review; if MAE ≤ 5 over 7 days → mark Shadow MAE gate green | — |

### D.7 Shadow MAE threshold

The shadow MAE guard requires **MAE ≤ 15** before expanding past 10% of tenants,
and **MAE ≤ 5** before declaring GA.

Assess from structlog events:

```
# coherence.shadow.delta   — emitted by ShadowRunner.emit() (stdlib logger)
# coherence.v1_v2_score_delta — emitted by ShadowRunner.emit() (structlog, Phase D)
```

Query your log aggregator (e.g. Datadog / CloudWatch Logs Insights):

```
fields delta_abs
| filter event = "coherence.v1_v2_score_delta"
| stats avg(delta_abs) as mae by bin(1h)
| sort by @timestamp desc
```

A MAE value > 15 means v2 calibration is off — stop expanding, investigate
`missing_categories` and `conflicting_categories` distributions in the events.

### D.8 Rollback procedure

1. Flip `coherence_v2_enabled` back to `false` for affected tenants (SQL above or API).
2. `TenantFlagsService.set_flag` automatically calls `cache_invalidation.on_flag_flip`
   which UNLINKs all `coherence:*:{tenant_id}:*` keys — no manual cache flush needed.
3. Verify rollback in logs: `coherence.cache_invalidated trigger=flag_flip keys_unlinked=N`.
4. Monitor `coherence.v1_v2_score_delta` — events should cease within 1 minute.
5. If cache invalidation hook failed (log: `coherence.flag_changed.cache_invalidation_failed`),
   run the Phase G one-shot purge script manually:
   ```bash
   python apps/api/scripts/purge_coherence_cache.py --dry-run  # verify count
   python apps/api/scripts/purge_coherence_cache.py             # execute
   ```

---

## Agent Dispatch Matrix

| Step | Agent | Model | Phase(s) |
|---|---|---|---|
| Backlog writes | (Haiku writer) | Haiku | A-G (after this plan lands) |
| Write tests RED | tdd-guide | Sonnet | A, B, C, D, F, G |
| Implement | (main session) | Sonnet | A, B, C, D, F, G |
| Frontend impl | (main session) | Sonnet | C, F (web slice) |
| Alembic migration | (main session) | Sonnet | F |
| Code review | code-reviewer | Sonnet | every PR before merge |
| Security review | security-reviewer | Sonnet | D (tenant flag), G (cache) |
| Build error fix | build-error-resolver | Sonnet | as needed |
| E2E | e2e-runner | Sonnet | C (Playwright) |
| Refactor cleanup | refactor-cleaner | Sonnet | after F (remove legacy values) |
| Docs | doc-updater | Haiku | E |
| ADR rename audit (D.0) | (read-only investigation) | Sonnet | D.0 |

---

## Estimated PR Sequence

| # | Branch | Phases bundled | Tests added | Reviewers required |
|---|---|---|---|---|
| 1 | `fix/coherence-v1-active-weight-guard` | A + B | ~14 unit + 1 int | code-reviewer |
| 2 | `feat/coherence-frontend-null-safe` | C | ~6 unit + 1 e2e | code-reviewer |
| 3 | `feat/coherence-score-version-canonical` | F | ~3 + 1 migration | code-reviewer + security-reviewer |
| 4 | `feat/coherence-cache-namespacing` | G | ~5 | code-reviewer + security-reviewer |
| 5 | `docs/coherence-adr-009-accepted` | E | none | doc-updater |
| 6 | `feat/coherence-v2-authoritative-canary` | D.0 audit only | n/a | architect sign-off |
| 7 | `feat/coherence-v2-authoritative` | D.1+ | ~6 + 1 int | code-reviewer + security-reviewer + architect |

**No pushes to `main`.** PR + CR mandatory per project rules.

---

## Cross-Phase Acceptance Gate

Before declaring ECOA v2 cutover done:

- [ ] User's original repro returns `null` with `score_reason="insufficient_active_weight"` on **both** v1 and v2 paths
- [ ] No `?? 0` / `|| 0` on coherence score paths in web
- [ ] `score_version` is `"coherence-v1"` or `"coherence-v2"` in every response, every export, every cache key
- [ ] Shadow MAE ≤ 5 over 7 days before any GA flip
- [ ] ADR-009 status = Accepted, file rename complete
- [ ] All 7 backlog tasks marked `[x]` in `C2PRO_MASTER_BACKLOG.md` (Haiku-written)
- [ ] No new task-specific .md files outside `backlogs/` and `blackboard/`
