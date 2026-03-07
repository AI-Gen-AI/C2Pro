#!/bin/bash
# ===========================================
# C2Pro - Development Environment Startup
# ===========================================
# Usage: ./scripts/start-dev.sh
#
# This script starts all required services for local development:
# - PostgreSQL (database)
# - Redis (cache/event bus)
# - MinIO (S3-compatible storage)
# - API (FastAPI backend)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  C2Pro Development Environment Startup${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Step 1: Start infrastructure services
echo -e "${YELLOW}[1/4] Starting infrastructure services (postgres, redis, minio)...${NC}"
docker-compose up -d postgres redis minio

# Step 2: Wait for services to be healthy
echo -e "${YELLOW}[2/4] Waiting for services to be healthy...${NC}"
echo -n "  PostgreSQL: "
until docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e "${GREEN}ready${NC}"

echo -n "  Redis: "
until docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e "${GREEN}ready${NC}"

echo -n "  MinIO: "
sleep 3  # MinIO needs a moment
until docker-compose exec -T minio curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e "${GREEN}ready${NC}"

# Step 3: Start MinIO bucket setup
echo -e "${YELLOW}[3/4] Setting up MinIO bucket...${NC}"
docker-compose up -d minio-setup
sleep 2

# Step 4: Start API
echo -e "${YELLOW}[4/4] Starting API service...${NC}"
docker-compose up -d api

# Final status
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  All services started successfully!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
docker-compose ps
echo ""
echo -e "API:     ${GREEN}http://localhost:8000${NC}"
echo -e "Health:  ${GREEN}http://localhost:8000/health${NC}"
echo -e "MinIO:   ${GREEN}http://localhost:9001${NC} (admin: minioadmin/minioadmin)"
echo ""
echo -e "To view logs: ${YELLOW}docker-compose logs -f api${NC}"
echo -e "To stop:      ${YELLOW}docker-compose down${NC}"
