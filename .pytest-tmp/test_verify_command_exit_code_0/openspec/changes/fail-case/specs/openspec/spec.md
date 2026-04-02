# OpenSpec Specification

### Requirement: OpenSpec Rules Compliance Validation
Verification validates artifacts against policy.

#### Scenario: Rule violation is reported with evidence
- GIVEN malformed requirement wording
- WHEN verification runs
- THEN failure SHALL be reported
