# Graph-Aware Embedding Deployment Guide

## Overview
This guide walks through deploying the complete graph-aware embedding system for Confluence Q&A, integrating:
- ✅ Cosmos DB graph data
- ✅ Azure AI Search with vector embeddings
- ✅ Graph enrichment Azure Function
- ✅ OpenAI embeddings

## Prerequisites Checklist

### 1. Environment Variables
```bash
# Azure OpenAI
export AOAI_ENDPOINT="https://your-aoai.openai.azure.com/"
export AOAI_KEY="your-aoai-key"
export AOAI_EMBED_DEPLOY="text-embedding-3-large"
export OPENAI_API_KEY="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"

# Azure Resources
export RESOURCE_GROUP="rg-rag-confluence"
export SEARCH_SERVICE="srch-rag-conf"
export STORAGE_ACCOUNT="stgragconf"
export COSMOS_ACCOUNT="cosmos-rag-conf"
export FUNCTION_APP="func-rag-conf"

# Cosmos DB
export COSMOS_ENDPOINT="https://${COSMOS_ACCOUNT}.documents.azure.com/"
export COSMOS_KEY="<get-from-azure-portal>"
export COSMOS_DB="confluence"
export COSMOS_GRAPH="pages"

# Storage
export STORAGE_CONN="<get-from-azure-portal>"

# Search
export SEARCH_ENDPOINT="https://${SEARCH_SERVICE}.search.windows.net"
export SEARCH_KEY="<get-from-azure-portal>"
export SEARCH_INDEX="confluence-graph-embeddings"
```

### 2. Verify Prerequisites
```bash
# Check Azure CLI login
az account show

# Verify resources exist
az resource list --resource-group $RESOURCE_GROUP --output table

# Test Cosmos DB connectivity
az cosmosdb show --name $COSMOS_ACCOUNT --resource-group $RESOURCE_GROUP

# Check if raw pages exist in storage
az storage blob list --account-name $STORAGE_ACCOUNT --container-name raw --query "[?ends_with(name, '.json')] | length(@)"
```

## Deployment Steps

### Step 1: Deploy Graph Enrichment Function

```bash
cd infra

# Deploy the function app with graph enrichment skill
./deploy-function-code.sh

# The script will:
# 1. Create Python virtual environment
# 2. Install dependencies
# 3. Copy embedding modules
# 4. Deploy to Azure Function App
# 5. Set environment variables
```

### Step 2: Get Function URL

```bash
# Get the function URL for the graph enrichment skill
FUNCTION_URL=$(az functionapp function show \
    --resource-group $RESOURCE_GROUP \
    --name $FUNCTION_APP \
    --function-name graph_enrichment_skill \
    --query "invokeUrlTemplate" -o tsv)

FUNCTION_KEY=$(az functionapp function keys list \
    --resource-group $RESOURCE_GROUP \
    --name $FUNCTION_APP \
    --function-name graph_enrichment_skill \
    --query "default" -o tsv)

echo "Function URL: $FUNCTION_URL"
echo "Function Key: $FUNCTION_KEY"
```

### Step 3: Deploy Enhanced Search Infrastructure

Create a new deployment script that properly integrates both graph enrichment and embeddings:

