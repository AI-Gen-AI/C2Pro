# Golden Corpus Specification

## Purpose

Define a deterministic, CI-runnable 15-bundle golden corpus that seeds top-level evaluation of C2Pro's tridimensional audit (Contract + Schedule + Budget) and guards against Agent Drift.

## Requirements

### Requirement: Fixed Corpus Size

The corpus MUST contain exactly 15 bundles identified `BUNDLE-001` through `BUNDLE-015`.

#### Scenario: Corpus size is exactly 15

- GIVEN `evals/golden_corpus/manifest.yaml` and `evals/golden_corpus/bundles/`
- WHEN the loader enumerates bundles
- THEN the total SHALL be exactly 15 and every ID SHALL match `^BUNDLE-0(0[1-9]|1[0-5])$`

#### Scenario: Missing bundle fails verification

- GIVEN one of the 15 bundle files is absent
- WHEN `python evals/run_evals.py --corpus --ci` runs
- THEN the process MUST exit with code 2 and print the missing bundle ID

### Requirement: Dimension Coverage

The corpus MUST collectively cover all 6 coherence dimensions (Legal, Quality, Scope, Schedule, Cost, Technical) with at least one bundle per dimension.

#### Scenario: All dimensions present

- GIVEN the 15 bundles are loaded
- WHEN dimensions are aggregated across `bundle.dimensions`
- THEN the union SHALL equal `{Legal, Quality, Scope, Schedule, Cost, Technical}`

#### Scenario: Cross-dimensional bundles exist

- GIVEN the 15 bundles are loaded
- WHEN multi-dimensional bundles are counted
- THEN at least 4 bundles SHALL declare `len(dimensions) >= 2`

### Requirement: Bundle Schema Validity

Every bundle JSON file MUST validate against `evals/golden_corpus/schema.py::Bundle`.

#### Scenario: Valid bundle passes

- GIVEN a bundle with contract + schedule + budget documents and ≥1 expected issue
- WHEN `Bundle.model_validate` is invoked
- THEN validation SHALL succeed with no errors

#### Scenario: Missing document type fails

- GIVEN a bundle lacking either a `contract`, `schedule`, or `budget` document
- WHEN validation runs
- THEN a ValidationError MUST be raised and the bundle MUST be reported as failing

#### Scenario: Expected issue with malformed rule_id fails

- GIVEN an expected issue with `rule_id` not matching `^[A-Z]{2,10}-\d{1,4}$`
- WHEN validation runs
- THEN the bundle MUST be rejected

### Requirement: Non-Interactive CI Mode

`evals/run_evals.py` MUST provide a `--corpus --ci` mode that runs without human input and produces machine-readable output.

#### Scenario: CI mode runs without stdin

- GIVEN no attached TTY
- WHEN `python evals/run_evals.py --corpus --ci --output evals/results/` is invoked
- THEN the command SHALL complete without blocking on input and SHALL write `corpus_results.json` and `corpus_results.xml`

#### Scenario: Exit code reflects outcome

- GIVEN the corpus
- WHEN the run completes
- THEN the exit code SHALL be 0 if every bundle passed, 1 if any bundle failed assertions, and 2 if the manifest or any bundle could not be loaded

### Requirement: Synthetic-Only Content

Every bundle MUST declare `synthetic: true` and MUST NOT reference real project paths, PDFs, or XLSX files.

#### Scenario: All bundles are synthetic

- GIVEN the 15 bundles
- WHEN each is inspected
- THEN `bundle.synthetic` SHALL be `true` for every bundle

#### Scenario: Bundle referencing real file fails review

- GIVEN a bundle whose document `synthetic_text` is empty and whose title references a real project code
- WHEN the manifest validator runs
- THEN the bundle MUST be rejected

### Requirement: CI Wiring

The repository MUST include a GitHub Actions workflow that runs the corpus on `push` and `pull_request`.

#### Scenario: Workflow triggers on push and PR

- GIVEN `.github/workflows/golden-corpus-evals.yml`
- WHEN a commit is pushed or a PR is opened
- THEN the workflow SHALL execute the corpus run job

#### Scenario: Results are uploaded as artifacts

- GIVEN the corpus job completes
- WHEN the workflow reaches its final step
- THEN `corpus_results.json` and `corpus_results.xml` SHALL be uploaded via `actions/upload-artifact@v4`

### Requirement: Minimum Assertion Density

To prevent trivial-pass CI, the corpus MUST declare at least 20 expected issues across all 15 bundles.

#### Scenario: Aggregate expected-issue count

- GIVEN the 15 bundles
- WHEN expected issues are summed
- THEN the total SHALL be greater than or equal to 20

#### Scenario: No bundle is empty

- GIVEN any bundle
- WHEN its `expected_issues` list is inspected
- THEN its length SHALL be greater than or equal to 1
