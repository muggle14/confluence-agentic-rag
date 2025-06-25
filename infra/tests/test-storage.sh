#!/bin/bash

# Storage Account Validation Tests
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Storage Account Validation Tests${NC}"
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

# Test 1: Storage Account exists
run_test "Storage Account exists" \
    "az storage account show --name $STORAGE_ACCOUNT --resource-group $AZ_RESOURCE_GROUP"

# Test 2: Storage Account is accessible
run_test "Storage Account is accessible" \
    "az storage account keys list --account-name $STORAGE_ACCOUNT --resource-group $AZ_RESOURCE_GROUP"

# Test 3: Storage containers exist
run_test "Storage containers exist" \
    "az storage container list --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY --output table"

# Test 4: Raw container exists
run_test "Raw container exists" \
    "az storage container show --name raw --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY"

# Test 5: Processed container exists
run_test "Processed container exists" \
    "az storage container show --name processed --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY"

# Test 6: Storage connectivity
echo -e "\n${YELLOW}🔍 Testing: Storage connectivity${NC}"
if az storage blob list --container-name raw --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY --output table > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Storage connectivity${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Storage connectivity${NC}"
    ((TESTS_FAILED++))
fi

# Summary
echo -e "\n${BLUE}📊 Storage Account Test Summary${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All Storage Account tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Some Storage Account tests failed.${NC}"
    exit 1
fi 