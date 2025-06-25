# Confluence Data Ingestion Pipeline

## Overview

This document outlines the data ingestion pipeline for extracting Confluence pages and processing them for the Q&A system. The pipeline uses Azure Functions with the Atlassian SDK for reliable, incremental data extraction.

## Architecture

```
Confluence API → Azure Function → Azure Blob Storage → Processing Pipeline
```

## 1. Data Ingestion Strategy

### Why Atlassian SDK?

The Atlassian SDK provides several advantages over direct REST API calls:

- **Automatic Pagination**: Handles `limit` and `cursorId` parameters automatically
- **Built-in Retry Logic**: Exponential back-off on 429 rate limit responses
- **Convenience Methods**: Simplified API calls with `get_page`, `get_space`, `get_content_with_expansion`
- **Error Handling**: Robust error handling for network and API issues

### Incremental Updates

The pipeline supports incremental updates by:
- Tracking page modification dates
- Using `DELTA_DAYS` to fetch only recently modified content
- Overwriting existing files for idempotent operations

## 2. Environment Configuration

Add these variables to your `.env` file:

```bash
# Confluence API Configuration
CONFLUENCE_EMAIL=your-email@domain.com
CONFLUENCE_TOKEN=your-api-token
CONFLUENCE_BASE=https://your-org.atlassian.net/wiki/rest/api
CONFLUENCE_SPACE_KEYS=ENG,OPS    # optional: comma-separated list, blank = ALL spaces

# Ingestion Settings
DELTA_DAYS=1                     # pull pages edited in last N days
BLOB_MOUNT_PATH=/mnt/blob        # mount point for Azure Blob Fuse

# Azure Storage
STORAGE_ACCOUNT=your-storage-account
STORAGE_KEY=your-storage-key
```

## 3. Azure Function Implementation

### 3.1 Main Function Code (`ingestion/__init__.py`)

```python
import os, json, logging, datetime as dt
from atlassian import Confluence
from pathlib import Path

# Environment variables
EMAIL = os.environ['CONFLUENCE_EMAIL']
TOKEN = os.environ['CONFLUENCE_TOKEN']
BASE_URL = os.environ['CONFLUENCE_BASE'].replace('/rest/api','')
SPACE_KEYS = [s.strip() for s in os.getenv('CONFLUENCE_SPACE_KEYS','').split(',') if s]
DELTA = int(os.getenv('DELTA_DAYS', '1'))
SINCE = (dt.datetime.utcnow() - dt.timedelta(days=DELTA)).isoformat()+"Z"

# Atlassian SDK connection
conf = Confluence(url=BASE_URL, username=EMAIL, password=TOKEN, cloud=True)

# Blob storage path
RAW_PATH = Path(os.getenv('BLOB_MOUNT_PATH', '/mnt/blob')) / 'raw'
RAW_PATH.mkdir(parents=True, exist_ok=True)

def main(mytimer):
    """Timer trigger entrypoint"""
    spaces = SPACE_KEYS or [s['key'] for s in conf.get_all_spaces(limit=500)['results']]
    logging.info(f"Ingesting spaces: {spaces}")
    
    for space in spaces:
        fetch_pages(space)

def fetch_pages(space_key: str):
    """Fetch all pages from a space with pagination"""
    start = 0
    while True:
        page_batch = conf.get_all_pages_from_space(
            space_key=space_key,
            start=start,
            limit=100,
            status='current',
            expand="version,body.storage,ancestors,space",
            start_date=SINCE
        )
        if not page_batch:
            break
        
        for page in page_batch:
            persist(page)
        
        start += 100

def persist(page_json):
    """Store page data as JSON with metadata"""
    meta = {
        'id': page_json['id'],
        'title': page_json['title'],
        'space': page_json['space']['key'],
        'version': page_json['version']['number'],
        'updated': page_json['version']['when'],
        'url': f"{BASE_URL}/wiki{page_json['_links']['webui']}"
    }
    
    record = {
        'meta': meta,
        'content': page_json['body']['storage']['value']
    }
    
    out_file = RAW_PATH / f"{page_json['id']}.json"
    with out_file.open('w') as fp:
        json.dump(record, fp)
```

### 3.2 Function Configuration (`function.json`)

```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "name": "mytimer",
      "type": "timerTrigger",
      "direction": "in",
      "schedule": "0 0 */1 * * *"
    }
  ]
}
```

**Schedule Options:**
- `"0 0 */1 * * *"` - Every hour
- `"0 0 */6 * * *"` - Every 6 hours
- `"0 0 0 * * *"` - Daily at midnight

## 4. Azure Blob Storage Integration

### 4.1 Container Setup

Create the required storage container:

```bash
# Create ingest container
az storage container create \
    --name ingest \
    --account-name $STORAGE_ACCOUNT \
    --account-key $STORAGE_KEY
```

### 4.2 SAS Token Generation

Generate a Shared Access Signature for secure access:

```bash
# Generate SAS token with write and list permissions
az storage container generate-sas \
    --account-name $STORAGE_ACCOUNT \
    --name ingest \
    --permissions wl \
    --expiry $(date -u -d "+1 year" '+%Y-%m-%dT%H:%MZ')
```

