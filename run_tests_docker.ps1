param(
  [string]$PyImage = "python:3.11",
  [string]$Network = "c2pro-test-network",
  [string]$DbHost = "c2pro-postgres-test",
  [string]$DbName = "c2pro_test",
  [string]$DbUser = "nonsuperuser",
  [string]$DbPass = "test",
  [string]$PytestArgs = "-vv"
)

$ErrorActionPreference = "Stop"

$root = (Get-Location).Path
$apiPath = Join-Path $root "apps/api"

$dbUrl = "postgresql+asyncpg://$DbUser`:$DbPass@$DbHost`:5432/$DbName"

docker run --rm `
  --network $Network `
  -v "${root}:/app" `
  -w "/app/apps/api" `
  $PyImage `
  bash -lc "pip install -r requirements.txt && DATABASE_URL='$dbUrl' pytest $PytestArgs"
