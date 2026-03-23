# Incident Response Runbook

## Purpose

Provide a standard process for triaging and resolving operational incidents in C2Pro.

## Leadership Gap Closure

- [x] `LEAD-GAP-OPS-READINESS` Define operational ownership, escalation, and on-call expectations for production incidents and release-adjacent platform failures.

## Operational Ownership Matrix

| Service Area                               | Primary Owner                    | Secondary Owner  | Responsibilities                                                                                           |
| :----------------------------------------- | :------------------------------- | :--------------- | :--------------------------------------------------------------------------------------------------------- |
| API / Auth / Tenant Isolation              | Team Alpha (Sentinel)            | Engineering Lead | FastAPI health, auth, tenant isolation, security-sensitive incidents, release-blocking backend regressions |
| Worker / AI Pipeline / LangGraph           | Team Bravo (Nexus)               | Engineering Lead | Celery, LangGraph state, AI execution failures, coherence/analysis degradation, MCP execution issues       |
| Web App / Demo Isolation / API Client      | Team Charlie (Prism)             | Engineering Lead | frontend availability, auth UX, proxy routing, viewer/evidence flows, production-vs-demo safety            |
| Database / Migrations / Backup-Restore     | Team Alpha (Sentinel)            | Engineering Lead | PostgreSQL, Supabase migration authority, backup/restore coordination, rollback readiness                  |
| CI/CD / Staging / Production Deployability | Team Alpha (Sentinel)            | Engineering Lead | GitHub Actions, staging deploys, environment health, deploy/rollback coordination                          |
| Product / Customer Communications          | Product + Engineering Leadership | Delivery Manager | incident summaries, external status, stakeholder coordination, go/no-go recommendations                    |

Owner rules:

- The primary owner leads diagnosis and recovery for incidents in their service area.
- The secondary owner must be able to take over within 15 minutes if the primary owner is unavailable.
- Engineering Leadership acts as the final escalation point for cross-team incidents, Sev-1 events, and release go/no-go decisions.

## On-Call Expectations

Coverage expectations:

- Production-facing systems require one named primary on-call owner and one named backup for each of the three engineering teams.
- On-call assignments must be published before any production release window and updated whenever staffing changes.
- Release days require explicit confirmation that Alpha, Bravo, and Charlie have live coverage during deploy and rollback windows.

Response targets:

| Severity | Ack Target      | Update Cadence         | Recovery Target                                     | Required Participants                                             |
| :------- | :-------------- | :--------------------- | :-------------------------------------------------- | :---------------------------------------------------------------- |
| Sev-1    | 5 minutes       | every 15 minutes       | immediate containment, same-hour recovery plan      | primary owner, backup owner, engineering lead, product/leadership |
| Sev-2    | 15 minutes      | every 30 minutes       | same business day                                   | owning team primary, backup if needed                             |
| Sev-3    | 1 business hour | at major state changes | next planned fix window or hotfix if risk increases | owning team                                                       |

Operational expectations:

- Acknowledgement means the incident has an assigned owner in Slack/incident channel and work has started.
- If the primary on-call cannot respond within the ack target, the backup owner is paged immediately.
- If neither responds within the target, Engineering Leadership becomes acting incident commander.
- On-call engineers must stay reachable by Slack and phone during scheduled coverage windows.

## Escalation Path

1. Detect issue from monitoring, CI/CD failure, customer report, or manual QA.
2. Open or update the incident channel/ticket with severity, affected area, and current owner.
3. Page the primary owner for the affected service area.
4. If ack target is missed, page the backup owner and notify Engineering Leadership.
5. For Sev-1 or multi-service incidents, Engineering Leadership appoints an incident commander and pulls in all impacted team owners.
6. Product/leadership is notified when customer-facing impact, release delay, rollback, or data integrity risk is confirmed.
7. Close only after recovery is verified on the critical path and follow-up actions are assigned.

Escalate immediately to Engineering Leadership when any of the following are true:

- tenant isolation, auth, or security controls may be broken
- production deploy requires rollback or emergency freeze
- database migration, restore, or data-integrity risk is involved
- more than one team is needed to restore service
- customer-facing outage exceeds 30 minutes

## Incident Commander Expectations

- keeps one active severity and owner assignment
- drives containment before root-cause depth work
- ensures stakeholder updates stay on schedule
- records rollback decisions, customer impact, and release implications
- opens post-incident follow-up tasks before closure

## Severity Levels

- Sev-1: Full outage or critical security exposure.
- Sev-2: Partial outage or degraded core workflow.
- Sev-3: Non-critical issue with workaround available.

## Response Flow

1. Detect and acknowledge incident.
2. Classify severity and assign incident lead.
3. Contain immediate impact.
4. Communicate status and ETA to stakeholders.
5. Recover service and validate critical paths.
6. Publish post-incident summary with corrective actions.

## Required Outputs

- Timeline of events (UTC timestamps).
- Root cause statement.
- Corrective and preventive actions with owners and due dates.

## Release-Day Operating Rule

- No production release proceeds unless all three engineering teams have confirmed primary/backup coverage for the release window.
- Any unresolved Sev-1 or Sev-2 incident blocks release promotion until leadership explicitly re-approves.
- If rollback is triggered, Team Alpha leads infrastructure rollback, the impacted service owner validates recovery, and Engineering Leadership confirms status before reopening release work.

---

Last Updated: 2026-03-22

Changelog:

- 2026-03-22: Added operational ownership matrix, on-call expectations, escalation path, and leadership gap closure marker for production ops readiness.
- 2026-02-13: Added initial incident response scaffold with severity and workflow.
