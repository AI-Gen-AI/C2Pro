# Design: 15-Bundle Golden Corpus

## Architecture Decisions

### ADR-1: Keep `evals/` Self-Contained

**Decision.** The top-level `evals/` harness MUST NOT import from `apps/api`. The bundle schema lives at `evals/golden_corpus/schema.py` and is a deliberate, narrower mirror of `apps/api/src/golden/schemas.py`.

**Rationale.** `evals/run_evals.py` is executed from the repo root and is the single entrypoint the CI job invokes. Forcing CI to install `apps/api/requirements.txt` to run a handful of deterministic JSON assertions adds minutes to every push. The two schemas share the same vocabulary (dimensions, severities, rule-id prefix pattern), so drift is bounded.

**Trade-off.** A small amount of duplication — roughly 80 lines — in exchange for fast CI and clear module boundaries.

### ADR-2: Deterministic Offline Run in CI

**Decision.** The `--ci` mode executes zero LLM calls and only verifies structural + expected-issue properties of each bundle against its declared manifest entry.

**Rationale.** The purpose of this corpus is to prevent regressions in the corpus itself (missing fields, malformed rule IDs, dimension mismatches) and to provide a seed dataset for downstream runners. End-to-end LLM evaluation already exists in `.github/workflows/evaluation-regression.yml` against `apps/api/src/golden/`.

### ADR-3: Exactly 15 Bundles, Frozen Count

**Decision.** The corpus is sized at exactly 15 bundles. The pytest regression test asserts `len(bundles) == 15`.

**Rationale.** The count is fixed by the product requirement ("15-bundle golden corpus"). Growing the corpus is a deliberate, separately-scoped change that MUST update this spec and the backlog.

### ADR-4: Coverage Matrix

Bundles are distributed so every coherence dimension is represented and cross-dimensional cases are exercised:

| Bundle ID    | Primary Dimension(s)     | Difficulty | Notes                                       |
| ------------ | ------------------------ | ---------- | ------------------------------------------- |
| BUNDLE-001   | Schedule                 | Easy       | Milestone date mismatch                     |
| BUNDLE-002   | Cost                     | Easy       | Budget line overrun                         |
| BUNDLE-003   | Legal                    | Easy       | Missing liability clause                    |
| BUNDLE-004   | Quality                  | Easy       | QA plan missing acceptance criteria         |
| BUNDLE-005   | Scope                    | Easy       | Deliverable absent from schedule            |
| BUNDLE-006   | Technical                | Easy       | Spec mismatch between drawings and contract |
| BUNDLE-007   | Schedule + Cost          | Medium     | Payment milestone drift                     |
| BUNDLE-008   | Legal + Quality          | Medium     | Warranty vs. QA clause inconsistency        |
| BUNDLE-009   | Scope + Technical        | Medium     | Scope of works omits BIM deliverable        |
| BUNDLE-010   | Cost + Technical         | Medium     | Unpriced technical scope item               |
| BUNDLE-011   | Schedule + Legal         | Hard       | Force-majeure clause contradicts baseline   |
| BUNDLE-012   | Schedule + Cost + Scope  | Hard       | Tri-dimensional cascade                     |
| BUNDLE-013   | Quality + Technical      | Hard       | Acceptance criteria vs. test protocol gap   |
| BUNDLE-014   | All 6 dimensions         | Expert     | Cross-cutting EPC incoherence               |
| BUNDLE-015   | Legal + Cost + Technical | Expert     | Indemnity vs. LD cap mismatch               |

## Sequence: CI Run

```
GitHub Actions (push/PR)
        │
        ▼
 checkout + setup-python
        │
        ▼
 pip install pyyaml pydantic
        │
        ▼
 python evals/run_evals.py --corpus --ci --output evals/results/
        │
        ├── load manifest.yaml
        ├── for each bundle_id:
        │      └── load bundles/{bundle_id}.json
        │          └── validate schema
        │          └── assert issues match manifest row
        │
        ▼
 emit corpus_results.json + corpus_results.xml
        │
        ▼
 upload-artifact + job status
```

## Data Model

```python
# evals/golden_corpus/schema.py  (sketch)

class BundleDocument(BaseModel):
    kind: Literal["contract", "schedule", "budget", "specifications", "drawings"]
    title: str
    synthetic_text: str          # inline synthetic payload; no external file refs
    language: Literal["es", "en"] = "es"

class ExpectedIssue(BaseModel):
    rule_id: str                 # pattern: ^[A-Z]{2,10}-\d{1,4}$
    dimension: Literal["Legal", "Quality", "Scope", "Schedule", "Cost", "Technical"]
    severity: Literal["high", "medium", "low"]
    description_contains: str

class Bundle(BaseModel):
    bundle_id: str               # pattern: ^BUNDLE-\d{3}$
    name: str
    dimensions: list[Dimension]  # non-empty, deduplicated
    difficulty: Literal["Easy", "Medium", "Hard", "Expert"]
    synthetic: Literal[True]     # MUST be true — no real project data
    documents: list[BundleDocument]    # min 3 (contract, schedule, budget)
    expected_issues: list[ExpectedIssue]  # min 1
    metadata: dict[str, Any] | None
```

The manifest is:

```yaml
# evals/golden_corpus/manifest.yaml
version: 1
total_bundles: 15
bundles:
  - id: BUNDLE-001
    dimensions: [Schedule]
    difficulty: Easy
    expected_issue_count: 1
  # ... 14 more
```

## Non-Goals

- No change to the LangGraph workflow executor.
- No change to `apps/api/src/golden/` cases.
- No synthetic PDF/XLSX generation — bundles inline plain-text payloads.
