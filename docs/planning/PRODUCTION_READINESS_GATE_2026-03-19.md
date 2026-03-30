# C2Pro Production Readiness Gate

Date: `2026-03-19`
Status: `OPEN`
Owner: `Senior Staff Architect / Engineering Leadership`
Purpose: Convert the engineering backlog into an executive-quality release gate so the team can distinguish feature completion from true production readiness.

---

## Governance Note

This document defines production-readiness gates and approval expectations.

It is not the canonical task register. Any open implementation or follow-up items derived from these gates must be tracked in `C2PRO_MASTER_BACKLOG.md`.

---

## Executive Position

`C2PRO_MASTER_BACKLOG.md` is now the primary engineering delivery backlog for known work.

It is not, by itself, sufficient evidence that C2Pro is production-ready.

Production readiness requires both:

1. `Engineering delivery complete` — backlog items implemented and verified.
2. `Operational release gates approved` — security, infra, QA, data, observability, and release controls explicitly signed off.

This document defines those gates.

---

## Gap Audit Against Current Master Backlog

The current master backlog is strong on implementation work, especially around:

- migration authority and DB reconciliation
- fake-data elimination
- frontend real-data correctness
- CI/security hygiene
- targeted backend/runtime fixes

The current master backlog is still light or incomplete in these production categories:

### Missing or underrepresented gate categories

- `Release governance`
  - go/no-go checklist
  - approval owners
  - rollback/cutover plan
- `Operational readiness`
  - on-call expectations
  - incident escalation
  - service ownership matrix
- `Observability and SLOs`
  - service-level indicators/objectives
  - production alert coverage
  - dashboard ownership
- `Performance and capacity`
  - throughput targets
  - queue/worker saturation validation
  - DB/query performance thresholds
- `Security operations`
  - secrets rotation policy
  - dependency/vulnerability scanning beyond gitleaks
  - permission/access review
- `Data protection and resilience`
  - restore test evidence
  - disaster recovery verification
  - retention/deletion workflows
- `Deployment readiness`
  - staging parity criteria
  - promotion flow from main to staging to production
  - runtime config verification
- `Quality certification`
  - exact suites required for release
  - minimum pass thresholds
  - UAT/manual QA signoff
- `AI/LLM governance`
  - model/version traceability
  - cost guardrail verification
  - fallback behavior acceptance
  - accuracy baseline thresholds

These gaps do not invalidate the master backlog. They show that one more governance layer is required before calling the product production-ready.

---

## Gate Structure

Each gate must be in one of four states:

- `[ ]` Not started
- `[-]` In progress
- `[x]` Complete
- `[!]` Risk accepted temporarily with explicit approval

Release approval requires:

- no `P0` engineering items open
- no gate marked `[ ]` in Gate 1-6
- any `[!]` exception documented with owner, expiration date, and mitigation

---

## Gate 1: Product and Data Integrity

Objective: The product must use real persisted data on production paths and preserve correctness across refreshes, restarts, and analysis updates.

- [x] `G1-01` Eliminate fake project runtime state. Source: `B-1`, `REM-CHECK-2`
- [x] `G1-02` Eliminate fake alerts runtime state. Source: `B-2`, `REM-CHECK-3`
- [x] `G1-03` Derive dashboard coherence from persisted analysis/coherence data. Source: `B-4`, `REM-CHECK-4`
- [x] `G1-04` Replace synthetic MCP completions with real execution. Source: `B-6`, `REM-CHECK-5`
- [x] `G1-05` Ensure evidence/document rendering uses real files and extracted entities in production mode. Source: `C-7`, `REM-CHECK-10`
- [x] `G1-06` Complete remaining real-data remediation acceptance criteria. Source: `REM-CHECK-COMPLETION`

Approval evidence:

- tenant-safe CRUD verification
- refresh/restart persistence verification
- manual QA proving no fake data on authenticated production paths

---

## Gate 2: Security and Tenant Isolation

Objective: Authentication, authorization, RLS, secrets handling, and sensitive-data controls must be production-safe.

- [x] `G2-01` Mirror SQL RLS cleanup and duplicate index normalization into Alembic. Source: `A-1`, `DB-REC-P3-01`
- [x] `G2-02` Deploy auth bootstrap function surface to approved runtime. Source: `A-2`, `DB-REC-P0-06`
- [x] `G2-03` Add CI secrets scanning with gitleaks. Source: `A-5`, `AUDIT-TASK-3.4`
- [x] `G2-04` Harden PII anonymization dependency strategy. Source: `A-8`, `AUDIT-S1`
- [x] `G2-05` Audit and tighten CORS by environment. Source: `A-9`, `AUDIT-S3`
- [x] `G2-06` Implement API key validation for integration traffic. Source: `A-10`, `CODE-TODO-SEC-APIKEY`
- [x] `G2-07` Add final review for alert mutation authorization rules. Source: `B-10`, `CODE-TODO-ALERTS-AUTH`

