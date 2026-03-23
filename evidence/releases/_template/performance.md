# Performance Evidence Template

## Acceptance Targets

Reference: `docs/performance/baseline.md`

| Layer  | Metric           | Target     | Measured     | Result      | Notes     |
| ------ | ---------------- | ---------- | ------------ | ----------- | --------- |
| API    | Health P95       | `<target>` | `<measured>` | Pass / Fail | `<notes>` |
| API    | List P95         | `<target>` | `<measured>` | Pass / Fail | `<notes>` |
| API    | Single fetch P95 | `<target>` | `<measured>` | Pass / Fail | `<notes>` |
| Worker | Queue completion | `<target>` | `<measured>` | Pass / Fail | `<notes>` |
| Queue  | Depth or latency | `<target>` | `<measured>` | Pass / Fail | `<notes>` |

## Evidence

- Tooling used: `<tool>`
- Run identifier: `<run-id>`
- Environment: `<environment>`
- Regression assessment: `<summary>`
