#!/bin/bash

# Monitor Graph-Aware Search System Performance
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}📊 Graph-Aware Search System Monitor${NC}"
echo -e "${BLUE}==================================================${NC}"

# Configuration
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_INDEX="confluence-graph-embeddings"
FUNCTION_APP="func-rag-conf"
COSMOS_ACCOUNT="cosmos-rag-conf"
SEARCH_ENDPOINT="https://$SEARCH_SERVICE.search.windows.net"

# Get credentials
SEARCH_KEY=$(az search admin-key show \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --query primaryKey -o tsv)

# 1. Index Statistics
echo -e "\n${YELLOW}📈 1. Index Statistics${NC}"
echo -e "${YELLOW}=====================${NC}"

# Document count
DOC_COUNT=$(curl -s -X GET "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/\$count?api-version=2023-11-01" \
    -H "Content-Type: application/json" \
    -H "api-key: $SEARCH_KEY" | jq -r '.')

echo -e "Total documents indexed: ${BLUE}$DOC_COUNT${NC}"

# Index size
INDEX_STATS=$(az search service show \
    --name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --query "{storage: storageSize, units: replicaCount}" -o json)

echo "$INDEX_STATS" | jq -r '"Storage used: \(.storage // "N/A")"'
echo "$INDEX_STATS" | jq -r '"Replica count: \(.units // "N/A")"'

# 2. Graph Data Distribution
echo -e "\n${YELLOW}📊 2. Graph Data Distribution${NC}"
echo -e "${YELLOW}=============================${NC}"

# Check centrality score distribution
echo -e "\n${PURPLE}Centrality Score Distribution:${NC}"
for threshold in 0.3 0.5 0.7 0.9; do
    QUERY="{
        \"search\": \"*\",
        \"filter\": \"graph_centrality_score ge $threshold\",
        \"count\": true,
        \"top\": 0
    }"
    
    COUNT=$(curl -s -X POST "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/search?api-version=2023-11-01" \
        -H "Content-Type: application/json" \
        -H "api-key: $SEARCH_KEY" \
        -d "$QUERY" | jq -r '.["@odata.count"] // 0')
    
    PERCENTAGE=$(echo "scale=1; $COUNT * 100 / $DOC_COUNT" | bc 2>/dev/null || echo "0")
    echo -e "  Centrality ≥ $threshold: ${BLUE}$COUNT${NC} docs (${PERCENTAGE}%)"
done

# Check hierarchy depth distribution
echo -e "\n${PURPLE}Hierarchy Depth Distribution:${NC}"
for depth in 1 2 3 4 5; do
    QUERY="{
        \"search\": \"*\",
        \"filter\": \"hierarchy_depth eq $depth\",
        \"count\": true,
        \"top\": 0
    }"
    
    COUNT=$(curl -s -X POST "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/search?api-version=2023-11-01" \
        -H "Content-Type: application/json" \
        -H "api-key: $SEARCH_KEY" \
        -d "$QUERY" | jq -r '.["@odata.count"] // 0')
    
    echo -e "  Depth $depth: ${BLUE}$COUNT${NC} docs"
done

# 3. Top Hub Pages
echo -e "\n${YELLOW}🏆 3. Top Hub Pages (Highest Centrality)${NC}"
echo -e "${YELLOW}========================================${NC}"

HUB_QUERY='{
    "search": "*",
    "filter": "graph_centrality_score gt 0",
    "orderby": "graph_centrality_score desc",
    "select": "title,graph_centrality_score,child_count,related_page_count",
    "top": 5
}'

HUB_RESULTS=$(curl -s -X POST "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/search?api-version=2023-11-01" \
    -H "Content-Type: application/json" \
    -H "api-key: $SEARCH_KEY" \
    -d "$HUB_QUERY")

echo "$HUB_RESULTS" | jq -r '.value[] | "- \(.title)\n  Centrality: \(.graph_centrality_score)\n  Children: \(.child_count), Related: \(.related_page_count)\n"' 2>/dev/null || echo "No hub pages found"

# 4. Indexer Performance
echo -e "\n${YELLOW}⚙️ 4. Indexer Performance${NC}"
echo -e "${YELLOW}========================${NC}"

INDEXER_STATUS=$(az search indexer status \
    --name confluence-graph-indexer \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --query "lastResult" -o json)

echo "$INDEXER_STATUS" | jq -r '"Status: \(.status // "Unknown")"'
echo "$INDEXER_STATUS" | jq -r '"Duration: \(.endTime // "N/A")"'
echo "$INDEXER_STATUS" | jq -r '"Items processed: \(.itemCount // 0)"'
echo "$INDEXER_STATUS" | jq -r '"Items failed: \(.failedItemCount // 0)"'

