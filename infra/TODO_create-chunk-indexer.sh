#!/bin/bash

# Create an indexer that processes chunks as separate documents
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_ADMIN_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)

echo "Creating chunk-level indexer..."

# First, create a temporary indexer to use the skillset
curl -X PUT \
  "https://srch-rag-conf.search.windows.net/indexers/confluence-chunk-indexer?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "confluence-chunk-indexer",
  "dataSourceName": "confluence-blob-datasource",
  "skillsetName": "confluence-chunk-skillset",
  "targetIndexName": "confluence-chunks",
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
      "targetFieldName": "parent_title"
    },
    {
      "sourceFieldName": "body/storage/value",
      "targetFieldName": "chunk_text"
    },
    {
      "sourceFieldName": "space/key",
      "targetFieldName": "space_key"
    },
    {
      "sourceFieldName": "metadata_storage_path",
      "targetFieldName": "parent_id"
    }
  ]
}'

echo ""
echo "Note: This indexer creates the Knowledge Store projections."
echo "To index the chunks, you'll need to:"
echo "1. Run this indexer to populate the Knowledge Store"
echo "2. Use a separate process to read from Knowledge Store and index chunks"
echo ""
echo "Alternative: Use a custom skill that creates multiple documents per chunk"