#!/bin/bash

# Fix the indexer configuration with correct field mappings

RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_ADMIN_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)

echo "Updating indexer with correct field mappings..."

# Update the indexer with proper field mappings
curl -X PUT \
  "https://srch-rag-conf.search.windows.net/indexers/confluence-graph-indexer?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "confluence-graph-indexer",
  "dataSourceName": "confluence-blob-datasource",
  "skillsetName": "confluence-graph-skillset",
  "targetIndexName": "confluence-graph-embeddings",
  "parameters": {
    "maxFailedItems": -1,
    "maxFailedItemsPerBatch": -1,
    "configuration": {
      "dataToExtract": "contentAndMetadata",
      "parsingMode": "json"
    }
  },
  "fieldMappings": [
    {
      "sourceFieldName": "id",
      "targetFieldName": "page_id"
    },
    {
      "sourceFieldName": "title",
      "targetFieldName": "title"
    },
    {
      "sourceFieldName": "body/storage/value",
      "targetFieldName": "content"
    },
    {
      "sourceFieldName": "space/key",
      "targetFieldName": "space_key"
    },
    {
      "sourceFieldName": "version/when",
      "targetFieldName": "updated_at"
    }
  ],
  "outputFieldMappings": [
    {
      "sourceFieldName": "/document/pages/*/contentVector",
      "targetFieldName": "contentVector"
    },
    {
      "sourceFieldName": "/document/titleVector",
      "targetFieldName": "titleVector"
    }
  ]
}'

echo ""
echo "Indexer updated. Now resetting and running it..."

# Reset the indexer
curl -X POST \
    "https://srch-rag-conf.search.windows.net/indexers/confluence-graph-indexer/reset?api-version=2023-11-01" \
    -H "api-key: $SEARCH_ADMIN_KEY" \
    -H "Content-Length: 0"

sleep 5

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
    -H "api-key: $SEARCH_ADMIN_KEY" | jq '.lastResult'