Approval evidence:

- green tenant-isolation/security suites
- documented authN/authZ model
- no unaudited bypasses in production paths

---

## Gate 3: Database, Migration, and Schema Authority

Objective: The schema authority must be singular, replayable, and safe for rollout.

- [x] `G3-01` Deduplicate SQL initializers. Source: `A-6`, `DB-REC-P3-02`
- [x] `G3-02` Archive legacy Supabase SQL runner path. Source: `A-3`, `DB-REC-P3-03`
- [x] `G3-03` Re-enable deferred ORM/FK model integration safely. Source: `B-7`, `CODE-TODO-DB-MODELS`
- [x] `G3-04` Complete Supabase bootstrap/security checklist validation. Source: `A-15`, `RUNBOOK-SUPABASE-CHECKLIST`
- [x] `G3-05` Verify runtime/test isolation guardrails for DB usage. Source: `A-12`, `A-13`, `REM-CHECK-6.15.1`, `REM-CHECK-6.15.2`

Approval evidence:

- deterministic bootstrap path documented
- forward migration authority uncontested
- restore/rebuild tests proven on scratch/staging environments

---

## Gate 4: Platform, Infrastructure, and Deployability

Objective: The system must be deployable, observable, and operable under controlled release practices.

- [x] `G4-01` Add worker health endpoint for parsing queue. Source: `A-4`, `AUDIT-TASK-3.2`
- [x] `G4-02` Establish merge-to-main deployment automation for backend and frontend. Source: `A-7`, `AUDIT-TASK-3.5`
- [x] `G4-03` Move MCP operational controls from in-memory handling to production persistence where required. Source: `A-11`, `CODE-TODO-MCP-RATE`
- [x] `G4-04` Wire Sentry lifecycle fully into app startup/shutdown. Source: `A-14`, `CODE-TODO-SENTRY`
- [x] `G4-05` Define release promotion, rollback, and environment signoff workflow. Source: `LEAD-GAP-RELEASE-GOVERNANCE`
- [x] `G4-06` Define operational ownership, escalation, and on-call expectations. Source: `LEAD-GAP-OPS-READINESS`

Approval evidence:

- deployment runbook
- rollback test record
- monitoring/alerting ownership
- healthy staging promotion flow

---

## Gate 5: Frontend Production Behavior and UX Safety

Objective: The frontend must use one consistent transport strategy, fail closed in production, and clearly isolate demo behavior.

- [x] `G5-01` Finish proxy-first API routing consistency across all clients. Source: `C-1`, `REM-CHECK-11`, `REM-CHECK-7.1`
- [x] `G5-02` Ensure dashboard auth-aware loading path is correct. Source: `C-2`, `DB-REC-P3-05`
- [x] `G5-03` Replace OpenAPI stub with real backend-generated schema. Source: `C-3`, `REM-CHECK-6.14.1`
- [x] `G5-04` Add unmistakable demo mode labeling. Source: `C-4`, `REM-CHECK-7.3`
- [x] `G5-05` Make PDF/document viewer fail closed in production. Source: `C-5`, `REM-CHECK-7.2`, `REM-CHECK-13`
- [x] `G5-06` Remove ambiguous auth-failure redirect/fallback behavior. Source: `C-8`, `REM-CHECK-12`
- [x] `G5-07` Complete document/entity highlight mapping. Source: `C-11`, `CODE-TODO-WEB-HIGHLIGHTS`
- [x] `G5-08` Wire viewer UI actions to real backend endpoints. Source: `C-12`, `WIREFRAME-CE-S2-010`
- [x] `G5-09` Complete highlight search verification. Source: `C-13`, `WIREFRAME-HIGHLIGHT-SEARCH`

Approval evidence:

- real-browser QA on protected routes
- no demo-only fallback on production paths
- explicit error states for missing or unauthorized resources

---

## Gate 6: AI/LLM Reliability and Evaluation

Objective: The AI pipeline must be stateful, measurable, traceable, and safe to operate.

- [x] `G6-01` Verify LangGraph checkpointer persistence in Postgres. Source: `B-3`, `AUDIT-TASK-3.1`
- [x] `G6-02` Build a golden dataset baseline for accuracy regression. Source: `B-5`, `AUDIT-TASK-3.3`
- [x] `G6-03` Add node-level execution progress streaming for users. Source: `C-6`, `AUDIT-TASK-3.6` (UI Implemented)
- [x] `G6-04` Replace hardcoded pricing with `model_router` pricing source of truth. Source: `B-9`, `CODE-TODO-LLM-PRICING`
- [x] `G6-05` Improve coherence alert grouping quality. Source: `B-8`, `CODE-TODO-COHERENCE-ALERTS`
- [x] `G6-06` Verify the legacy document adapter retirement assumption and close it if the adapters are still active runtime code. Source: `B-12`, `CODE-TODO-LEGACY-DOC-ADAPTERS`. Evidence: `docs/G6-06_LEGACY_ADAPTERS_RETIREMENT_PLAN.md`

