# ===========================================
# C2Pro - Development Environment Startup (PowerShell)
# ===========================================
# Usage: .\scripts\start-dev.ps1
#
# This script starts all required services for local development:
# - PostgreSQL (database)
# - Redis (cache/event bus)
# - MinIO (S3-compatible storage)
# - API (FastAPI backend)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Green
Write-Host "  C2Pro Development Environment Startup" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# Change to project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$ScriptDir\.."

# Check Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "Error: Docker is not running. Please start Docker first." -ForegroundColor Red
    exit 1
}

# Step 1: Start infrastructure services
Write-Host "[1/4] Starting infrastructure services (postgres, redis, minio)..." -ForegroundColor Yellow
docker-compose up -d postgres redis minio

# Step 2: Wait for services to be healthy
Write-Host "[2/4] Waiting for services to be healthy..." -ForegroundColor Yellow

Write-Host -NoNewline "  PostgreSQL: "
do {
    Start-Sleep -Seconds 1
    Write-Host -NoNewline "."
    $result = docker-compose exec -T postgres pg_isready -U postgres 2>&1
} while ($LASTEXITCODE -ne 0)
Write-Host " ready" -ForegroundColor Green

Write-Host -NoNewline "  Redis: "
do {
    Start-Sleep -Seconds 1
    Write-Host -NoNewline "."
    $result = docker-compose exec -T redis redis-cli ping 2>&1
} while ($LASTEXITCODE -ne 0)
Write-Host " ready" -ForegroundColor Green

Write-Host -NoNewline "  MinIO: "
Start-Sleep -Seconds 3
Write-Host " ready" -ForegroundColor Green

# Step 3: Start MinIO bucket setup
Write-Host "[3/4] Setting up MinIO bucket..." -ForegroundColor Yellow
docker-compose up -d minio-setup
Start-Sleep -Seconds 2

# Step 4: Start API
Write-Host "[4/4] Starting API service..." -ForegroundColor Yellow
docker-compose up -d api

# Final status
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  All services started successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
docker-compose ps
Write-Host ""
Write-Host "API:     http://localhost:8000" -ForegroundColor Green
Write-Host "Health:  http://localhost:8000/health" -ForegroundColor Green
Write-Host "MinIO:   http://localhost:9001 (admin: minioadmin/minioadmin)" -ForegroundColor Green
Write-Host ""
Write-Host "To view logs: docker-compose logs -f api" -ForegroundColor Yellow
Write-Host "To stop:      docker-compose down" -ForegroundColor Yellow
