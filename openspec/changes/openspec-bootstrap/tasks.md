# Tasks: OpenSpec Bootstrap

## Phase 1: Foundation

- [x] 1.1 Confirm bootstrap folder contract in `openspec/changes/openspec-bootstrap/` includes `proposal.md`, `design.md`, and `specs/openspec/spec.md`; note any gaps before editing.
- [x] 1.2 Create `openspec/changes/openspec-bootstrap/tasks.md` with phased, hierarchical checklist format required by `openspec/config.yaml`.
- [x] 1.3 Add a short reviewer validation checklist section to `openspec/changes/openspec-bootstrap/design.md` that maps checks to required artifacts and rules.

## Phase 2: Core Implementation

- [x] 2.1 Review `openspec/changes/openspec-bootstrap/specs/openspec/spec.md` and ensure each requirement uses RFC 2119 terms (MUST/SHALL/SHOULD/MAY).
- [x] 2.2 Normalize every scenario in `openspec/changes/openspec-bootstrap/specs/openspec/spec.md` to explicit GIVEN/WHEN/THEN bullets when wording is ambiguous.
- [x] 2.3 Align `openspec/changes/openspec-bootstrap/design.md` file-change table and rollout steps with the finalized artifact set (including `tasks.md`).

## Phase 3: Testing and Verification

- [x] 3.1 Perform a structure check in `openspec/changes/openspec-bootstrap/` and verify required files exist: `proposal.md`, `design.md`, `tasks.md`, and `specs/openspec/spec.md`.
- [x] 3.2 Execute a manual rules review against `openspec/config.yaml` for proposal/spec/design/tasks sections and record pass/fail notes in the change discussion.
- [x] 3.3 Dry-run a follow-up change scaffold under `openspec/changes/` and verify contributors can place proposal/spec/tasks artifacts without path ambiguity.

## Phase 4: Cleanup and Handoff

- [x] 4.1 Update any wording in `openspec/changes/openspec-bootstrap/proposal.md` success criteria that no longer matches the final artifact set.
- [x] 4.2 Add a completion note to this file by checking finished items and confirming bootstrap is ready for `sdd-apply` execution.

## Verification Notes

- Structure check: PASS (`proposal.md`, `design.md`, `tasks.md`, `specs/openspec/spec.md` all present in `openspec/changes/openspec-bootstrap/`).
- Rules review: PASS for proposal/spec/design/tasks against `openspec/config.yaml` sections (`proposal`, `specs`, `design`, `tasks`).
- Follow-up scaffold dry-run: PASS using `openspec/changes/<new-change>/` with `proposal.md`, `specs/<domain>/spec.md`, and `tasks.md`; no path ambiguity observed.

## Completion

All bootstrap tasks are complete. `openspec-bootstrap` is ready for `sdd-verify`.
