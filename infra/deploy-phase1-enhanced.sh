#!/bin/bash

# Phase 1 Enhanced: Deploy Azure AI Search with Graph Enrichment and Embedding Layer Fields
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}🚀 Phase 1 Enhanced: Graph-Aware Search with Embedding Layer Support${NC}"
echo -e "${BLUE}==================================================${NC}"

# Configuration
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_INDEX="confluence-graph-embeddings"
STORAGE_ACCOUNT="stgragconf"
COSMOS_ACCOUNT="cosmos-rag-conf"
FUNCTION_APP="func-rag-conf"
AZURE_OPENAI_ENDPOINT="${AOAI_ENDPOINT:-https://your-aoai.openai.azure.com/}"
AZURE_OPENAI_KEY="${AOAI_KEY}"

# Step 1: Deploy Graph Enrichment Function (if not already deployed)
echo -e "\n${YELLOW}📦 Step 1: Ensuring Graph Enrichment Function is deployed...${NC}"
if [ -f "./deploy-graph-enrichment-function.sh" ]; then
    ./deploy-graph-enrichment-function.sh
else
    echo -e "${RED}Graph enrichment deployment script not found!${NC}"
    exit 1
fi

# Get Function Key for Graph Enrichment
echo -e "\n${YELLOW}🔑 Getting Function Key...${NC}"
FUNCTION_KEY=$(az functionapp function keys list \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --function-name graph_enrichment_skill \
    --query default -o tsv)

if [ -z "$FUNCTION_KEY" ]; then
    echo -e "${RED}Failed to get function key!${NC}"
    exit 1
fi

# Step 2: Create Data Source
echo -e "\n${YELLOW}📊 Step 2: Creating Data Source...${NC}"
cat > datasource.json << EOF
{
  "name": "confluence-blob-datasource",
  "type": "azureblob",
  "credentials": {
    "connectionString": "$(az storage account show-connection-string --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query connectionString -o tsv)"
  },
  "container": {
    "name": "confluence-data",
    "query": "raw/"
  }
}
EOF

az search datasource create \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --datasource @datasource.json

# Step 3: Create Skillset with Graph Enrichment and Azure OpenAI
echo -e "\n${YELLOW}🧠 Step 3: Creating Skillset with Graph Enrichment...${NC}"
cat > skillset.json << EOF
{
  "name": "confluence-graph-skillset",
  "description": "Graph-aware skillset with chunking, enrichment, and embeddings",
  "skills": [
    {
      "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
      "name": "SplitSkill",
      "description": "Split content into chunks",
      "context": "/document",
      "textSplitMode": "pages",
      "maximumPageLength": 512,
      "pageOverlapLength": 128,
      "defaultLanguageCode": "en",
      "inputs": [
        {
          "name": "text",
          "source": "/document/content"
        }
      ],
      "outputs": [
        {
          "name": "textItems",
          "targetName": "pages"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Custom.WebApiSkill",
      "name": "GraphEnrichment",
      "description": "Enrich with Cosmos DB graph data",
      "uri": "https://$FUNCTION_APP.azurewebsites.net/api/graph_enrichment_skill",
      "httpMethod": "POST",
      "timeout": "PT90S",
      "batchSize": 10,
      "httpHeaders": {
        "x-functions-key": "$FUNCTION_KEY"
      },
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
          "source": "/document/space_key"
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
          "name": "sibling_count",
          "targetName": "sibling_count"
        },
        {
          "name": "related_page_count",
          "targetName": "related_page_count"
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
      "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
      "name": "AzureOpenAIEmbedding",
      "description": "Generate embeddings using Azure OpenAI",
      "context": "/document/pages/*",
      "resourceUri": "$AZURE_OPENAI_ENDPOINT",
      "apiKey": "$AZURE_OPENAI_KEY",
      "deploymentId": "text-embedding-ada-002",
      "inputs": [
        {
          "name": "text",
          "source": "/document/pages/*"
        }
      ],
      "outputs": [
        {
          "name": "embedding",
          "targetName": "contentVector"
        }
      ]
    }
  ]
}
EOF

az search skillset create \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --skillset @skillset.json

# Step 4: Create Index with Graph Fields and Vector Configuration
echo -e "\n${YELLOW}🗄️ Step 4: Creating Index with Enhanced Fields...${NC}"
cat > index.json << EOF
{
  "name": "$SEARCH_INDEX",
  "fields": [
    {
      "name": "id",
      "type": "Edm.String",
      "key": true,
      "searchable": false,
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
      "name": "title",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "sortable": true,
      "analyzer": "standard.lucene",
      "retrievable": true
    },
    {
      "name": "content",
      "type": "Edm.String",
      "searchable": true,
      "analyzer": "standard.lucene",
      "retrievable": true
    },
    {
      "name": "space_key",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "chunk_type",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "contentVector",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 1536,
      "vectorSearchProfile": "vector-profile"
    },
    {
      "name": "content_vector",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 1536,
      "vectorSearchProfile": "vector-profile"
    },
    {
      "name": "title_vector",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 1536,
      "vectorSearchProfile": "vector-profile"
    },
    {
      "name": "chunk_id",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "chunk_text",
      "type": "Edm.String",
      "searchable": true,
      "analyzer": "standard.lucene",
      "retrievable": true
    },
    {
      "name": "chunk_index",
      "type": "Edm.Int32",
      "searchable": false,
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "total_chunks",
      "type": "Edm.Int32",
      "searchable": false,
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "breadcrumb",
      "type": "Collection(Edm.String)",
      "searchable": true,
      "retrievable": true
    },
    {
      "name": "hierarchy_depth",
      "type": "Edm.Int32",
      "filterable": true,
      "sortable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "hierarchy_path",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "analyzer": "keyword",
      "retrievable": true
    },
    {
      "name": "parent_page_id",
      "type": "Edm.String",
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "parent_page_title",
      "type": "Edm.String",
      "searchable": true,
      "retrievable": true
    },
    {
      "name": "has_children",
      "type": "Edm.Boolean",
      "filterable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "child_count",
      "type": "Edm.Int32",
      "filterable": true,
      "sortable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "sibling_count",
      "type": "Edm.Int32",
      "filterable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "related_page_count",
      "type": "Edm.Int32",
      "filterable": true,
      "sortable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "graph_centrality_score",
      "type": "Edm.Double",
      "filterable": true,
      "sortable": true,
      "facetable": true,
      "retrievable": true
    },
    {
      "name": "graph_metadata",
      "type": "Edm.String",
      "retrievable": true
    },
    {
      "name": "metadata",
      "type": "Edm.String",
      "searchable": false,
      "retrievable": true
    },
    {
      "name": "created_at",
      "type": "Edm.DateTimeOffset",
      "searchable": false,
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "updated_at",
      "type": "Edm.DateTimeOffset",
      "searchable": false,
      "filterable": true,
      "retrievable": true
    }
  ],
  "scoringProfiles": [
    {
      "name": "confluence-graph-boost",
      "text": {
        "weights": {
          "title": 3.0,
          "parent_page_title": 2.0,
          "hierarchy_path": 1.5,
          "content": 1.0,
          "chunk_text": 0.8
        }
      },
      "functions": [
        {
          "fieldName": "graph_centrality_score",
          "type": "magnitude",
          "boost": 5.0,
          "interpolation": "quadratic",
          "magnitude": {
            "boostingRangeStart": 0.3,
            "boostingRangeEnd": 1.0,
            "constantBoostBeyondRange": true
          }
        },
        {
          "fieldName": "hierarchy_depth",
          "type": "magnitude",
          "boost": 2.0,
          "interpolation": "logarithmic",
          "magnitude": {
            "boostingRangeStart": 5,
            "boostingRangeEnd": 1,
            "constantBoostBeyondRange": false
          }
        },
        {
          "fieldName": "child_count",
          "type": "magnitude",
          "boost": 1.5,
          "interpolation": "linear",
          "magnitude": {
            "boostingRangeStart": 0,
            "boostingRangeEnd": 10,
            "constantBoostBeyondRange": true
          }
        },
        {
          "fieldName": "related_page_count",
          "type": "magnitude",
          "boost": 1.2,
          "interpolation": "linear",
          "magnitude": {
            "boostingRangeStart": 0,
            "boostingRangeEnd": 20,
            "constantBoostBeyondRange": true
          }
        }
      ],
      "functionAggregation": "sum"
    }
  ],
  "defaultScoringProfile": "confluence-graph-boost",
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
        "algorithm": "hnsw-algorithm",
        "vectorizer": "azure-openai-vectorizer"
      }
    ],
    "vectorizers": [
      {
        "@odata.type": "#Microsoft.Azure.Search.AzureOpenAIVectorizer",
        "name": "azure-openai-vectorizer",
        "azureOpenAIParameters": {
          "resourceUri": "$AZURE_OPENAI_ENDPOINT",
          "deploymentId": "text-embedding-ada-002",
          "apiKey": "$AZURE_OPENAI_KEY"
        }
      }
    ]
  },
  "semantic": {
    "configurations": [
      {
        "name": "confluence-semantic-config",
        "prioritizedFields": {
          "titleField": {
            "fieldName": "title"
          },
          "prioritizedContentFields": [
            {
              "fieldName": "content"
            },
            {
              "fieldName": "chunk_text"
            }
          ]
        }
      }
    ]
  }
}
EOF

az search index create \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --index @index.json

# Step 5: Create Indexer with Projections
echo -e "\n${YELLOW}⚙️ Step 5: Creating Indexer with Projections...${NC}"
cat > indexer.json << EOF
{
  "name": "confluence-graph-indexer",
  "dataSourceName": "confluence-blob-datasource",
  "skillsetName": "confluence-graph-skillset",
  "targetIndexName": "$SEARCH_INDEX",
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
      "sourceFieldName": "content",
      "targetFieldName": "content"
    },
    {
      "sourceFieldName": "space_key",
      "targetFieldName": "space_key"
    }
  ],
  "outputFieldMappings": [
    {
      "sourceFieldName": "/document/pages/*/contentVector",
      "targetFieldName": "contentVector"
    },
    {
      "sourceFieldName": "/document/pages/*/contentVector",
      "targetFieldName": "content_vector"
    },
    {
      "sourceFieldName": "/document/pages/*",
      "targetFieldName": "chunk_text"
    },
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
      "sourceFieldName": "/document/sibling_count",
      "targetFieldName": "sibling_count"
    },
    {
      "sourceFieldName": "/document/related_page_count",
      "targetFieldName": "related_page_count"
    },
    {
      "sourceFieldName": "/document/graph_centrality_score",
      "targetFieldName": "graph_centrality_score"
    },
    {
      "sourceFieldName": "/document/graph_metadata",
      "targetFieldName": "graph_metadata"
    }
  ],
  "schedule": {
    "interval": "PT1H"
  },
  "parameters": {
    "configuration": {
      "parsingMode": "json",
      "indexProjections": {
        "selectors": [
          {
            "targetIndexName": "$SEARCH_INDEX",
            "parentKeyFieldName": "id",
            "sourceContext": "/document/pages/*",
            "mappings": [
              {
                "name": "chunk_id",
                "source": "/document/pages/*/chunk_id",
                "inputFieldMappingFunction": {
                  "name": "generateId"
                }
              },
              {
                "name": "contentVector",
                "source": "/document/pages/*/contentVector"
              },
              {
                "name": "content_vector",
                "source": "/document/pages/*/contentVector"
              },
              {
                "name": "chunk_text",
                "source": "/document/pages/*"
              }
            ]
          }
        ]
      }
    }
  }
}
EOF

az search indexer create \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --indexer @indexer.json

# Step 6: Run the indexer
echo -e "\n${YELLOW}🚀 Step 6: Running the indexer...${NC}"
az search indexer run \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --name confluence-graph-indexer

# Step 7: Monitor indexer status
echo -e "\n${YELLOW}📊 Step 7: Monitoring indexer status...${NC}"
sleep 10
az search indexer status \
    --service-name $SEARCH_SERVICE \
    --resource-group $RESOURCE_GROUP \
    --name confluence-graph-indexer

# Step 8: Test the search
echo -e "\n${YELLOW}🔍 Step 8: Testing search with graph boost...${NC}"
cat > test-search.json << EOF
{
  "search": "getting started",
  "queryType": "simple",
  "searchFields": "title,content,parent_page_title,hierarchy_path,chunk_text",
  "select": "title,page_id,chunk_type,hierarchy_path,graph_centrality_score,parent_page_title",
  "top": 5,
  "scoringProfile": "confluence-graph-boost"
}
EOF

echo -e "\n${GREEN}✅ Phase 1 Enhanced Deployment Complete!${NC}"
echo -e "\n${BLUE}Next Steps:${NC}"
echo -e "1. Monitor indexer progress in Azure Portal"
echo -e "2. Test search queries with graph boost"
echo -e "3. Verify graph enrichment data"
echo -e "4. Configure monitoring alerts"

echo -e "\n${BLUE}Key Features Enabled:${NC}"
echo -e "✅ Azure OpenAI native embedding skill"
echo -e "✅ Graph enrichment from Cosmos DB"  
echo -e "✅ Automatic query vectorization"
echo -e "✅ Graph-based scoring profiles"
echo -e "✅ Index projections for chunking"
echo -e "✅ Hierarchical navigation support"
echo -e "✅ Embedding layer field support"
echo -e "✅ Dual vector fields (content & title)"
echo -e "✅ Chunk type categorization"
echo -e "✅ Timestamp tracking"

# Cleanup
rm -f datasource.json skillset.json index.json indexer.json test-search.json 