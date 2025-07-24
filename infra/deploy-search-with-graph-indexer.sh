#!/bin/bash

# Deploy Azure AI Search with Native Graph-Aware Indexing
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Azure AI Search with Native Graph-Aware Indexing${NC}"
echo -e "${BLUE}========================================================${NC}"

# Set OpenAI API key if not already set
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}📋 Setting OpenAI API key from configuration...${NC}"
    export OPENAI_API_KEY="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"
fi

# Configuration
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_INDEX="confluence-graph-index"
STORAGE_ACCOUNT="stgragconf"
COSMOS_ACCOUNT="cosmos-rag-conf"

echo -e "${GREEN}✅ Using existing resources:${NC}"
echo -e "  - Resource Group: $RESOURCE_GROUP"
echo -e "  - Search Service: $SEARCH_SERVICE"
echo -e "  - Storage Account: $STORAGE_ACCOUNT"
echo -e "  - Cosmos DB: $COSMOS_ACCOUNT"

# Get connection strings and keys
echo -e "\n${YELLOW}🔑 Retrieving connection strings...${NC}"

STORAGE_CONN=$(az storage account show-connection-string --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query connectionString -o tsv)
SEARCH_KEY=$(az search admin-key show --resource-group $RESOURCE_GROUP --service-name $SEARCH_SERVICE --query primaryKey -o tsv)
SEARCH_ENDPOINT="https://${SEARCH_SERVICE}.search.windows.net"

echo -e "${GREEN}✅ Connection strings retrieved${NC}"

# Step 1: Create Graph-Aware Search Index
echo -e "\n${YELLOW}📋 Creating graph-aware search index...${NC}"

cat > search-index.json << 'EOF'
{
  "name": "confluence-graph-index",
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
      "name": "breadcrumb",
      "type": "Edm.String",
      "searchable": true
    },
    {
      "name": "hierarchy_depth",
      "type": "Edm.Int32",
      "searchable": false,
      "filterable": true,
      "sortable": true
    },
    {
      "name": "parent_page_id",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true
    },
    {
      "name": "content_vector",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 3072,
      "vectorSearchProfile": "vector-profile"
    },
    {
      "name": "metadata",
      "type": "Edm.String",
      "searchable": false
    },
    {
      "name": "last_modified",
      "type": "Edm.DateTimeOffset",
      "searchable": false,
      "filterable": true
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
              "fieldName": "breadcrumb"
            }
          ]
        }
      }
    ]
  }
}
EOF

# Create the index
curl -X PUT "${SEARCH_ENDPOINT}/indexes/${SEARCH_INDEX}?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_KEY" \
  -d @search-index.json

echo -e "\n${GREEN}✅ Search index created${NC}"

# Step 2: Create Data Source (pointing to raw pages)
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

# Step 3: Create Skillset with Custom Web API Skill for Embeddings
echo -e "\n${YELLOW}📋 Creating skillset with OpenAI embeddings...${NC}"

