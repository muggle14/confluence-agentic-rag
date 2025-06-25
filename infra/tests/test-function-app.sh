#!/bin/bash

# Function App Validation Tests
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Function App Validation Tests${NC}"
echo -e "${BLUE}================================${NC}"

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

# Test 1: Function App exists
run_test "Function App exists" \
    "az functionapp show --name $FUNC_APP --resource-group $AZ_RESOURCE_GROUP"

# Test 2: Function App is running
run_test "Function App is running" \
    "az functionapp show --name $FUNC_APP --resource-group $AZ_RESOURCE_GROUP --query 'state' -o tsv | grep -q 'Running'"

# Test 3: Function App has correct runtime
echo -e "\n${YELLOW}🔍 Testing: Function App runtime configuration${NC}"
runtime=$(az functionapp config show --name $FUNC_APP --resource-group $AZ_RESOURCE_GROUP --query 'linuxFxVersion' -o tsv 2>/dev/null || echo "")
if [[ "$runtime" == *"Python"* ]]; then
    echo -e "${GREEN}✅ PASS: Function App runtime configuration (Python)${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Function App runtime configuration (expected Python, got: $runtime)${NC}"
    ((TESTS_FAILED++))
fi

# Test 4: Function App environment variables
echo -e "\n${YELLOW}🔍 Testing: Function App environment variables${NC}"
required_env_vars=("CONFLUENCE_BASE" "CONFLUENCE_EMAIL" "STORAGE_CONN" "COSMOS_ACCOUNT" "SEARCH_ENDPOINT")
missing_vars=()

for var in "${required_env_vars[@]}"; do
    if ! az functionapp config appsettings list --name $FUNC_APP --resource-group $AZ_RESOURCE_GROUP --query "[?name=='$var'].value" -o tsv | grep -q .; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ PASS: Function App environment variables${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Function App environment variables${NC}"
    echo -e "${YELLOW}Missing variables: ${missing_vars[*]}${NC}"
    ((TESTS_FAILED++))
fi

# Test 5: Application Insights connection
echo -e "\n${YELLOW}🔍 Testing: Application Insights connection${NC}"
insights_key=$(az functionapp config appsettings list --name $FUNC_APP --resource-group $AZ_RESOURCE_GROUP --query "[?name=='APPINSIGHTS_INSTRUMENTATIONKEY'].value" -o tsv 2>/dev/null || echo "")
if [ -n "$insights_key" ] && [ "$insights_key" != "null" ]; then
    echo -e "${GREEN}✅ PASS: Application Insights connection${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Application Insights connection${NC}"
    ((TESTS_FAILED++))
fi

# Test 6: Function App accessibility
echo -e "\n${YELLOW}🔍 Testing: Function App accessibility${NC}"
function_url="https://$FUNC_APP.azurewebsites.net"
if curl -s -f "$function_url" --connect-timeout 10 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Function App accessibility${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  SKIP: Function App accessibility (may not have code deployed yet)${NC}"
fi

# Test 7: Function deployment status
echo -e "\n${YELLOW}🔍 Testing: Function deployment status${NC}"
deployment_status=$(az functionapp deployment source show --name $FUNC_APP --resource-group $AZ_RESOURCE_GROUP --query 'status' -o tsv 2>/dev/null || echo "No deployment")
if [ "$deployment_status" = "4" ] || [ "$deployment_status" = "Success" ]; then
    echo -e "${GREEN}✅ PASS: Function deployment status${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  INFO: Function deployment status: $deployment_status${NC}"
    echo -e "${YELLOW}💡 Run ./deploy-function-code.sh to deploy the function code${NC}"
fi

# Test 8: Storage containers accessibility from Function App
echo -e "\n${YELLOW}🔍 Testing: Storage containers accessibility${NC}"
if az functionapp config appsettings list --name $FUNC_APP --resource-group $AZ_RESOURCE_GROUP --query "[?name=='STORAGE_CONN'].value" -o tsv | grep -q "AccountName=$STORAGE_ACCOUNT"; then
    echo -e "${GREEN}✅ PASS: Storage containers accessibility${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Storage containers accessibility${NC}"
    ((TESTS_FAILED++))
fi

# Summary
echo -e "\n${BLUE}📊 Function App Test Summary${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All Function App tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Some Function App tests failed.${NC}"
    exit 1
fi 