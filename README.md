# C2Pro — Contract & Project Intelligence

C2Pro is a multi-tenant platform for turning contracts and project evidence into traceable analysis, project controls and human-reviewed decisions.

The repository is under active development. **Do not infer production qualification from code presence or a green historical CI run.** Product lifecycle state is controlled separately from architecture and implementation state.

## Current platform baseline

| Layer | Current repository baseline |
| --- | --- |
| Web | Next.js 16.3.6, React 19.2.7, TypeScript 5.9, Node 22, pnpm 10 |
| Identity | Clerk JWT / organization identity mapped to internal tenant/user context |
| API | FastAPI 0.141.x, Pydantic v2, Python 3.11 |
| Persistence | PostgreSQL/Supabase, SQLAlchemy/Alembic, RLS, pgvector |
| Async | Celery + Redis |
| Documents | R2/S3-compatible object storage, parsing, PII handling |
| AI | Anthropic-oriented application layer with LangChain adapters |
| Orchestration | LangGraph 1.2.10 + PostgreSQL checkpointing 3.1.2 |
| Observability | Structlog, Sentry, Prometheus, LangSmith |
| Testing | pytest, Vitest, Playwright, contract/security/evaluation gates |

## Architecture in one view

```text
Browser / Next.js
      |
      | Clerk identity
      v
FastAPI + tenant middleware
      |
      +--> PostgreSQL / RLS / pgvector
      +--> R2 document storage
      +--> Redis / Celery
      |
      v
Document processing authority
(revision + generation + attempt + fencing lease)
      |
      v
LangGraph analysis
(authority-scoped checkpoint lineage)
      |
      v
HITL exact checkpoint/review boundary
      |
      v
Evidence / Health / Project intelligence
```

After #711 and #758/#759, an owned analysis attempt has its own LangGraph lineage:

`document:{document_id}:g{generation}:f{fencing_token}:analysis`

HITL resume binds an exact persisted checkpoint identity rather than selecting a document-wide "latest" checkpoint. See ADR-026.

## Source-of-truth map

C2Pro intentionally uses different authorities for different questions:

- **landed implementation:** Git `main`, merged PRs and exact-SHA CI/evidence;
- **product lifecycle:** `validation/product/c2pro-master-product-control-v1.yaml`;
- **development execution:** `.c2pro/control/` + assigned `.c2pro/work/`;
- **platform architecture:** `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md` + Accepted ADRs;
- **historical evidence:** Git history, `docs/archive/`, dated audits/reports.

Legacy `C2PRO_MASTER_BACKLOG.md`, domain backlogs and `blackboard.json` are cold/read-only references for ordinary workers under the Single-Writer Control Plane.

Start with [Documentation Governance](docs/DOCUMENTATION_GOVERNANCE.md).

## Key architecture documents

- [Platform TDD v4.2](docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md)
- [Architecture Decisions](docs/architecture/decisions/README.md)
- [ADR-026 — Processing Authority, Checkpoint Lineage and HITL Resume Fencing](docs/architecture/decisions/ADR-026-processing-authority-checkpoint-lineage.md)
- [LangGraph Checkpointing and Lineage](docs/architecture/LANGGRAPH_CHECKPOINTING.md)
- [Architecture Index](docs/ARCHITECTURE_INDEX.md)
- [Master Development Status](docs/MASTER_DEVELOPMENT_STATUS.md)
- [Product Control projection](docs/product/00-c2pro-master-product-control-v1.md)

## Product trust model

C2Pro separates evidence, proposal, human decision and canonical state. The broader #714 Trusted-State Commit design is still in-flight; this README does not claim it has been accepted or merged.

## Security posture

The repository contains controls for Clerk JWT verification and tenant mapping, PostgreSQL RLS, PII minimization/anonymization, bounded MCP/tool access, security scanning, durable processing fencing and exact HITL checkpoint/review lineage.

Security claims are only valid when tied to current exact-SHA evidence.

## CI

Primary and supporting GitHub Actions include `ci.yml`, `secret-scan.yml`, `install-drift-guard.yml`, dependency review/audit, CodeQL, Product-Control Guard, OpenAPI, evaluation and real-document workflows.

The repository ruleset, not this README, is authoritative for which checks are required for a given merge.

## Local development

Use the root `Makefile` and package-specific tooling:

```bash
make help
make setup-local
make dev
make test
make lint
make typecheck
```

For exact backend/frontend commands see `CLAUDE.md`, package manifests and the relevant runbooks.

## Documentation discipline

- Current docs must distinguish Canonical, Supporting, Proposed, Snapshot and Historical material.
- Accepted ADRs own durable architecture decisions.
- Product lifecycle changes are reconciled through Product Control, not by prose edits.
- Historical audits/archives are preserved rather than rewritten.

## License metadata

Licensing metadata is currently inconsistent: the public repository has no standalone `LICENSE` file while `package.json` declares ISC and historical text used different wording. Redistribution rights should not be inferred until maintainers publish canonical license terms.
