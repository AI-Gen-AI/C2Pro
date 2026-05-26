# Changelog

All notable changes to C2Pro are tracked here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the repo uses Conventional Commits.

## [Unreleased]

### EPIC-ECOA-V2-HOTFIX-AND-CUTOVER — Coherence Score™ v2 hotfix and cutover

Trademark-critical fix for ADR-009 §1 P1 + §14 violations in the v1 coherence engine. Bug repro: `POST /api/v1/coherence/evaluate/diagnostics` on a 2-document SCOPE-only project returned `overall_score=15` (a `mean × coverage_ratio` collapse forbidden by ADR-009 §1 P1) instead of `null` + `score_reason="insufficient_active_weight"`.

#### Added

- ADR-009 §14 active-weight guard in `apps/api/src/coherence/scoring.py:_calculate_detailed_with_coverage`. When the sum of weights of assessed categories falls below `MIN_ACTIVE_WEIGHT (0.35)`, the engine returns `score=None` with `reason="insufficient_active_weight"` instead of collapsing to a low integer. Mirrors the v2 implementation in `services/v2/aggregator_v2.py`.
- Frontend "Pending evidence" empty state per ADR-009 §18. Null `coherence_score` and null per-category sub-scores render as neutral `—` / `Pending`, never as `0` or red.
- CI guard step in `.github/workflows/frontend-ci.yml` ("Coherence score-path null-fallback guard") that fails the build if `?? 0` or `|| 0` appears on coherence score paths in `apps/web/components/coherence/**` or `apps/web/lib/api/contracts.ts`. `weights_used` fallbacks are exempted.
- New backend tests: 16 across `apps/api/tests/coherence/test_scoring_min_active_weight.py`, `test_router_score_reason_propagation.py`, `test_enriched_overall_score_nullable.py`, `test_v1_to_v2_adapter_phase_b.py`, and `apps/api/tests/integration/coherence/test_diagnostics_partial_coverage.py`.
- New frontend tests: 4 null-safe regression tests in `apps/web/components/coherence/DashboardClient.test.tsx` (sort ordering, BreakdownChart NaN-free, PDF `—`, XLS String `—`).
- `docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md` (spec) and `docs/superpowers/plans/2026-05-25-ecoa-v2-hotfix-and-cutover.md` (plan).
- 7 backlog entries (`TASK-COH-V2-HOTFIX-001` through `-CUTOVER-004`) in `C2PRO_MASTER_BACKLOG.md` Tier 4 + Pending by Category, with inline detail in `backlogs/BCK_BACKEND.md` §2.
- `TASK-BCK-077` follow-up ticket for pre-existing test infra failures surfaced during review (LangGraph tracer `KeyError: 'parent'`, `test_scoring_v3.py` ScoringResult/float comparison, partial Anthropic mock bypass).

#### Changed

- v1→v2 shadow adapter (`apps/api/src/coherence/adapters/v1_to_v2.py`) rewrote its partial-coverage branch. Previously it hardcoded `active_weight=1.0` and echoed v1's possibly-buggy `coherence_score` into `categories_v2`. Now it iterates canonical `DEFAULT_CATEGORY_WEIGHTS`, classifies null `sub_scores` as `CategoryStatus.INSUFFICIENT_EVIDENCE`, computes the real `active_weight`, and applies the §14 guard — never re-emitting v1's collapsed number.
- `apps/api/src/coherence/models.py`: `DashboardSummary.global_score`, `.coherence_score`, and `sub_scores` values widened from `int` to `float | None` so the dashboard contract carries null states honestly through the API surface. `EnrichedCoherenceResult.overall_score` already nullable.
- `apps/api/src/coherence/router.py::_normalized_sub_scores` and `_empty_sub_scores` return type widened to `dict[str, float | None]`, replacing `int(score)` with `float(score)` to preserve precision and null semantics.
- `apps/web/lib/api/contracts.ts`: `DashboardSummary.sub_scores: Record<string, number | null>`.
- `apps/web/hooks/useCountUp.ts` accepts `number | null` (null target stays null; caller renders `—`).
- `apps/web/components/coherence/ScoreCard.tsx`: null score renders neutral `Pending` badge (outline variant); ARIA label says `pending` not `0/100`; red badge is reserved for validated incoherence only.
- `apps/web/components/coherence/CategoryDetail.tsx`, `BreakdownChart.tsx`, `RadarView.tsx`: prop types accept `number | null`; chart components filter null entries from rendering.
- `apps/web/components/coherence/DashboardClient.tsx` + `CoherenceClient.tsx`: sub-category sort places nulls last (explicit guards prevent NaN coercion from `a - b`). PDF export renders `—` for null score cells. XLS export emits `<Data ss:Type="String">—</Data>` instead of coercing null to Number 0.
- `docs/api/openapi.yaml` regenerated via `make openapi` to reflect the widened nullable score fields, `score_reason` enum, and v2 categories payload.
- ADR-009 status note refreshed with a Phase A+B+C revision-history entry; `CLAUDE.md` Active Analysis Pipeline N8 row updated to describe post-fix behaviour.

#### Deferred (tracked in backlog)

- `TASK-COH-V2-VERSIONING-006` (Phase F) — canonical `score_version` enum `"coherence-v1" / "coherence-v2"` everywhere (DB, DTOs, telemetry, exports). Alembic backfill of legacy `"v0_flag_based"` and `"v1_exponential_decay"` → `"coherence-v1"`.
- `TASK-COH-V2-CACHING-007` (Phase G) — `apps/api/src/coherence/cache_keys.py` single SoT for namespaced cache keys (`coherence:v1:*` / `coherence:v2:*`), flag-flip invalidation, one-shot Phase A purge script.
- `TASK-COH-V2-CUTOVER-004` (Phase D) — make ECOA v2 authoritative behind per-tenant flag stored on `Tenant.settings` JSONB (alerts pattern). Canary 10→50→100% with shadow-MAE ≤ 15 auto-block.
- Playwright E2E spec for the partial-coverage UI flow — deferred from Phase C because the e2e environment needs separate setup; will land alongside Phase D canary instrumentation.

#### Refs

- ADR-009 — `docs/architecture/decisions/009-coherence-score-v2-evidence-aware.md`
- Spec — `docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md`
- Plan — `docs/superpowers/plans/2026-05-25-ecoa-v2-hotfix-and-cutover.md`
- PR #146 — ECOA v2 Phase 1 (compatibility) + Phase 2 (shadow mode)
