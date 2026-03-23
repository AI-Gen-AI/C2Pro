# OpenSpec Specification

## Purpose

Define a lightweight verification path for process-only OpenSpec changes so compliance can be validated without running unrelated product test suites.

## Requirements

### Requirement: Process-Only Verify Entry Point

The system MUST provide a dedicated command for validating OpenSpec process artifacts under `openspec/changes/{change-name}`.

#### Scenario: Docs-only verification executes

- GIVEN a change contains OpenSpec artifacts and no runtime code modifications
- WHEN a reviewer runs the dedicated OpenSpec verify command
- THEN verification SHALL execute without requiring full frontend or backend test suites

#### Scenario: Runtime scope mismatch is flagged

- GIVEN a change includes runtime code modifications outside OpenSpec process artifacts
- WHEN the docs-only verify command is executed
- THEN the command MUST report that full verification gates are still required

### Requirement: Scenario-to-Check Traceability

Each spec scenario in the change MUST map to an executable check or deterministic manual validation step with pass/fail output.

#### Scenario: Complete traceability matrix exists

- GIVEN a change spec with one or more scenarios
- WHEN verification metadata is generated
- THEN each scenario SHALL include a corresponding check identifier and result

#### Scenario: Missing mapping fails verification

- GIVEN at least one scenario has no mapped check or validation step
- WHEN compliance verification runs
- THEN the change MUST be marked non-compliant

### Requirement: OpenSpec Rules Compliance Validation

Verification MUST validate the change artifacts against `openspec/config.yaml` spec and verify rules.

#### Scenario: Rules-compliant artifacts pass

- GIVEN change artifacts use RFC 2119 keywords and Given/When/Then scenarios
- WHEN compliance verification evaluates configured rules
- THEN the artifacts SHALL pass rule compliance checks

#### Scenario: Rule violation is reported with evidence

- GIVEN a spec artifact violates required scenario format or requirement language
- WHEN verification executes
- THEN the report MUST identify the violating file, rule, and failure reason

### Requirement: Deterministic Verification Report

The verification workflow SHOULD produce a deterministic report that reviewers can use as evidence for approval decisions.

#### Scenario: Report includes required sections

- GIVEN verification has completed for a process-only change
- WHEN the report is generated
- THEN it SHALL include artifact presence, scenario coverage, rule compliance, and overall verdict

#### Scenario: Re-run produces stable conclusions

- GIVEN the same artifacts and rules are verified multiple times
- WHEN no inputs have changed
- THEN the workflow SHOULD produce equivalent pass/fail conclusions
