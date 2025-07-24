#!/bin/bash

# Deploy Azure AI Search with Graph Enrichment and Embeddings
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Graph-Aware Search with Embeddings${NC}"
echo -e "${BLUE}==============================================${NC}"

# Configuration
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_INDEX="confluence-graph-embeddings"
STORAGE_ACCOUNT="stgragconf"
COSMOS_ACCOUNT="cosmos-rag-conf"
FUNCTION_APP="func-rag-conf"

# Set OpenAI API key
OPENAI_API_KEY="${OPENAI_API_KEY:-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}"

echo -e "${GREEN}✅ Using resources:${NC}"
echo -e "  - Resource Group: $RESOURCE_GROUP"
echo -e "  - Search Service: $SEARCH_SERVICE"
echo -e "  - Storage Account: $STORAGE_ACCOUNT"
echo -e "  - Cosmos DB: $COSMOS_ACCOUNT"
echo -e "  - Function App: $FUNCTION_APP"

# Get connection strings and keys
echo -e "\n${YELLOW}🔑 Retrieving connection strings...${NC}"

STORAGE_CONN=$(az storage account show-connection-string --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query connectionString -o tsv)
SEARCH_KEY=$(az search admin-key show --resource-group $RESOURCE_GROUP --service-name $SEARCH_SERVICE --query primaryKey -o tsv)
SEARCH_ENDPOINT="https://${SEARCH_SERVICE}.search.windows.net"

# Get Function URL and Key
echo -e "\n${YELLOW}🔑 Getting Function App details...${NC}"
FUNCTION_URL="https://${FUNCTION_APP}.azurewebsites.net/api/graph_enrichment_skill"
FUNCTION_KEY=$(az functionapp function keys list \
    --resource-group $RESOURCE_GROUP \
    --name $FUNCTION_APP \
    --function-name graph_enrichment_skill \
    --query "default" -o tsv 2>/dev/null || echo "")

if [ -z "$FUNCTION_KEY" ]; then
    echo -e "${YELLOW}⚠️  Function key not found. Ensure graph_enrichment_skill is deployed.${NC}"
    echo -e "${YELLOW}   Run ./deploy-function-code.sh first if needed.${NC}"
fi

echo -e "${GREEN}✅ Connection strings retrieved${NC}"

# Step 1: Create Enhanced Search Index
echo -e "\n${YELLOW}📋 Creating enhanced search index...${NC}"

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
      "analyzer": "en.microsoft"
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

# Delete existing index if it exists
echo -e "${YELLOW}🗑️  Deleting existing index if present...${NC}"
curl -X DELETE "${SEARCH_ENDPOINT}/indexes/${SEARCH_INDEX}?api-version=2023-11-01" \
  -H "api-key: $SEARCH_KEY" \
  -s -o /dev/null || true

# Create the enhanced index
curl -X PUT "${SEARCH_ENDPOINT}/indexes/${SEARCH_INDEX}?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_KEY" \
  -d @enhanced-index.json

echo -e "\n${GREEN}✅ Search index created${NC}"

# Step 2: Create Data Source
echo -e "\n${YELLOW}📋 Creating data source...${NC}"

cat > datasource.json << EOF
{
  "name": "confluence-raw-datasource",
  "type": "azureblob",
  "credentials": {
    "connectionString": "${STORAGE_CONN}"
  },
  "container": {
    "name": "raw"
  }
}
EOF

curl -X PUT "${SEARCH_ENDPOINT}/datasources/confluence-raw-datasource?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_KEY" \
  -d @datasource.json

echo -e "${GREEN}✅ Data source created${NC}"

