# PHASE 5 — Evaluator Registry Expansion to 18 — REPORT

Task: `TASK-COH-V1-05`  
Branch observed: `coh-v1/consolidation`  
PR title: `feat(coherence): expand evaluator registry to 18 (12 det + 6 LLM)`

## Summary

Implemented the Coherence Score v1 evaluator registry as a fixed 18-entry set:

- 12 deterministic evaluators: 2 per C2Pro category.
- 6 LLM-backed evaluators: 1 per C2Pro category, built from YAML rules and routed through `LLMRulePort`.
- `scoring_arbiter` consumes the same `FindingSignal` output shape; graph evaluator nodes now source their evaluators from `rules_engine.registry`.
- Every v1 `rule_id` has entries in `RULE_TITLES`, `RULE_SEVERITIES`, and `TEMPLATES`.
- Registry startup now fails fast if a v1 `rule_id` is orphaned from alert template metadata.

Note: the brief contains an arithmetic conflict: it asks for both `12 deterministic + 6 LLM = 18` and `3 deterministic + 1 LLM × 6 = 24`. I implemented the PRD/acceptance target of 18 entries.

## Coverage Table

| Category | Deterministic Count | LLM Count | FP Rate Golden Corpus | FN Rate Golden Corpus |
|---|---:|---:|---|---|
| SCOPE | 2 | 1 | TBD — Phase 7 corpus extension not landed | TBD — Phase 7 corpus extension not landed |
| BUDGET | 2 | 1 | TBD — Phase 7 corpus extension not landed | TBD — Phase 7 corpus extension not landed |
| TIME | 2 | 1 | TBD — Phase 7 corpus extension not landed | TBD — Phase 7 corpus extension not landed |
| TECHNICAL | 2 | 1 | TBD — Phase 7 corpus extension not landed | TBD — Phase 7 corpus extension not landed |
| LEGAL | 2 | 1 | TBD — Phase 7 corpus extension not landed | TBD — Phase 7 corpus extension not landed |
| QUALITY | 2 | 1 | TBD — Phase 7 corpus extension not landed | TBD — Phase 7 corpus extension not landed |

## V1 Rule IDs

| Category | Deterministic Rule IDs | LLM Rule ID |
|---|---|---|
| SCOPE | `DET-SCP-DELIVERABLES`, `DET-CRS-SCPBUD` | `R-SCOPE-CLARITY-01` |
| BUDGET | `DET-BUD-OVERRUN`, `DET-BUD-LINEITEM` | `R-PAYMENT-CLARITY-01` |
| TIME | `DET-TIM-STATUS`, `DET-TIM-DURATION` | `R-SCHEDULE-CLARITY-01` |
| TECHNICAL | `DET-TEC-SPEC`, `DET-TEC-BOMBUDGET` | `R-TECHNICAL-SPEC-CLARITY-01` |
| LEGAL | `DET-LEG-PENALTY`, `DET-LEG-NOTICE` | `R-RESPONSIBILITY-01` |
| QUALITY | `DET-QUA-STANDARD`, `DET-QUA-INSPECT` | `R-QUALITY-STANDARDS-01` |

## Sample FindingSignal By Category

| Category | Sample |
|---|---|
| SCOPE | `rule_id='DET-SCP-DELIVERABLES', source='deterministic', severity='medium', impact_score=0.40` |
| BUDGET | `rule_id='DET-BUD-OVERRUN', source='deterministic', severity='high', impact_score>0.60` |
| TIME | `rule_id='DET-TIM-DURATION', source='deterministic', severity='critical', impact_score=0.90` |
| TECHNICAL | `rule_id='DET-TEC-SPEC', source='deterministic', severity='medium', impact_score=0.45` |
| LEGAL | `rule_id='DET-LEG-PENALTY', source='deterministic', severity='high', impact_score=0.80` |
| QUALITY | `rule_id='DET-QUA-INSPECT', source='deterministic', severity='medium', impact_score=0.54` |

LLM signal shape is covered by tests with a fake `LLMRulePort`: `source='llm'`, `severity='high'`, `impact_score=0.62`, `confidence=0.88`, and category mapped from YAML category.

## Verification

RED:

```text
apps/api/tests/unit/coherence/rules_engine/test_registry_v1.py
22 failed as expected with missing registry API:
AttributeError: module 'src.coherence.rules_engine.registry' has no attribute 'list_evaluators'
```

GREEN:

```text
cd apps/api
pytest tests/unit/coherence/rules_engine/ -xvs
22 passed in 1.51s
```

No `core.ai` imports in rules engine:

```text
rg -n "from core\.ai|from src\.core\.ai|import core\.ai|import src\.core\.ai" apps/api/src/coherence/rules_engine
0 matches
```

Registry startup/import check:

```text
python -c "from src.coherence.rules_engine.registry import list_evaluators, assert_v1_rule_ids_have_alert_templates; evaluators = list_evaluators(); assert_v1_rule_ids_have_alert_templates(evaluators=evaluators); print(len(evaluators))"
18
```

Integration:

```text
cd apps/api
pytest tests/integration/coherence/ -xvs
BLOCKED: PostgreSQL test database unavailable at postgresql://postgres:postgres@postgres-test:5432/c2pro_test
Original error: [Errno 11001] getaddrinfo failed
```

App import/startup:

```text
python -c "import src.main"
BLOCKED before app startup by existing LangGraph package mismatch:
ImportError: cannot import name 'interrupt' from 'langgraph.types'
```

Mypy:

```text
cd apps/api
mypy src/coherence
FAILED: broad existing type debt remains in coherence and transitive imports.
Latest scoped rerun reported 253 errors in 35 files, including pre-existing deterministic evaluator numeric narrowing, alert DTO call shapes, graph literal typing, and transitive core/procurement typing issues.
```

## Diff Stat

```text
apps/api/src/coherence/alert_generator.py                  |  72 +++++++
apps/api/src/coherence/graph/nodes.py                      |  44 ++--
apps/api/src/coherence/qualitative_rules.yaml              |  30 +++
apps/api/src/coherence/rules_engine/__init__.py            |   5 +
apps/api/src/coherence/rules_engine/llm_evaluator.py       | 132 +++---------
apps/api/src/coherence/rules_engine/registry.py            | 226 +++++++++++++++++++--
apps/api/tests/unit/coherence/rules_engine/test_registry_v1.py | 224 ++++++++++++++++++++
blackboard/coh-v1/PHASE-5-opencode-REPORT.md              | new
C2PRO_MASTER_BACKLOG.md                                    | updated
blackboard.json                                            | updated
```

