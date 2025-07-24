#!/bin/bash

# Test Azure OpenAI embedding generation
AZURE_OPENAI_ENDPOINT="https://aoai-rag-confluence.openai.azure.com/"
AZURE_OPENAI_KEY="2N8xjmhO6M6kE6MO8Opa6KRXMvdyuzvJoJ3kqCJQDdfBaFM1qlz2JQQJ99BGACYeBjFXJ3w3AAABACOGXqVW"

echo "Testing Azure OpenAI embedding generation..."

curl -X POST "${AZURE_OPENAI_ENDPOINT}openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15" \
  -H "Content-Type: application/json" \
  -H "api-key: ${AZURE_OPENAI_KEY}" \
  -d '{
    "input": "This is a test text for embedding generation"
  }' | jq '.data[0].embedding | length'