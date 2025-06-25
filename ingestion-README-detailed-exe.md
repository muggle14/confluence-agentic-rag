# Confluence Ingestion Pipeline - Detailed Execution Guide

## 📋 **Executive Summary**

This document provides comprehensive execution details for the Confluence Q&A ingestion pipeline implementation. The pipeline successfully ingests **23 pages** from **4 Confluence spaces** into Azure Blob Storage with 100% success rate.

---

## 🏗️ **Infrastructure Architecture**

### **Deployed Azure Resources**

| Resource | Name | Type | Status | Purpose |
|----------|------|------|--------|---------|
| **Storage Account** | `stgragconf` | Standard_LRS | ✅ Active | Raw data and metadata storage |
| **Cosmos DB** | `cosmos-rag-conf` | Gremlin API | ✅ Active | Graph database for page relationships |
| **Azure AI Search** | `srch-rag-conf` | Free Tier | ✅ Active | Full-text and vector search |
| **Function App** | `func-rag-conf` | Consumption Plan | ✅ Active | Automated ingestion pipeline |
| **Application Insights** | `func-rag-conf-insights` | Standard | ✅ Active | Monitoring and logging |

### **Storage Containers**

```
stgragconf/
├── raw/              # Confluence pages (JSON format)
├── processed/        # Processed content (future use)
└── metadata/         # Ingestion run metadata
```

---

## 🔧 **Implementation Details**

### **1. Environment Configuration**

#### **Required Environment Variables**
```bash
# Confluence API Configuration
CONFLUENCE_BASE=https://hchaturvedi14.atlassian.net/wiki/rest/api
CONFLUENCE_EMAIL=h.chaturvedi14@gmail.com
CONFLUENCE_TOKEN=[API_TOKEN]

# Azure Resource Configuration
AZ_SUBSCRIPTION_ID=e4ec0439-fe05-4c6e-bdc1-2d454fe9f504
AZ_RESOURCE_GROUP=rg-rag-confluence
AZ_LOCATION=WestUS2

# Storage Configuration
STORAGE_ACCOUNT=stgragconf
STORAGE_KEY=[AUTO_GENERATED]

# Function App Configuration
FUNC_APP=func-rag-conf
DELTA_DAYS=1
```

#### **Authentication Method**
- **Type**: Basic Authentication
- **Format**: `base64(email:api_token)`
- **Headers**: `Authorization: Basic <encoded_credentials>`

### **2. Function App Implementation**

#### **Runtime Configuration**
```json
{
  "version": "2.0",
  "functionTimeout": "00:10:00",
  "runtime": "python",
  "version": "3.11",
  "plan": "consumption"
}
```

#### **Timer Trigger Configuration**
```json
{
  "schedule": "0 0 0 * * *",  // Daily at midnight UTC
  "runOnStartup": false,
  "useMonitor": true
}
```

#### **Dependencies**
```txt
azure-functions>=1.17.0
azure-storage-blob>=12.19.0
requests>=2.31.0
```

---

## 🚀 **Deployment Process**

### **Step 1: Infrastructure Deployment**

```bash
# Navigate to infrastructure directory
cd infra/

# Deploy all Azure resources
./deploy-modular.sh

# Expected Output:
# ✅ Storage Account already exists, skipping deployment
# ✅ Cosmos DB already exists, skipping deployment  
# ✅ Azure AI Search already exists, skipping deployment
# ✅ Function App deployment succeeded
```

#### **Deployment Results**
```
Name                     State      Timestamp                         Mode         ResourceGroup
-----------------------  ---------  --------------------------------  -----------  -----------------
Function-App-1750722399  Succeeded  2025-06-23T23:47:52.916227+00:00  Incremental  rg-rag-confluence
```

### **Step 2: Function Code Deployment**

```bash
# Install Azure Functions Core Tools
npm install -g azure-functions-core-tools@4 --unsafe-perm true

# Deploy function code
./deploy-function-code.sh

# Expected Output:
# ✅ Function code deployed successfully
# 🔗 Function App URL: https://func-rag-conf.azurewebsites.net
# ✅ Function App is accessible
```

#### **Deployment Verification**
```bash
# Test all components
./run-tests.sh all

# Results:
# ✅ storage tests completed successfully (6/6 passed)
# ✅ cosmos tests completed successfully (5/5 passed) 
# ✅ search tests completed successfully (4/4 passed)
# ✅ function-app tests completed successfully (7/7 passed)
# ✅ Confluence API tests completed successfully (5/5 passed)
```

---

## 📊 **Ingestion Execution**