```bash
cat > deploy-graph-aware-search.sh << 'SCRIPT_END'
#!/bin/bash
set -e

# Your existing variables here...

# Step 3.1: Create Enhanced Index
echo "Creating enhanced search index..."

cat > enhanced-index.json << 'EOF'
{
  "name": "confluence-graph-embeddings",
  "fields": [
    {
      "name": "id",
      "type": "Edm.String",
      "key": true,
      "searchable": false
    },
    {
      "name": "page_id",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true
    },
    {
      "name": "content",
      "type": "Edm.String",
      "searchable": true,
      "analyzer": "en.microsoft"
    },
    {
      "name": "title",
      "type": "Edm.String",
      "searchable": true,
      "analyzer": "en.microsoft",
      "boost": 2.0
    },
    {
      "name": "space_key",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "facetable": true
    },
    {
      "name": "hierarchy_path",
      "type": "Edm.String",
      "searchable": true
    },
    {
      "name": "hierarchy_depth",
      "type": "Edm.Int32",
      "filterable": true,
      "sortable": true
    },
    {
      "name": "parent_page_id",
      "type": "Edm.String",
      "filterable": true
    },
    {
      "name": "parent_page_title",
      "type": "Edm.String",
      "searchable": true
    },
    {
      "name": "has_children",
      "type": "Edm.Boolean",
      "filterable": true
    },
    {
      "name": "child_count",
      "type": "Edm.Int32",
      "filterable": true,
      "sortable": true
    },
    {
      "name": "graph_centrality_score",
      "type": "Edm.Double",
      "filterable": true,
      "sortable": true
    },
    {
      "name": "content_vector",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 3072,
      "vectorSearchProfile": "vector-profile"
    },
    {
      "name": "graph_metadata",
      "type": "Edm.String",
      "searchable": false
    },
    {
      "name": "last_modified",
      "type": "Edm.DateTimeOffset",
      "filterable": true,
      "sortable": true
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
        "algorithmConfigurationName": "hnsw-algorithm"
      }
    ]
  },
  "semantic": {
    "configurations": [
      {
        "name": "semantic-config",
        "prioritizedFields": {
          "titleField": {
            "fieldName": "title"
          },
          "prioritizedContentFields": [
            {
              "fieldName": "content"
            },
            {
              "fieldName": "hierarchy_path"
            }
          ],
          "prioritizedKeywordsFields": [
            {
              "fieldName": "parent_page_title"
            }
          ]
        }
      }
    ]
  },
  "scoringProfiles": [
    {
      "name": "graph-boost",
      "functions": [
        {
          "fieldName": "graph_centrality_score",
          "interpolation": "linear",
          "type": "magnitude",
          "boost": 2.0,
          "magnitude": {
            "boostingRangeStart": 0.5,
            "boostingRangeEnd": 1.0
          }
        },
        {
          "fieldName": "hierarchy_depth",
          "interpolation": "linear",
          "type": "magnitude",
          "boost": 1.5,
          "magnitude": {
            "boostingRangeStart": 3,
            "boostingRangeEnd": 1
          }
        }
      ]
    }
  ]
}
EOF

# Create the enhanced index
curl -X PUT "${SEARCH_ENDPOINT}/indexes/confluence-graph-embeddings?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_KEY" \
  -d @enhanced-index.json

# Step 3.2: Create Skillset with Graph Enrichment + Embeddings
echo "Creating integrated skillset..."

cat > integrated-skillset.json << EOF
{
  "name": "confluence-integrated-skillset",
  "description": "Graph enrichment + OpenAI embeddings",
  "skills": [
    {
      "@odata.type": "#Microsoft.Skills.Custom.WebApiSkill",
      "name": "GraphEnrichment",
      "description": "Enrich with Cosmos DB graph data",
      "uri": "${FUNCTION_URL}",
      "httpMethod": "POST",
      "timeout": "PT30S",
      "batchSize": 10,
      "httpHeaders": {
        "x-functions-key": "${FUNCTION_KEY}",
        "Content-Type": "application/json"
      },
      "inputs": [
        {
          "name": "page_id",
          "source": "/document/id"
        },
        {
          "name": "title",
          "source": "/document/title"
        },
        {
          "name": "space_key",
          "source": "/document/space/key"
        }
      ],
      "outputs": [
        {
          "name": "hierarchy_depth",
          "targetName": "hierarchy_depth"
        },
        {
          "name": "hierarchy_path",
          "targetName": "hierarchy_path"
        },
        {
          "name": "parent_page_id",
          "targetName": "parent_page_id"
        },
        {
          "name": "parent_page_title",
          "targetName": "parent_page_title"
        },
        {
          "name": "has_children",
          "targetName": "has_children"
        },
        {
          "name": "child_count",
          "targetName": "child_count"
        },
        {
          "name": "graph_centrality_score",
          "targetName": "graph_centrality_score"
        },
        {
          "name": "graph_metadata",
          "targetName": "graph_metadata"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Custom.WebApiSkill",
      "name": "GenerateEmbeddings",
      "description": "Generate embeddings using OpenAI",
      "uri": "https://api.openai.com/v1/embeddings",
      "httpMethod": "POST",
      "timeout": "PT30S",
      "batchSize": 1,
      "httpHeaders": {
        "Authorization": "Bearer ${OPENAI_API_KEY}",
        "Content-Type": "application/json"
      },
      "inputs": [
        {
          "name": "input",
          "source": "/document/body/storage/value"
        },
        {
          "name": "model",
          "source": "='text-embedding-3-large'"
        }
      ],
      "outputs": [
        {
          "name": "data",
          "targetName": "embedding_response"
        }
      ]
    }
  ]
}
EOF

curl -X PUT "${SEARCH_ENDPOINT}/skillsets/confluence-integrated-skillset?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_KEY" \
  -d @integrated-skillset.json

echo "Deployment complete!"
SCRIPT_END

chmod +x deploy-graph-aware-search.sh
./deploy-graph-aware-search.sh
```

