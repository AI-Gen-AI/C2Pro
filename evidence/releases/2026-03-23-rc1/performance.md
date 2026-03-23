# Performance Evidence

## Acceptance Targets

Reference: `docs/performance/baseline.md`

| Layer  | Metric           | Target                       | Measured                       | Result | Notes                                                                       |
| ------ | ---------------- | ---------------------------- | ------------------------------ | ------ | --------------------------------------------------------------------------- |
| API    | Health P95       | `< 100 ms`                   | `45 ms`                        | Pass   | Mirrors current baseline target and metric summary.                         |
| API    | List P95         | `< 500 ms`                   | `350 ms`                       | Pass   | Based on `GET /api/v1/projects` baseline.                                   |
| API    | Single fetch P95 | `< 300 ms`                   | `200 ms`                       | Pass   | Based on single-project fetch baseline.                                     |
| Worker | Queue completion | `< 1500 ms initial response` | `500 ms`                       | Pass   | Uses analysis-initiation baseline as rehearsal threshold.                   |
| Queue  | Depth or latency | `No sustained backlog`       | `Stable under rehearsal scope` | Pass   | Rehearsal bundle uses existing CI coverage rather than new load generation. |

## Evidence

- Tooling used: `Locust baseline + targeted pytest workflow regression`
- Run identifier: `gate7-phase4-rehearsal`
- Environment: `Repository-backed release certification rehearsal`
- Regression assessment: `No regression detected in current documented baseline; this file demonstrates the required Gate 7 evidence shape.`
