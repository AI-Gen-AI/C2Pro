#!/bin/bash
# =====================================================
# C2Pro - pgTAP Test Runner
# =====================================================
# Version: 2.4.0
# Date: 2026-01-13
#
# This script runs the pgTAP security tests to verify
# multi-tenant isolation and identity constraints.
#
# Prerequisites:
#   1. PostgreSQL client (psql) installed
#   2. pgTAP extension installed in database
#   3. DATABASE_URL environment variable set
#
# Usage:
#   ./infrastructure/supabase/tests/run_tests.sh
#
# Or with explicit DATABASE_URL:
#   DATABASE_URL="postgresql://..." ./infrastructure/supabase/tests/run_tests.sh
# =====================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "========================================="
echo "C2PRO - PGTAP SECURITY TESTS"
echo "========================================="
echo ""

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}ERROR: DATABASE_URL environment variable is not set${NC}"
    echo ""
    echo "Please set it with:"
    echo "  export DATABASE_URL=\"postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres\""
    echo ""
    exit 1
fi

echo -e "${BLUE}Database URL:${NC} ${DATABASE_URL%%@*}@***"
echo ""

# Check if psql is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}ERROR: psql is not installed${NC}"
    echo ""
    echo "Install PostgreSQL client:"
    echo "  macOS: brew install postgresql"
    echo "  Ubuntu: sudo apt install postgresql-client"
    echo "  Windows: https://www.postgresql.org/download/windows/"
    echo ""
    exit 1
fi

# Check if pgTAP extension is available
echo -e "${YELLOW}Step 1/3: Checking pgTAP extension...${NC}"
PGTAP_INSTALLED=$(psql "$DATABASE_URL" -tAc "SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'pgtap';")

if [ "$PGTAP_INSTALLED" -eq "0" ]; then
    echo -e "${RED}ERROR: pgTAP extension is not available in your database${NC}"
    echo ""
    echo "For Supabase Pro/Enterprise, pgTAP should be available by default."
    echo "For self-hosted PostgreSQL, install with:"
    echo "  git clone https://github.com/theory/pgtap.git"
    echo "  cd pgtap"
    echo "  make && make install"
    echo ""
    exit 1
fi

# Enable pgTAP extension
echo -e "${GREEN}pgTAP extension is available${NC}"
echo -e "${YELLOW}Step 2/3: Enabling pgTAP extension...${NC}"
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS pgtap;" > /dev/null 2>&1
echo -e "${GREEN}pgTAP extension enabled${NC}"
echo ""

# Run tests
echo -e "${YELLOW}Step 3/3: Running security tests...${NC}"
echo ""
echo "========================================="
echo "TEST SUITE: Multi-Tenant Isolation"
echo "========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the test file
TEST_FILE="$SCRIPT_DIR/01_tenant_isolation.sql"

if [ ! -f "$TEST_FILE" ]; then
    echo -e "${RED}ERROR: Test file not found: $TEST_FILE${NC}"
    exit 1
fi

# Execute the test and capture output
TEST_OUTPUT=$(psql "$DATABASE_URL" -f "$TEST_FILE" 2>&1)
TEST_EXIT_CODE=$?

# Display output
echo "$TEST_OUTPUT"
echo ""

# Parse results
if echo "$TEST_OUTPUT" | grep -q "All tests successful"; then
    TESTS_PASSED=$(echo "$TEST_OUTPUT" | grep -oP '\d+(?= tests)' | head -1)
    echo "========================================="
    echo -e "${GREEN}✓ ALL TESTS PASSED ($TESTS_PASSED/15)${NC}"
    echo "========================================="
    echo ""
    echo -e "${GREEN}CTO Gate 1 (Isolation): VERIFIED${NC}"
    echo -e "${GREEN}CTO Gate 2 (Identity): VERIFIED${NC}"
    echo ""
    echo "Your database is production-ready for multi-tenant deployment."
    echo ""
    exit 0
elif [ $TEST_EXIT_CODE -ne 0 ]; then
    echo "========================================="
    echo -e "${RED}✗ TESTS FAILED${NC}"
    echo "========================================="
    echo ""
    echo -e "${RED}CTO Gates NOT PASSED${NC}"
    echo ""
    echo "Review the output above to identify which tests failed."
    echo "Common issues:"
    echo "  1. RLS not enabled on tables"
    echo "  2. Missing RLS policies"
    echo "  3. Incorrect JWT claims configuration"
    echo "  4. Missing UNIQUE(tenant_id, email) constraint"
    echo ""
    echo "Run validation script first:"
    echo "  psql \$DATABASE_URL -f infrastructure/supabase/scripts/validate_rls.sql"
    echo ""
    exit 1
else
    # Partial success
    echo "========================================="
    echo -e "${YELLOW}⚠ SOME TESTS FAILED${NC}"
    echo "========================================="
    echo ""
    echo "Review the output above to identify which tests failed."
    echo ""
    exit 1
fi
