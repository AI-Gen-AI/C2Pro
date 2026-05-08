# SESSION 2026-04-21 — Backlog Audit & Epic Restructure

**Mode**: Autonomous Principal-Architect audit
**Scope**: C2PRO_MASTER_BACKLOG.md + 9 category backlogs
**Output**: Restructured Manifest v3 (Epic-Based) injected into master backlog

---

## 1. Decision Log — Merges / Prunes

### [STATUS: WONT DO] — Pruned
| Task ID | Justification (single sentence) |
| ------- | ------------------------------- |
| `TASK-AI-038` | Duplicate of completed `TASK-INF-006`; MCP `{service}_mcp` naming convention already documented. |
| `TASK-BCK-040` | Superseded by `TASK-QA-072` Phase 1 completion — Ruff debt reduced 2692→82; remainder tracked in QA-072, no net-new scope. |
| `TASK-BCK-041` | Superseded by completed `TASK-ARCH-002` + `TASK-LINT-002`; the 235-hit ARG002 audit confirmed 0 security bugs, remediation already shipped. |
| `TASK-QA-100` | Orphan row — no specification in QA_QUALITY_ASSURANCE.md; appears only as an ID in status-view. |
| `TASK-QA-101` | Orphan row — no specification in QA_QUALITY_ASSURANCE.md; appears only as an ID in status-view. |
| `TASK-INF-049` | Duplicate of completed `TASK-DDD-004` execution lane for documents hexagonal refactor. |
| `TASK-INF-050` | Duplicate of completed `TASK-DDD-005` execution lane for stakeholders hexagonal refactor. |
| `TASK-INF-051` | Duplicate of completed `TASK-DDD-006` execution lane for procurement hexagonal refactor. |
| `TASK-AI-039` | Duplicate of `TASK-INF-007`/`TASK-FRT-123` — prompt-template validator already shipped @2026-04-09. |
| `TASK-INF-007` | Duplicate of `TASK-FRT-123` — completed @2026-04-09. |
| `TASK-FRT-091` | Master already reflects `[x]` @2026-04-06; detail file drift only. |

### [MERGED INTO EPIC] — Consolidated
| Merged Tasks | Into Epic | Rationale |
| ------------ | --------- | --------- |
| `TASK-AI-041`, `TASK-INF-009`, `TASK-FRT-125` | `EPIC-LC-WORKFLOWS` | Three silos for the same Procurement Plan LangChain flow. |
| `TASK-AI-042`, `TASK-INF-010`, `TASK-FRT-126` | `EPIC-LC-WORKFLOWS` | Three silos for the same RACI LangChain flow. |
| `TASK-AI-043`, `TASK-INF-011`, `TASK-FRT-127` | `EPIC-LC-WORKFLOWS` | Three silos for the same Stakeholder Resolution flow. |
| `TASK-AI-040`, `TASK-INF-008` | `EPIC-LC-WORKFLOWS` | Multi-language prompts belong to the workflows deliverable. |
| `TASK-AI-044`, `TASK-INF-012` | `EPIC-LANGSMITH-PHASE-2` | `ai_usage_logs` writes are an instrumentation sub-task under tracing. |
| `TASK-AI-045`, `TASK-INF-013` | `EPIC-LANGSMITH-ROLLOUT` | A/B framework needs Hub + rollout stage — belongs to Phase 2/6. |
| `TASK-AI-046`, `TASK-INF-014` | `EPIC-LANGSMITH-ANALYTICS` | Optimization hints are a read-side of the analytics endpoints. |
| `TASK-AI-047`, `TASK-INF-015` | `EPIC-AI-CACHE` | Flash/cache layer is orthogonal to LangSmith — own epic. |
| `TASK-AI-048..051`, `TASK-INF-016..019`, `TASK-FRT-132..135` | `EPIC-COVERAGE-GATES` | 12 copy-paste coverage tasks across three silos → one deliverable. |
| `TASK-BCK-032`, `TASK-BCK-033` | `EPIC-HITL-OBSERVABILITY` | Both are HITL-resume instrumentation follow-ups from TASK-BCK-024. |
| `TASK-BCK-043`, `TASK-BCK-044`, `TASK-QA-077`, `TASK-1480`, `TASK-QA-074` | `EPIC-TEST-STABILIZATION` | All timing/flakiness/misplacement bugs in the test suite. |
| `TASK-AI-027..029` | `EPIC-LANGSMITH-VALIDATION` | Unit + integration + E2E tests for LangSmith form one validation gate. |
| `TASK-AI-030..034` | `EPIC-LANGSMITH-ROLLOUT` | Load/deploy/rollout/docs/monitoring = Phase-6 rollout bundle. |
| `TASK-QA-028`, `TASK-QA-034`, `TASK-QA-050..064`, `TASK-QA-069`, `TASK-QA-070`, `TASK-QA-084..095` | `EPIC-QA-CONTRACT-COVERAGE` | Contract/wireframe/quality-gate backlog needs reformation as one planned deliverable; current specs are stubs. |
| `TASK-DDD-004`, `TASK-DDD-005`, `TASK-DDD-006` | `EPIC-DDD-MIGRATION` | Three in-progress DDD refactors with the same pattern → single epic, finish together. |
| `TASK-IMPL-010.3..010.16` | `EPIC-CORE-DECOUPLE` | Already a well-structured 14-subtask decomposition; promoted to top-level epic. |

