# C2Pro — Contract & Project Intelligence Platform

[![CI](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/ci.yml/badge.svg)](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/ci.yml)
[![Secret Scan](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/secret-scan.yml)
[![CodeQL](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/codeql.yml/badge.svg)](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/codeql.yml)
![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)

C2Pro is an evidence-backed contract, project-controls and procurement intelligence platform for construction/infrastructure projects.

It connects documents and project state through a governed project model, one canonical hierarchical WBS, temporal/change intelligence, Health, relational Coherence, Alerts/HITL and traceable evidence.

## Current status — revalidated 2026-10-03

Do not infer product readiness from this README.

- **Product programme authority:** `validation/product/c2pro-master-product-control-v1.yaml`
- **Human product projection:** `docs/product/00-c2pro-master-product-control-v1.md`
- **Development execution authority:** `.c2pro/control/current.yaml` + `.c2pro/control/work-queue.yaml`
- **Architecture authority:** accepted ADRs under `docs/architecture/decisions/`
- **Current architecture synthesis:** `docs/architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md`

At this revalidated baseline, the full production end-user GOAL **#706 remains open**. The production acceptance harness is implemented, but a merged harness is not equivalent to an accepted production qualification. Product Control remains conservative until explicit evidence promotes lifecycle state.

## Architecture at a glance

```text
Browser
  │
  ▼
Next.js 16.3 / React 19.2 (Vercel)
  │  Clerk organization-scoped auth
  ▼
FastAPI 0.141 (Railway API)
  │
  ├── PostgreSQL / Supabase + RLS + pgvector
  ├── Redis
  ├── Celery Worker
  ├── Celery Scheduler
  ├── LangGraph + PostgreSQL checkpoints
  ├── Configured object storage (R2-compatible provider path)
  └── governed AI/provider adapters
```

Core architecture rules:

- project state is the intelligence boundary;
- one project → one canonical hierarchical WBS is the architectural invariant; complete one-root enforcement remains PARTIAL in Product Control;
- missing evidence is Unknown/null, never fabricated zero/green;
- Health, Coherence and Alerts are distinct signals;
- when HITL review is required, approval is an exact trusted-state commit boundary; policy-approved non-gated completions are a separate path;
- processing authority and checkpoint lineage are fenced across takeover/reprocess;
- CI/deployment/evidence do not self-promote Product Control.

See [Current Technical Architecture Baseline](./docs/architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md).

## Repository structure

```text
C2Pro/
├── apps/
│   ├── api/                  # FastAPI backend, workers, domain/runtime code
│   └── web/                  # Next.js frontend
├── docs/                     # canonical/supporting human documentation
│   ├── architecture/         # current baseline, ADRs, diagrams
│   ├── product/              # human Product Control projection/contracts
│   ├── runbooks/             # operational procedures
│   ├── testing/              # test strategy/inventories
│   ├── audits/               # dated audit evidence
│   └── archive/              # historical/superseded material
├── validation/               # machine control/validation contracts
├── .c2pro/                   # development control plane
├── infrastructure/           # infrastructure/migration/ops support
├── context/                  # non-canonical working/historical context
└── evidence/                 # bounded generated evidence
```

## Documentation

Start here:

- [Documentation authority](./docs/DOCUMENTATION_AUTHORITY.md)
- [Documentation index](./docs/README.md)
- [Architecture index](./docs/ARCHITECTURE_INDEX.md)
- [Architecture decisions](./docs/architecture/decisions/README.md)
- [Current architecture baseline](./docs/architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md)
- [Product programme control](./docs/product/00-c2pro-master-product-control-v1.md)
- [CI/CD runbook](./docs/runbooks/ci-cd-setup.md)
- [Documentation reconciliation audit](./docs/audits/DOCUMENTATION_RECONCILIATION_2026-10-01.md)

Older platform TDDs and roadmaps remain useful as history/supporting design, but they are not live product-status authorities.

## Local development

### Prerequisites

- Python 3.11+
- Node.js 22.x
- pnpm 10+
- Docker / Docker Compose for local infrastructure
- configured Clerk/Supabase/provider credentials as required by the selected flow

Before starting local infrastructure, copy the environment template and validate the
PostgreSQL password contract:

```bash
cp .env.example .env
python scripts/validate_local_postgres_password.py
docker compose up -d
```

### Backend

```bash
cd apps/api
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

### Frontend

```bash
cd apps/web
pnpm install
pnpm dev
```

### Tests

```bash
# backend
cd apps/api
pytest

# frontend
cd apps/web
pnpm test:all
```

The authoritative CI contract is `.github/workflows/ci.yml` and the current operational explanation is [docs/runbooks/ci-cd-setup.md](./docs/runbooks/ci-cd-setup.md).

## Security and trust

C2Pro treats the following as architectural invariants rather than optional hardening:

- tenant/RLS isolation;
- evidence provenance;
- exact human-review binding;
- stale-worker/checkpoint fencing;
- bounded secret-free qualification evidence;
- protected-main required checks;
- fail-closed handling of contradictory/insufficient evidence.

## License

Proprietary — © 2025–2026 C2Pro.
