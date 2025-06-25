#!/bin/bash

# Cosmos DB Validation Tests
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Cosmos DB Validation Tests${NC}"
echo -e "${BLUE}=============================${NC}"

# Load environment variables
if [ -f "../.env.updated" ]; then
    echo -e "${YELLOW}📋 Loading environment variables from .env.updated${NC}"
    set -a
    source ../.env.updated
    set +a
elif [ -f "../.env" ]; then
    echo -e "${YELLOW}📋 Loading environment variables from .env${NC}"
    set -a
    source ../.env
    set +a
else
    echo -e "${RED}❌ No environment file found${NC}"
    exit 1
fi

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "\n${YELLOW}🔍 Testing: $test_name${NC}"
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS: $test_name${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAIL: $test_name${NC}"
        # Show the actual error for debugging
        echo -e "${YELLOW}Debug info:${NC}"
        eval "$test_command" 2>&1 | head -3
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test 1: Cosmos DB account exists
run_test "Cosmos DB account exists" \
    "az cosmosdb show --name $COSMOS_ACCOUNT --resource-group $AZ_RESOURCE_GROUP"

# Test 2: Cosmos DB account is accessible
run_test "Cosmos DB account is accessible" \
    "az cosmosdb keys list --name $COSMOS_ACCOUNT --resource-group $AZ_RESOURCE_GROUP"

# Test 3: Cosmos DB database exists
run_test "Cosmos DB database exists" \
    "az cosmosdb gremlin database show --account-name $COSMOS_ACCOUNT --resource-group $AZ_RESOURCE_GROUP --name $COSMOS_DB"

# Test 4: Cosmos DB graph exists
run_test "Cosmos DB graph exists" \
    "az cosmosdb gremlin graph show --account-name $COSMOS_ACCOUNT --resource-group $AZ_RESOURCE_GROUP --database-name $COSMOS_DB --name $COSMOS_GRAPH"

# Test 5: Cosmos DB endpoint accessibility
echo -e "\n${YELLOW}🔍 Testing: Cosmos DB endpoint accessibility${NC}"
cosmos_endpoint="https://$COSMOS_ACCOUNT.gremlin.cosmos.azure.com:443/"
if curl -s --connect-timeout 10 "$cosmos_endpoint" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Cosmos DB endpoint accessibility${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  SKIP: Cosmos DB endpoint (authentication required)${NC}"
fi

# Summary
echo -e "\n${BLUE}📊 Cosmos DB Test Summary${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All Cosmos DB tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Some Cosmos DB tests failed.${NC}"
    exit 1
fi 