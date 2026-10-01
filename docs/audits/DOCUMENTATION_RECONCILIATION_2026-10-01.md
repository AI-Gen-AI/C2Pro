# Active Documentation Reconciliation — 2026-10-01

**Status:** Evidence snapshot  
**Tracking:** #771  
**Baseline:** `be0c7c7eac087ea95698362ed7a9a163618f9e9a`

## Material drift found

| Area | Finding | Disposition |
| --- | --- | --- |
| Governance | active docs disagreed on legacy backlog vs `.c2pro/` authority | Align to existing Single-Writer Control Plane |
| Platform TDD | v4.1 (2026-03-29) still marked Current | Supersede with v4.2 |
| README | old Sprint S2 / old stack/auth claims | Replace with current repository baseline |
| ADR catalog | `docs/DECISION_LOG.md` competed with live ADR directory | Convert to compatibility pointer |
| Checkpointing | shared-thread/latest-checkpoint guide contradicted #758/#759 | Rewrite + ADR-026 |
| Diagrams | old master-flow contains pre-current assumptions | Mark historical/non-canonical rather than partially modernize |
| License metadata | public repo + package ISC + no LICENSE + historical conflicting wording | Leave unresolved for explicit maintainer decision |

## Evidence sampled

- `apps/web/package.json` — Next.js 16.3.6, React 19.2.7, Clerk, Vitest/Playwright.
- `.nvmrc` — Node 22.
- `.python-version` — Python 3.11.9.
- `apps/api/requirements.txt` — FastAPI, LangGraph 1.2.10, checkpoint-postgres 3.1.2, Celery, Presidio, LangSmith.
- Clerk middleware/auth lookup code.
- #711 processing authority.
- #758/#759 checkpoint/review lineage implementation/tests.

## Conclusion

The durable new architecture decision is how processing authority constrains LangGraph lineage and HITL resume. It is recorded as ADR-026.

#714 Trusted-State Commit remains Proposed/In-flight and is deliberately not promoted.

## Exclusions

No Product Control lifecycle promotion, production requalification, historical audit rewrite, Sonar mutation or legal-license choice.
