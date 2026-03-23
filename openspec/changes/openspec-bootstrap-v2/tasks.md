# Tasks: OpenSpec Bootstrap v2

## Phase 1: Foundation / Contracts

- [x] 1.1 Update `openspec/config.yaml` `rules.verify` to define docs-only verification scope, required report sections, and runtime-drift escalation behavior.
- [x] 1.2 Create `scripts/verify_openspec_change.py` CLI skeleton (`--change`, exit codes `0/1/2`) and central dataclasses for input/report contracts.
- [x] 1.3 Add root `package.json` script `verify:openspec` that calls the verifier with pass-through args.
- [x] 1.4 Add optional proxy command in `apps/web/package.json` forwarding to the root `verify:openspec` script.

## Phase 2: Core Verification Implementation

- [x] 2.1 Implement artifact presence checks in `scripts/verify_openspec_change.py` for `proposal.md`, `design.md`, `tasks.md`, and `specs/*/spec.md` under `openspec/changes/{change}`.
- [x] 2.2 Implement runtime-drift detection in `scripts/verify_openspec_change.py` to classify non-OpenSpec edits and return exit code `2` with required full-gates message.
- [x] 2.3 Implement scenario parser in `scripts/verify_openspec_change.py` to extract Requirement/Scenario blocks and build scenario-to-check mapping IDs.
- [x] 2.4 Implement rules-compliance checks in `scripts/verify_openspec_change.py` for RFC 2119 requirement wording and Given/When/Then scenario format.
- [x] 2.5 Implement deterministic markdown report generation in `scripts/verify_openspec_change.py` with artifact presence, scenario coverage, rules compliance, and overall verdict.

## Phase 3: Test-First Verification

- [x] 3.1 Add unit tests in `tests/unit/scripts/test_verify_openspec_change.py` for scenario parsing, RFC 2119 checks, Given/When/Then validation, and runtime-file classification (RED -> GREEN).
- [x] 3.2 Add integration tests in `tests/integration/openspec/test_verify_openspec_change_integration.py` using fixture change folders for compliant, missing-mapping, and rule-violation cases.
- [x] 3.3 Add determinism test in `tests/integration/openspec/test_verify_openspec_change_determinism.py` asserting stable matrix keys and verdict across repeated runs.
- [x] 3.4 Add command-path test in `tests/integration/openspec/test_verify_openspec_command.py` validating script invocation and exit code contract `0/1/2`.

## Phase 4: Adoption / Handoff

- [x] 4.1 Add reviewer usage notes to `openspec/changes/openspec-bootstrap-v2/design.md` with command examples and interpretation of each exit code.
- [x] 4.2 Run `npm run verify:openspec -- --change openspec-bootstrap-v2` and capture pass/fail evidence in `openspec/changes/openspec-bootstrap-v2/tasks.md` completion notes.
- [x] 4.3 Confirm `openspec-bootstrap-v2/specs/openspec/spec.md` scenarios each reference an implemented check path and mark the change ready for `sdd-apply`.

## Completion Notes

- Verification command evidence: `npm run verify:openspec -- --change openspec-bootstrap-v2` completed with exit code `0` and generated `openspec/changes/openspec-bootstrap-v2/verify-report.md`.
- Scenario-to-check traceability evidence: `verify-report.md` includes deterministic `SCN-*` entries for all eight scenarios declared in `specs/openspec/spec.md`.
- Change readiness: All planned Foundation, Core, Test-First, and Adoption tasks are complete; change is ready for `sdd-verify`.