Approval evidence:

- persisted orchestration state across transitions
- defined evaluation baseline
- verified cost controls and fallback behavior

---

## Gate 7: Verification, QA, and Release Certification

Objective: Production readiness must be proven through explicit verification, not inferred from code completion.

Canonical certification bundle:

- Release bundle root: `evidence/releases/<release-id>/`
- Promotion workflow: `.github/workflows/deploy-production.yml`
- Required bundle files:
  - `manifest.yaml`
  - `signoff.md`
  - `performance.md`
  - `disaster-recovery.md`

Required automated suite matrix for Gate 7:

- Backend validation: `.github/workflows/tests.yml`
- Frontend validation: `.github/workflows/frontend-ci.yml`
- Security validation: `.github/workflows/e2e-security-tests.yml`
- Evaluation regression: `.github/workflows/evaluation-regression.yml`
- Reliability validation: `.github/workflows/i13-real-e2e-scheduled.yml` via release-time dispatch for the candidate SHA

- [x] `G7-01` Execute active Swagger/API contract workbook against the live intended runtime behavior. Source: `B-11`, `SWAGGER-WB-01`
- [x] `G7-02` Define minimum required automated suite set for release signoff. Source: `LEAD-GAP-QUALITY-GATE`
- [x] `G7-03` Define UAT/manual QA signoff checklist for product, security, and operations. Source: `LEAD-GAP-UAT`. Evidence: `docs/UAT_CHECKLIST.md`
- [x] `G7-04` Record performance/capacity acceptance targets for API, DB, queue, and worker layers. Source: `LEAD-GAP-PERF`. Evidence: `docs/SLA_TARGETS.md`
- [x] `G7-05` Record backup/restore and DR verification evidence. Source: `LEAD-GAP-DR`

Approval evidence:

- signed release checklist
- green required test matrix
- manual certification records using `docs/UAT_CHECKLIST.md`
- capacity and restore evidence attached
- repository-backed release bundle present under `evidence/releases/<release-id>/` (sample rehearsal available at `evidence/releases/2026-03-23-rc1/`)
- TODO: keep `.github/workflows/deploy-production.yml` undispatched during rehearsals until the project is explicitly cleared for production-gated validation

---

## Release Decision Rule

The system may be presented as `production-ready` only when:

- all `P0` items in the master backlog are `[x]`
- Gate 1 through Gate 6 contain no `[ ]`
- Gate 7 has explicit signoff artifacts attached
- the Gate 7 release bundle is complete and matches the candidate commit SHA
- any temporary exception is recorded as `[!]` with:
  - owner
  - risk statement
  - mitigation
  - expiration date

Until then, the correct executive language is:

`Production hardening in progress; not yet certified production-ready.`

---

## Strict Execution Sequence

This is the recommended execution order across the open backlog and the production gates.

Principles:

1. `P0` first — no production claim is credible while top-risk fake-data or transport-authority items remain open.
2. `Gate-critical P1` second — close the highest-risk security, data, deployment, and verification blockers.
3. `Release certification` third — prove readiness through evidence and signoff.

### Wave 0 — Open P0 blockers

1. `C-1 / G5-01` Finish any remaining proxy-first API routing inconsistencies across frontend clients and dashboard paths.

Exit criteria:

- no `P0` rows remain open in the master backlog
- authenticated production paths no longer rely on fake project/alert state
- frontend transport path is consistent and tenant-safe

### Wave 1 — Gate-critical P1: Security and schema safety

5. `A-12 + A-13 / G3-05` Add runtime/test isolation guardrails.

### Wave 2 — Gate-critical P1: Platform and deployability

11. `A-7 / G4-02` Establish merge-to-main deployment automation.

### Wave 3 — Gate-critical P1: Frontend production safety

14. `C-7 / G1-05` Ensure real evidence/document rendering in production mode.
15. `C-8 / G5-06` Remove ambiguous auth-failure redirects/fallbacks.
16. `C-9 / G5-03/G5-04 path support` Isolate Orval/MSW mock output from production builds.
17. `C-10 / G5-03` Automate frontend client sync against real OpenAPI.

### Wave 4 — Gate-critical P1: AI and runtime integrity

18. `B-3 / G6-01` Verify LangGraph checkpointer persistence.
19. `B-6 / G1-04` Replace synthetic MCP completions with real execution.

