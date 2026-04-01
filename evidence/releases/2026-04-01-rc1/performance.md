# Performance Evidence

## Acceptance Targets

Reference: `docs/performance/baseline.md`

| Layer  | Metric                 | Target                       | Measured    | Result | Notes                                                                                                                                                 |
| ------ | ---------------------- | ---------------------------- | ----------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| API    | Health P95             | `< 100 ms`                   | `68.10 ms`  | Pass   | Local Docker benchmark environment (Verified 2026-03-28).                                                                                             |
| API    | List P95               | `< 500 ms`                   | `138.67 ms` | Pass   | Authenticated requests against `GET /api/v1/projects`.                                                                                                |
| API    | Single fetch P95       | `< 300 ms`                   | `239.88 ms` | Pass   | Authenticated requests against `GET /api/v1/projects/{project_id}`.                                                                                   |
| Queue  | Bulk operation result  | `< 3000 ms`                  | `76.59 ms`  | Pass   | `POST /api/v1/projects/{project_id}/documents/bulk` acceptance test.                                                                                 |
| Worker | Queue initial response | `< 1500 ms initial response` | `69.54 ms`  | Pass   | `POST /api/v1/projects/{project_id}/export` async response.                                                                                           |

## Evidence

- Release ID: `2026-04-01-rc1`
- Commit SHA: `HEAD`
- Target environment: `Local Docker Compose runtime (Verified 2026-03-28)`
- Tooling used: `Python urllib smoke benchmark`
- Run identifier: `gate7-2026-04-01-rc1-local-perf`
- Sample counts: `5` health, `5` list, `5` single-fetch requests
- Regression assessment: `All measured metrics remained within the approved Gate 7 targets from docs/performance/baseline.md.`
