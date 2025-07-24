# Azure AI Search Vector Index Deployment Guide

## Overview

This guide provides instructions for deploying Azure AI Search with vector search capabilities using Azure OpenAI embeddings for the Confluence Q&A system.

## Prerequisites

- Azure CLI installed and authenticated
- Azure subscription with the following resources already deployed:
  - Resource Group: `rg-rag-confluence`
  - Azure OpenAI Service: `aoai-rag-confluence` with `text-embedding-ada-002` deployment
  - Azure AI Search Service: `srch-rag-conf`
  - Storage Account: `stgragconf` with `confluence-data` container
  - Confluence data already ingested into storage

## Deployment Scripts

### 1. Main Deployment Script: `deploy-vector-index-final.sh`

This is the primary deployment script that:
- Creates a data source pointing to Azure Storage
- Creates a skillset with text splitting and Azure OpenAI embeddings
- Creates an index with vector fields and semantic search
- Creates and runs an indexer to process documents

**Features:**
- Uses API version `2024-05-01-preview` for latest Azure OpenAI embedding skill support
- Automatic text splitting (1000 chars with 100 char overlap)
- Dual vector fields for content and title embeddings
- Semantic search configuration
- Recency boost scoring profile
- Scheduled indexing every 2 hours

**Usage:**
```bash
./deploy-vector-index-final.sh
```

### 2. Testing Script: `test-vector-search.sh`

Comprehensive testing script that validates:
- Index existence and statistics
- Indexer status and health
- Keyword search functionality
- Semantic search functionality
- Faceted search
- Filtered search
- Vector field population

**Usage:**
```bash
./test-vector-search.sh
```

### 3. Query Embedding Generator: `generate-azure-query-embedding.py`

Python script to generate query embeddings for vector search testing:
- Uses Azure OpenAI to generate embeddings
- Creates properly formatted vector search queries
- Outputs curl commands for testing

**Usage:**
```bash
python generate-azure-query-embedding.py "your search query"
```

## Architecture

### Index Schema

| Field | Type | Purpose |
|-------|------|---------|
| id | Edm.String | Unique document identifier |
| page_id | Edm.String | Confluence page ID |
| title | Edm.String | Page title (searchable) |
| content | Edm.String | Page content (searchable) |
| space_key | Edm.String | Confluence space (filterable) |
| pages | Collection(Edm.String) | Content chunks |
| contentVector | Collection(Edm.Single) | Content embeddings (1536 dimensions) |
| titleVector | Collection(Edm.Single) | Title embeddings (1536 dimensions) |
| created_at | Edm.DateTimeOffset | Creation timestamp |
| updated_at | Edm.DateTimeOffset | Update timestamp |
| breadcrumb | Collection(Edm.String) | Navigation path |

### Skillset Pipeline

1. **Text Splitting**: Splits long content into manageable chunks
2. **Content Embedding**: Generates embeddings for each content chunk
3. **Title Embedding**: Generates embeddings for document titles
4. **Metadata Merge**: Combines metadata fields

### Vector Search Configuration

- **Algorithm**: HNSW (Hierarchical Navigable Small World)
- **Distance Metric**: Cosine similarity
- **Parameters**:
  - m: 4 (number of bi-directional links)
  - efConstruction: 400 (size of dynamic list)
  - efSearch: 500 (search parameter)

## Search Queries

### 1. Simple Keyword Search
```bash
curl -X POST 'https://srch-rag-conf.search.windows.net/indexes/confluence-vectors-final/docs/search?api-version=2024-05-01-preview' \
  -H 'api-key: YOUR_SEARCH_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"search": "confluence setup", "top": 5}'
```

### 2. Semantic Search
```bash
curl -X POST 'https://srch-rag-conf.search.windows.net/indexes/confluence-vectors-final/docs/search?api-version=2024-05-01-preview' \
  -H 'api-key: YOUR_SEARCH_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "search": "how to create a new page in confluence",
    "queryType": "semantic",
    "semanticConfiguration": "confluence-semantic-config",
    "top": 5
  }'
```

### 3. Vector Search
First generate query embedding:
```bash
python generate-azure-query-embedding.py "your search query"
```

Then use the generated vector in search:
```bash
curl -X POST 'https://srch-rag-conf.search.windows.net/indexes/confluence-vectors-final/docs/search?api-version=2024-05-01-preview' \
  -H 'api-key: YOUR_SEARCH_KEY' \
  -H 'Content-Type: application/json' \
  -d @vector-search-query.json
```

### 4. Hybrid Search (Keyword + Vector)
```json
{
  "search": "confluence permissions",
  "vectors": [{
    "value": [/* query embedding vector */],
    "fields": "contentVector,titleVector",
    "k": 5
  }],
  "queryType": "simple",
  "top": 5
}
```

### 5. Filtered Search
```json
{
  "search": "*",
  "filter": "space_key eq 'PROJ'",
  "top": 10
}
```

## Monitoring and Troubleshooting

### Check Indexer Status
```bash
curl -X GET 'https://srch-rag-conf.search.windows.net/indexers/confluence-final-indexer/status?api-version=2024-05-01-preview' \
  -H 'api-key: YOUR_SEARCH_KEY' | jq
```

### Common Issues

1. **No vectors in documents**
   - Check Azure OpenAI deployment is active
   - Verify API key permissions
   - Review indexer execution history for errors

2. **Indexer failures**
   - Check skillset errors in indexer status
   - Verify data source connection
   - Review document format in storage

3. **Poor search results**
   - Tune the scoring profiles
   - Adjust text splitting parameters
   - Consider hybrid search approach

### Performance Optimization

1. **Indexing Performance**
   - Adjust batch size in indexer (default: 10)
   - Monitor Azure OpenAI rate limits
   - Consider parallel indexing for large datasets

2. **Search Performance**
   - Use filters to reduce search scope
   - Implement caching for common queries
   - Monitor and adjust efSearch parameter

## Cost Considerations

- **Azure OpenAI**: Charged per 1K tokens for embeddings
- **Azure AI Search**: Based on tier and storage
- **Storage**: Minimal cost for JSON documents
- **Compute**: Function Apps for custom skills (if used)

## Security

- API keys are retrieved dynamically from Azure
- No credentials are hardcoded in scripts
- Use managed identities where possible
- Implement RBAC for production deployments

## Next Steps

1. Implement a search API wrapper for the application
2. Add query expansion and relevance tuning
3. Implement result re-ranking based on user feedback
4. Add monitoring and analytics
5. Consider implementing incremental indexing for updates