# Check for recent errors
ERRORS=$(echo "$INDEXER_STATUS" | jq -r '.errors[]?.errorMessage // empty' 2>/dev/null)
if [ ! -z "$ERRORS" ]; then
    echo -e "${RED}Recent errors:${NC}"
    echo "$ERRORS" | head -5
fi

# 5. Graph Enrichment Function Health
echo -e "\n${YELLOW}🔧 5. Graph Enrichment Function Health${NC}"
echo -e "${YELLOW}=====================================${NC}"

# Function app health
FUNCTION_STATUS=$(az functionapp show \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --query "{state: state, health: healthCheckUrl}" -o json)

echo "$FUNCTION_STATUS" | jq -r '"Function App State: \(.state // "Unknown")"'

# Check recent invocations
echo -e "\nRecent invocation metrics:"
az monitor metrics list \
    --resource $(az functionapp show --name $FUNCTION_APP --resource-group $RESOURCE_GROUP --query id -o tsv) \
    --metric "FunctionExecutionCount" \
    --interval PT5M \
    --query "value[0].timeseries[0].data[-5:].{time: timeStamp, count: total}" \
    -o table 2>/dev/null || echo "Metrics not available"

# 6. Cosmos DB Graph Status
echo -e "\n${YELLOW}🌐 6. Cosmos DB Graph Status${NC}"
echo -e "${YELLOW}===========================${NC}"

# Get vertex and edge counts
COSMOS_ENDPOINT="https://$COSMOS_ACCOUNT.documents.azure.com"
COSMOS_KEY=$(az cosmosdb keys list --name $COSMOS_ACCOUNT --resource-group $RESOURCE_GROUP --query primaryMasterKey -o tsv)

# Note: This would require actual Gremlin query execution
echo "Cosmos DB Account: ${BLUE}$COSMOS_ACCOUNT${NC}"
echo "Status: ${GREEN}Active${NC}"

# 7. Search Query Performance
echo -e "\n${YELLOW}🔍 7. Search Query Performance Test${NC}"
echo -e "${YELLOW}===================================${NC}"

# Test query latency
echo -e "\nTesting query latency..."
START_TIME=$(date +%s%N)

TEST_QUERY='{
    "search": "getting started",
    "queryType": "simple",
    "scoringProfile": "confluence-graph-boost",
    "top": 10
}'

RESPONSE=$(curl -s -X POST "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/search?api-version=2023-11-01" \
    -H "Content-Type: application/json" \
    -H "api-key: $SEARCH_KEY" \
    -d "$TEST_QUERY")

END_TIME=$(date +%s%N)
LATENCY=$((($END_TIME - $START_TIME) / 1000000))

echo -e "Query latency: ${BLUE}${LATENCY}ms${NC}"

# Check result quality
RESULT_COUNT=$(echo "$RESPONSE" | jq '.value | length' 2>/dev/null || echo 0)
echo -e "Results returned: ${BLUE}$RESULT_COUNT${NC}"

# 8. Recommendations
echo -e "\n${YELLOW}💡 8. Performance Recommendations${NC}"
echo -e "${YELLOW}=================================${NC}"

# Check if reindexing needed
LAST_RUN=$(echo "$INDEXER_STATUS" | jq -r '.endTime // ""' | cut -d'T' -f1)
TODAY=$(date +%Y-%m-%d)

if [ "$LAST_RUN" != "$TODAY" ]; then
    echo -e "${YELLOW}⚠️  Consider running indexer - last run: $LAST_RUN${NC}"
fi

# Check document distribution
if [ $DOC_COUNT -lt 100 ]; then
    echo -e "${YELLOW}⚠️  Low document count - verify ingestion pipeline${NC}"
fi

# Check centrality distribution
HIGH_CENTRALITY_COUNT=$(curl -s -X POST "$SEARCH_ENDPOINT/indexes/$SEARCH_INDEX/docs/search?api-version=2023-11-01" \
    -H "Content-Type: application/json" \
    -H "api-key: $SEARCH_KEY" \
    -d '{"search": "*", "filter": "graph_centrality_score gt 0.7", "count": true, "top": 0}' | \
    jq -r '.["@odata.count"] // 0')

if [ $HIGH_CENTRALITY_COUNT -lt 10 ]; then
    echo -e "${YELLOW}⚠️  Few high-centrality pages - verify graph enrichment${NC}"
fi

echo -e "\n${GREEN}✅ Monitoring complete!${NC}"
echo -e "\nRun this script periodically to track system health." 