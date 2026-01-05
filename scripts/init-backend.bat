@echo off
REM C2Pro - Backend Initialization Script (Windows)
REM Este script configura e inicia el backend automáticamente

echo ================================
echo C2Pro - Backend Setup
echo ================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo [ERROR] No se encontro el archivo .env
    echo.
    echo Por favor copia .env.example a .env y configura las variables:
    echo   1. DATABASE_URL
    echo   2. SUPABASE_URL
    echo   3. SUPABASE_ANON_KEY
    echo   4. SUPABASE_SERVICE_ROLE_KEY
    echo.
    pause
    exit /b 1
)

echo [1/4] Verificando Python...
python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado
    pause
    exit /b 1
)

echo.
echo [2/4] Navegando al directorio de la API...
cd apps\api

echo.
echo [3/4] Ejecutando setup...
python setup.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Setup fallido. Revisa los errores anteriores.
    pause
    exit /b 1
)

echo.
echo [4/4] Iniciando servidor de desarrollo...
echo.
echo ================================
echo Backend listo!
echo ================================
echo.
echo Accede a la API en:
echo   - API: http://localhost:8000
echo   - Docs: http://localhost:8000/docs
echo.
echo Presiona Ctrl+C para detener el servidor
echo.
pause

python dev.py
