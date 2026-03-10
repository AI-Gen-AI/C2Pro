# C2Pro API - Backend

Backend de la plataforma C2Pro, construido con FastAPI, PostgreSQL (Supabase) y Python 3.11+.

## Document Navigation

- [Repository README](../../README.md)
- [Documentation index](../../docs/README.md)
- [Architecture index](../../docs/architecture/README.md)
- [API docs index](../../docs/api/README.md)
- [Runbooks index](../../docs/runbooks/README.md)
- [Testing docs index](../../docs/testing/README.md)
- [API tests README](./tests/README.md)

## 🚀 Quick Start

### 1. Configurar Variables de Entorno

```bash
# Desde la raíz del proyecto
cp .env.example .env
# Editar .env con tus credenciales de Supabase
```

**Variables críticas a configurar:**
- `DATABASE_URL`: Connection string de Supabase
- `SUPABASE_URL`: URL de tu proyecto Supabase
- `SUPABASE_ANON_KEY`: Anon key de Supabase
- `SUPABASE_SERVICE_ROLE_KEY`: Service role key de Supabase
- `JWT_SECRET_KEY`: Clave secreta para JWT (cambiar en producción)

### 2. Setup Inicial

```bash
cd apps/api
python setup.py
```

Este script:
- �
 Verifica la versión de Python
- �
 Valida el archivo .env
- �
 Instala dependencias
- �
 Ejecuta migraciones de base de datos
- �
 Crea directorios necesarios

### 3. Iniciar Servidor de Desarrollo

```bash
python dev.py
```

El servidor estará disponible en:
- **API**: http://localhost:8000
- **Documentación**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📦 Estructura del Proyecto

```
apps/api/
├── alembic/               # Migraciones de base de datos
│   ├── versions/          # Scripts de migración
│   └── env.py            # Configuración de Alembic
├── src/
│   ├── main.py           # Aplicación FastAPI principal
│   ├── config.py         # Configuración global
│   ├── core/             # Core funcionalidad
│   │   ├── database.py   # Setup de SQLAlchemy
│   │   ├── security.py   # Utilidades de seguridad
│   │   ├── middleware.py # Middlewares custom
│   │   └── exceptions.py # Excepciones custom
│   └── modules/          # Módulos de negocio
│       ├── auth/         # Autenticación y usuarios
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── service.py
│       │   └── router.py
│       ├── projects/     # Gestión de proyectos
│       └── documents/    # Gestión de documentos
├── tests/                # Tests
├── storage/              # Almacenamiento local (dev)
├── requirements.txt      # Dependencias Python
├── setup.py             # Script de setup
├── dev.py               # Script de desarrollo
└── migrate.py           # Helper de migraciones
```

## 🗄️ Base de Datos

### Gestión de Migraciones

```bash
# Aplicar todas las migraciones
python migrate.py upgrade

# Ver migración actual
python migrate.py current

# Ver historial
python migrate.py history

# Crear nueva migración
python migrate.py create "descripcion del cambio"

# Revertir última migración
python migrate.py downgrade
```

### Migraciones Supabase (SQL)

Desde la raiz del repo:
```bash
python infrastructure/supabase/run_migrations.py --env staging --dry-run
python infrastructure/supabase/run_migrations.py --env staging
```

### Modelos Actuales (Sprint 1)

- **Tenant**: Organizaciones (multi-tenancy)
- **User**: Usuarios del sistema
- **Project**: Proyectos de construcción

## 🔐 Autenticación

El sistema usa JWT tokens para autenticación:

1. **Registro**: `POST /api/v1/auth/register`
2. **Login**: `POST /api/v1/auth/login`
3. **Obtener usuario actual**: `GET /api/v1/auth/me`

### Ejemplo de uso:

