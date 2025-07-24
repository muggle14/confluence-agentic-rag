#!/bin/bash

# Run the indexer and check status
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_ADMIN_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)

echo "Running indexer..."

# Run the indexer
curl -X POST \
  "https://srch-rag-conf.search.windows.net/indexers/confluence-graph-indexer/run?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -H "Content-Length: 0"

echo ""
echo "Waiting for indexer to process..."
sleep 15

# Check status
echo "Checking indexer status..."
curl -s "https://srch-rag-conf.search.windows.net/indexers/confluence-graph-indexer/status?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" | jq '.lastResult | {status: .status, itemsProcessed: .itemsProcessed, itemsFailed: .itemsFailed, errors: (.errors[:3] | map({key: .key, errorMessage: .errorMessage}))}'

# Check document count
echo ""
echo "Checking document count..."
curl -X GET "https://srch-rag-conf.search.windows.net/indexes/confluence-graph-embeddings/docs/\$count?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY"