# C2Pro - Quick Start Guide 🚀

Guía rápida para poner en marcha el backend de C2Pro en **menos de 5 minutos**.

## �
 Prerrequisitos

- [x] Python 3.11+ instalado
- [x] Cuenta de Supabase creada
- [x] Proyecto de Supabase configurado
- [x] Dependencias de anonimización AI (si vas a correr tests/IA): `spacy`, `presidio-analyzer`, `presidio-anonymizer`

## 🔧 Paso 1: Obtener Contraseña de Base de Datos

1. Ve a tu proyecto Supabase: https://supabase.com/dashboard/project/your-project-ref
2. Navega a: **Settings** -> **Database**
3. En **Connection string**, elige **URI**:
   - Recomendado: **Pooler** (pgbouncer, puerto 6543) para Windows o redes restrictivas.
   - Alternativa: **Direct** (puerto 5432) si necesitas conexion directa.
4. Usa el formato que corresponda:
   ```
   postgresql://postgres:[PASSWORD]@aws-<region>.pooler.supabase.com:6543/postgres
   postgresql://postgres:[PASSWORD]@db.<project>.supabase.co:5432/postgres
   ```
5. Actualiza `DATABASE_URL` en `.env` (usa `.env.example` como base).

Opcional (Supabase local):
- Ejecuta `supabase status` y copia `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` y `DATABASE_URL` (localhost:54322).
## 🚀 Paso 2: Inicializar Backend (Opción A - Automático)

### Windows:
```bash
.\scripts\init-backend.bat
```

### Linux/Mac:
```bash
chmod +x scripts/init-backend.sh
./scripts/init-backend.sh
```

Este script hace todo automáticamente:
- �
 Verifica Python
- �
 Instala dependencias
- �
 Ejecuta migraciones
- �
 Inicia el servidor

## 🚀 Paso 2: Inicializar Backend (Opción B - Manual)

Si prefieres hacerlo paso a paso:

```bash
# 1. Instalar dependencias
cd apps/api
pip install -r requirements.txt

# 2. Ejecutar setup (crea DB, migraciones, etc.)
python setup.py

# 3. Iniciar servidor de desarrollo
python dev.py
```

## 🚀 Paso 2: Inicializar Backend (Opción C - Con Make)

Si tienes `make` instalado:

```bash
# Setup inicial
make setup

# Configurar .env con tu password de Supabase
# Editar línea 29 de .env

# Inicializar (migraciones + setup)
make backend-init

# Iniciar servidor
make backend-dev
```

## 🎉 ¡Listo! Backend Corriendo

Si todo funcionó, deberías ver:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Accede a:

- **API**: http://localhost:8000
- **Documentación Interactiva**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🧪 Probar la API

### 1. Registrar un usuario

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Mi Empresa",
    "email": "usuario@ejemplo.com",
    "password": "Password123!",
    "password_confirm": "Password123!",
    "first_name": "Juan",
    "last_name": "Pérez",
    "accept_terms": true
  }'
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "usuario@ejemplo.com",
    "password": "Password123!"
  }'
```

Copia el `access_token` de la respuesta.

### 3. Crear un proyecto

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TU_ACCESS_TOKEN" \
  -d '{
    "name": "Proyecto de Prueba",
    "description": "Mi primer proyecto",
    "project_type": "construction",
    "estimated_budget": 100000,
    "currency": "EUR"
  }'
```

### 4. Listar proyectos

```bash
curl http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer TU_ACCESS_TOKEN"
```

## 📚 Comandos Útiles

### Gestión de Base de Datos

```bash
# Ver estado de migraciones
python apps/api/migrate.py current

# Ver historial
python apps/api/migrate.py history

# Crear nueva migración
python apps/api/migrate.py create "descripcion del cambio"

# Aplicar migraciones
python apps/api/migrate.py upgrade
```

### Migraciones Supabase (SQL)

```bash
# Ejecutar migraciones SQL (local/staging/production)
python infrastructure/supabase/run_migrations.py --env local
python infrastructure/supabase/run_migrations.py --env staging --dry-run
```

### Con Make

```bash
# Ver todos los comandos
make help

# Ver estado de migraciones
make db-migrate-status

# Crear migración
make db-migrate-create MSG="descripcion"

# Aplicar migraciones
make db-migrate
```

## 🔍 Verificar que Todo Funciona

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Respuesta esperada:
```json
{
  "status": "ok",
  "app": "C2Pro API",
  "version": "1.0.0",
  "environment": "development"
}
```

### 2. Verificar Base de Datos

En Supabase Dashboard → **Table Editor**, deberías ver las tablas:
- �
 `tenants`
- �
 `users`
- �
 `projects`

### 3. OpenAPI Docs

Abre http://localhost:8000/docs en tu navegador y verás:
- 📝 Documentación interactiva
- 🧪 Probador de endpoints
- 📖 Schemas de datos

## 🐛 Troubleshooting

### Error: "Database not initialized"

**Solución:**
```bash
cd apps/api
python setup.py
```

### Error: "Invalid credentials"

**Solución:** Verifica que `DATABASE_URL` en `.env` tenga la contraseña correcta.

### Error: "Module not found"


### Error: "spacy/presidio_* not found"

**Solución (tests/IA):**
```bash
pip install spacy presidio-analyzer presidio-anonymizer
```

**Solución:**
```bash
cd apps/api
pip install -r requirements.txt
```

### Puerto 8000 en uso

**Windows:**
```bash
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Linux/Mac:**
```bash
lsof -ti:8000 | xargs kill -9
```

## 📖 Documentación Adicional

- **Backend README**: `apps/api/README.md`
- **Roadmap Completo**: `docs/ROADMAP_v2.3.0.md`
- **Sprint Plan**: `docs/SPRINT_1_PLAN.md`

## 🎯 Próximos Pasos

Ahora que el backend está funcionando:

1. �
 Backend corriendo ← **Estás aquí**
2. ⬜ Configurar Frontend (Next.js)
3. ⬜ Implementar módulo de Documentos
4. ⬜ Implementar análisis de coherencia
5. ⬜ Deploy a producción

---

**¿Problemas?** Revisa los logs en la terminal donde ejecutaste el servidor.

**¿Necesitas ayuda?** Consulta `apps/api/README.md` para documentación detallada.
