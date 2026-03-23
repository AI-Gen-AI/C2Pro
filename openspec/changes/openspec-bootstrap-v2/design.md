# Design: OpenSpec Bootstrap v2

## Technical Approach

Implement a docs-first verification workflow that validates OpenSpec change artifacts without invoking product runtime suites. The flow adds a deterministic compliance runner that reads `openspec/config.yaml`, inspects `openspec/changes/{change-name}` contents, detects runtime-code drift, and emits a stable markdown report. This maps directly to the proposal (lightweight verify path + traceability + report) and the spec requirements for process-only execution, scenario mapping, rule compliance, and deterministic conclusions.

## Architecture Decisions

| Option                                                                                      | Tradeoff                                                                                                               | Decision                                                                          |
| ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Validate via reusable script (`scripts/verify_openspec_change.py`) vs manual checklist only | Script adds small maintenance cost but gives repeatability and objective pass/fail output                              | Use script-backed verification as default; keep manual checklist as fallback      |
| Verify command at workspace root vs app-local command only                                  | Root command is easier for process artifacts outside `apps/web`; app-local command aligns with current reviewer habits | Add root command and optional proxy script in `apps/web/package.json`             |
| Rule checks via hardcoded logic vs config-driven checks from `openspec/config.yaml`         | Hardcoding is faster initially but drifts from governance rules                                                        | Read and enforce rules from `openspec/config.yaml` to keep policy source-of-truth |

Rationale: The failed `openspec-bootstrap` verification showed full-suite coupling and untested scenarios. A small config-driven verifier gives reliable process validation while preserving existing product gates for runtime changes.

## Data Flow

```text
Reviewer -> npm run verify:openspec -- --change <name>
             |
             v
      verify_openspec_change.py
             |
   +---------+---------+
   |                   |
artifact scanner   rule validator (config.yaml)
   |                   |
runtime-drift check    scenario/check mapping
   +---------+---------+
             |
             v
      verify-report.md + exit code
```

Sequence (complex flow):

```text
Reviewer      CLI command      Verifier Script      change/spec docs      config.yaml
   |               |                 |                     |                  |
   | run command   |                 |                     |                  |
   |-------------->| invoke script   |                     |                  |
   |               |---------------->| parse inputs        |                  |
   |               |                 |-------------------->| read scenarios   |
   |               |                 |--------------------------------------->| read rules
   |               |                 | runtime drift scan  |                  |
   |               |                 | build matrix+verdict|                  |
   |               |<----------------| report path+status  |                  |
   |<--------------| print summary   |                     |                  |
```

## File Changes

| File                                               | Action                  | Description                                                           |
| -------------------------------------------------- | ----------------------- | --------------------------------------------------------------------- |
| `scripts/verify_openspec_change.py`                | Create                  | Deterministic compliance verifier for process-only OpenSpec changes   |
| `openspec/changes/openspec-bootstrap-v2/design.md` | Create                  | Technical design for v2 workflow                                      |
| `openspec/changes/openspec-bootstrap-v2/tasks.md`  | Create                  | Phased implementation and verification checklist                      |
| `openspec/config.yaml`                             | Modify                  | Clarify `rules.verify` for docs-only scope and expected report fields |
| `package.json`                                     | Modify                  | Add root `verify:openspec` command                                    |
| `apps/web/package.json`                            | Modify (optional proxy) | Add convenience command that forwards to root verifier                |

## Interfaces / Contracts

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class VerifyInput:
    change_name: str
    change_path: str

@dataclass(frozen=True)
class ScenarioCheckResult:
    requirement: str
    scenario: str
    check_id: str
    status: str  # PASS | FAIL | NA
    evidence: str

@dataclass(frozen=True)
class VerifyReport:
    artifact_presence: list[str]
    runtime_scope: str  # PROCESS_ONLY | RUNTIME_DETECTED
    scenario_coverage: list[ScenarioCheckResult]
    rules_compliance: list[str]
    verdict: str  # PASS | FAIL
```

CLI contract:

- `npm run verify:openspec -- --change openspec-bootstrap-v2`
- Exit code `0` when compliant process-only checks pass.
- Exit code `1` when rule/scenario/artifact checks fail.
- Exit code `2` when runtime-code modifications are detected and full gates are required.

## Testing Strategy

| Layer       | What to Test                                                                                  | Approach                                                                           |
| ----------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Unit        | Scenario extraction, RFC 2119 detection, Given/When/Then parsing, runtime-file classification | `pytest` for pure functions in verifier script module                              |
| Integration | End-to-end verifier behavior on fixture change folders                                        | `pytest` fixture directories under `openspec/changes/*` and temp copies            |
| E2E         | Reviewer command path and report determinism                                                  | Run verify command twice on same inputs and assert identical verdict + matrix keys |

## Migration / Rollout

No data migration required. Rollout steps:

1. Land verifier script and command entry points.
2. Use v2 verifier for process-only OpenSpec changes.
3. Keep full product suites mandatory when runtime drift is detected.
4. Document adoption in `openspec-bootstrap-v2/tasks.md` and reviewer notes.

## Reviewer Usage Notes

Primary command:

- `npm run verify:openspec -- --change openspec-bootstrap-v2`
- Optional proxy from web app workspace: `npm --prefix apps/web run verify:openspec -- --change openspec-bootstrap-v2`

Exit code interpretation:

- `0`: Process-only compliance checks passed (artifact presence, scenario coverage, rules compliance).
- `1`: Non-compliant docs verification (missing required artifacts, scenario mapping gaps, or rule violations).
- `2`: Runtime drift detected; full backend/frontend verification gates remain mandatory.

Reviewer evidence checklist:

1. Confirm `openspec/changes/openspec-bootstrap-v2/verify-report.md` exists.
2. Validate report sections: Artifact Presence, Scenario Coverage, Rules Compliance, Overall Verdict.
3. If exit code is `2`, treat docs-only verification as informational and run full product suites.

## Open Questions

- [ ] Should CI auto-run `verify:openspec` only when files under `openspec/changes/**` are touched?
- [ ] Should the verifier produce JSON in addition to markdown for future dashboarding?
