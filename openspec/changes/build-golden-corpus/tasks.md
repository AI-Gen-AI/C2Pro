# Tasks: Build 15-Bundle Golden Corpus

## Phase 1 — Infrastructure

- [x] 1.1 Create `evals/golden_corpus/` directory layout (`bundles/`, `schema.py`, `manifest.yaml`).
- [x] 1.2 Define Pydantic bundle schema with dimension, severity, and rule-id validators.
- [x] 1.3 Define manifest schema and loader (YAML).

## Phase 2 — Implementation

- [x] 2.1 Author 15 bundle JSON files (`BUNDLE-001`..`BUNDLE-015`) matching the coverage matrix in `design.md`.
- [x] 2.2 Extend `evals/run_evals.py` with:
    - [x] 2.2.1 A `--corpus` flag that loads manifest + bundles from `evals/golden_corpus/`.
    - [x] 2.2.2 A `--ci` flag that disables interactive prompts and emits JSON + JUnit XML.
    - [x] 2.2.3 Deterministic assertions per bundle (schema validity, issue count match, dimension coverage).
    - [x] 2.2.4 Exit code 0 on all-pass, 1 on failures, 2 on load/config errors.
- [x] 2.3 Add `evals/golden_corpus/manifest.yaml` referencing all 15 bundles.

## Phase 3 — Testing

- [x] 3.1 Add `tests/evals/test_golden_corpus.py`:
    - [x] 3.1.1 `test_manifest_lists_exactly_15_bundles`.
    - [x] 3.1.2 `test_every_manifest_entry_has_a_bundle_file`.
    - [x] 3.1.3 `test_every_bundle_validates_against_schema`.
    - [x] 3.1.4 `test_all_six_dimensions_are_covered_across_corpus`.
    - [x] 3.1.5 `test_bundle_ids_are_sequential_and_unique`.
    - [x] 3.1.6 `test_run_evals_ci_mode_exits_zero_on_clean_corpus`.

## Phase 4 — CI Wiring

- [x] 4.1 Add `.github/workflows/golden-corpus-evals.yml`:
    - [x] 4.1.1 Trigger on `push` to `main`/`develop` and `pull_request`.
    - [x] 4.1.2 Set up Python 3.11, install `pyyaml` and `pydantic`.
    - [x] 4.1.3 Run `python evals/run_evals.py --corpus --ci --output evals/results/`.
    - [x] 4.1.4 Upload `evals/results/corpus_results.json` and `corpus_results.xml` as artifacts.
    - [x] 4.1.5 Fail the job on non-zero exit.

## Phase 5 — Verification & Documentation

- [x] 5.1 Update `C2PRO_MASTER_BACKLOG.md` with TASK-EVAL-015 entry and Change Log line.
- [x] 5.2 Produce `verify-report.md` covering artifact presence, scenario coverage, rules compliance, overall verdict.
- [x] 5.3 Commit and push on branch `claude/build-golden-corpus-clJDX`.
