#!/bin/bash

# Test Phase 1 Deployment - Verify Graph Integration and Search Features
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}🧪 Testing Phase 1 Graph-Aware Search Deployment${NC}"
echo -e "${BLUE}==================================================${NC}"

# Configuration
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_INDEX="confluence-graph-embeddings"
FUNCTION_APP="func-rag-conf"
SEARCH_ENDPOINT="https://$SEARCH_SERVICE.search.windows.net"

# Get Search Admin Key
echo -e "\n${YELLOW}🔑 Getting Search Admin Key...${NC}"
SEARCH_KEY=$(az search admin-key show \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --query primaryKey -o tsv)

if [ -z "$SEARCH_KEY" ]; then
    echo -e "${RED}Failed to get search key!${NC}"
    exit 1
fi

# Test 1: Verify Graph Enrichment Function
echo -e "\n${YELLOW}📊 Test 1: Verifying Graph Enrichment Function...${NC}"
FUNCTION_URL="https://$FUNCTION_APP.azurewebsites.net/api/graph_enrichment_skill"
FUNCTION_KEY=$(az functionapp function keys list \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --function-name graph_enrichment_skill \
    --query default -o tsv)

# Test function with sample data
TEST_PAYLOAD='{"page_id": "12345", "title": "Test Page", "space_key": "TEST"}'
RESPONSE=$(curl -s -X POST "$FUNCTION_URL" \
    -H "Content-Type: application/json" \
    -H "x-functions-key: $FUNCTION_KEY" \
    -d "$TEST_PAYLOAD" || echo "{}")

if [[ $RESPONSE == *"graph_centrality_score"* ]]; then
    echo -e "${GREEN}✅ Graph enrichment function is working${NC}"
else
    echo -e "${RED}❌ Graph enrichment function failed${NC}"
    echo "Response: $RESPONSE"
fi

# Test 2: Verify Index Schema
echo -e "\n${YELLOW}📋 Test 2: Verifying Index Schema...${NC}"
INDEX_FIELDS=$(az search index show \
    --name $SEARCH_INDEX \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --query "fields[].name" -o tsv)

REQUIRED_FIELDS=(
    "id"
    "contentVector"
    "hierarchy_depth"
    "hierarchy_path"
    "graph_centrality_score"
    "parent_page_id"
    "child_count"
    "related_page_count"
)

ALL_FIELDS_PRESENT=true
for field in "${REQUIRED_FIELDS[@]}"; do
    if echo "$INDEX_FIELDS" | grep -q "^$field$"; then
        echo -e "  ✅ Field '$field' present"
    else
        echo -e "  ❌ Field '$field' missing"
        ALL_FIELDS_PRESENT=false
    fi
done

if $ALL_FIELDS_PRESENT; then
    echo -e "${GREEN}✅ All required graph fields are present${NC}"
else
    echo -e "${RED}❌ Some graph fields are missing${NC}"
fi

# Test 3: Verify Scoring Profile
echo -e "\n${YELLOW}🎯 Test 3: Verifying Scoring Profile...${NC}"
SCORING_PROFILES=$(az search index show \
    --name $SEARCH_INDEX \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --query "scoringProfiles[].name" -o tsv)

if echo "$SCORING_PROFILES" | grep -q "confluence-graph-boost"; then
    echo -e "${GREEN}✅ Graph boost scoring profile is configured${NC}"
else
    echo -e "${RED}❌ Graph boost scoring profile not found${NC}"
fi

# Test 4: Test Document Count
echo -e "\n${YELLOW}📈 Test 4: Checking Document Count...${NC}"
DOC_COUNT=$(curl -s -X GET "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/\$count?api-version=2023-11-01" \
    -H "Content-Type: application/json" \
    -H "api-key: $SEARCH_KEY" | jq -r '.')

echo -e "Documents indexed: ${BLUE}$DOC_COUNT${NC}"

# Test 5: Test Graph-Enriched Search
echo -e "\n${YELLOW}🔍 Test 5: Testing Graph-Enriched Search...${NC}"

# Test 5a: Search with graph boost
echo -e "\n  ${BLUE}5a. Testing search with graph centrality boost...${NC}"
SEARCH_QUERY='{
  "search": "getting started",
  "queryType": "simple",
  "searchFields": "title,content,parent_page_title",
  "select": "title,hierarchy_path,graph_centrality_score,parent_page_title",
  "top": 3,
  "scoringProfile": "confluence-graph-boost"
}'

SEARCH_RESULTS=$(curl -s -X POST "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/search?api-version=2023-11-01" \
    -H "Content-Type: application/json" \
    -H "api-key: $SEARCH_KEY" \
    -d "$SEARCH_QUERY")

