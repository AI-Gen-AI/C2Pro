# Proposal: Build 15-Bundle Golden Corpus and Wire Into evals/run_evals.py

## Intent

Create a deterministic, version-controlled golden corpus of **15 tridimensional audit bundles** (Contract + Schedule + Budget) paired with expected coherence findings, and wire it into `evals/run_evals.py` so the top-level eval harness can run in CI without human interaction and detect Agent Drift on every push.

## Scope

### In Scope

- Add 15 bundle fixtures under `evals/golden_corpus/bundles/*.json` spanning the 6 coherence dimensions (Legal, Quality, Scope, Schedule, Cost, Technical) and cross-dimensional (MULTI) cases.
- Add a corpus manifest (`evals/golden_corpus/manifest.yaml`) that declares bundle IDs, dimensions, difficulty, and expected issue counts for each bundle.
- Extend `evals/run_evals.py` with a non-interactive "corpus" execution path that loads the 15 bundles, runs deterministic assertions (structural + expected-issue match), and writes a CI-consumable JSON + JUnit XML report.
- Add a GitHub Actions workflow (`.github/workflows/golden-corpus-evals.yml`) that invokes the corpus run on push/PR.
- Add a pytest regression test (`tests/evals/test_golden_corpus.py`) that validates manifest integrity and bundle schema.
- Reflect the task in `C2PRO_MASTER_BACKLOG.md`.

### Out of Scope

- Replacing or migrating the existing `apps/api/src/golden/` dataset used by the LangGraph workflow runner. That dataset stays; this corpus is the lighter, top-level harness driven from `evals/`.
- Connecting the top-level harness to real LLM calls. The CI run MUST be offline and deterministic.
- Building the UI or API to browse the corpus.

## Approach

1. Design a small, frozen Pydantic-style schema for a "bundle" that captures contract/schedule/budget text payloads, metadata, and expected coherence issues — independent of `apps/api/src/golden/schemas.py` because `evals/` is outside the `apps/api` package and MUST NOT import from it.
2. Author 15 bundles (`BUNDLE-001` through `BUNDLE-015`) that each cover at least one coherence dimension and collectively span all 6 + cross-dimensional cases.
3. Add a deterministic evaluator in `evals/run_evals.py` that:
   - Loads the manifest and all bundle JSON files.
   - Validates each bundle against the schema.
   - For each bundle, verifies that `expected_issues[*].rule_id` and `dimension` match the declared set and that counts match.
   - Emits JSON + JUnit XML.
4. Add a CI job that runs `python evals/run_evals.py --corpus --ci` and uploads artifacts.
5. Add pytest tests that lock in the schema and count of 15 bundles.

## Affected Areas

| Area                                                  | Impact   | Description                                               |
| ----------------------------------------------------- | -------- | --------------------------------------------------------- |
| `evals/run_evals.py`                                  | Modified | Adds `--corpus` / `--ci` modes, JSON + JUnit emission     |
| `evals/golden_corpus/bundles/*.json`                  | New      | 15 bundle fixtures                                        |
| `evals/golden_corpus/manifest.yaml`                   | New      | Bundle manifest                                           |
| `evals/golden_corpus/schema.py`                       | New      | Local Pydantic schema for bundles                         |
| `.github/workflows/golden-corpus-evals.yml`           | New      | CI workflow that runs the corpus on push/PR               |
| `tests/evals/test_golden_corpus.py`                   | New      | Regression test for manifest/bundle integrity             |
| `C2PRO_MASTER_BACKLOG.md`                             | Modified | Adds TASK-EVAL-015 entry and updates Change Log           |

## Risks

| Risk                                                        | Likelihood | Mitigation                                                                  |
| ----------------------------------------------------------- | ---------- | --------------------------------------------------------------------------- |
| Corpus drifts from the `apps/api/src/golden/` taxonomy      | Med        | Reuse the same dimension/severity vocabulary; cross-reference in the spec   |
| CI job becomes a silent pass because assertions are trivial | Med        | Require ≥1 expected issue per bundle and total ≥20 issues across 15 bundles |
| JSON bundles accidentally include PII or real project data  | Low        | All bundles are synthetic; manifest marks `synthetic: true`                 |
| `evals/` imports from `apps/api` and breaks top-level run   | Med        | Keep `evals/` self-contained; test importable without `apps/api` on PYTHONPATH |

## Rollback Plan

1. Delete `evals/golden_corpus/`, `.github/workflows/golden-corpus-evals.yml`, and `tests/evals/test_golden_corpus.py`.
2. Revert `evals/run_evals.py` to the previous single-mode interactive runner.
3. Remove the TASK-EVAL-015 entry from `C2PRO_MASTER_BACKLOG.md`.

No database or runtime dependencies are introduced, so rollback is pure file deletion.