```python
import requests

# Registro
response = requests.post("http://localhost:8000/api/v1/auth/register", json={
    "company_name": "Mi Empresa",
    "email": "usuario@ejemplo.com",
    "password": "Password123!",
    "password_confirm": "Password123!",
    "first_name": "Juan",
    "last_name": "Pérez",
    "accept_terms": True
})

tokens = response.json()["tokens"]
access_token = tokens["access_token"]

# Usar token en requests
headers = {"Authorization": f"Bearer {access_token}"}
projects = requests.get("http://localhost:8000/api/v1/projects", headers=headers)
```

## 🛠️ Desarrollo

### Instalar Dependencias

```bash
pip install -r requirements.txt
```

### Ejecutar Tests

```bash
pytest
pytest --cov=src tests/  # Con coverage
```

### Linting y Formato

```bash
# Formato con black
black src/

# Linting con ruff
ruff check src/

# Type checking con mypy
mypy src/
```

## 📋 Endpoints Disponibles (Sprint 1)

### Autenticación (`/api/v1/auth`)
- `POST /register` - Registrar nuevo usuario y empresa
- `POST /login` - Login con email/password
- `POST /refresh` - Refrescar access token
- `GET /me` - Obtener usuario actual
- `PUT /me` - Actualizar perfil
- `POST /logout` - Logout
- `POST /change-password` - Cambiar contraseña

### Proyectos (`/api/v1/projects`)
- `GET /` - Listar proyectos (paginado)
- `POST /` - Crear proyecto
- `GET /stats` - Estadísticas de proyectos
- `GET /{id}` - Obtener proyecto
- `PUT /{id}` - Actualizar proyecto
- `DELETE /{id}` - Eliminar proyecto
- `PATCH /{id}/status` - Actualizar estado

## 🔧 Configuración

### Variables de Entorno Críticas

```bash
# Base de datos
DATABASE_URL=postgresql://postgres.<project_ref>:[PASSWORD]@aws-<region>.pooler.supabase.com:6543/postgres
# Directo (si necesitas conexion directa)
# DATABASE_URL=postgresql://postgres:[PASSWORD]@db.<project>.supabase.co:5432/postgres
# Supabase local (CLI)
# DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
# Docker compose (PostgreSQL local)
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/c2pro

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# JWT
JWT_SECRET_KEY=your-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

### Opcionales (para funcionalidad completa)

```bash
# Redis (cache)
REDIS_URL=redis://localhost:6379

# Anthropic (AI)
ANTHROPIC_API_KEY=sk-ant-...

# Storage (R2/S3)
STORAGE_PROVIDER=local  # local, r2, s3
```

## 🚨 Troubleshooting

### Error de conexión a base de datos

1. Verifica que `DATABASE_URL` esté correcta
2. Asegúrate de tener acceso a la base de datos de Supabase
3. Revisa que la IP esté permitida en Supabase

### Error al ejecutar migraciones

```bash
# Resetear migraciones (CUIDADO: elimina datos)
alembic downgrade base
alembic upgrade head
```

### Puerto 8000 ya en uso

```bash
# Matar proceso en el puerto
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

## 📚 Recursos

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Alembic Docs](https://alembic.sqlalchemy.org/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Supabase Docs](https://supabase.com/docs)
- [C2Pro architecture docs](../../docs/architecture/README.md)
- [C2Pro runbooks](../../docs/runbooks/README.md)
- [C2Pro testing docs](../../docs/testing/README.md)

## 🎯 Próximos Pasos (Roadmap)

- [ ] Módulo de Documentos (upload, parsing)
- [ ] Módulo de Análisis (coherencia)
- [ ] Extracción de Stakeholders
- [ ] Generación de WBS/BOM
- [ ] Tests unitarios e integración
- [ ] CI/CD con GitHub Actions
- [ ] Deployment en producción

## 📝 Notas

- El sistema implementa **multi-tenancy** completo con aislamiento de datos
- Todos los endpoints protegidos requieren autenticación JWT
- Los logs están estructurados con `structlog`
- El middleware de tenant isolation es **crítico** para seguridad