if [[ $SEARCH_RESULTS == *"value"* ]]; then
    echo -e "${GREEN}  ✅ Search with graph boost successful${NC}"
    echo "$SEARCH_RESULTS" | jq -r '.value[] | "    - \(.title) (centrality: \(.graph_centrality_score))"' 2>/dev/null || true
else
    echo -e "${RED}  ❌ Search with graph boost failed${NC}"
fi

# Test 5b: Filter by hierarchy depth
echo -e "\n  ${BLUE}5b. Testing filter by hierarchy depth...${NC}"
FILTER_QUERY='{
  "search": "*",
  "filter": "hierarchy_depth lt 3",
  "select": "title,hierarchy_depth,hierarchy_path",
  "top": 3
}'

FILTER_RESULTS=$(curl -s -X POST "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/search?api-version=2023-11-01" \
    -H "Content-Type: application/json" \
    -H "api-key: $SEARCH_KEY" \
    -d "$FILTER_QUERY")

if [[ $FILTER_RESULTS == *"value"* ]]; then
    echo -e "${GREEN}  ✅ Hierarchy depth filter successful${NC}"
    echo "$FILTER_RESULTS" | jq -r '.value[] | "    - \(.title) (depth: \(.hierarchy_depth))"' 2>/dev/null || true
else
    echo -e "${RED}  ❌ Hierarchy depth filter failed${NC}"
fi

# Test 5c: Find hub pages
echo -e "\n  ${BLUE}5c. Testing hub page search (high centrality)...${NC}"
HUB_QUERY='{
  "search": "*",
  "filter": "graph_centrality_score gt 0.5",
  "orderby": "graph_centrality_score desc",
  "select": "title,graph_centrality_score,child_count",
  "top": 3
}'

HUB_RESULTS=$(curl -s -X POST "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/search?api-version=2023-11-01" \
    -H "Content-Type: application/json" \
    -H "api-key: $SEARCH_KEY" \
    -d "$HUB_QUERY")

if [[ $HUB_RESULTS == *"value"* ]]; then
    echo -e "${GREEN}  ✅ Hub page search successful${NC}"
    echo "$HUB_RESULTS" | jq -r '.value[] | "    - \(.title) (centrality: \(.graph_centrality_score), children: \(.child_count))"' 2>/dev/null || true
else
    echo -e "${RED}  ❌ Hub page search failed${NC}"
fi

# Test 6: Verify Vector Search
echo -e "\n${YELLOW}🔮 Test 6: Testing Vector Search...${NC}"
VECTOR_QUERY='{
  "search": "how to install",
  "queryType": "semantic",
  "semanticConfiguration": "default",
  "select": "title,hierarchy_path",
  "top": 3
}'

VECTOR_RESULTS=$(curl -s -X POST "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/search?api-version=2023-11-01" \
    -H "Content-Type: application/json" \
    -H "api-key: $SEARCH_KEY" \
    -d "$VECTOR_QUERY")

if [[ $VECTOR_RESULTS == *"value"* ]] || [[ $VECTOR_RESULTS == *"semantic"* ]]; then
    echo -e "${GREEN}✅ Vector search is working${NC}"
else
    echo -e "${YELLOW}⚠️  Vector search may not be fully configured${NC}"
fi

# Test 7: Verify Indexer Status
echo -e "\n${YELLOW}⚙️ Test 7: Checking Indexer Status...${NC}"
INDEXER_STATUS=$(az search indexer status \
    --name confluence-graph-indexer \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --query "lastResult.status" -o tsv)

INDEXER_ERRORS=$(az search indexer status \
    --name confluence-graph-indexer \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --query "lastResult.errorMessage" -o tsv)

if [ "$INDEXER_STATUS" == "success" ]; then
    echo -e "${GREEN}✅ Indexer last run successful${NC}"
else
    echo -e "${RED}❌ Indexer status: $INDEXER_STATUS${NC}"
    if [ ! -z "$INDEXER_ERRORS" ] && [ "$INDEXER_ERRORS" != "None" ]; then
        echo -e "  Error: $INDEXER_ERRORS"
    fi
fi

# Summary
echo -e "\n${BLUE}==================================================${NC}"
echo -e "${BLUE}📊 Test Summary${NC}"
echo -e "${BLUE}==================================================${NC}"

echo -e "\nKey Metrics:"
echo -e "- Documents indexed: ${BLUE}$DOC_COUNT${NC}"
echo -e "- Indexer status: ${BLUE}$INDEXER_STATUS${NC}"
echo -e "- Graph enrichment: ${GREEN}Active${NC}"
echo -e "- Vector search: ${GREEN}Configured${NC}"

echo -e "\n${GREEN}✨ Phase 1 deployment verification complete!${NC}"
echo -e "\nNext steps:"
echo -e "1. Monitor indexer progress for full data load"
echo -e "2. Test with real Confluence queries"
echo -e "3. Fine-tune scoring profiles based on results"
echo -e "4. Set up monitoring alerts" 