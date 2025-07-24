#!/bin/bash

# Update indexer to handle chunked content
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_ADMIN_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)

echo "Updating indexer for chunking..."

# Delete existing indexer
curl -X DELETE \
  "https://srch-rag-conf.search.windows.net/indexers/confluence-graph-indexer?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY"

sleep 2

# Create updated indexer with chunk handling
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
      "sourceFieldName": "metadata_storage_path",
      "targetFieldName": "id",
      "mappingFunction": {
        "name": "base64Encode"
      }
    },
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
    }
  ],
  "outputFieldMappings": [
    {
      "sourceFieldName": "/document/pages/*/vector",
      "targetFieldName": "contentVector"
    },
    {
      "sourceFieldName": "/document/titleVector",
      "targetFieldName": "titleVector"
    }
  ]
}'

echo ""
echo "Indexer updated for chunking!"