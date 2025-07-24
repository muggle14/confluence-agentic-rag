#!/bin/bash

# Create skillset with proper Azure OpenAI configuration
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
SEARCH_ADMIN_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)

# Azure OpenAI details
AZURE_OPENAI_ENDPOINT="https://aoai-rag-confluence.openai.azure.com/"
AZURE_OPENAI_KEY="2N8xjmhO6M6kE6MO8Opa6KRXMvdyuzvJoJ3kqCJQDdfBaFM1qlz2JQQJ99BGACYeBjFXJ3w3AAABACOGXqVW"

echo "Creating skillset..."

curl -X PUT \
  "https://srch-rag-conf.search.windows.net/skillsets/confluence-graph-skillset?api-version=2023-11-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "confluence-graph-skillset",
  "description": "Skillset with text splitting and Azure OpenAI embeddings",
  "skills": [
    {
      "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
      "name": "SplitSkill",
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
      "name": "ContentEmbeddingSkill",
      "description": "Generate embeddings for content chunks",
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
          "targetName": "contentVector"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
      "name": "TitleEmbeddingSkill",
      "description": "Generate embeddings for title",
      "context": "/document",
      "resourceUri": "'"$AZURE_OPENAI_ENDPOINT"'",
      "apiKey": "'"$AZURE_OPENAI_KEY"'",
      "deploymentId": "text-embedding-ada-002",
      "inputs": [
        {
          "name": "text",
          "source": "/document/title"
        }
      ],
      "outputs": [
        {
          "name": "embedding",
          "targetName": "titleVector"
        }
      ]
    }
  ]
}'

echo ""
echo "Skillset created!"