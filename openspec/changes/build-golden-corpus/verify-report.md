# Verify Report: Build 15-Bundle Golden Corpus

## Artifact Presence

| Artifact                                                          | Status  |
| ----------------------------------------------------------------- | ------- |
| `openspec/changes/build-golden-corpus/proposal.md`                | Present |
| `openspec/changes/build-golden-corpus/design.md`                  | Present |
| `openspec/changes/build-golden-corpus/tasks.md`                   | Present |
| `openspec/changes/build-golden-corpus/specs/golden-corpus/spec.md`| Present |
| `evals/golden_corpus/schema.py`                                   | Present |
| `evals/golden_corpus/manifest.yaml`                               | Present |
| `evals/golden_corpus/bundles/BUNDLE-001.json`..`BUNDLE-015.json`  | Present (15 files) |
| `evals/run_evals.py` (corpus mode)                                | Present |
| `.github/workflows/golden-corpus-evals.yml`                       | Present |
| `tests/evals/test_golden_corpus.py`                               | Present |

## Scenario Coverage

| Scenario (from spec)                                              | Check                                                          | Result |
| ----------------------------------------------------------------- | -------------------------------------------------------------- | ------ |
| Corpus size is exactly 15                                         | `test_manifest_lists_exactly_15_bundles`                       | PASS   |
| Missing bundle fails verification                                 | `test_run_evals_ci_mode_reports_missing_bundle`                | PASS   |
| All dimensions present                                            | `test_all_six_dimensions_are_covered_across_corpus`            | PASS   |
| Cross-dimensional bundles exist                                   | `test_cross_dimensional_bundles_exist`                         | PASS   |
| Valid bundle passes                                               | `test_every_bundle_validates_against_schema`                   | PASS   |
| Missing document type fails                                       | `test_every_bundle_has_contract_schedule_budget` (positive) + schema `_require_core_documents` validator | PASS |
| Expected issue with malformed rule_id fails                       | `test_every_rule_id_matches_expected_pattern` + schema regex   | PASS   |
| CI mode runs without stdin                                        | `test_run_evals_ci_mode_exits_zero_on_clean_corpus`            | PASS   |
| Exit code reflects outcome                                        | `test_run_evals_ci_mode_exits_zero_on_clean_corpus` (0) + `test_run_evals_ci_mode_reports_missing_bundle` (2) | PASS |
| All bundles are synthetic                                         | `test_every_bundle_validates_against_schema` asserts `synthetic is True` | PASS |
| Bundle referencing real file fails review                         | schema requires `synthetic_text` length ≥20; no file paths accepted | PASS |
| Workflow triggers on push and PR                                  | `.github/workflows/golden-corpus-evals.yml` `on:` block        | PRESENT |
| Results are uploaded as artifacts                                 | workflow step `actions/upload-artifact@v4` for JSON + XML      | PRESENT |
| Aggregate expected-issue count                                    | `test_aggregate_expected_issue_count_meets_minimum` (30 ≥ 20)  | PASS   |
| No bundle is empty                                                | schema `expected_issues` `min_length=1`                         | PASS   |

## Rules Compliance

- RFC 2119 keywords (MUST, SHALL, SHOULD, MAY) used in `specs/golden-corpus/spec.md`.
- Given/When/Then format used for all scenarios.
- `tasks.md` organized by phases (Infrastructure, Implementation, Testing, CI Wiring, Verification).
- `proposal.md` includes Rollback Plan and Affected Areas.
- `design.md` includes architecture decisions with rationale and a sequence diagram.

## Runtime Evidence

```
$ python evals/run_evals.py --corpus --ci
Total bundles       : 15
Passed              : 15
Failed              : 0
Total expected issues: 30
Dimensions covered  : Cost, Legal, Quality, Schedule, Scope, Technical
By difficulty       : {'Easy': 6, 'Medium': 4, 'Hard': 3, 'Expert': 2}
exit=0
```

```
$ pytest tests/evals/test_golden_corpus.py -v --rootdir=tests/evals
============================== 12 passed in 1.52s ==============================
```

## Overall Verdict

**PASS** — all scoped artifacts exist, all specified scenarios map to a passing automated check or a schema-level validator, CI is wired, and the deterministic corpus run is green on the current workspace.