## Verification Steps

### 1. Test Graph Enrichment Function
```bash
# Test the function directly
curl -X POST $FUNCTION_URL \
  -H "x-functions-key: $FUNCTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [{
      "recordId": "1",
      "data": {
        "page_id": "12345",
        "title": "Test Page",
        "space_key": "TEST"
      }
    }]
  }'
```

### 2. Monitor Indexer Progress
```bash
# Check indexer status
curl -X GET "${SEARCH_ENDPOINT}/indexers/confluence-integrated-indexer/status?api-version=2023-11-01" \
  -H "api-key: $SEARCH_KEY" | jq

# View document count
curl -X GET "${SEARCH_ENDPOINT}/indexes/confluence-graph-embeddings/docs/\$count?api-version=2023-11-01" \
  -H "api-key: $SEARCH_KEY"
```

### 3. Test Search with Graph Boost
```bash
# Vector search with graph scoring
curl -X POST "${SEARCH_ENDPOINT}/indexes/confluence-graph-embeddings/docs/search?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_KEY" \
  -d '{
    "search": "installation guide",
    "searchFields": "content,title,hierarchy_path",
    "select": "page_id,title,hierarchy_path,graph_centrality_score",
    "scoringProfile": "graph-boost",
    "top": 5
  }'
```

## Troubleshooting

### Common Issues

1. **Function not found**
   - Ensure function app is deployed: `az functionapp list --resource-group $RESOURCE_GROUP`
   - Check function logs: `az functionapp logs tail --name $FUNCTION_APP --resource-group $RESOURCE_GROUP`

2. **Indexer errors**
   - View detailed errors: `curl -X GET "${SEARCH_ENDPOINT}/indexers/confluence-integrated-indexer/status?api-version=2023-11-01" -H "api-key: $SEARCH_KEY" | jq '.executionHistory[0].errors'`
   - Check skillset validation: Skills must output all expected fields

3. **No embeddings generated**
   - Verify OpenAI API key is valid
   - Check rate limits and quotas
   - Monitor function app for errors

4. **Graph data missing**
   - Ensure Cosmos DB has graph data populated
   - Verify function can connect to Cosmos DB
   - Check function app environment variables

## Next Steps

1. **Monitor Performance**
   - Set up Application Insights dashboards
   - Monitor embedding generation costs
   - Track search query performance

2. **Optimize Search**
   - Tune scoring profiles based on user feedback
   - Adjust vector search parameters
   - Implement caching for frequent queries

3. **Scale Considerations**
   - Consider dedicated search service tier for production
   - Implement rate limiting for OpenAI calls
   - Use managed identity for enhanced security 