cat > skillset.json << EOF
{
  "name": "confluence-graph-skillset",
  "description": "Skillset for processing Confluence pages with graph context",
  "skills": [
    {
      "@odata.type": "#Microsoft.Skills.Text.EntityRecognitionSkill",
      "name": "ExtractEntities",
      "context": "/document",
      "categories": ["Organization", "Person", "Location"],
      "defaultLanguageCode": "en",
      "inputs": [
        {
          "name": "text",
          "source": "/document/body/storage/value"
        }
      ],
      "outputs": [
        {
          "name": "organizations",
          "targetName": "organizations"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Custom.WebApiSkill",
      "name": "GenerateEmbeddings",
      "description": "Generate embeddings using OpenAI API",
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
    },
    {
      "@odata.type": "#Microsoft.Skills.Util.ShaperSkill",
      "name": "ExtractVector",
      "context": "/document",
      "inputs": [
        {
          "name": "embedding",
          "source": "/document/embedding_response/0/embedding"
        }
      ],
      "outputs": [
        {
          "name": "output",
          "targetName": "content_vector"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Util.ShaperSkill",
      "name": "ExtractMetadata",
      "context": "/document",
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
        },
        {
          "name": "ancestors",
          "source": "/document/ancestors"
        }
      ],
      "outputs": [
        {
          "name": "output",
          "targetName": "metadata"
        }
      ]
    }
  ],
  "cognitiveServices": {
    "@odata.type": "#Microsoft.Azure.Search.CognitiveServicesByKey",
    "description": "OpenAI API Key",
    "key": "${OPENAI_API_KEY}"
  }
}
EOF

curl -X PUT "${SEARCH_ENDPOINT}/skillsets/confluence-graph-skillset?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_KEY" \
  -d @skillset.json

echo -e "${GREEN}✅ Skillset created${NC}"

# Step 4: Create Indexer
echo -e "\n${YELLOW}📋 Creating indexer...${NC}"

cat > indexer.json << EOF
{
  "name": "confluence-graph-indexer",
  "dataSourceName": "confluence-raw-datasource",
  "targetIndexName": "confluence-graph-index",
  "skillsetName": "confluence-graph-skillset",
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
      "sourceFieldName": "space/key",
      "targetFieldName": "space_key",
      "mappingFunction": {
        "name": "jsonArrayToStringCollection"
      }
    },
    {
      "sourceFieldName": "ancestors",
      "targetFieldName": "breadcrumb",
      "mappingFunction": {
        "name": "jsonArrayToStringCollection"
      }
    }
  ],
  "outputFieldMappings": [
    {
      "sourceFieldName": "/document/content_vector/output/embedding",
      "targetFieldName": "content_vector"
    },
    {
      "sourceFieldName": "/document/metadata/output",
      "targetFieldName": "metadata"
    }
  ],
  "schedule": {
    "interval": "PT2H",
    "startTime": "2025-01-01T00:00:00Z"
  },
  "parameters": {
    "configuration": {
      "parseMode": "jsonArray",
      "parsingMode": "json"
    }
  }
}
EOF

curl -X PUT "${SEARCH_ENDPOINT}/indexers/confluence-graph-indexer?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_KEY" \
  -d @indexer.json

echo -e "${GREEN}✅ Indexer created${NC}"

# Step 5: Run the indexer
echo -e "\n${YELLOW}🚀 Running indexer...${NC}"

curl -X POST "${SEARCH_ENDPOINT}/indexers/confluence-graph-indexer/run?api-version=2023-11-01" \
  -H "api-key: $SEARCH_KEY"

echo -e "${GREEN}✅ Indexer started${NC}"

# Clean up temporary files
rm -f search-index.json datasource.json skillset.json indexer.json

# Summary
echo -e "\n${BLUE}📊 Deployment Summary${NC}"
echo -e "${BLUE}=====================${NC}"
echo -e "✅ Search Index: ${SEARCH_INDEX}"
echo -e "✅ Data Source: confluence-raw-datasource (blob storage)"
echo -e "✅ Skillset: Custom Web API skill for OpenAI embeddings"
echo -e "✅ Indexer: confluence-graph-indexer (runs every 2 hours)"
echo -e "✅ Vector Search: Enabled with 3072 dimensions"
echo -e "✅ Semantic Search: Configured"

echo -e "\n${YELLOW}📋 Key Features:${NC}"
echo -e "- Direct blob storage to search indexing"
echo -e "- No custom function app needed"
echo -e "- OpenAI embeddings via Web API skill"
echo -e "- Automatic incremental updates"
echo -e "- Built-in retry and error handling"

echo -e "\n${YELLOW}🔍 Monitor Progress:${NC}"
echo -e "1. Check indexer status:"
echo -e "   curl -X GET '${SEARCH_ENDPOINT}/indexers/confluence-graph-indexer/status?api-version=2023-11-01' -H 'api-key: $SEARCH_KEY' | jq"
echo -e ""
echo -e "2. View indexed documents:"
echo -e "   curl -X GET '${SEARCH_ENDPOINT}/indexes/${SEARCH_INDEX}/docs/\$count?api-version=2023-11-01' -H 'api-key: $SEARCH_KEY'"

echo -e "\n${GREEN}🎉 Azure AI Search native indexing deployed!${NC}" 