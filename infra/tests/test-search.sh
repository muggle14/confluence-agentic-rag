#!/bin/bash

# Azure AI Search Validation Tests
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Azure AI Search Validation Tests${NC}"
echo -e "${BLUE}===================================${NC}"

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

# Test 1: Azure AI Search service exists
run_test "Azure AI Search service exists" \
    "az search service show --name $SEARCH_SERVICE --resource-group $AZ_RESOURCE_GROUP"

# Test 2: Azure AI Search service is accessible
run_test "Azure AI Search service is accessible" \
    "az search admin-key show --service-name $SEARCH_SERVICE --resource-group $AZ_RESOURCE_GROUP"

# Test 3: Azure AI Search endpoint connectivity
echo -e "\n${YELLOW}🔍 Testing: Azure AI Search endpoint connectivity${NC}"
search_endpoint="https://$SEARCH_SERVICE.search.windows.net/indexes?api-version=2023-11-01"
if curl -s -X GET "$search_endpoint" -H "api-key: $SEARCH_KEY" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Azure AI Search endpoint connectivity${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Azure AI Search endpoint connectivity${NC}"
    echo -e "${YELLOW}Debug info:${NC}"
    curl -s -X GET "$search_endpoint" -H "api-key: $SEARCH_KEY" 2>&1 | head -3
    ((TESTS_FAILED++))
fi

# Test 4: List indexes (should be empty initially)
echo -e "\n${YELLOW}🔍 Testing: List indexes${NC}"
if curl -s -X GET "$search_endpoint" -H "api-key: $SEARCH_KEY" | grep -q "value" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: List indexes${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: List indexes${NC}"
    ((TESTS_FAILED++))
fi

# Summary
echo -e "\n${BLUE}📊 Azure AI Search Test Summary${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All Azure AI Search tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Some Azure AI Search tests failed.${NC}"
    exit 1
fi 