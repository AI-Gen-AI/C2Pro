@echo off
REM CE-22: Execute Migrations in Staging
REM Executes database migrations with full logging

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..\..
set LOG_DIR=%PROJECT_ROOT%\logs

echo ==================================
echo CE-22: Execute Migrations
echo ==================================
echo Started at: %date% %time%
echo.
echo WARNING: This will modify the staging database!
echo Press Ctrl+C to cancel, or
pause

REM Load environment variables
if exist "%PROJECT_ROOT%\.env.staging" (
    for /f "usebackq tokens=*" %%a in ("%PROJECT_ROOT%\.env.staging") do set %%a
)

REM Execute migrations
echo.
echo --- Executing Migrations ---
python "%PROJECT_ROOT%\infrastructure\supabase\run_migrations.py" --env staging --verbose --log-file "%LOG_DIR%\ce22_migration_execution.log" 2>&1 | tee "%LOG_DIR%\ce22_migration_console.log"

if %errorlevel% equ 0 (
    echo.
    echo √ Migrations completed successfully

    REM Verify schema version
    echo.
    echo --- Verifying Schema Version ---
    psql "%DATABASE_URL%" -c "SELECT * FROM alembic_version;" 2>&1 | tee "%LOG_DIR%\ce22_post_version.log"

    REM Capture post-migration state
    echo.
    echo --- Capturing Post-Migration State ---
    psql "%DATABASE_URL%" -f "%SCRIPT_DIR%\capture_db_state.sql" > "%LOG_DIR%\ce22_post_state.log" 2>&1

    echo.
    echo ==================================
    echo CE-22 Migration Complete!
    echo ==================================
    echo.
    echo Deliverables:
    echo   √ Migration log: %LOG_DIR%\ce22_migration_execution.log
    echo   √ Console log: %LOG_DIR%\ce22_migration_console.log
    echo   √ Post-state: %LOG_DIR%\ce22_post_state.log
    echo.
    echo Status: READY FOR CE-23 (RLS Verification^)
    echo Completed at: %date% %time%
) else (
    echo.
    echo × Migration FAILED
    echo Check logs: %LOG_DIR%\ce22_*.log
    echo.
    echo Consider rollback if needed
    exit /b 1
)

endlocal
