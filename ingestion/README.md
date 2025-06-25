# Confluence Ingestion Pipeline

## Overview

This directory contains the Azure Function implementation for the Confluence data ingestion pipeline. The function runs daily to incrementally fetch pages from Confluence and store them in Azure Blob Storage.

## 📁 Directory Structure

```
ingestion/
├── __init__.py              # Main function implementation
├── function.json            # Function binding configuration
├── host.json               # Function host configuration
├── requirements.txt        # Python dependencies
├── tests/                  # Test suite
│   ├── test_ingestion_unit.py         # Unit tests
│   ├── test_ingestion_integration.py  # Integration tests
│   └── run_tests.sh                   # Test runner
└── README.md              # This file
```

## 🚀 Features

### Incremental Updates
- **Daily Schedule**: Runs every 24 hours at midnight UTC
- **Delta Processing**: Only fetches pages modified in the last day (configurable)
- **Idempotent**: Safe to re-run, overwrites existing files

### Robust Data Handling
- **Pagination**: Handles large Confluence instances with automatic pagination
- **Error Resilience**: Continues processing if individual pages fail
- **Enriched Metadata**: Adds ingestion timestamps and pipeline metadata

### Monitoring & Logging
- **Application Insights**: Comprehensive logging and monitoring
- **Progress Tracking**: Logs progress every 10 pages processed
- **Metadata Storage**: Stores ingestion run metadata for tracking

## 🔧 Configuration

### Environment Variables

The function requires these environment variables (automatically configured by infrastructure):

```bash
# Confluence API
CONFLUENCE_BASE=https://your-org.atlassian.net/wiki/rest/api
CONFLUENCE_TOKEN=your-api-token
CONFLUENCE_EMAIL=your-email@domain.com

# Azure Storage
STORAGE_CONN=DefaultEndpointsProtocol=https;AccountName=...
STORAGE_ACCOUNT=your-storage-account
STORAGE_KEY=your-storage-key

# Cosmos DB
COSMOS_ACCOUNT=your-cosmos-account
COSMOS_KEY=your-cosmos-key
COSMOS_DB=confluence
COSMOS_GRAPH=pages

# Search Service
SEARCH_ENDPOINT=https://your-search.search.windows.net
SEARCH_SERVICE=your-search-service
SEARCH_KEY=your-search-key
SEARCH_INDEX=confluence-idx

# Ingestion Settings
DELTA_DAYS=1                    # Days to look back for changes
CONFLUENCE_SPACE_KEYS=          # Comma-separated space keys (empty = all spaces)
```

### Schedule Configuration

The function schedule is configured in `function.json`:

```json
{
  "schedule": "0 0 0 * * *"  // Daily at midnight UTC
}
```

**Common schedules:**
- `"0 0 0 * * *"` - Daily at midnight
- `"0 0 */6 * * *"` - Every 6 hours
- `"0 0 */1 * * *"` - Every hour

## 📊 Data Flow

```
Confluence API → Function App → Azure Blob Storage → Processing Pipeline
```

### Input: Confluence API
- Fetches pages using Basic Authentication
- Expands: `body.storage,space,ancestors,version,history`
- Filters by modification date for incremental updates

### Processing: Function App
- Enriches page data with metadata
- Adds ingestion timestamps
- Handles pagination and error recovery

### Output: Azure Blob Storage
- **Container**: `raw`
- **Format**: JSON files named `{page_id}.json`
- **Metadata Container**: Ingestion run metadata

### Data Structure

Each page is stored as:

```json
{
  "id": "123456",
  "title": "Page Title",
  "type": "page",
  "status": "current",
  "space": {
    "key": "ENG",
    "name": "Engineering"
  },
  "body": {
    "storage": {
      "value": "<confluence-storage-format>..."
    }
  },
  "ancestors": [...],
  "version": {
    "number": 5,
    "when": "2024-01-15T10:30:00.000Z",
    "by": {...}
  },
  "history": {...},
  "_links": {...},
  "ingestion_timestamp": "2024-01-15T12:00:00.000000",
  "ingestion_metadata": {
    "pipeline_version": "1.0",
    "source": "confluence_api",
    "incremental_update": true
  }
}
```

