@echo off
REM C2Pro - Test Database Setup Script (Windows)
REM Sets up and initializes the test database

echo ================================
echo C2Pro - Test Database Setup
echo ================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running. Please start Docker first.
    exit /b 1
)

REM Start test database
echo [1/4] Starting test database container...
docker-compose -f docker-compose.test.yml up -d

REM Wait for database to be ready
echo [2/4] Waiting for database to be ready...
timeout /t 5 /nobreak >nul

REM Run migrations
echo [3/4] Running database migrations...
cd apps\api
set DATABASE_URL=postgresql://nonsuperuser:test@localhost:5433/c2pro_test
alembic upgrade head
cd ..\..

REM Verify setup
echo [4/4] Verifying setup...
docker-compose -f docker-compose.test.yml ps

echo.
echo ================================
echo Test database ready!
echo ================================
echo.
echo Database connection:
echo   Host: localhost
echo   Port: 5433
echo   Database: c2pro_test
echo   User: nonsuperuser
echo   Password: test
echo.
echo To run tests:
echo   cd apps\api
echo   pytest tests\e2e\security\ -v -m "e2e and security"
echo.
echo To stop the database:
echo   docker-compose -f docker-compose.test.yml down
echo.
