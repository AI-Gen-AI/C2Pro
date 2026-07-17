# Clean Python Bootstrap Runbook

Date: `2026-07-17`  
Scope: `Python Dependency Hygiene & Environment Bootstrap`

## Objective
Provide clean, reproducible guidelines to bootstrap the backend Python virtual environment from scratch, ensuring zero broken dependencies and passing security audits.

## 1. Clean Virtual Environment Creation
To avoid lingering orphaned packages (like legacy `supafunc` which conflicts with newer `httpx` versions), always create a completely fresh virtual environment:

```bash
# Navigate to the backend application directory
cd apps/api

# Delete any existing virtual environment directory
rm -rf .venv

# Create a fresh virtual environment using Python 3.11
python -m venv .venv

# Activate the virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Windows (CMD):
.venv\Scripts\activate.bat
# On Linux/macOS:
source .venv/bin/activate
```

## 2. Dependency Installation & Verification
Once active, upgrade package installer tools and install the single psycopg constraint and other requirements from scratch:

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install project requirements
pip install -r requirements.txt

# Verify the dependency graph has no conflicts
pip check

# Verify there are no known security vulnerabilities
pip-audit -r requirements.txt
```

## 3. Local Test Infrastructure Bootstrap
To prepare the database and Redis test services locally, run the bootstrap script:

```bash
# Starts Postgres-test (5433) and Redis-test (6380) locally
python scripts/bootstrap_test_infra.py --start-services --require-redis
```
