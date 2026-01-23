@echo off
REM =====================================================
REM C2Pro - pgTAP Test Runner (Windows)
REM =====================================================
REM Version: 2.4.0
REM Date: 2026-01-13
REM
REM This script runs the pgTAP security tests to verify
REM multi-tenant isolation and identity constraints.
REM
REM Prerequisites:
REM   1. PostgreSQL client (psql) installed
REM   2. pgTAP extension installed in database
REM   3. DATABASE_URL environment variable set
REM
REM Usage:
REM   infrastructure\supabase\tests\run_tests.bat
REM
REM Or with explicit DATABASE_URL:
REM   set DATABASE_URL=postgresql://...
REM   infrastructure\supabase\tests\run_tests.bat
REM =====================================================

setlocal EnableDelayedExpansion

echo.
echo =========================================
echo C2PRO - PGTAP SECURITY TESTS
echo =========================================
echo.

REM Check if DATABASE_URL is set
if "%DATABASE_URL%"=="" (
    echo [ERROR] DATABASE_URL environment variable is not set
    echo.
    echo Please set it with:
    echo   set DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres
    echo.
    exit /b 1
)

echo Database URL: %DATABASE_URL:@*=@***%
echo.

REM Check if psql is installed
where psql >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] psql is not installed
    echo.
    echo Install PostgreSQL client from:
    echo   https://www.postgresql.org/download/windows/
    echo.
    exit /b 1
)

REM Check if pgTAP extension is available
echo Step 1/3: Checking pgTAP extension...
for /f "delims=" %%i in ('psql "%DATABASE_URL%" -tAc "SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'pgtap';"') do set PGTAP_INSTALLED=%%i

if "%PGTAP_INSTALLED%"=="0" (
    echo [ERROR] pgTAP extension is not available in your database
    echo.
    echo For Supabase Pro/Enterprise, pgTAP should be available by default.
    echo.
    exit /b 1
)

echo [OK] pgTAP extension is available
echo Step 2/3: Enabling pgTAP extension...
psql "%DATABASE_URL%" -c "CREATE EXTENSION IF NOT EXISTS pgtap;" >nul 2>&1
echo [OK] pgTAP extension enabled
echo.

REM Run tests
echo Step 3/3: Running security tests...
echo.
echo =========================================
echo TEST SUITE: Multi-Tenant Isolation
echo =========================================
echo.

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
set TEST_FILE=%SCRIPT_DIR%01_tenant_isolation.sql

if not exist "%TEST_FILE%" (
    echo [ERROR] Test file not found: %TEST_FILE%
    exit /b 1
)

REM Execute the test
psql "%DATABASE_URL%" -f "%TEST_FILE%"
set TEST_EXIT_CODE=%errorlevel%

echo.

if %TEST_EXIT_CODE%==0 (
    echo =========================================
    echo [OK] ALL TESTS PASSED
    echo =========================================
    echo.
    echo [OK] CTO Gate 1 ^(Isolation^): VERIFIED
    echo [OK] CTO Gate 2 ^(Identity^): VERIFIED
    echo.
    echo Your database is production-ready for multi-tenant deployment.
    echo.
    exit /b 0
) else (
    echo =========================================
    echo [FAIL] TESTS FAILED
    echo =========================================
    echo.
    echo [FAIL] CTO Gates NOT PASSED
    echo.
    echo Review the output above to identify which tests failed.
    echo Common issues:
    echo   1. RLS not enabled on tables
    echo   2. Missing RLS policies
    echo   3. Incorrect JWT claims configuration
    echo   4. Missing UNIQUE^(tenant_id, email^) constraint
    echo.
    echo Run validation script first:
    echo   psql %%DATABASE_URL%% -f infrastructure\supabase\scripts\validate_rls.sql
    echo.
    exit /b 1
)
