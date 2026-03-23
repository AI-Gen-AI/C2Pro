# Session Lifecycle Specification

## Purpose

Define the required close sequence for agent sessions so final responses are not emitted before session state is persisted.

## Requirements

### Requirement: Final Response Gate

The system MUST treat any final `done`, `listo`, or `completed` response as blocked until the session-close sequence has completed successfully.

#### Scenario: Final response after successful close

- GIVEN an agent has finished the requested work
- WHEN it prepares to send a final completion response
- THEN it SHALL first complete the session-close sequence
- AND only after success MAY it emit the final response

#### Scenario: Final response attempted too early

- GIVEN at least one close step has not completed
- WHEN the agent attempts a final completion response
- THEN the session MUST be treated as still open

### Requirement: Mandatory Session-Close Sequence

The session-close sequence MUST, in order, persist a session summary, record final task status, and mark the session as ended.

#### Scenario: Normal close sequence

- GIVEN the work session is ready to close
- WHEN the close sequence runs
- THEN a summary SHALL be persisted
- AND task/status state SHALL be updated before the session is marked ended

#### Scenario: No open tasks remain

- GIVEN all planned work is complete
- WHEN task/status state is recorded
- THEN the session SHALL show no in-progress work items

### Requirement: Failure Handling Before Closure

If any close step fails, the system MUST NOT present the session as completed and MUST report the blocking failure.

#### Scenario: Summary persistence fails

- GIVEN the agent starts the close sequence
- WHEN summary persistence fails
- THEN the session SHALL remain open
- AND the final response MUST report that closure is incomplete

#### Scenario: Session end fails after summary succeeds

- GIVEN summary persistence and task updates succeeded
- WHEN the explicit session-end step fails
- THEN the agent MUST report partial closure
- AND the session MUST NOT be represented as fully closed

### Requirement: Close Sequence Visibility

The system SHOULD make the executed close sequence visible in the final handoff so reviewers can verify that closure occurred.

#### Scenario: Final handoff references closure

- GIVEN the close sequence completed successfully
- WHEN the final response is generated
- THEN it SHOULD reference the saved summary or closed-session state
