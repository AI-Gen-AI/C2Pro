# C2Pro — Contract Intelligence Platform

C2Pro is an AI-assisted platform for **contractual coherence analysis** in construction and engineering projects. It cross-checks contract clauses, project schedules, and budget structures to detect inconsistencies early and reduce cost overruns.

This README is the **main documentation hub** for the repository.

## Project Purpose

Construction and infrastructure projects often fail due to misalignment between:

- **Contract commitments**
- **Execution schedule**
- **Budget and procurement assumptions**

C2Pro helps teams identify these mismatches before they become legal, financial, or operational risks.

## Repository Overview

```text
c2pro/
├── apps/
│   ├── api/                  # FastAPI backend (domain logic, AI integrations, tests)
│   └── web/                  # Frontend application
├── docs/                     # Primary project documentation
│   ├── architecture/         # ADRs and architecture diagrams
│   ├── runbooks/             # Operations and incident procedures
│   ├── specifications/       # Functional and technical specs
│   ├── plans/                # Delivery and implementation plans
│   ├── audits/               # Quality, UX, and readiness audits
│   └── archive/              # Historical reports, roadmaps, and closed work
├── infrastructure/           # Supabase config, scripts, infra setup/testing
└── tests/                    # Cross-cutting test suites and fixtures
```

## Quick Start

- Platform bootstrapping: [QUICK_START.md](./QUICK_START.md)
- Windows setup: [windows-setup.md](./windows-setup.md)
- Backend setup and API details: [apps/api/README.md](./apps/api/README.md)
- Test execution guidance: [TESTING.md](./TESTING.md)

## Documentation Index (Current)

### Architecture

- [docs/PLAN_ARQUITECTURA.md](./docs/PLAN_ARQUITECTURA.md) — high-level architecture plan and target structure.
- [docs/architecture/FLOW_DIAGRAMS.md](./docs/architecture/FLOW_DIAGRAMS.md) — system-level flow diagrams.
- [docs/architecture/decisions/](./docs/architecture/decisions/) — Architecture Decision Records (ADRs) that explain key technical choices.

### Design and Product Definition

- [context/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md](./context/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md) — comprehensive technical design baseline.
- [docs/wireframes/README.md](./docs/wireframes/README.md) — UI/UX wireframe documentation index.
- [docs/wireframes/](./docs/wireframes/) — feature-level interface and interaction design notes.

### Implementation and Engineering Status

- [docs/DEVELOPMENT_STATUS.md](./docs/DEVELOPMENT_STATUS.md) — active development progress and status.
- [docs/SPRINT_S2_PROGRESS_SUMMARY.md](./docs/SPRINT_S2_PROGRESS_SUMMARY.md) — sprint-level delivery summary.
- [docs/LESSONS_LEARNED.md](./docs/LESSONS_LEARNED.md) — implementation retrospectives and engineering learnings.

### Configuration and Infrastructure

- [infrastructure/supabase/README.md](./infrastructure/supabase/README.md) — Supabase workspace structure and usage.
- [infrastructure/supabase/SETUP_INSTRUCTIONS.md](./infrastructure/supabase/SETUP_INSTRUCTIONS.md) — setup steps for local/staging infrastructure.
- [docs/runbooks/ci-cd-setup.md](./docs/runbooks/ci-cd-setup.md) — CI/CD operational setup.
- [docs/runbooks/backup-restore.md](./docs/runbooks/backup-restore.md) — backup and restore procedures.

### Usage and Operations

- [apps/api/README.md](./apps/api/README.md) — backend usage, endpoints, and operational guidance.
- [apps/web/README_SETUP.md](./apps/web/README_SETUP.md) — frontend environment/setup usage notes.
- [docs/runbooks/incident-response.md](./docs/runbooks/incident-response.md) — incident handling workflow.

### Testing and Quality

- [TESTING.md](./TESTING.md) — repository-wide test strategy and commands.
- [tests/README.md](./tests/README.md) — tests directory index and organization.
- [docs/TEST_COVERAGE_ANALYSIS.md](./docs/TEST_COVERAGE_ANALYSIS.md) — test coverage assessment.
- [docs/TEST_STATUS_CHECKLIST_2026-03-08.md](./docs/TEST_STATUS_CHECKLIST_2026-03-08.md) — current test readiness checklist.

### Planning and Roadmap

- [docs/ROADMAP_v2.4.0.md](./docs/ROADMAP_v2.4.0.md) — current roadmap and milestones.
- [docs/planning/](./docs/planning/) — implementation planning documents.
- [docs/PHASE4_TDD_IMPLEMENTATION_ROADMAP.md](./docs/PHASE4_TDD_IMPLEMENTATION_ROADMAP.md) — phased TDD execution roadmap.

### Security and Audits

- [docs/audits/PRODUCTION_READINESS_AUDIT_2026-02-14.md](./docs/audits/PRODUCTION_READINESS_AUDIT_2026-02-14.md) — production readiness findings.
- [docs/INFRASTRUCTURE_AUDIT_2026-03-07.md](./docs/INFRASTRUCTURE_AUDIT_2026-03-07.md) — infrastructure audit summary.
- [docs/INFRASTRUCTURE_AUDIT_EXTENDED_COMMITTEE_2026-03-07.md](./docs/INFRASTRUCTURE_AUDIT_EXTENDED_COMMITTEE_2026-03-07.md) — extended committee audit review.

## Recommended Core Documentation Backbone (to standardize)

To keep this documentation architecture stable as the project grows, maintain these canonical files at repository root (or `docs/` where noted):

- `README.md` — central project overview and documentation map.
- `CONTRIBUTING.md` — contribution workflow, coding standards, and review process.
- `ARCHITECTURE.md` (or `docs/ARCHITECTURE.md`) — system context, boundaries, and component interactions.
- `DESIGN.md` — product and technical design principles.
- `INSTALLATION.md` — clean installation and local environment setup.
- `USAGE.md` — user/developer workflows and operational usage.
- `API.md` (or `docs/API.md`) — API contracts, conventions, auth, and error models.
- `CHANGELOG.md` — versioned change history.
- `ROADMAP.md` — forward-looking plan and milestones.
- `LICENSE.md` (or `LICENSE`) — legal usage terms.

> These files can start minimal and expand over time without changing the top-level documentation structure.

## Contributing

Formal contributing guidelines are not yet centralized in a dedicated `CONTRIBUTING.md`. Until then, use the implementation and testing references above when submitting changes.

## License

This repository is currently maintained as a private/internal project. Add a canonical `LICENSE` or `LICENSE.md` file when distribution terms are finalized.
