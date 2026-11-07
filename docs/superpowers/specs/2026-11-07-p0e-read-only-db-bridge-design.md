# P0-E Read-only database bridge

## Intent

Provide the missing application/service reader that builds the existing historical-risk advisory planner input from persisted PostgreSQL records. It serves an authenticated tenant-scoped caller and never changes artifacts, alerts, analyses, reviews, or events.

## Scope and constraints

The caller supplies the authenticated tenant and an exact project/document/revision/artifact selector; those values are selectors, never proof. The reader re-checks project ownership, the artifact scope, active/trusted state, full payload digest, revision identity, and an APPROVED review whose candidate binding names the exact artifact id/version/digest. It refuses absent or stale authority rather than manufacturing trusted state.

It selects completed RISK analyses and RISK alerts for the same tenant/project, then determines document relevance from each alert's persisted affected-document list. It does not select historical alerts merely by `Analysis.source_artifact_id`; that field is subsequently included as the planner's exact pin. Raw risks remain untouched, including `source_quote` status and human decision fields.

## Design choices

Two focused layers are used: a SQLAlchemy read repository and an application service. The repository performs SELECT-only ORM queries and maps records into planner snapshots. The service accepts the authenticated scope, invokes the repository, and calls `plan_historical_risk_alert_reconciliation` unchanged. An untrusted/inactive row is passed through as untrusted so the existing planner emits `PLAN_BLOCKED`; an unavailable/ambiguous authority raises a typed read-boundary refusal.

No endpoint, migration, write path, LLM work, automatic decision, or trust transition is introduced.

## Verified legacy provenance limitation (2026-11-07)

The current `analyses` ORM row has `tenant_id`, `project_id`, and an optional
`source_artifact_id`, but no persisted `document_id` or `revision_id`. The
legacy N4/N17 RISK writer stores the extracted item in `alert_metadata.raw`,
but does not set `affected_entities.documents`. It therefore cannot prove that
an historical RISK alert belongs to the selected document revision. In
particular, `source_artifact_id` is not used as a substitute: the known legacy
rows may be pinned to a V2 artifact incorrectly.

The implemented reader authenticates project/artifact scope and derives active
trusted state and digest from the artifact row. It returns no historical
analysis snapshots while this required historical document/revision provenance
is absent. The existing pure planner consequently emits `PLAN_BLOCKED` with
`NOT_ENOUGH_EVIDENCE`; it never silently classifies legacy alerts as V2
matches. A schema/provenance migration or independently persisted, verifiable
historical document-and-revision association is required before reconciliation
can produce a ready plan.