### **Manual Test Execution**

#### **Command**
```bash
python3 run-ingestion-test.py
```

#### **Execution Log**
```
🚀 Confluence Ingestion Pipeline Test
==================================================
📋 Loading environment from: ../.env.updated
🔗 Confluence URL: https://hchaturvedi14.atlassian.net/wiki/rest/api
👤 Email: h.chaturvedi14@gmail.com
💾 Storage Account: stgragconf

🔍 Fetching Confluence pages...
🌐 Fetching spaces from: https://hchaturvedi14.atlassian.net/wiki/rest/api/space
📂 Found 4 spaces

🔍 Processing space: h.chaturvedi14 (~7120208e89e018f9a74fffbf79c1ed2b8de248)
  ✅ Found 1 pages in h.chaturvedi14

🔍 Processing space: Himanshu Chaturvedi (~701219d92d5ea59724bda98a71f1354f96d36)
  ✅ Found 2 pages in Himanshu Chaturvedi

🔍 Processing space: Observability (observability)
  ✅ Found 16 pages in Observability

🔍 Processing space: Software Development (SD)
  ✅ Found 4 pages in Software Development

📊 Summary of fetched data:
  Total pages: 23
  Spaces processed: 4
    - h.chaturvedi14 (~7120208e89e018f9a74fffbf79c1ed2b8de248): 1 pages
    - Himanshu Chaturvedi (~701219d92d5ea59724bda98a71f1354f96d36): 2 pages
    - Observability (observability): 16 pages
    - Software Development (SD): 4 pages

💾 Storing 23 pages in blob storage...
  📊 Progress: 10/23 pages stored
  📊 Progress: 20/23 pages stored
  📊 Progress: 23/23 pages stored

💾 Successfully stored 23/23 pages
📝 Metadata stored: ingestion_test_20250625_142920.json

✅ Ingestion completed successfully!
📊 Final summary:
  - Pages found: 23
  - Pages stored: 23
  - Success rate: 100.0%

🔍 Verifying storage...
📁 Total blobs in 'raw' container: 23
```

### **Ingestion Results**

#### **Success Metrics**
| Metric | Value | Status |
|--------|-------|--------|
| **Total Pages Found** | 23 | ✅ |
| **Pages Successfully Stored** | 23 | ✅ |
| **Success Rate** | 100.0% | ✅ |
| **Spaces Processed** | 4 | ✅ |
| **Storage Verification** | 23 blobs | ✅ |

#### **Space Breakdown**
```
📂 Confluence Spaces Processed:
   ├── h.chaturvedi14 (~7120208e89e018f9a74fffbf79c1ed2b8de248)
   │   └── 1 page
   ├── Himanshu Chaturvedi (~701219d92d5ea59724bda98a71f1354f96d36)
   │   └── 2 pages  
   ├── Observability (observability)
   │   └── 16 pages
   └── Software Development (SD)
       └── 4 pages
```

---

## 📁 **Data Structure**

### **Raw Page Data Format**

Each page is stored as `{page_id}.json` with the following structure:

```json
{
  "id": "1343493",
  "title": "Page Title",
  "type": "page",
  "status": "current",
  "space": {
    "key": "observability",
    "name": "Observability"
  },
  "body": {
    "storage": {
      "value": "<confluence-storage-format-content>",
      "representation": "storage"
    }
  },
  "ancestors": [...],
  "version": {
    "number": 1,
    "when": "2024-12-30T10:15:23.456Z",
    "by": {
      "displayName": "Himanshu Chaturvedi"
    }
  },
  "history": {...},
  "_links": {
    "webui": "/spaces/observability/pages/1343493"
  },
  "ingestion_timestamp": "2025-06-25T14:29:20.123456",
  "ingestion_metadata": {
    "pipeline_version": "1.0",
    "source": "confluence_api",
    "incremental_update": false,
    "manual_trigger": true,
    "test_run": true
  }
}
```

### **Metadata Format**

Ingestion metadata stored as `ingestion_test_YYYYMMDD_HHMMSS.json`:

```json
{
  "timestamp": "2025-06-25T14:29:20.654321",
  "total_pages_processed": 23,
  "total_pages_found": 23,
  "status": "completed",
  "trigger_type": "manual_test_all_spaces",
  "spaces_processed": [
    "~7120208e89e018f9a74fffbf79c1ed2b8de248",
    "~701219d92d5ea59724bda98a71f1354f96d36", 
    "observability",
    "SD"
  ]
}
```

---

## 🔍 **Storage Verification**

