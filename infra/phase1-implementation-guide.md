# Phase 1: Implementation Guide

This guide provides step-by-step instructions for implementing Phase 1 of the Confluence Q&A modernization using Azure AI Search native features.

## Prerequisites
- Azure OpenAI resource with text-embedding-ada-002 deployment
- Azure AI Search service (Basic tier or higher)
- Storage account with raw Confluence data
- Cosmos DB with graph data populated

## Step 1: Switch to Azure OpenAI Embedding Skill

### Replace custom Web API skill with built-in skill

**Old (Custom Web API):**
```json
{
  "@odata.type": "#Microsoft.Skills.Custom.WebApiSkill",
  "name": "GenerateEmbeddings",
  "uri": "https://api.openai.com/v1/embeddings",
  "httpHeaders": {
    "Authorization": "Bearer YOUR-OPENAI-KEY"
  }
}
```

**New (Azure OpenAI):**
```json
{
  "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
  "name": "AzureOpenAIEmbedding",
  "description": "Generate embeddings using Azure OpenAI",
  "resourceUri": "https://YOUR-RESOURCE.openai.azure.com",
  "apiKey": "YOUR-AZURE-OPENAI-KEY",
  "deploymentId": "text-embedding-ada-002",
  "inputs": [{
    "name": "text",
    "source": "/document/content"
  }],
  "outputs": [{
    "name": "embedding",
    "targetName": "contentVector"
  }]
}
```

## Step 2: Configure text-embedding-ada-002

Keep using the same model for compatibility:
```bash
# Deploy the model in Azure OpenAI
az cognitiveservices account deployment create \
  --name YOUR-OPENAI-RESOURCE \
  --resource-group YOUR-RG \
  --deployment-name text-embedding-ada-002 \
  --model-name text-embedding-ada-002 \
  --model-version "2" \
  --model-format OpenAI \
  --sku-capacity "120"
```

## Step 3: Add Query Vectorizers

Update your index definition to include vectorizers:

```json
{
  "name": "confluence-index",
  "fields": [...],
  "vectorSearch": {
    "algorithms": [{
      "name": "hnsw-algorithm",
      "kind": "hnsw",
      "hnswParameters": {
        "metric": "cosine",
        "m": 4,
        "efConstruction": 400,
        "efSearch": 500
      }
    }],
    "profiles": [{
      "name": "vector-profile",
      "algorithmConfigurationName": "hnsw-algorithm",
      "vectorizer": "ada-vectorizer"
    }],
    "vectorizers": [{
      "name": "ada-vectorizer",
      "kind": "azureOpenAI",
      "azureOpenAIParameters": {
        "resourceUri": "https://YOUR-RESOURCE.openai.azure.com",
        "deploymentId": "text-embedding-ada-002",
        "apiKey": "YOUR-AZURE-OPENAI-KEY"
      }
    }]
  }
}
```

Now queries automatically get vectorized:
```python
# Old way (manual embedding)
query_vector = openai.Embedding.create(input=query, model="text-embedding-ada-002")
search_client.search(vector=query_vector, ...)

# New way (automatic)
search_client.search(
    search_text=query,  # Just send text!
    vector_queries=[{
        "kind": "text",
        "text": query,
        "fields": "contentVector"
    }]
)
```

## Step 4: Optimize Chunking with Built-in Skills

Replace custom chunking with TextSplitSkill:

```json
{
  "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
  "name": "SplitSkill",
  "description": "Split content into chunks",
  "context": "/document",
  "textSplitMode": "pages",
  "maximumPageLength": 512,
  "pageOverlapLength": 128,
  "defaultLanguageCode": "en",
  "inputs": [{
    "name": "text",
    "source": "/document/content"
  }],
  "outputs": [{
    "name": "textItems",
    "targetName": "pages"
  }]
}
```

## Step 5: Configure Index Projections

Enable automatic parent-child mapping in your skillset:

```json
{
  "name": "confluence-skillset",
  "skills": [...],
  "indexProjections": {
    "selectors": [{
      "targetIndexName": "confluence-chunks",
      "parentKeyFieldName": "parentId",
      "sourceContext": "/document/pages/*",
      "mappings": [
        {
          "name": "chunkId",
          "source": "/document/pages/*/id"
        },
        {
          "name": "content",
          "source": "/document/pages/*"
        },
        {
          "name": "contentVector",
          "source": "/document/pages/*/contentVector"
        },
        {
          "name": "title",
          "source": "/document/title"
        }
      ]
    }]
  }
}
```

## Step 6: Add Hybrid Scoring Profiles

Configure graph-aware scoring in your index:

```json
{
  "name": "confluence-index",
  "fields": [
    {
      "name": "graph_centrality_score",
      "type": "Edm.Double",
      "searchable": false,
      "filterable": true,
      "sortable": true
    },
    {
      "name": "hierarchy_depth",
      "type": "Edm.Int32",
      "searchable": false,
      "filterable": true,
      "sortable": true
    }
  ],
  "scoringProfiles": [{
    "name": "confluence-graph-boost",
    "functions": [
      {
        "fieldName": "graph_centrality_score",
        "type": "magnitude",
        "boost": 3.0,
        "interpolation": "linear",
        "magnitude": {
          "boostingRangeStart": 0.5,
          "boostingRangeEnd": 1.0,
          "constantBoostBeyondRange": true
        }
      },
      {
        "fieldName": "hierarchy_depth",
        "type": "magnitude",
        "boost": 1.5,
        "interpolation": "logarithmic",
        "magnitude": {
          "boostingRangeStart": 1,
          "boostingRangeEnd": 5,
          "constantBoostBeyondRange": false
        }
      }
    ],
    "functionAggregation": "sum"
  }]
}
```

