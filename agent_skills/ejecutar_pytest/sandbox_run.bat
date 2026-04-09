@echo off
REM Skill: ejecutar_pytest — Ejecuta tests en entorno aislado
REM Usage: sandbox_run.bat [target_path]

set TARGET=%1
if "%TARGET%"=="" set TARGET=tests

echo [PYTEST] Ejecutando tests en: %TARGET%
echo [PYTEST] Timestamp: %DATE% %TIME%

python -m pytest %TARGET% -v --tb=short --no-header --resultlog=.pytest-tmp/pytest_result.log 2>&1

set EXIT_CODE=%ERRORLEVEL%
echo [PYTEST] Exit code: %EXIT_CODE%
exit /b %EXIT_CODE%
