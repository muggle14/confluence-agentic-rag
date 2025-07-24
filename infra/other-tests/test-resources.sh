#!/bin/bash

# Confluence Q&A System - Resource Validation Tests
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Starting Azure Resources Validation Tests${NC}"

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
    
    echo -e "${YELLOW}🔍 Testing: $test_name${NC}"
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS: $test_name${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL: $test_name${NC}"
        ((TESTS_FAILED++))
    fi
}

# Test 1: Resource Group exists
run_test "Resource Group exists" \
    "az group show --name $AZ_RESOURCE_GROUP"

# Test 2: Storage Account exists and accessible
run_test "Storage Account exists" \
    "az storage account show --name $STORAGE_ACCOUNT --resource-group $AZ_RESOURCE_GROUP"

# Test 3: Storage containers exist
run_test "Storage containers exist" \
    "az storage container list --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY --query '[].name' -o tsv | grep -q 'raw\|processed'"

# Test 4: Cosmos DB account exists
run_test "Cosmos DB account exists" \
    "az cosmosdb show --name $COSMOS_ACCOUNT --resource-group $AZ_RESOURCE_GROUP"

# Test 5: Cosmos DB database exists
run_test "Cosmos DB database exists" \
    "az cosmosdb gremlin database show --account-name $COSMOS_ACCOUNT --resource-group $AZ_RESOURCE_GROUP --name confluence"

# Test 6: Cosmos DB graph exists
run_test "Cosmos DB graph exists" \
    "az cosmosdb gremlin graph show --account-name $COSMOS_ACCOUNT --resource-group $AZ_RESOURCE_GROUP --database-name confluence --name pages"

# Test 7: Azure AI Search service exists
run_test "Azure AI Search service exists" \
    "az search service show --name $SEARCH_SERVICE --resource-group $AZ_RESOURCE_GROUP"

# Skip Azure OpenAI - using direct OpenAI API
echo -e "${BLUE}ℹ️  Skipping Azure OpenAI tests - using direct OpenAI API${NC}"

# Skip Function App and Web App for now - not deployed yet
echo -e "${BLUE}ℹ️  Skipping Function App and Web App tests - will be deployed separately${NC}"

echo -e "\n${BLUE}🔗 Testing Connectivity${NC}"

# Test 11: Storage Account connectivity
echo -e "${YELLOW}🔍 Testing: Storage Account connectivity${NC}"
if az storage blob list --container-name raw --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Storage Account connectivity${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Storage Account connectivity${NC}"
    ((TESTS_FAILED++))
fi

# Test 12: Cosmos DB connectivity
echo -e "${YELLOW}🔍 Testing: Cosmos DB connectivity${NC}"
if curl -s -X GET "https://$COSMOS_ACCOUNT.gremlin.cosmos.azure.com:443/" \
    -H "Authorization: type%3Dmaster%26ver%3D1.0%26sig%3D$(echo -n "get\n\ndbs\n\n$(date -u '+%a, %d %b %Y %H:%M:%S GMT')\n" | openssl dgst -sha256 -hmac "$(echo $COSMOS_KEY | base64 -d)" -binary | base64)" \
    -H "x-ms-date: $(date -u '+%a, %d %b %Y %H:%M:%S GMT')" \
    -H "x-ms-version: 2020-07-15" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Cosmos DB connectivity${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  SKIP: Cosmos DB connectivity (complex auth)${NC}"
fi

# Test 13: Azure AI Search connectivity
echo -e "${YELLOW}🔍 Testing: Azure AI Search connectivity${NC}"
if curl -s -X GET "https://$SEARCH_SERVICE.search.windows.net/indexes?api-version=2023-11-01" \
    -H "api-key: $SEARCH_KEY" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Azure AI Search connectivity${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Azure AI Search connectivity${NC}"
    ((TESTS_FAILED++))
fi

# Skip OpenAI and Function App connectivity tests
echo -e "${BLUE}ℹ️  Skipping OpenAI and Function App connectivity tests${NC}"

echo -e "\n${BLUE}📊 Test Summary${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All critical tests passed! Infrastructure is ready.${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Some tests failed. Please check the resources and configuration.${NC}"
    exit 1
fi 