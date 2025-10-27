#!/bin/bash
# ============================================================================
# Quick test runner for conversation_orchestrator with PostgreSQL
# ============================================================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Conversation Orchestrator Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Check PostgreSQL
echo -e "${YELLOW}[1/5] Checking PostgreSQL...${NC}"
if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${RED}✗ PostgreSQL is NOT running${NC}"
    echo -e "${YELLOW}Please start PostgreSQL:${NC}"
    echo "  sudo service postgresql start"
    exit 1
fi

# Step 2: Check if database exists
echo -e "${YELLOW}[2/5] Checking test database...${NC}"
if psql -U postgres -h localhost -lqt | cut -d \| -f 1 | grep -qw bot_framework_test; then
    echo -e "${GREEN}✓ Database 'bot_framework_test' exists${NC}"
else
    echo -e "${RED}✗ Database 'bot_framework_test' does NOT exist${NC}"
    echo -e "${YELLOW}Creating database...${NC}"
    createdb -U postgres -h localhost bot_framework_test || {
        echo -e "${RED}Failed to create database. Please create manually:${NC}"
        echo "  createdb -U postgres -h localhost bot_framework_test"
        exit 1
    }
    echo -e "${GREEN}✓ Database created${NC}"
fi

# Step 3: Set environment variable
echo -e "${YELLOW}[3/5] Setting environment...${NC}"
export TEST_DATABASE_URL="postgresql+psycopg2://postgres:admin@localhost:5432/bot_framework_test"
echo -e "${GREEN}✓ TEST_DATABASE_URL set${NC}"

# Step 4: Quick validation test (models + parser)
echo -e "${YELLOW}[4/5] Running quick validation (62 tests)...${NC}"
python -m pytest test/conversation_orchestrator/test_models.py test/conversation_orchestrator/test_parser.py -v --tb=line -q 2>&1 | tail -5

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}✓ Quick validation passed${NC}"
else
    echo -e "${RED}✗ Quick validation failed${NC}"
    exit 1
fi

# Step 5: Run full test suite
echo -e "${YELLOW}[5/5] Running FULL test suite (123 tests)...${NC}"
echo ""
echo -e "${BLUE}========================================${NC}"
echo ""

python test/conversation_orchestrator/run_tests.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✓ ALL TESTS PASSED${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  ✗ SOME TESTS FAILED${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi
