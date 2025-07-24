#!/bin/bash

# Create skillset with Knowledge Store for chunk projection (fixed)
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
STORAGE_ACCOUNT="stgragconf"
SEARCH_ADMIN_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)
STORAGE_CONNECTION=$(az storage account show-connection-string --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query "connectionString" -o tsv)

# Azure OpenAI details
AZURE_OPENAI_ENDPOINT="https://aoai-rag-confluence.openai.azure.com/"
AZURE_OPENAI_KEY="2N8xjmhO6M6kE6MO8Opa6KRXMvdyuzvJoJ3kqCJQDdfBaFM1qlz2JQQJ99BGACYeBjFXJ3w3AAABACOGXqVW"

echo "Creating chunk-level skillset with Knowledge Store (fixed)..."

# Delete existing skillset
curl -X DELETE \
  "https://srch-rag-conf.search.windows.net/skillsets/confluence-chunk-skillset?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY"

sleep 2

# Create container for Knowledge Store
az storage container create \
  --name knowledge-store-chunks \
  --account-name $STORAGE_ACCOUNT \
  --auth-mode key 2>/dev/null || true

# Create new skillset with proper structure
curl -X PUT \
  "https://srch-rag-conf.search.windows.net/skillsets/confluence-chunk-skillset?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "confluence-chunk-skillset",
  "description": "Skillset with chunking and Knowledge Store projection",
  "skills": [
    {
      "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
      "name": "SplitContent",
      "description": "Split content into chunks",
      "context": "/document",
      "defaultLanguageCode": "en",
      "textSplitMode": "pages",
      "maximumPageLength": 2000,
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
      "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
      "name": "GenerateChunkEmbeddings",
      "description": "Generate embeddings for each chunk",
      "context": "/document/pages/*",
      "resourceUri": "'"$AZURE_OPENAI_ENDPOINT"'",
      "apiKey": "'"$AZURE_OPENAI_KEY"'",
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
          "targetName": "vector"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Util.ShaperSkill",
      "name": "ShapeChunks",
      "description": "Shape chunks for projection",
      "context": "/document/pages/*",
      "inputs": [
        {
          "name": "chunk_text",
          "source": "/document/pages/*"
        },
        {
          "name": "chunk_embedding",
          "source": "/document/pages/*/vector"
        },
        {
          "name": "parent_title",
          "source": "/document/title"
        },
        {
          "name": "parent_id",
          "source": "/document/page_id"
        },
        {
          "name": "space_key",
          "source": "/document/space_key"
        },
        {
          "name": "parent_path",
          "source": "/document/metadata_storage_path"
        }
      ],
      "outputs": [
        {
          "name": "output",
          "targetName": "chunkDocument"
        }
      ]
    }
  ],
  "knowledgeStore": {
    "storageConnectionString": "'"$STORAGE_CONNECTION"'",
    "projections": [
      {
        "tables": [],
        "objects": [
          {
            "storageContainer": "knowledge-store-chunks",
            "generatedKeyName": "chunk_id",
            "source": "/document/pages/*/chunkDocument"
          }
        ],
        "files": []
      }
    ]
  }
}'

echo ""
echo "Chunk-level skillset with Knowledge Store created!"