### [INJECTED — Major Refactor] — New Epics Created
| New Epic | Trigger | Reason |
| -------- | ------- | ------ |
| `EPIC-TENANT-RLS-HARDENING` | SEC_SECURITY.md pending P0 items + `TASK-FRT-045` blocked credential rotation | Multi-tenant security is foundational — feature work on leaky base is unacceptable. RLS for `clause_embeddings` is the single remaining P0 compliance gap per Gate 1. |
| `EPIC-CORE-DECOUPLE` | `TASK-IMPL-010` is CORE P0 with 14 open subtasks | LangGraph nodes own business logic; feature layer depends on this. Blocks HITL-observability + Workflows. |
| `EPIC-DDD-MIGRATION` | `TASK-DDD-004/005/006` all "in progress" on same hexagonal pattern | LangChain workflows (`EPIC-LC-WORKFLOWS`) layer onto procurement/stakeholders; completing DDD first is architecturally mandatory. |

---

## 2. Dependency Graph (verified acyclic)

```
TIER 0 (foundation):
  EPIC-TENANT-RLS-HARDENING  ──┐
  EPIC-CORE-DECOUPLE ──────────┤
                               ▼
TIER 1 (refactor):
  EPIC-DDD-MIGRATION ──────────┐
                               ▼
TIER 2 (build-on-refactor):
  EPIC-LANGSMITH-PHASE-1 ──────┐
    └─► EPIC-LANGSMITH-PHASE-2 ┤
    └─► EPIC-LANGSMITH-ANALYTICS
    └─► EPIC-LANGSMITH-VALIDATION
    └─► EPIC-LANGSMITH-ROLLOUT
  EPIC-LC-WORKFLOWS ───────────┤
  EPIC-HITL-OBSERVABILITY ─────┤
  EPIC-DLQ-ADMIN ──────────────┤
                               ▼
TIER 3 (debt/stabilization):
  EPIC-TEST-STABILIZATION
  EPIC-QA-CONTRACT-COVERAGE
  EPIC-COVERAGE-GATES
  EPIC-SENTRY-PERF
  EPIC-AI-CACHE
  TASK-1481 (Supervisor API keys)
```

No circular dependencies. Simulated execution order: Tier 0 → 1 → 2 → 3 converges deterministically.

---

## 3. Files Touched in This Audit
- `C2PRO_MASTER_BACKLOG.md` — injected §Restructured Manifest v3, updated Change Log, stamped WONT-DO on pruned tasks.
- `blackboard/SESSION_2026-04-21_backlog_audit.md` — this file.

No task-specific standalone `.md` created (complies with `.claude/rules/DOCUMENTATION_STRUCTURE.md`).