# Step 3: Create Integrated Skillset
echo -e "\n${YELLOW}📋 Creating integrated skillset...${NC}"

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
      "degreeOfParallelism": 5,
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
      "degreeOfParallelism": 5,
      "httpHeaders": {
        "Authorization": "Bearer ${OPENAI_API_KEY}",
        "Content-Type": "application/json"
      },
      "inputs": [
        {
          "name": "input",
          "source": "/document/body/value"
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
    },
    {
      "@odata.type": "#Microsoft.Skills.Util.ShaperSkill",
      "name": "ExtractVector",
      "context": "/document",
      "inputs": [
        {
          "name": "embedding",
          "sourceContext": "/document/embedding_response/*/",
          "source": "/document/embedding_response/*/embedding"
        }
      ],
      "outputs": [
        {
          "name": "output",
          "targetName": "content_vector_extracted"
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

echo -e "${GREEN}✅ Skillset created${NC}"

# Step 4: Create Indexer
echo -e "\n${YELLOW}📋 Creating indexer...${NC}"

cat > indexer.json << EOF
{
  "name": "confluence-integrated-indexer",
  "dataSourceName": "confluence-raw-datasource",
  "targetIndexName": "confluence-graph-embeddings",
  "skillsetName": "confluence-integrated-skillset",
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
      "sourceFieldName": "body/value",
      "targetFieldName": "content"
    },
    {
      "sourceFieldName": "space/key",
      "targetFieldName": "space_key"
    },
    {
      "sourceFieldName": "version/when",
      "targetFieldName": "last_modified"
    }
  ],
  "outputFieldMappings": [
    {
      "sourceFieldName": "/document/hierarchy_depth",
      "targetFieldName": "hierarchy_depth"
    },
    {
      "sourceFieldName": "/document/hierarchy_path",
      "targetFieldName": "hierarchy_path"
    },
    {
      "sourceFieldName": "/document/parent_page_id",
      "targetFieldName": "parent_page_id"
    },
    {
      "sourceFieldName": "/document/parent_page_title",
      "targetFieldName": "parent_page_title"
    },
    {
      "sourceFieldName": "/document/has_children",
      "targetFieldName": "has_children"
    },
    {
      "sourceFieldName": "/document/child_count",
      "targetFieldName": "child_count"
    },
    {
      "sourceFieldName": "/document/graph_centrality_score",
      "targetFieldName": "graph_centrality_score"
    },
    {
      "sourceFieldName": "/document/graph_metadata",
      "targetFieldName": "graph_metadata"
    },
    {
      "sourceFieldName": "/document/content_vector_extracted/embedding",
      "targetFieldName": "content_vector"
    }
  ],
  "schedule": {
    "interval": "PT2H",
    "startTime": "2025-01-01T00:00:00Z"
  },
  "parameters": {
    "configuration": {
      "parsingMode": "json"
    }
  }
}
EOF

curl -X PUT "${SEARCH_ENDPOINT}/indexers/confluence-integrated-indexer?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_KEY" \
  -d @indexer.json

echo -e "${GREEN}✅ Indexer created${NC}"

# Step 5: Run the indexer
echo -e "\n${YELLOW}🚀 Running indexer...${NC}"

curl -X POST "${SEARCH_ENDPOINT}/indexers/confluence-integrated-indexer/run?api-version=2023-11-01" \
  -H "api-key: $SEARCH_KEY"

echo -e "${GREEN}✅ Indexer started${NC}"

# Clean up temporary files
rm -f enhanced-index.json datasource.json integrated-skillset.json indexer.json

# Summary
echo -e "\n${BLUE}📊 Deployment Summary${NC}"
echo -e "${BLUE}=====================${NC}"
echo -e "✅ Search Index: ${SEARCH_INDEX}"
echo -e "✅ Data Source: confluence-raw-datasource"
echo -e "✅ Skillset: Graph enrichment + OpenAI embeddings"
echo -e "✅ Indexer: confluence-integrated-indexer"
echo -e "✅ Function URL: ${FUNCTION_URL}"
echo -e "✅ Schedule: Every 2 hours"

echo -e "\n${YELLOW}📋 Key Features:${NC}"
echo -e "- Graph enrichment via Azure Function"
echo -e "- OpenAI embeddings (3072 dimensions)"
echo -e "- Hierarchical scoring and boosting"
echo -e "- Semantic search configuration"
echo -e "- Graph centrality scoring"

echo -e "\n${YELLOW}🔍 Monitor Progress:${NC}"
echo "az search indexer status --name confluence-integrated-indexer --service-name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP"

echo -e "\n${YELLOW}📈 Check Document Count:${NC}"
echo "curl -X GET '${SEARCH_ENDPOINT}/indexes/${SEARCH_INDEX}/docs/\$count?api-version=2023-11-01' -H 'api-key: $SEARCH_KEY'"

echo -e "\n${GREEN}🎉 Graph-aware search with embeddings deployed!${NC}" 