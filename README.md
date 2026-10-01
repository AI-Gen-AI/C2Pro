# C2Pro — Contract & Project Intelligence Platform

[![CI](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/ci.yml/badge.svg)](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/ci.yml)
[![Secret Scan](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/secret-scan.yml)
[![Install Drift Guard](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/install-drift-guard.yml/badge.svg)](https://github.com/AI-Gen-AI/C2Pro/actions/workflows/install-drift-guard.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

> Continuous, evidence-backed contract, project-controls and procurement intelligence for complex project environments.

## Current engineering posture

C2Pro is beyond its original Sprint/Security-Foundation framing. The repository now contains:

- project-centric intelligence and typed ProjectGraph architecture;
- canonical Project Controls/WBS governance;
- Health / Coherence / change / alert / HITL surfaces;
- explicit Trusted-State Commit semantics (`persisted != trusted`);
- machine-backed Product Control and qualification evidence contracts;
- consolidated CI with security, coverage, integration, E2E and Docker gates;
- a landed synthetic production-acceptance harness.

**Important:** harness implementation/merge is not the same as production qualification. Current lifecycle truth is owned by Product Control and current evidence, not this README.

## Product model

The current architecture is project-first:

`Evidence → Project State → Canonical WBS / Project Controls → Health / Coherence / Change / Alerts / HITL → governed decisions`

Core invariants:

- evidence remains traceable to source;
- unknown/insufficient evidence is not coerced to zero;
- one project owns one canonical hierarchical WBS;
- pending AI output does not become canonical merely because it is persisted;
- consequential approval binds the exact reviewed candidate/version/hash.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         C2Pro                               │
├─────────────────────────────────────────────────────────────┤
│ Web       Next.js / Clerk / typed API / Playwright         │
│ API       FastAPI / Pydantic / SQLAlchemy / LangGraph      │
│ Data      PostgreSQL/Supabase + RLS / Redis                │
│ Control   Product Control YAML + guarded Markdown parity   │
│ CI        CI Status + gitleaks + Install Drift Guard       │
│ Runtime   Railway planes + Vercel frontend                 │
└─────────────────────────────────────────────────────────────┘
```

The current platform design is [TDD v4.2](./docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md).

## Repository structure

```text
c2pro/
├── apps/
│   ├── api/                  # FastAPI backend
│   └── web/                  # Next.js frontend
├── validation/
│   └── product/              # machine Product Control / qualification guards
├── docs/
│   ├── architecture/         # TDD, ADRs, diagrams
│   ├── product/              # Product Control projection / qualification contracts
│   ├── runbooks/             # operational procedures
│   ├── specifications/       # durable specifications
│   ├── testing/              # test strategy and registries
│   ├── planning/             # planning intent (not runtime proof)
│   └── audits/               # dated point-in-time evidence
├── evidence/                 # release / qualification evidence
├── context/                  # non-canonical working context
└── .github/workflows/        # CI, security, release, qualification
```

## Documentation and authority

Start with:

- [Documentation index](./docs/README.md)
- [Architecture index](./docs/ARCHITECTURE_INDEX.md)
- [TDD v4.2](./docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md)
- [ADR index](./docs/architecture/decisions/README.md)
- [Master Product Control](./docs/product/00-c2pro-master-product-control-v1.md)
- [Qualification evidence contract](./docs/product/qualification-evidence-contract-v1.md)
- [Production qualification runbook](./docs/product/production-qualification-operator-runbook.md)

Architecture/design documents do not override machine-backed Product Control lifecycle state.

## 🚀 Quick Start

### Sprint 1 - Backend Foundation (✅ Completado)

```bash
# 1. Configurar .env con tus credenciales de Supabase
cp .env.example .env
# Edita .env y añade tu DATABASE_URL

# 2. Opción A: Script automático (Windows)
.\infrastructure\scripts\init-backend.bat

# 2. Opción B: Script automático (Linux/Mac)
chmod +x infrastructure/scripts/init-backend.sh
./infrastructure/scripts/init-backend.sh

# 2. Opción C: Manual
cd apps/api
pip install -r requirements.txt
python setup.py
python dev.py
```

**Accede a:**

- API: http://localhost:8000
- Documentación: http://localhost:8000/docs
- Guía completa: [QUICK_START.md](./QUICK_START.md)

### Prerrequisitos

- Python 3.11+
- Cuenta en Supabase (free tier)
- Node.js 20+ (para frontend, próximo sprint)
- Docker & Docker Compose (opcional, para desarrollo local)

### 1. Clonar y configurar

```bash
git clone https://github.com/tu-usuario/c2pro.git
cd c2pro

# Copiar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

### 2. Iniciar servicios locales

```bash
# Validar el password PostgreSQL local y después iniciar servicios
python scripts/validate_local_postgres_password.py
docker-compose up -d

# O usar Supabase local
pnpm exec supabase start
```

### 3. Backend

```bash
cd apps/api

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate  # Windows

# Instalar dependencias

pip install -r requirements.txt

# Aplicar migraciones
alembic upgrade head

# Iniciar servidor
uvicorn src.main:app --reload
```

### 4. Frontend

```bash
cd apps/web

# Instalar dependencias
pnpm install

# Iniciar servidor de desarrollo
pnpm dev
```

### 5. Verificar

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 🧪 Tests

```bash
# Backend
cd apps/api
pytest

# Con coverage
pytest --cov=src --cov-report=html

# Frontend
cd apps/web
pnpm test
```

## 📊 Variables de Entorno

Ver `.env.example` para la lista completa. Las críticas son:

| Variable | Descripción |
|----------|-------------|

| `DATABASE_URL` | Connection string de PostgreSQL (Supabase o local) |
| `SUPABASE_URL` | URL de tu proyecto Supabase |
| `SUPABASE_ANON_KEY` | Key pública de Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Key de servicio (solo backend) |
| `ANTHROPIC_API_KEY` | API key de Claude |
| `UPSTASH_REDIS_URL` | URL de Redis |
| `R2_ACCOUNT_ID` | Account ID de Cloudflare |
| `R2_ACCESS_KEY_ID` | Access key de R2 |
| `R2_SECRET_ACCESS_KEY` | Secret key de R2 |

## 🔒 Seguridad

- **Multi-tenancy**: Row Level Security (RLS) en PostgreSQL
- **PII**: Anonymization antes de enviar a AI
- **Auth**: Supabase Auth con JWT
- **Secrets**: Variables de entorno, nunca en código

## 📚 Documentación

- [Índice de Documentación](./docs/README.md) - Punto de entrada oficial a la documentación
- [Quick Start](./QUICK_START.md) - Arranque local y modos de ejecución
- [Roadmap activo](./docs/planning/ROADMAP_v2.4.0.md) - Plan vigente del proyecto
- [Arquitectura](./docs/architecture/) - ADRs, diagramas y diseño técnico
- [Runbooks](./docs/runbooks/) - Operación, setup y procedimientos
- [Especificaciones](./docs/specifications/) - Documentación técnica y funcional
- [Testing](./docs/testing/) - Inventarios, backlog y estrategia de tests
- [Auditorías](./docs/audits/) - Revisiones estructurales y técnicas aún útiles
- [Histórico archivado](./docs/archive/) - Reportes cerrados, duplicados y material legacy

## 🧭 Significado de carpetas clave

- `apps/`: productos ejecutables (backend/frontend).
- `infrastructure/`: base de datos, migraciones y scripts operativos (todo lo infra).
- `supabase/`: workspace del Supabase CLI (config local + migrations para CLI).
- `docs/`: documentación canónica organizada por función y ciclo de vida.
- `context/`: working memory, notas operativas cortas y material no canónico.
- `sandbox/`: experimentos aislados que no deben tratarse como fuente oficial.
- `tests/`: suites globales y utilidades de testing.
- `evidence/`: evidencia generada (CTO gates, reportes, artefactos).
- `backups/`: backups locales/manuales (si se usan).

## 🛣️ Roadmap

### CTO Gates (Seguridad)

- [x] **Gate 1**: Multi-tenant Isolation (RLS) ✅
- [x] **Gate 2**: Identity Model (UNIQUE constraint) ✅
- [x] **Gate 3**: MCP Security (23/23 tests) ✅
- [x] **Gate 4**: Legal Traceability (clauses + FKs) ✅
- [ ] **Gate 5**: Coherence Score Formal (en progreso)
- [ ] **Gate 6**: Human-in-the-loop
- [ ] **Gate 7**: Observability
- [x] **Gate 8**: Document Security ✅

### Fases del Producto

- [x] **Fase 1**: Platform Foundation (Sprint 1) ✅
- [x] **Fase 1.5**: Security Foundation (Sprints P0) ✅
- [ ] **Fase 2**: Coherence Engine MVP (Sprint S2 - 65%)
- [ ] **Fase 3**: Copiloto de Compras
- [ ] **Fase 4**: Control de Ejecución

## 📄 Licencia

Propietario - © 2025-2026 C2Pro

## 🤝 Contribuir

Este es un proyecto privado. Contacta al equipo para colaborar.