## 🧪 Testing

### Unit Tests
Test individual functions without external dependencies:

```bash
cd tests
./run_tests.sh unit
```

### Integration Tests
Test against real Azure and Confluence services:

```bash
cd tests
# Set environment variables first
export CONFLUENCE_BASE=...
export CONFLUENCE_TOKEN=...
# ... other variables

./run_tests.sh integration
```

### All Tests
```bash
cd tests
./run_tests.sh all
```

## 🚀 Deployment

### 1. Deploy Infrastructure
From the `infra` directory:

```bash
# Deploy all infrastructure including Function App
./deploy-modular.sh

# Verify Function App is created
./run-tests.sh function-app
```

### 2. Deploy Function Code
From the `infra` directory:

```bash
# Deploy the function code to Azure
./deploy-function-code.sh
```

### 3. Verify Deployment
```bash
# Test the complete pipeline
./run-tests.sh all

# Monitor function execution
az functionapp log tail --name func-rag-conf --resource-group rg-rag-confluence
```

## 📈 Monitoring

### Application Insights
- **Function Execution**: Monitor successful/failed runs
- **Performance**: Track execution time and memory usage
- **Dependencies**: Monitor Confluence API and Storage calls

### Key Metrics
- **Pages Processed**: Total pages ingested per run
- **Execution Time**: Function duration
- **Error Rate**: Failed page processing rate
- **API Response Time**: Confluence API performance

### Logs Location
- **Azure Portal**: Function App → Monitor → Logs
- **Application Insights**: Search for function name
- **CLI**: `az functionapp log tail`

## 🔧 Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **Authentication Failed** | Invalid Confluence credentials | Check `CONFLUENCE_TOKEN` and `CONFLUENCE_EMAIL` |
| **Storage Access Denied** | Invalid storage connection | Verify `STORAGE_CONN` string |
| **Function Timeout** | Large Confluence instance | Increase `functionTimeout` in `host.json` |
| **No Pages Found** | Incorrect space configuration | Check `CONFLUENCE_SPACE_KEYS` |

### Debug Steps

1. **Check Function App Status**
   ```bash
   az functionapp show --name func-rag-conf --resource-group rg-rag-confluence
   ```

2. **View Recent Logs**
   ```bash
   az functionapp log tail --name func-rag-conf --resource-group rg-rag-confluence
   ```

3. **Test Confluence API**
   ```bash
   cd ../infra
   python3 test-confluence-api.py
   ```

4. **Verify Storage Access**
   ```bash
   cd ../infra
   ./run-tests.sh storage
   ```

## 🔄 Maintenance

### Updating the Function
1. Modify code in this directory
2. Run tests: `cd tests && ./run_tests.sh all`
3. Deploy: `cd ../infra && ./deploy-function-code.sh`

### Changing Schedule
1. Update `schedule` in `function.json`
2. Redeploy function code

### Adding New Spaces
1. Update `CONFLUENCE_SPACE_KEYS` environment variable
2. Or leave empty to process all spaces

### Performance Tuning
- **Batch Size**: Modify `limit` parameter (currently 100)
- **Timeout**: Increase `functionTimeout` for large instances
- **Retry Logic**: Configure in `host.json`

## 📚 Next Steps

After successful ingestion:

1. **Processing Pipeline**: Transform raw data into structured format
2. **Embedding Generation**: Create vector embeddings for search
3. **Graph Population**: Build page relationship graph in Cosmos DB
4. **Search Indexing**: Populate Azure AI Search index
5. **Frontend Integration**: Connect to Q&A interface

## 🆘 Support

For issues:
1. Check the troubleshooting section above
2. Review Application Insights logs
3. Run the test suite to isolate problems
4. Verify all environment variables are set correctly 