### Wave 5 — P2 quality, enablement, and long-tail hardening

20. `B-5 / G6-02` Build golden dataset baseline.
21. `B-8 / G6-05` Improve coherence alert grouping quality.
22. `B-11 / G7-01` Complete Swagger/API workbook verification.
23. `B-12 / G6-06` Verify document adapter retirement assumptions before any deletion work.
24. `C-11 / G5-07` Finish document highlight mapping.
25. `C-12 / G5-08` Wire viewer actions to backend endpoints.
26. `C-13 / G5-09` Finish highlight search verification.

### Wave 6 — Release certification and executive signoff

29. `G4-05` Define release promotion, rollback, and environment signoff workflow.
30. `G4-06` Define operational ownership, escalation, and on-call expectations.
31. `G7-02` Define the minimum automated suite required for release signoff.
32. `G7-03` Define UAT/manual QA signoff checklist.
33. `G7-04` Record performance/capacity acceptance targets.
34. `G7-05` Record backup/restore and disaster recovery evidence.

---

## Owner-Based Delivery Plan

### Sprint 1 — Clear production blockers

`Team Alpha / Sentinel`

- security verification support for Bravo runtime changes

`Team Bravo / Nexus`

- persisted-data validation support

`Team Charlie / Prism`

- `C-1` close remaining proxy-first inconsistencies
- support Bravo validation flows against real frontend paths

Sprint 1 outcome:

- remaining open `P0` items reduced to transport/dashboard consistency only
- Gate 1 and Gate 2 materially de-risked

### Sprint 2 — Harden deployability and real production behavior

`Team Alpha / Sentinel` (codex)

- `A-7` CD pipeline automation
- `A-12` runtime/test env guardrail
- `A-13` seeded identity isolation

`Team Bravo / Nexus`(Claude)

- `B-3` LangGraph checkpointer verification
- `B-6` real MCP execution

`Team Charlie / Prism`(gemini)

- `C-7` real evidence rendering
- `C-8` frontend auth failure clarity
- `C-9` Orval mock isolation
- `C-10` Orval CI sync

Sprint 2 outcome:

- Gate 3, Gate 4, and Gate 5 major blockers reduced
- real production path confidence significantly improved

### Sprint 3 — Quality, AI governance, and certification evidence

`Team Alpha / Sentinel`

- lead documentation for release workflow and operating ownership (`G4-05`, `G4-06`)

`Team Bravo / Nexus`

- `B-5` golden dataset baseline
- `B-8` coherence alert grouping
- `B-11` Swagger/API verification sweep
- `B-12` document adapter retirement review

`Team Charlie / Prism`

- `C-11` highlight mapping
- `C-12` viewer backend integration
- `C-13` highlight search verification

Sprint 3 outcome:

- Gates 5 through 7 have the evidence needed for final signoff

---

## Go / No-Go Dashboard

Current recommendation: `NO-GO`

Reason:

- open `P0` backlog items remain
- Gate 1 is open on core real-data integrity
- Gate 2 is open on security hardening
- Gate 3 is open on schema/runtime guardrails
- Gate 4 is open on deployability and operations governance
- Gate 5 is open on frontend production-safe behavior
- Gate 6 is open on AI persistence/evaluation controls
- Gate 7 now has a repo-backed certification bundle and promotion contract, but live Swagger execution and final approval evidence remain open

### Current production blockers

`Red blockers`

- `C-1` frontend transport/proxy consistency still tracked as open
- `B-3` LangGraph persistence verification not yet complete
- `A-7` deployment automation not yet complete

`Amber blockers`

- PII dependency hardening and CORS audit
- runtime/test DB guardrails
- real evidence rendering and auth failure clarity on the frontend
- OpenAPI/Orval contract discipline
- golden dataset and verification sweeps

### Minimum conditions to move from `NO-GO` to `CONDITIONAL GO`

- all open `P0` items closed
- Gate 1 and Gate 2 materially complete
- deployment path defined and tested in staging
- release rollback owner named and documented
- required automated suites defined and green

### Conditions for final `GO`

- Gate 1 through Gate 6 complete
- Gate 7 evidence attached and approved
- no unresolved critical security or data-integrity exceptions

---

## Mapping Index to Master Backlog

Primary execution backlog:

- `docs/planning/MASTER_ORCHESTRATION_BACKLOG_2026-03-19.md`

Primary production certification overlay:

- `docs/planning/PRODUCTION_READINESS_GATE_2026-03-19.md`

Leadership snapshot:

- `docs/planning/EXECUTIVE_STATUS_REPORT_2026-03-19.md`

Operating rule:

- Engineering teams execute against the master backlog.
- Leadership reviews release readiness against this gate document.
- A task can be coded complete but still blocked from release if its gate evidence is incomplete.