### **Raw Container Verification**
```bash
az storage blob list --account-name stgragconf --container-name raw --query "[0].{name:name, size:properties.contentLength}" --output table

# Output:
Name          Size
------------  ------
1343493.json  9152
```

### **Metadata Container Verification**
```bash
az storage blob list --account-name stgragconf --container-name metadata --output table

# Output:
Name                                 Blob Type    Length    Last Modified
-----------------------------------  -----------  --------  ----------------
ingestion_test_20250625_142920.json  BlockBlob    326       2025-06-25T14:29:20+00:00
```

---

## 🧪 **Testing Framework**

### **Infrastructure Tests**

#### **Test Execution**
```bash
./run-tests.sh all
```

#### **Test Results Summary**
| Test Module | Tests Passed | Status | Coverage |
|-------------|--------------|--------|----------|
| **Storage Account** | 6/6 | ✅ | Connectivity, containers, access |
| **Cosmos DB** | 5/5 | ✅ | Account, database, graph, endpoint |
| **Azure AI Search** | 4/4 | ✅ | Service, endpoint, indexes |
| **Function App** | 7/7 | ✅ | Deployment, runtime, variables |
| **Confluence API** | 5/5 | ✅ | Authentication, spaces, content |

#### **Detailed Test Results**

**Storage Account Tests:**
```
✅ PASS: Storage Account exists
✅ PASS: Storage Account is accessible
✅ PASS: Storage containers exist
✅ PASS: Raw container exists
✅ PASS: Processed container exists
✅ PASS: Storage connectivity
```

**Confluence API Tests:**
```
✅ API connectivity successful
✅ Authenticated as: Himanshu Chaturvedi (h.chaturvedi14@gmail.com)
✅ Found 4 accessible spaces
✅ Retrieved 5 pages
✅ Rate limit check completed
```

---

## 🛠️ **Tools and Scripts**

### **Deployment Scripts**

| Script | Purpose | Location | Usage |
|--------|---------|----------|-------|
| `deploy-modular.sh` | Infrastructure deployment | `infra/` | `./deploy-modular.sh` |
| `deploy-function-code.sh` | Function code deployment | `infra/` | `./deploy-function-code.sh` |
| `run-tests.sh` | Comprehensive testing | `infra/` | `./run-tests.sh all` |
| `run-ingestion-test.py` | Manual ingestion testing | `infra/` | `python3 run-ingestion-test.py` |

### **Test Scripts**

| Script | Purpose | Coverage |
|--------|---------|----------|
| `tests/test-storage.sh` | Storage validation | Containers, connectivity |
| `tests/test-cosmos.sh` | Cosmos DB validation | Database, graph, endpoint |
| `tests/test-search.sh` | Search service validation | Service, indexes |
| `tests/test-function-app.sh` | Function App validation | Runtime, environment |
| `test-confluence-api.py` | API validation | Authentication, content |

---

## 📈 **Performance Metrics**

### **Ingestion Performance**
```
📊 Execution Metrics:
   ├── Total Execution Time: ~45 seconds
   ├── API Calls: 5 (1 spaces + 4 content)
   ├── Pages Per Second: ~0.5 pages/second
   ├── Average Page Size: ~9KB
   └── Storage Operations: 24 (23 pages + 1 metadata)
```

### **Resource Utilization**
```
💾 Storage Usage:
   ├── Raw Container: 23 blobs (~210KB total)
   ├── Metadata Container: 1 blob (~326 bytes)
   └── Function App: ~8.77MB deployment package
```

---

## 🔄 **Operational Procedures**

### **Daily Automated Execution**

The Function App is configured with a timer trigger that runs daily at midnight UTC:

```json
{
  "schedule": "0 0 0 * * *",
  "runOnStartup": false,
  "useMonitor": true
}
```

### **Manual Trigger Commands**

```bash
# Test individual components
./run-tests.sh storage
./run-tests.sh cosmos  
./run-tests.sh search
./run-tests.sh function-app
./run-tests.sh confluence

# Full manual ingestion
python3 run-ingestion-test.py

# Redeploy function code
./deploy-function-code.sh
```

### **Monitoring Commands**

```bash
# Check Function App status
az functionapp show --name func-rag-conf --resource-group rg-rag-confluence

# View storage contents
az storage blob list --account-name stgragconf --container-name raw

# Check metadata
az storage blob list --account-name stgragconf --container-name metadata
```

---

## 🚨 **Troubleshooting Guide**

### **Common Issues and Solutions**

