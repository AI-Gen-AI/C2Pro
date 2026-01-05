# C2Pro - Contract Intelligence Platform

> Sistema de auditoría tridimensional (Contrato + Cronograma + Presupuesto) con IA para detectar incoherencias antes de que generen sobrecostes.

## 🎉 Estado Actual: Sprint 1 Completado ✅

**Backend MVP funcional** con autenticación, gestión de proyectos y base de datos configurada.

### 🚀 Comenzar Ahora

**¿Primera vez aquí?** Lee la [Guía de Inicio Rápido](./QUICK_START.md) para poner en marcha el backend en 5 minutos.

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
│   ├── web/              # Frontend Next.js
│   └── api/              # Backend FastAPI
├── packages/             # Shared packages (futuro)
├── infrastructure/       # Supabase migrations, scripts
├── docs/                 # Documentación técnica
└── docker-compose.yml    # Desarrollo local
```

## 🚀 Quick Start

### Sprint 1 - Backend Foundation (✅ Completado)

```bash
# 1. Configurar .env con tus credenciales de Supabase
cp .env.example .env
# Edita .env y añade tu DATABASE_URL

# 2. Opción A: Script automático (Windows)
.\scripts\init-backend.bat

# 2. Opción B: Script automático (Linux/Mac)
chmod +x scripts/init-backend.sh
./scripts/init-backend.sh

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
| `SUPABASE_URL` | URL de tu proyecto Supabase |
| `SUPABASE_ANON_KEY` | Key pública de Supabase |
| `SUPABASE_SERVICE_KEY` | Key de servicio (solo backend) |
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

- [Arquitectura](docs/architecture/README.md)
- [API Reference](docs/api/README.md)
- [Runbooks](docs/runbooks/README.md)
- [ADRs](docs/architecture/decisions/README.md)

## 🛣️ Roadmap

- [x] **Fase 1**: Auditoría Tridimensional (MVP)
- [ ] **Fase 2**: Copiloto de Compras
- [ ] **Fase 3**: Control de Ejecución
- [ ] **Fase 4**: Integraciones (Procore, SAP)

## 📄 Licencia

Propietario - © 2024 C2Pro

## 🤝 Contribuir

Este es un proyecto privado. Contacta al equipo para colaborar.