## Complete Deployment Script

```bash
#!/bin/bash
# deploy-phase1.sh

# Variables
RESOURCE_GROUP="rg-rag-confluence"
SEARCH_SERVICE="srch-rag-conf"
OPENAI_RESOURCE="aoai-rag-conf"
OPENAI_KEY="YOUR-KEY"

# Step 1: Update the skillset
echo "Updating skillset with Azure OpenAI embedding skill..."
curl -X PUT "https://${SEARCH_SERVICE}.search.windows.net/skillsets/confluence-skillset?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: ${SEARCH_KEY}" \
  -d @phase1-skillset.json

# Step 2: Update the index with vectorizers and scoring profiles
echo "Updating index with vectorizers and scoring profiles..."
curl -X PUT "https://${SEARCH_SERVICE}.search.windows.net/indexes/confluence-index?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: ${SEARCH_KEY}" \
  -d @phase1-index.json

# Step 3: Update the indexer
echo "Updating indexer configuration..."
curl -X PUT "https://${SEARCH_SERVICE}.search.windows.net/indexers/confluence-indexer?api-version=2023-11-01" \
  -H "Content-Type: application/json" \
  -H "api-key: ${SEARCH_KEY}" \
  -d @phase1-indexer.json

# Step 4: Run the indexer
echo "Starting indexer run..."
curl -X POST "https://${SEARCH_SERVICE}.search.windows.net/indexers/confluence-indexer/run?api-version=2023-11-01" \
  -H "api-key: ${SEARCH_KEY}"

echo "Phase 1 deployment complete!"
```

## Testing Phase 1

### Test 1: Verify Automatic Query Vectorization
```python
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# Create client
search_client = SearchClient(
    endpoint="https://YOUR-SEARCH.search.windows.net",
    index_name="confluence-chunks",
    credential=AzureKeyCredential("YOUR-KEY")
)

# Test text query (no manual embedding needed!)
results = search_client.search(
    search_text="How to configure Azure OpenAI?",
    vector_queries=[{
        "kind": "text",
        "text": "How to configure Azure OpenAI?",
        "fields": "contentVector",
        "k": 5
    }],
    select=["title", "content", "graph_centrality_score"],
    scoring_profile="confluence-graph-boost"
)

for result in results:
    print(f"Score: {result['@search.score']}")
    print(f"Title: {result['title']}")
    print(f"Centrality: {result['graph_centrality_score']}")
    print("---")
```

### Test 2: Verify Graph Boosting
```python
# Compare results with and without scoring profile
results_no_boost = search_client.search(
    search_text="Azure setup guide",
    top=5
)

results_with_boost = search_client.search(
    search_text="Azure setup guide",
    scoring_profile="confluence-graph-boost",
    top=5
)

print("Results WITHOUT graph boost:")
for r in results_no_boost:
    print(f"- {r['title']} (score: {r['@search.score']})")

print("\nResults WITH graph boost:")
for r in results_with_boost:
    print(f"- {r['title']} (score: {r['@search.score']})")
```

## Monitoring Phase 1

### Key Metrics to Track
1. **Indexing Performance**
   ```bash
   az search indexer status show \
     --name confluence-indexer \
     --service-name $SEARCH_SERVICE \
     --resource-group $RESOURCE_GROUP
   ```

2. **Embedding API Usage**
   ```bash
   az monitor metrics list \
     --resource "/subscriptions/.../providers/Microsoft.CognitiveServices/accounts/$OPENAI_RESOURCE" \
     --metric "TokenTransaction" \
     --interval PT1H
   ```

3. **Search Latency**
   ```python
   import time
   
   start = time.time()
   results = search_client.search(search_text="test query", top=1)
   list(results)  # Force execution
   latency = (time.time() - start) * 1000
   print(f"Search latency: {latency:.2f}ms")
   ```

## Rollback Plan

If issues arise, rollback to previous configuration:
```bash
# Restore previous skillset
curl -X PUT ".../skillsets/confluence-skillset?api-version=2023-11-01" \
  -d @backup/skillset-backup.json

# Restore previous index
curl -X PUT ".../indexes/confluence-index?api-version=2023-11-01" \
  -d @backup/index-backup.json

# Reset indexer
curl -X POST ".../indexers/confluence-indexer/reset?api-version=2023-11-01"
```

## Success Criteria

Phase 1 is complete when:
- [ ] All embeddings generated via Azure OpenAI skill
- [ ] Queries automatically vectorized (no manual embedding code)
- [ ] Text split skill handling all chunking
- [ ] Index projections creating proper parent-child relationships
- [ ] Graph boost scoring profiles improving relevance
- [ ] Search latency < 300ms for 95th percentile
- [ ] Zero custom embedding functions in production

## Next: Phase 2
Once Phase 1 is stable (1-2 weeks), proceed to Phase 2 for caching and performance optimization. 