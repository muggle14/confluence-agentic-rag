# Azure Search Implementation Guide: Complete Process Flow

## Table of Contents
1. [Overview](#overview)
2. [Resource Flow Diagram](#resource-flow-diagram)
3. [Code Flow Diagram](#code-flow-diagram)
4. [Relevant Code Assets](#relevant-code-assets)
5. [Deprecated Scripts and Files](#deprecated-scripts-and-files)
6. [Step-by-Step Implementation](#step-by-step-implementation)
7. [Azure Resources](#azure-resources)

---

## Overview

This document details the complete implementation of the Azure AI Search solution for Confluence Q&A, including both document-level and chunk-level search capabilities.

## Resource Flow Diagram

```
┌─────────────────────┐
│   Confluence API    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌──────────────────────┐
│  Azure Function     │────▶│  Blob Storage        │
│  (Ingestion)        │     │  Container: raw/     │
└─────────────────────┘     └──────────┬───────────┘
                                       │
                                       ▼
                            ┌──────────────────────┐
                            │  Azure AI Search     │
                            │  - Indexer           │
                            │  - Skillset          │
                            │  - Index             │
                            └──────────┬───────────┘
                                       │
                            ┌──────────┴───────────┐
                            ▼                      ▼
                    ┌───────────────┐     ┌──────────────────┐
                    │ Document Index │     │   Chunk Index    │
                    │ (Full docs)    │     │ (Doc fragments)  │
                    └───────────────┘     └──────────────────┘
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │  Azure OpenAI    │
                                          │  (Embeddings)    │
                                          └──────────────────┘
```

## Code Flow Diagram

```
1. Data Ingestion
   └── Azure Function reads from Confluence API
   └── Stores raw JSON in blob storage

2. Document-Level Indexing (Simple)
   ├── create-index.sh
   ├── create-simple-skillset.sh
   ├── update-indexer-simple.sh
   └── run-indexer.sh

3. Chunk-Level Indexing (Advanced)
   ├── create-chunk-index.sh
   ├── create-chunking-solution.py
   └── test-chunk-indexing.py
```

---

## Relevant Code Assets

### 🟢 ACTIVE - Infrastructure Scripts

#### 1. **Index Creation**
```bash
# Document-level index
infra/create-index.sh

# Chunk-level index  
infra/create-chunk-index.sh
```

#### 2. **Skillset Configuration**
```bash
# Current working skillset (simple, no chunking)
infra/create-simple-skillset.sh

# Skillset with chunking (Knowledge Store approach)
infra/create-chunk-skillset-fixed.sh
```

#### 3. **Indexer Configuration**
```bash
# Simple indexer for document-level
infra/update-indexer-simple.sh

# Indexer running script
infra/run-indexer.sh
```

#### 4. **Chunking Solution**
```python
# Python solution for chunk-level indexing
infra/create-chunking-solution.py
infra/test-chunk-indexing.py
infra/run-chunking-solution.sh
```

#### 5. **Fix Scripts**
```bash
# Field mapping fixes
infra/fix-indexer.sh
```

### 🟢 ACTIVE - Configuration Files

#### 1. **Data Source Configuration**
```json
infra/datasource.json
{
  "name": "confluence-blob-datasource",
  "type": "azureblob",
  "container": {
    "name": "confluence-data",
    "query": "raw/"
  }
}
```

#### 2. **Skillset Configuration**
```json
infra/skillset.json
# Contains Azure OpenAI embedding skills configuration
```

#### 3. **Sample Data**
```json
infra/sample_page.json
# Sample Confluence page structure for reference
```

### 🟢 ACTIVE - Test and Utility Scripts

```bash
# Embedding tests
infra/test-embedding.sh
infra/generate-azure-query-embedding.py

# Search tests
infra/test-vector-search.sh

# Deployment verification
infra/test-phase1-deployment.sh
```

---

## Deprecated Scripts and Files

### 🔴 DEPRECATED - Can Be Deleted

#### 1. **Old Deployment Scripts**
These scripts use outdated configurations or API versions:

```bash
# Phase 1 deployment attempts (various issues)
infra/deploy-phase1-enhanced.sh
infra/deploy-phase1-fixed.sh
infra/deploy-phase1-with-graph.sh



# Graph-aware search (complex, not working)
infra/deploy-graph-aware-search-integrated.sh
infra/deploy-search-with-graph-indexer.sh

# Embedding search deployment
infra/deploy-embedding-search.sh

# Graph enrichment function deployment
infra/deploy-graph-enrichment-function.sh
```

#### 2. **Old Skillset Configurations**
```bash


```

#### 3. **Complete Deployment Script**
```bash
infra/complete-deployment.sh  # Uses outdated approach
```

#### 4. **Old Documentation**
```markdown
# Can be archived/deleted
INGESTION-PIPELINE-SUMMARY.md
PROCESSING-PIPELINE-SUMMARY.md
ingestion-README-consolidated.md
ingestion-README-detailed-exe.md
ingestion-README.md
processing-README.md
```

### 🟡 KEEP FOR REFERENCE - But Not Active

#### 1. **Working But Not Used**
```bash
infra/deploy-vector-index-working.sh  # Last working full deployment attempt
infra/create-chunk-indexer.sh  # Knowledge Store approach (not used)
```

#### 2. **OpenAI Direct Integration**
```python
infra/generate-openai-query-embedding.py  # Uses OpenAI directly, not Azure
```

---

## Step-by-Step Implementation

### Phase 1: Azure Resources Setup

1. **Resource Group**: `rg-rag-confluence`
2. **Storage Account**: `stgragconf`
   - Container: `confluence-data`
   - Folder: `raw/`
3. **Azure AI Search**: `srch-rag-conf`
4. **Azure OpenAI**: `aoai-rag-confluence`
   - Deployment: `text-embedding-ada-002`

### Phase 2: Document-Level Search

```bash
# 1. Create index
bash infra/create-index.sh

# 2. Create skillset
bash infra/create-simple-skillset.sh

# 3. Create data source (if not exists)
az search datasource create \
  --service-name srch-rag-conf \
  --resource-group rg-rag-confluence \
  --name confluence-blob-datasource \
  --type azureblob \
  --credentials "{\"connectionString\":\"$STORAGE_CONNECTION\"}" \
  --container '{"name":"confluence-data","query":"raw/"}'

# 4. Update indexer
bash infra/update-indexer-simple.sh

# 5. Run indexer
bash infra/run-indexer.sh
```

### Phase 3: Chunk-Level Search

```bash
# 1. Create chunk index
bash infra/create-chunk-index.sh

# 2. Install dependencies
pip3 install azure-storage-blob azure-search-documents openai

# 3. Run chunking solution
python3 infra/create-chunking-solution.py
```

---

## Azure Resources

### Resource Details

| Resource | Name | Purpose |
|----------|------|---------|
| Resource Group | `rg-rag-confluence` | Container for all resources |
| Storage Account | `stgragconf` | Blob storage for documents |
| Search Service | `srch-rag-conf` | Azure AI Search service |
| Azure OpenAI | `aoai-rag-confluence` | Embedding generation |
| Cosmos DB | `cosmos-rag-conf` | Graph storage (optional) |
| Function App | `func-rag-conf` | Ingestion functions |

### Indexes

| Index Name | Type | Purpose |
|------------|------|---------|
| `confluence-graph-embeddings` | Document-level | Full document search |
| `confluence-chunks` | Chunk-level | Fragment search for Q&A |

### API Keys and Endpoints

```bash
# Search Service
SEARCH_ENDPOINT="https://srch-rag-conf.search.windows.net"
SEARCH_KEY="qLxEs0dPsL2lmCul6AHaiicNRMRBpvFQWsjvjTqTyHAzSeBx7u8Q"

# Azure OpenAI
AZURE_OPENAI_ENDPOINT="https://aoai-rag-confluence.openai.azure.com/"
AZURE_OPENAI_KEY="2N8xjmhO6M6kE6MO8Opa6KRXMvdyuzvJoJ3kqCJQDdfBaFM1qlz2JQQJ99BGACYeBjFXJ3w3AAABACOGXqVW"

# Storage
STORAGE_CONNECTION="DefaultEndpointsProtocol=https;..."
```

---

## Clean Architecture Summary

### Keep These Files:
```
infra/
├── create-index.sh                    # Document index creation
├── create-chunk-index.sh              # Chunk index creation
├── create-simple-skillset.sh          # Working skillset
├── update-indexer-simple.sh           # Working indexer config
├── run-indexer.sh                     # Indexer execution
├── create-chunking-solution.py        # Chunk processing
├── test-chunk-indexing.py             # Chunk testing
├── datasource.json                    # Data source config
├── skillset.json                      # Skillset config
├── sample_page.json                   # Sample data
└── test-embedding.sh                  # Embedding verification
```

### Delete These Files:
```
infra/
├── deploy-phase1-*.sh                 # All phase 1 attempts
├── deploy-vector-index-*.sh           # All except working.sh
├── deploy-graph-*.sh                  # Graph integration attempts

```

---

## Final Implementation Status

✅ **Working Features:**
- Document-level search with embeddings
- Chunk-level search for Q&A
- Azure OpenAI integration
- Vector search capabilities

❌ **Not Implemented:**
- Graph enrichment from Cosmos DB
- HTML stripping in skillset
- Automatic chunk indexing via Knowledge Store

🔧 **Manual Steps Required:**
- Running Python script for chunk indexing
- No automatic sync between document and chunk indexes