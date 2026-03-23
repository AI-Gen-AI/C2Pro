# Design: OpenSpec Bootstrap

## Technical Approach

Establish a minimal OpenSpec baseline by completing the bootstrap change folder with the missing design and tasks artifacts, and by encoding a lightweight validation workflow that reviewers can run against `openspec/config.yaml` rules. This design maps directly to the proposal approach (proposal -> specs -> design -> tasks) and the existing spec requirements for artifact completeness, RFC 2119 wording, and scenario structure.

## Architecture Decisions

| Decision                 | Options                                                                  | Tradeoffs                                                                         | Chosen                        |
| ------------------------ | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------- | ----------------------------- |
| Artifact scope           | A) Bootstrap only (`openspec-bootstrap`) B) Add templates in this change | A is smaller and lower risk; B improves onboarding but expands scope              | A                             |
| Validation mechanism     | A) Manual review checklist B) New automation script/CI job               | A is immediate and no infra work; B is stronger but adds implementation overhead  | A (now), leave B as follow-up |
| Location of process docs | A) Keep under `openspec/changes/...` B) Add root-level governance docs   | A keeps OpenSpec self-contained; B may improve visibility but duplicates guidance | A                             |

Rationale: the bootstrap objective is to create a repeatable baseline with minimal friction. Choosing the smallest viable structure reduces adoption risk while still satisfying the current spec.

## Data Flow

The bootstrap flow is documentation-first and review-driven.

```text
Author -> proposal.md -> spec.md -> design.md -> tasks.md
   |                                          |
   +--------------> Reviewer checks ----------+
                     (config.yaml rules,
                      required files,
                      scenario format)
                                  |
                                  v
                             Merge / Rework
```

Sequence diagram for the review/validation loop:

```text
Author      Change Folder        Reviewer           config.yaml
  |              |                  |                   |
  | write docs   |                  |                   |
  |------------->|                  |                   |
  |              | request review   |                   |
  |-------------------------------->|                   |
  |              |                  | read rules        |
  |              |                  |------------------>|
  |              |                  | validate artifacts|
  |              |                  |<------------------|
  | receive notes|                  |                   |
  |<--------------------------------|                   |
  | update docs  |                  |                   |
```

## File Changes

| File                                                         | Action             | Description                                                                         |
| ------------------------------------------------------------ | ------------------ | ----------------------------------------------------------------------------------- |
| `openspec/changes/openspec-bootstrap/design.md`              | Update             | Documents technical approach, decisions, validation flow, and reviewer checklist    |
| `openspec/changes/openspec-bootstrap/tasks.md`               | Update             | Defines phased, numbered implementation checklist and verification completion notes |
| `openspec/changes/openspec-bootstrap/specs/openspec/spec.md` | Modify (if needed) | Keep requirements aligned with the finalized design and task execution boundaries   |
| `openspec/changes/openspec-bootstrap/proposal.md`            | Modify (if needed) | Keep success criteria aligned with the finalized required artifact set              |

## Interfaces / Contracts

No runtime API or code interface changes are required. The contract for this change is a filesystem artifact contract:

```text
openspec/changes/openspec-bootstrap/
  proposal.md
  design.md
  tasks.md
  specs/<domain>/spec.md
```

Validation contract:

- Required files MUST exist in the bootstrap folder.
- Spec requirements SHALL include RFC 2119 keywords.
- Scenarios SHALL use GIVEN/WHEN/THEN formatting.

## Reviewer Validation Checklist

Reviewers SHOULD execute this checklist before approving the bootstrap change:

| Check                                      | Artifact(s)                                                      | Rule Source                              | Expected Result                                                         |
| ------------------------------------------ | ---------------------------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------- |
| Required files exist                       | `proposal.md`, `design.md`, `tasks.md`, `specs/openspec/spec.md` | `spec.md` bootstrap artifact requirement | Pass if all files are present in `openspec/changes/openspec-bootstrap/` |
| Tasks structure is phased and hierarchical | `tasks.md`                                                       | `openspec/config.yaml` `rules.tasks`     | Pass if phases and numbered items (for example 1.1, 2.1) are present    |
| Spec requirements use RFC 2119 terms       | `specs/openspec/spec.md`                                         | `openspec/config.yaml` `rules.specs`     | Pass if requirements include MUST/SHALL/SHOULD/MAY                      |
| Scenarios use GIVEN/WHEN/THEN              | `specs/openspec/spec.md`                                         | `openspec/config.yaml` `rules.specs`     | Pass if all scenarios are explicit GIVEN/WHEN/THEN bullets              |
| Design includes decisions and flow         | `design.md`                                                      | `openspec/config.yaml` `rules.design`    | Pass if architecture decisions and validation flow are documented       |

## Testing Strategy

| Layer       | What to Test                                  | Approach                                                                                    |
| ----------- | --------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Unit        | N/A (no runtime code)                         | Not applicable for this process-only bootstrap                                              |
| Integration | Artifact set completeness and rule compliance | Reviewer checklist against folder structure and `openspec/config.yaml`                      |
| E2E         | Reusability by a follow-up change             | Create next change and confirm contributors can place proposal/spec/tasks without ambiguity |

## Migration / Rollout

No data migration required. Rollout is procedural:

1. Complete bootstrap artifacts.
2. Run manual validation against `openspec/config.yaml` and record pass/fail notes in change discussion.
3. Dry-run a follow-up change scaffold under `openspec/changes/<new-change>/` with `proposal.md`, `specs/<domain>/spec.md`, and `tasks.md`.
4. Require new changes to follow the same artifact structure.
5. Collect early adoption feedback and adjust via a follow-up process change if ambiguity is found.

## Open Questions

- [ ] Should we add automated linting/CI checks for OpenSpec artifact compliance after bootstrap is accepted?
- [ ] Should reusable proposal/spec/tasks templates be introduced in a separate follow-up change?
