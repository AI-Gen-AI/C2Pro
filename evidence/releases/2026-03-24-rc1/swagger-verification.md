# Swagger Verification Report

## Runtime

- Base URL: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/api/v1/openapi.json`
- Verification date: `2026-03-24`
- Commit SHA: `4a63abb40d9966557237888670a528ffc85ce80f`

## Verified Endpoints

| Endpoint                                            | Result | Notes                                                                             |
| --------------------------------------------------- | ------ | --------------------------------------------------------------------------------- |
| `PUT /api/v1/auth/me`                               | Pass   | Returned `200` and persisted profile updates for the temporary verification user. |
| `POST /api/v1/auth/change-password`                 | Pass   | Returned `204`; subsequent login with the new password returned `200`.            |
| `GET /api/v1/projects/stats`                        | Pass   | Returned `200` with tenant-scoped aggregate counts.                               |
| `PUT /api/v1/projects/{project_id}`                 | Pass   | Returned `200` when called with a valid full payload and enum status `active`.    |
| `POST /api/v1/projects/{project_id}/documents/bulk` | Pass   | Returned `202` with `accepted_count: 2` and generated document ids.               |
| `POST /api/v1/projects/{project_id}/wbs/bulk`       | Pass   | Returned `201` with `created_count: 2`.                                           |
| `POST /api/v1/projects/{project_id}/export`         | Pass   | Returned `202` with `export_id`/`job_id`.                                         |
| `GET /api/v1/projects/{project_id}/budget`          | Pass   | Returned `200` with budget totals matching the seeded project values.             |

| `POST /api/v1/auth/logout` | Pass | After restarting the API runtime on `2026-03-24`, logout returned `204` and the same bearer token was rejected by `GET /api/v1/auth/me` with `401` and `reason_code: token_revoked`. |

## Conclusion

- `G7-01` is now complete for the active Swagger workbook.
- The active workbook now reflects the live runtime results.
- Gate 7 release certification still depends on the pending suite matrix, performance/DR refresh, and formal approvals in the release bundle.
