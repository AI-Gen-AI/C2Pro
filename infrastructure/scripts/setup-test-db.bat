@echo off
REM Script para inicializar la base de datos de test en Windows

echo 🚀 Iniciando setup de base de datos de test...

REM Verificar si Docker está corriendo
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Docker no está corriendo
    exit /b 1
)

REM Detener contenedor anterior si existe
echo 🧹 Limpiando contenedores anteriores...
docker-compose -f docker-compose.test.yml down -v >nul 2>&1

REM Iniciar PostgreSQL
echo 🐘 Iniciando PostgreSQL...
docker-compose -f docker-compose.test.yml up -d

REM Esperar a que PostgreSQL esté listo
echo ⏳ Esperando a que PostgreSQL esté listo...
:wait_loop
timeout /t 2 >nul
docker-compose -f docker-compose.test.yml exec -T postgres-test pg_isready -U test -d c2pro_test >nul 2>&1
if errorlevel 1 goto wait_loop

echo ✅ PostgreSQL está listo

REM Aplicar migraciones
echo 🔧 Aplicando migraciones...
for %%f in (infrastructure\supabase\migrations\*.sql) do (
    echo   ➡️  Aplicando %%~nxf...
    docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -d c2pro_test < "%%f" 2>nul
)

echo.
echo ✅ Base de datos de test configurada!
echo.
echo 📊 Información de conexión:
echo   Host:     localhost
echo   Port:     5432
echo   Database: c2pro_test
echo   User:     test
echo   Password: test
echo.
echo 🧪 Para ejecutar los tests:
echo   cd apps\api
echo   pytest tests\security\ -v
echo.
echo 🛑 Para detener la base de datos:
echo   docker-compose -f docker-compose.test.yml down
