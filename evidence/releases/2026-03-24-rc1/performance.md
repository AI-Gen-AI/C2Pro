# Performance Evidence

## Acceptance Targets

Reference: `docs/performance/baseline.md`

| Layer  | Metric                 | Target                       | Measured    | Result | Notes                                                                                                                                                 |
| ------ | ---------------------- | ---------------------------- | ----------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| API    | Health P95             | `< 100 ms`                   | `68.10 ms`  | Pass   | Five live requests against `GET /health` on the restarted local Docker runtime.                                                                       |
| API    | List P95               | `< 500 ms`                   | `138.67 ms` | Pass   | Five authenticated requests against `GET /api/v1/projects`.                                                                                           |
| API    | Single fetch P95       | `< 300 ms`                   | `239.88 ms` | Pass   | Five authenticated requests against `GET /api/v1/projects/{project_id}`.                                                                              |
| Queue  | Bulk operation result  | `< 3000 ms`                  | `76.59 ms`  | Pass   | `POST /api/v1/projects/{project_id}/documents/bulk` accepted `2/2` documents; this is a release-time smoke measurement, not a 100-document load test. |
| Worker | Queue initial response | `< 1500 ms initial response` | `69.54 ms`  | Pass   | `POST /api/v1/projects/{project_id}/export` returned `202` with job id `f7d8c4bd-aa3e-4954-ad79-6a83dc2fbae5`.                                        |

## Evidence

- Release ID: `2026-03-24-rc1`
- Commit SHA: `4a63abb40d9966557237888670a528ffc85ce80f`
- Target environment: `Local Docker Compose runtime on localhost:8000 after API restart`
- Tooling used: `Python urllib smoke benchmark against live Docker Compose runtime`
- Run identifier: `gate7-2026-03-24-rc1-live-perf`
- Environment: `Local Docker Compose runtime on localhost:8000 after API restart`
- Sample counts: `5` health, `5` list, `5` single-fetch requests
- Health comparison: `GET /health` P95 `68.10 ms` versus target `< 100 ms` -> `Pass`
- List comparison: `GET /api/v1/projects` P95 `138.67 ms` versus target `< 500 ms` -> `Pass`
- Single-fetch comparison: `GET /api/v1/projects/{project_id}` P95 `239.88 ms` versus target `< 300 ms` -> `Pass`
- Bulk-operation comparison: `POST /api/v1/projects/{project_id}/documents/bulk` result `76.59 ms` versus target `< 3000 ms` -> `Pass`
- Worker/queue comparison: `POST /api/v1/projects/{project_id}/export` initial response `69.54 ms` versus target `< 1500 ms` -> `Pass`
- Regression assessment: `All measured live smoke metrics remained within the approved Gate 7 targets from docs/performance/baseline.md.`
- Variance notes: `This refresh validates release-time smoke performance only; the broader load baseline remains the 2026-03-07 Locust benchmark in docs/performance/baseline.md.`
- Variance disposition: `Accepted for release-time smoke certification; no blocking exception opened.`
- Variance owner: `Engineering / Operations`