### 4.3 Function App Configuration

Configure the Function App with storage settings:

```bash
# Set application settings
az functionapp config appsettings set \
    -g $AZ_RESOURCE_GROUP \
    -n $FUNC_APP \
    --settings \
    AZURE_BLOB_SAS="<your-sas-token>" \
    AZURE_BLOB_URI="https://${STORAGE_ACCOUNT}.blob.core.windows.net/ingest"
```

## 5. Blob Fuse Mounting (Optional)

For high-performance scenarios, mount Azure Blob Storage as a file system:

### 5.1 Custom Startup Script

Create `function_app_extensions/startup.sh`:

```bash
#!/bin/bash
mkdir -p /mnt/blob && \
blobfuse2 mount /mnt/blob \
    --config-file=/etc/blobfuse2.cfg \
    --container-name=ingest &
exec /azure-functions-host/Microsoft.Azure.WebJobs.Script.WebHost
```

### 5.2 Blob Fuse Configuration

Create `/etc/blobfuse2.cfg`:

```ini
[blobfuse2]
type = block
account-name = your-storage-account
container-name = ingest
sas-token = your-sas-token
```

**Note**: Blob Fuse requires a Premium Function App plan. For cost savings on Consumption plans, use the Python `BlobClient` instead.

## 6. Data Structure

### 6.1 Raw Data Format

Each page is stored as a JSON file with the following structure:

```json
{
  "meta": {
    "id": "123456",
    "title": "Page Title",
    "space": "ENG",
    "version": 5,
    "updated": "2024-01-15T10:30:00.000Z",
    "url": "https://your-org.atlassian.net/wiki/spaces/ENG/pages/123456"
  },
  "content": "<ac:structured-document>...</ac:structured-document>"
}
```

### 6.2 File Naming Convention

- **Raw files**: `{page_id}.json`
- **Storage path**: `/raw/{page_id}.json`
- **Idempotent**: Same filename overwrites previous version

## 7. Processing Pipeline

### 7.1 Content Extraction

The processing pipeline extracts:

- **Text Content**: Clean text from Confluence storage format
- **Metadata**: Page hierarchy, links, and relationships
- **Structure**: Headers, tables, and embedded content
- **Relationships**: Parent-child page relationships for graph creation

### 7.2 Structured Output

Processed data is stored in structured JSON format:

```json
{
  "page_id": "123456",
  "title": "Page Title",
  "space": "ENG",
  "content": {
    "text": "Clean text content...",
    "headers": ["Header 1", "Header 2"],
    "tables": [...],
    "links": [...]
  },
  "hierarchy": {
    "parent_id": "123455",
    "children": ["123457", "123458"]
  },
  "embeddings": [...],
  "last_updated": "2024-01-15T10:30:00.000Z"
}
```

## 8. Deployment

### 8.1 CI/CD Pipeline

Add to `.github/workflows/deploy.yml`:

```yaml
jobs:
  deploy:
    strategy:
      matrix:
        track: [REST, GDC]
    steps:
      - name: Publish Functions
        if: matrix.track == 'REST'
        run: func azure functionapp publish $FUNC_APP --python
```

### 8.2 Environment-Specific Deployment

Control deployment with repository secrets:

- Set `TRACK=REST` for REST API-based ingestion
- Set `TRACK=GDC` for Graph Data Connect ingestion

## 9. Monitoring and Troubleshooting

### 9.1 Function Logs

Monitor function execution:

```bash
# Stream function logs
az functionapp log tail --name $FUNC_APP --resource-group $AZ_RESOURCE_GROUP
```

### 9.2 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **429 Rate Limits** | Too many API calls | SDK handles automatically with backoff |
| **Authentication Errors** | Invalid token/email | Verify credentials in app settings |
| **Storage Errors** | Invalid SAS/permissions | Regenerate SAS token with correct permissions |
| **Missing Pages** | Incorrect space keys | Check space configuration and permissions |

### 9.3 Performance Optimization

- **Batch Size**: Adjust `limit` parameter (50-100 pages per batch)
- **Delta Updates**: Use `DELTA_DAYS` for incremental updates
- **Parallel Processing**: Process multiple spaces concurrently
- **Caching**: Cache space metadata to reduce API calls

## 10. Cost Optimization

### 10.1 Function App Tiers

| Tier | Cost | Use Case |
|------|------|----------|
| **Consumption** | Pay-per-execution | Low-frequency ingestion |
| **Premium P0v3** | ~$50/month | High-frequency, blob fuse support |
| **App Service** | ~$15/month | Predictable workloads |

### 10.2 Storage Costs

- **Standard LRS**: ~$0.02/GB/month
- **Hot tier**: For frequently accessed data
- **Cool tier**: For archival data (>30 days old)

### 10.3 API Rate Limits

- **Confluence Cloud**: 10 requests/second per app
- **Best Practice**: Use SDK's built-in rate limiting
- **Cost Impact**: Minimal for typical usage patterns 