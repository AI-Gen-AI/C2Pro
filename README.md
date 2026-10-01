# C2Pro — Contract & Project Intelligence Platform

[![CI](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/ci.yml/badge.svg)](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/ci.yml)
[![Secret Scan](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/secret-scan.yml)
[![Install Drift Guard](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/install-drift-guard.yml/badge.svg)](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/install-drift-guard.yml)

> Continuous, evidence-backed contract, project-controls and procurement intelligence for complex project environments.

## What C2Pro is

C2Pro connects contractual evidence with project execution through a governed project model.

Current architectural chain:

`Evidence → Project State → Canonical WBS / Project Controls → Health / Coherence / Change / Alerts / HITL → governed decisions`

Core invariants:

- evidence remains traceable to real source material;
- unknown/insufficient evidence is represented honestly;
- one project owns one canonical hierarchical WBS;
- persisted AI output is not automatically trusted;
- consequential approval binds the exact reviewed candidate/version/hash;
- merge, deployment and production validation are separate lifecycle states.

## Architecture

| Layer | Current role |
|---|---|
| Web | Next.js, Clerk, typed API, Playwright |
| API | FastAPI, Pydantic, SQLAlchemy, LangGraph |
| Data | PostgreSQL/Supabase + RLS, Redis |
| Project intelligence | ProjectState, temporal/change model, ProjectGraph |
| Project Controls | canonical hierarchical WBS, linked domain planes |
| Trust | HITL + Trusted-State Commit |
| Product lifecycle control | `validation/product/` machine YAML + guarded Markdown projection |
| Development control | `.c2pro/control/` + bounded `.c2pro/work/` envelopes |
| CI | consolidated `CI Status`, secret and install-drift gates |
| Runtime | Railway service planes + Vercel frontend |

The current platform-wide design is [TDD v4.2](./docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md).

## Documentation

Start here:

1. [Documentation index](./docs/README.md)
2. [Architecture index](./docs/ARCHITECTURE_INDEX.md)
3. [TDD v4.2](./docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md)
4. [ADR index](./docs/architecture/decisions/README.md)
5. [Master Product Control](./docs/product/00-c2pro-master-product-control-v1.md)
6. [Development-control status pointer](./docs/MASTER_DEVELOPMENT_STATUS.md)
7. [Qualification evidence contract](./docs/product/qualification-evidence-contract-v1.md)
8. [Production qualification operator runbook](./docs/product/production-qualification-operator-runbook.md)

**Authority is scoped by concern.** Product lifecycle is machine-controlled under `validation/product/`; development execution is controlled under `.c2pro/`; architecture is governed by accepted ADRs/current TDD; runtime/merge truth comes from executable code, evidence and the live ruleset.

## Repository map

```text
c2pro/
├── apps/
│   ├── api/                  # FastAPI backend
│   └── web/                  # Next.js frontend
├── .c2pro/                   # canonical development-control hot state / work envelopes
├── validation/
│   └── product/              # machine Product Control / qualification guards
├── docs/
│   ├── architecture/         # TDD, ADRs, diagrams
│   ├── product/              # product-control and qualification contracts
│   ├── runbooks/             # operator procedures
│   ├── specifications/       # durable specifications
│   ├── testing/              # test strategy/registries
│   ├── planning/             # planning intent, not runtime proof
│   └── audits/               # dated point-in-time evidence
├── evidence/                 # release / qualification evidence
├── context/                  # non-canonical working context
└── .github/workflows/        # CI, security, release, qualification
```

## Local development

Use [QUICK_START.md](./QUICK_START.md) and app-specific setup docs for complete environment instructions.

Minimum toolchain:

- Python 3.11+
- Node.js / pnpm as pinned by repository configuration
- PostgreSQL/Supabase-compatible environment
- Redis where required by the selected flow
- Docker for the canonical local/test infrastructure workflows

Typical backend setup:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

Typical frontend setup:

```bash
pnpm install --frozen-lockfile
cd apps/web
pnpm dev
```

Do not copy production credentials into local configuration. Use the repository runbooks and example environment contracts.

## Testing

The consolidated CI graph is [`.github/workflows/ci.yml`](./.github/workflows/ci.yml).

Useful local entry points:

```bash
# backend
cd apps/api
python -m pytest

# frontend
cd apps/web
pnpm test
pnpm typecheck
pnpm lint
pnpm build
```

The active `main` ruleset and workflow definitions are authoritative for required merge checks.

## Production and release semantics

- Platform deploy and GitHub Release publication are distinct.
- Product qualification is a separate evidence-backed lifecycle.
- The production acceptance harness being present or merged does not itself prove a successful production journey.
- Failed qualification evidence must remain failed historical evidence.

See:

- [Release criteria](./docs/RELEASE_CRITERIA.md)
- [Release signoff policy](./docs/internal/RELEASE_SIGNOFF_POLICY.md)
- [Production qualification runbook](./docs/product/production-qualification-operator-runbook.md)

## Security

Key principles:

- multi-tenant fail-closed isolation;
- least privilege;
- no committed secrets;
- exact identity/approval binding for consequential operations;
- immutable/traceable evidence;
- no quality-gate or baseline manipulation to manufacture pass status.

Security-specific implementation and operator details live in current ADRs, runbooks and executable CI/security tests.

## Contributing / architecture changes

For a durable architecture change:

1. update or add an ADR;
2. update the current TDD if platform-wide;
3. update Product Control through its machine-backed workflow if **product lifecycle** changes;
4. reconcile `.c2pro` through the authorized Planner/Master flow if **development-control state** changes;
5. update affected runbooks/specs/tests;
6. preserve historical documents rather than rewriting history.

Documentation lifecycle rules: [`.claude/rules/DOCUMENTATION_STRUCTURE.md`](./.claude/rules/DOCUMENTATION_STRUCTURE.md).
