# OpenSpec Specification

## Purpose

Define the minimum governance and artifact structure the project MUST use to run spec-driven changes consistently.

## Requirements

### Requirement: Bootstrap Change Artifact Set

The system MUST provide a bootstrap change that includes proposal, design, spec, and tasks artifacts under a single change directory.

#### Scenario: Bootstrap artifacts exist

- GIVEN the repository includes `openspec/changes/openspec-bootstrap/`
- WHEN a reviewer inspects the change folder
- THEN `proposal.md`, `design.md`, at least one `specs/*/spec.md`, and `tasks.md` SHALL exist

#### Scenario: Missing artifact is detected

- GIVEN one required artifact is absent from the bootstrap folder
- WHEN validation is performed against expected bootstrap structure
- THEN the bootstrap change MUST be considered incomplete

### Requirement: Spec Rules Compliance

All bootstrap specs MUST use RFC 2119 requirement language and GIVEN/WHEN/THEN scenarios so they are testable and reviewable.

#### Scenario: Spec language and scenario format pass review

- GIVEN a bootstrap spec document
- WHEN the document is reviewed for rules compliance
- THEN each requirement SHALL include MUST/SHALL/SHOULD/MAY language
- AND each scenario SHALL follow GIVEN/WHEN/THEN structure

#### Scenario: Non-compliant spec is rejected

- GIVEN a bootstrap spec without RFC 2119 terms or scenario structure
- WHEN the change is reviewed
- THEN reviewers MUST request corrections before approval

### Requirement: Adoption Validation Path

The process SHOULD define a follow-up validation path proving the bootstrap structure can be reused by another change without path or template ambiguity.

#### Scenario: Follow-up change uses bootstrap conventions

- GIVEN bootstrap artifacts are merged
- WHEN a new change is created using the same folders and templates
- THEN contributors SHALL be able to place proposal, specs, and tasks in expected locations

#### Scenario: Ambiguity triggers improvement action

- GIVEN a contributor cannot determine artifact location from bootstrap conventions
- WHEN the issue is reported during early adoption
- THEN maintainers SHOULD update templates or guidance in the next process change
