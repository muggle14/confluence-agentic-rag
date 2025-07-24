#!/bin/bash

# Create an index designed for chunk-level documents
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_ADMIN_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)

echo "Creating chunk-level index..."

# Delete existing index if present
curl -X DELETE \
  "https://srch-rag-conf.search.windows.net/indexes/confluence-chunks?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY"

sleep 2

# Create new index for chunks
curl -X PUT \
  "https://srch-rag-conf.search.windows.net/indexes/confluence-chunks?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "confluence-chunks",
  "fields": [
    {
      "name": "chunk_id",
      "type": "Edm.String",
      "key": true,
      "searchable": false,
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "parent_id",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "page_id",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "chunk_index",
      "type": "Edm.Int32",
      "searchable": false,
      "filterable": true,
      "sortable": true,
      "retrievable": true
    },
    {
      "name": "chunk_text",
      "type": "Edm.String",
      "searchable": true,
      "filterable": false,
      "retrievable": true,
      "analyzer": "standard.lucene"
    },
    {
      "name": "parent_title",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "retrievable": true,
      "analyzer": "standard.lucene"
    },
    {
      "name": "space_key",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "facetable": true
    },
    {
      "name": "chunk_embedding",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 1536,
      "vectorSearchProfile": "vector-profile"
    },
    {
      "name": "metadata",
      "type": "Edm.String",
      "searchable": false,
      "retrievable": true
    }
  ],
  "vectorSearch": {
    "algorithms": [
      {
        "name": "hnsw-algorithm",
        "kind": "hnsw",
        "hnswParameters": {
          "metric": "cosine",
          "m": 4,
          "efConstruction": 400,
          "efSearch": 500
        }
      }
    ],
    "profiles": [
      {
        "name": "vector-profile",
        "algorithm": "hnsw-algorithm"
      }
    ]
  },
  "scoringProfiles": [
    {
      "name": "chunk-scoring",
      "text": {
        "weights": {
          "parent_title": 1.5,
          "chunk_text": 2.0
        }
      }
    }
  ],
  "defaultScoringProfile": "chunk-scoring"
}'

echo ""
echo "Chunk-level index created!"