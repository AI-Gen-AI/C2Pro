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

- Tooling used: `Python urllib smoke benchmark against live Docker Compose runtime`
- Run identifier: `gate7-2026-03-24-rc1-live-perf`
- Environment: `Local Docker Compose runtime on localhost:8000 after API restart`
- Sample counts: `5` health, `5` list, `5` single-fetch requests
- Regression assessment: `All measured live smoke metrics remained within the approved Gate 7 targets from docs/performance/baseline.md.`
- Variance notes: `This refresh validates release-time smoke performance only; the broader load baseline remains the 2026-03-07 Locust benchmark in docs/performance/baseline.md.`
