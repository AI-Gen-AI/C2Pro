# OpenSpec Specification

### Requirement: Deterministic Verification Report
The verifier SHOULD produce deterministic outputs.

#### Scenario: Re-run produces stable conclusions
- GIVEN identical inputs
- WHEN the verifier runs repeatedly
- THEN conclusions SHALL remain equivalent
