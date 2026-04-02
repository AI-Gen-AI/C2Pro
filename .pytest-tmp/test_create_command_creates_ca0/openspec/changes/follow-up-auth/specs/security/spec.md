# Security Specification

### Requirement: Follow Up Auth
The implementation MUST define the expected behavior for this follow-up change.

#### Scenario: Follow-up change applies canonical scaffold
- GIVEN a contributor creates a new OpenSpec follow-up change
- WHEN the scaffold is generated
- THEN the canonical proposal, design, tasks, and spec files SHALL exist in the expected paths
