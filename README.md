# C2Pro - Contract Intelligence Platform

[![Tests](https://github.com/AI-Gen-AI/c2pro/actions/workflows/tests.yml/badge.svg)](https://github.com/AI-Gen-AI/c2pro/actions/workflows/tests.yml)
[![E2E Security](https://github.com/AI-Gen-AI/c2pro/actions/workflows/e2e-security-tests.yml/badge.svg)](https://github.com/AI-Gen-AI/c2pro/actions/workflows/e2e-security-tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: Proprietary](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

> Sistema de auditoría tridimensional (Contrato + Cronograma + Presupuesto) con IA para detectar incoherencias antes de que generen sobrecostes.

## 🎉 Estado Actual: Sprint S2 en Progreso (65%)

**CTO Gates 1-4 Validados** ✅ | **Security Foundation Production Ready**

- ✅ 19 tablas con RLS desplegadas en staging
- ✅ 42 tests de seguridad implementados
- ✅ Frontend type safety 95%
- 🟡 Sprint S2: Wireframes + Coherence Engine

### 🚀 Comenzar Ahora

**¿Primera vez aquí?** Lee la [Guía de Inicio Rápido](./QUICK_START.md) para poner en marcha el backend en 5 minutos.

**¿Desarrollas en Windows?** Revisa nuestra [Guía de Configuración para Windows](./docs/development/windows-setup.md) para evitar problemas comunes.

**Desarrollador?** Ve a [apps/api/README.md](./apps/api/README.md) para documentación técnica completa.

---

## 🎯 Problema que Resolvemos

El 15-30% de sobrecostes en proyectos de construcción e ingeniería se deben a desconexión entre:

- Lo que dice el **contrato**
- Lo que planifica el **cronograma**
- Lo que presupuesta el **plan económico**

C2Pro cruza automáticamente estos documentos y detecta incoherencias antes de que cuesten dinero.

## 🏗️ Arquitectura

```

┌─────────────────────────────────────────────────────────┐
│                    C2PRO MVP                            │
├─────────────────────────────────────────────────────────┤
│  Frontend: Next.js 14 + Tailwind + shadcn/ui (Vercel)  │
│  Backend: FastAPI + Pydantic v2 (Railway)              │
│  Database: Supabase PostgreSQL (RLS enabled)           │
│  Cache: Upstash Redis                                   │
│  Storage: Cloudflare R2                                 │
│  AI: Claude API (Sonnet)                                │
└─────────────────────────────────────────────────────────┘
```

## 📁 Estructura del Proyecto

```

c2pro/
├── apps/
│   ├── web/                  # Frontend Next.js
│   └── api/                  # Backend FastAPI
├── packages/                 # Shared packages (futuro)
├── infrastructure/           # Infraestructura (DB, scripts operativos)
├── docs/
│   ├── README.md             # Índice principal de documentación
│   ├── architecture/         # ADRs, diagramas y diseño técnico
│   ├── api/                  # OpenAPI y ejemplos de API
│   ├── specifications/       # Especificaciones técnicas y funcionales
│   ├── runbooks/             # Guías operativas y de entorno
│   ├── planning/             # Roadmap y planificación activa
│   ├── testing/              # Inventarios y estrategia de tests
│   ├── audits/               # Auditorías vigentes como referencia
│   ├── assets/               # Cronogramas y material de apoyo
│   └── archive/              # Históricos, duplicados y reportes cerrados
├── context/                  # Working memory no canónica
├── sandbox/                  # Experimentos aislados y prototipos
└── docker-compose.yml        # Desarrollo local
```

## 📚 Navegación de Documentación

- Índice principal: [docs/README.md](./docs/README.md)
- Política de working context: [context/README.md](./context/README.md)
- Quick start operativo: [QUICK_START.md](./QUICK_START.md)
- Arquitectura: [docs/architecture/](./docs/architecture/)
- Runbooks: [docs/runbooks/](./docs/runbooks/)
- Testing: [docs/testing/](./docs/testing/)
- Planning activo: [docs/planning/](./docs/planning/)
- Histórico archivado: [docs/archive/](./docs/archive/)

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
# Iniciar PostgreSQL y Redis locales
docker-compose up -d

# O usar Supabase local
npx supabase start
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
npm install

# Iniciar servidor de desarrollo
npm run dev
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
npm test
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
- [ ] **Gate 8**: Document Security

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