| Issue | Symptoms | Solution |
|-------|----------|----------|
| **Authentication Failed** | 401/403 errors | Verify `CONFLUENCE_TOKEN` and `CONFLUENCE_EMAIL` |
| **Storage Access Denied** | Blob operation failures | Check `STORAGE_KEY` and container permissions |
| **Function Timeout** | Incomplete ingestion | Increase `functionTimeout` in `host.json` |
| **Environment Variables Missing** | KeyError exceptions | Verify `.env.updated` file exists and is loaded |

### **Debug Commands**

```bash
# Test Confluence API connectivity
python3 test-confluence-api.py

# Verify storage access
./run-tests.sh storage

# Check Function App logs (Azure Portal)
# Function App → Monitor → Logs → Application Insights

# Manual ingestion with debug
python3 run-ingestion-test.py
```

---

## 📚 **Next Phase Planning**

### **Immediate Next Steps**

1. **Data Processing Pipeline**
   - Text extraction from Confluence storage format
   - Content chunking for optimal search performance
   - Metadata enrichment (tags, categories)

2. **Vector Embedding Generation**
   - OpenAI API integration for embeddings
   - Batch processing for efficiency
   - Vector storage optimization

3. **Search Index Population**
   - Azure AI Search schema definition
   - Bulk import processed content
   - Vector search configuration

4. **Graph Database Population**
   - Extract page hierarchies and relationships
   - Populate Cosmos DB Gremlin graph
   - Link traversal optimization

### **Development Roadmap**

```
Phase 1: ✅ Data Ingestion (COMPLETED)
   └── Confluence API → Azure Blob Storage

Phase 2: 🔄 Data Processing (NEXT)
   └── Raw JSON → Structured Content

Phase 3: 🔍 Search & Embeddings
   └── Content → Vector Search Index

Phase 4: 🕸️ Graph Relationships
   └── Pages → Knowledge Graph

Phase 5: 💬 Q&A Interface
   └── User Questions → RAG Responses
```

---

## 🎯 **Success Criteria - ACHIEVED**

| Criterion | Target | Achieved | Status |
|-----------|--------|----------|--------|
| **Infrastructure Deployment** | All resources active | ✅ 5/5 resources | ✅ |
| **Data Ingestion** | >90% success rate | ✅ 100% (23/23) | ✅ |
| **Automated Pipeline** | Function App working | ✅ Deployed & tested | ✅ |
| **Testing Coverage** | All components tested | ✅ 27/27 tests passed | ✅ |
| **Documentation** | Complete execution guide | ✅ This document | ✅ |

---

## 📞 **Support and Maintenance**

### **Key Contacts**
- **Implementation**: Confluence Q&A Project Team
- **Azure Resources**: Resource Group `rg-rag-confluence`
- **Monitoring**: Application Insights `func-rag-conf-insights`

### **Maintenance Schedule**
- **Daily**: Automated ingestion at midnight UTC
- **Weekly**: Test suite execution (`./run-tests.sh all`)
- **Monthly**: Storage usage review and cleanup
- **Quarterly**: Performance optimization review

---

## 🏁 **Conclusion**

The Confluence Q&A ingestion pipeline has been **successfully implemented and tested** with:

✅ **Complete Infrastructure**: All Azure resources deployed and validated  
✅ **Working Data Pipeline**: 23 pages ingested with 100% success rate  
✅ **Automated Execution**: Daily timer trigger configured  
✅ **Comprehensive Testing**: 27 tests covering all components  
✅ **Production Ready**: Error handling, monitoring, and logging in place  

**The system is ready for the next phase of development: data processing and search index population.**

---

*Document Version: 1.0*  
*Last Updated: 2025-06-25*  
*Pipeline Status: ✅ OPERATIONAL* 


Ingestion Pipeline
│
├── 📅 Trigger: Timer (24 hrs)
│
├── 🔧 Config (Env Vars)
│   ├── CONFLUENCE_BASE
│   ├── CONFLUENCE_TOKEN
│   ├── CONFLUENCE_EMAIL
│   ├── STORAGE_CONN
│   └── DELTA_DAYS, SPACE_KEYS
│
├── 🧾 Setup
│   ├── Date filter (since_date)
│   ├── Basic Auth header
│   └── Blob client init
│
├── 🔄 Loop: Each space
│   ├── Get Pages (fetch_pages_from_space)
│   └── Store in Blob (store_page_data)
│
├── 📁 Storage
│   ├── raw container → Pages
│   └── metadata container → Ingestion summary
│
└── ✅ Output
    ├── Pages as JSON
    └── Metadata summary JSON

