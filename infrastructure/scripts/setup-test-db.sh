#!/bin/bash
# ===========================================
# C2PRO - Test Database Setup Script
# ===========================================
# Sets up and initializes the test database

set -e

echo "================================"
echo "C2Pro - Test Database Setup"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}[ERROR]${NC} Docker is not running. Please start Docker first."
    exit 1
fi

# Start test database
echo -e "${GREEN}[1/4]${NC} Starting test database container..."
docker-compose -f docker-compose.test.yml up -d

# Wait for database to be ready
echo -e "${GREEN}[2/4]${NC} Waiting for database to be ready..."
sleep 5

# Check if database is healthy
if ! docker-compose -f docker-compose.test.yml ps | grep -q "healthy"; then
    echo -e "${YELLOW}[WARNING]${NC} Database may not be fully ready yet, waiting a bit more..."
    sleep 5
fi

# Run migrations
echo -e "${GREEN}[3/4]${NC} Running database migrations..."
cd apps/api
DATABASE_URL="postgresql://nonsuperuser:test@localhost:5433/c2pro_test" alembic upgrade head
cd ../..

# Verify setup
echo -e "${GREEN}[4/4]${NC} Verifying setup..."
docker-compose -f docker-compose.test.yml ps

echo ""
echo "================================"
echo -e "${GREEN}Test database ready!${NC}"
echo "================================"
echo ""
echo "Database connection:"
echo "  Host: localhost"
echo "  Port: 5433"
echo "  Database: c2pro_test"
echo "  User: nonsuperuser"
echo "  Password: test"
echo ""
echo "To run tests:"
echo "  cd apps/api"
echo "  pytest tests/e2e/security/ -v -m \"e2e and security\""
echo ""
echo "To stop the database:"
echo "  docker-compose -f docker-compose.test.yml down"
echo ""
