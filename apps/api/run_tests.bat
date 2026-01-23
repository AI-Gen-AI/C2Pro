@echo off
REM Script para ejecutar tests de seguridad con PostgreSQL

echo Configurando variables de entorno...
set DATABASE_URL=postgresql://test:test@localhost:5433/c2pro_test
set ENVIRONMENT=test
set JWT_SECRET_KEY=test-secret-key-min-32-chars-required-for-testing-purposes-only

echo.
echo Ejecutando tests de seguridad...
echo.

python -m pytest tests/security/ -v --tb=short

echo.
echo Tests completados.
