# Azure CLI Search Commands Fix

## Problem
The original `deploy-phase1-enhanced.sh` script was failing with the error:
```
No module named 'msrestazure'
```

This occurs when Azure CLI's search module has dependency issues or is not properly installed.

## Solution
Created `deploy-phase1-fixed.sh` which replaces all Azure CLI search commands with REST API calls using curl.

### Changes Made

1. **Replaced Azure CLI commands with REST API calls:**
   - `az search datasource create` → `curl -X PUT` to datasources endpoint
   - `az search skillset create` → `curl -X PUT` to skillsets endpoint
   - `az search index create` → `curl -X PUT` to indexes endpoint
   - `az search indexer create` → `curl -X PUT` to indexers endpoint
   - `az search indexer run` → `curl -X POST` to indexer run endpoint
   - `az search indexer status` → `curl -X GET` to indexer status endpoint

2. **Added proper authentication:**
   - Retrieves Search Service admin key using Azure CLI
   - Uses the key in REST API headers

3. **Maintained all functionality:**
   - All original features preserved
   - Same JSON configurations
   - Same monitoring capabilities

## Usage

1. **Check dependencies first:**
   ```bash
   ./check-dependencies.sh
   ```

2. **Set required environment variables:**
   ```bash
   export AOAI_ENDPOINT="https://your-aoai.openai.azure.com/"
   export AOAI_KEY="your-api-key"
   ```

3. **Run the fixed deployment script:**
   ```bash
   ./deploy-phase1-fixed.sh
   ```

## Benefits of REST API Approach

1. **No Python dependencies** - Uses only curl and standard shell tools
2. **More reliable** - Direct API calls without CLI abstraction layer
3. **Better error visibility** - Can see exact API responses
4. **Portable** - Works on any system with curl installed

## Testing

After deployment, you can test the search service with:

```bash
# Get search key
SEARCH_KEY=$(az search admin-key show --service-name srch-rag-conf --resource-group rg-rag-confluence --query primaryKey -o tsv)

# Search documents
curl -X POST "https://srch-rag-conf.search.windows.net/indexes/confluence-graph-embeddings/docs/search?api-version=2023-11-01" \
  -H "api-key: $SEARCH_KEY" \
  -H "Content-Type: application/json" \
  -d '{"search": "*", "top": 5}' | jq
```

## Troubleshooting

If you still want to fix the Azure CLI installation:

```bash
# Reinstall Azure CLI search extension
az extension remove --name search-index-management
az extension add --name search-index-management

# Or update all extensions
az extension update --all
```

However, the REST API approach is more reliable and doesn't depend on Python package management.