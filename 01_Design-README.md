# Confluence Q&A System - Design Documentation

## Table of Contents
- [1. Components Overview](#1-components-overview)
- [2. Detailed Pipeline Design](#2-detailed-pipeline-design)
- [3. Hierarchy and Confidence-Based Decisioning Logic](#3-hierarchy-and-confidence-based-decisioning-logic)
- [4. Azure Cloud Architecture Stack](#4-azure-cloud-architecture-stack)
- [5. Flow Diagram](#5-flow-diagram)
- [6. Scalability and Optimization Strategies](#6-scalability-and-optimization-strategies)
- [7. Benefits](#7-benefits)
- [8. Implementation Example](#8-implementation-example)

---

## 1. Components Overview

### A. Data Ingestion and ETL Pipeline
- **Azure Functions**: Scheduled jobs to pull Confluence data via Confluence REST APIs
- **Azure Data Factory**: Manage ETL pipelines for data ingestion, processing, and normalization

### B. Storage Layer
- **Azure Blob Storage**: Store raw and structured page data (JSON format initially)
- **Azure Cosmos DB (Graph API)**: Store hierarchical relationships, nodes, and metadata (headers, links, attributes, table information)

### C. Indexing and Embedding Layer
- **Azure AI Search** (formerly Azure Cognitive Search): Index pages and embeddings
- **Azure OpenAI Service** (Embedding models): Generate vector embeddings from textual content (headers, body, tables)

### D. Retrieval and Generation
**Agentic RAG Layer**:
- **Azure OpenAI** (GPT-4 or GPT-4o): Generate intelligent answers
- Vector retrieval from Azure AI Search to obtain relevant page embeddings

### E. User Interface Layer
**Azure Web App** (Frontend React Application):
- Display QnA results, confidence levels, and page links
- Visualize hierarchical navigation on the right pane

---

## 2. Detailed Pipeline Design

### Step 1: Data Ingestion (Azure Functions + Data Factory)
- Confluence API to periodically extract pages
- Store raw JSON files with metadata into Azure Blob Storage
- Hierarchy (Parent-Child relationships) parsed and stored for graph creation

### Step 2: Data Processing (Azure Data Factory Pipeline)
- Extract textual content, headers, tables, links, and hierarchy from JSON
- Store structured JSON with clean format in Azure Blob Storage

### Step 3: Graph Representation (Cosmos DB Graph API)
Each Confluence page → Graph Node with attributes:
- Page ID
- Page title (header)
- Body content (textual)
- Tables extracted and structured as JSON
- Embedded links (child pages)

**Relationships**:
- `"ParentOf"` and `"ChildOf"` to represent page hierarchy
- `"LinksTo"` to represent embedded links

**Example Graph Schema**:
```
Page(Node)
├── pageID
├── title
├── content
├── tableData
└── confidenceScore (runtime)

Relationships:
├── (Page)-[:ParentOf]->(Page)
└── (Page)-[:LinksTo]->(Page)
```

### Step 4: Indexing and Embeddings (Azure AI Search + Azure OpenAI)
Use Azure OpenAI embedding APIs to generate embeddings for:
- Page titles and headers
- Content body (sections of pages)
- Table data summaries

Embeddings are indexed in Azure AI Search with metadata:
- Page ID, URL, hierarchy depth, header names, and table captions

### Step 5: Retrieval Augmentation and Generation (Agentic RAG)

**Retrieval**:
- User question embedding → Azure AI Search → relevant documents retrieved based on similarity
- Retrieve embedding similarity scores

**Agentic decision-making**:
- Confidence threshold established to determine specificity of answer
- If confidence low, the agent chooses the parent page or provides a hierarchy path instead

**Generation**:
- Azure OpenAI generates human-readable QnA from retrieved context

### Step 6: Frontend Display and Interaction
React-based web application hosted on Azure Web Apps.

**Results displayed with**:
- Answer (confidence indicated)
- Direct links to pages or parent page fallback
- Visual hierarchy tree on the right side pane:
  - Expandable nodes for intuitive navigation

---

## 3. Hierarchy and Confidence-Based Decisioning Logic

When retrieval results return low confidence:

```python
if similarity_score < CONFIDENCE_THRESHOLD:
    # Retrieve Parent Node via Cosmos DB Graph Query
    return parent_page_link and hierarchy
else:
    # Return specific_page_link and answer directly
    return specific_page_link and answer
```

---

## 4. Azure Cloud Architecture Stack

- **Azure Functions**: Serverless extraction jobs
- **Azure Data Factory**: ETL orchestration
- **Azure Blob Storage**: Data lake for raw/processed JSON
- **Azure Cosmos DB Graph API**: Graph representation of content hierarchy
- **Azure AI Search**: Embedding retrieval service
- **Azure OpenAI Service**: Embedding and generative AI model
- **Azure Web Apps**: React frontend hosting

---

## 5. Flow Diagram (High-level)

```
Confluence API → Azure Functions (scheduled ingestion)
    ↓
Azure Blob Storage (raw JSON storage)
    ↓
Azure Data Factory (ETL pipeline)
    ↓
Azure Blob Storage (processed structured JSON)
    ↓
Azure Cosmos DB Graph API (hierarchy, attributes)
    ↓
Azure OpenAI (Embedding generation)
    ↓
Azure AI Search (Embeddings index)
    ↓
Agentic Retrieval & Generation (OpenAI GPT + embeddings)
    ↓
Azure Web Apps (Frontend UI - React)

User Query → Agentic RAG → Confidence Decision → Frontend Display
```

---

## 6. Scalability and Optimization Strategies

- **Batch Processing**: Nightly ingestion to update embeddings
- **Incremental Updates**: Real-time API calls for newly added/updated pages
- **Caching and Edge Serving**: Azure CDN for static content and embedding caching
- **Monitoring and Logging**: Azure Application Insights integrated across pipeline components

---

## 7. Benefits

- **Graph-based Representation**: Effectively captures complex hierarchies
- **Agentic Confidence Decisions**: Graceful fallback to parent pages when uncertain
- **Rich Embeddings**: Ensures nuanced retrieval and accuracy
- **Azure Integration**: Scalable, secure, and seamless cloud-native operations

---

## 8. Implementation Example

Here's a detailed, modular Python script using Azure Cosmos DB Graph API (powered by Gremlin) to create a graph-based representation of hierarchical Confluence pages, their metadata, relationships, and embedded links.

```python
# Required libraries
from gremlin_python.driver import client, serializer
import json

# Azure Cosmos DB Graph Configuration
COSMOS_ENDPOINT = 'wss://<your-cosmosdb-account>.gremlin.cosmos.azure.com:443/'
COSMOS_DB_KEY = '<your-cosmosdb-key>'
DATABASE = '<your-database>'
GRAPH = '<your-graph>'

# Gremlin Client Initialization
gremlin_client = client.Client(
    COSMOS_ENDPOINT, 
    'g', 
    username=f'/dbs/{DATABASE}/colls/{GRAPH}', 
    password=COSMOS_DB_KEY,
    message_serializer=serializer.GraphSONSerializersV2d0()
)

# Example page data structure
confluence_pages = [
    {
        "page_id": "1",
        "title": "Home",
        "content": "Main page content",
        "tables": [{"Table1": [["Row1Col1", "Row1Col2"], ["Row2Col1", "Row2Col2"]]}],
        "links": ["2", "3"],
        "parent_id": None
    },
    {
        "page_id": "2",
        "title": "About",
        "content": "About page content",
        "tables": [],
        "links": ["4"],
        "parent_id": "1"
    },
    # Add more pages similarly
]

# Function to add pages to Cosmos Graph
def add_page_vertex(page):
    query = f"""
    g.V('{page['page_id']}').fold().coalesce(
        unfold(),
        addV('page').property('id', '{page['page_id']}')
                     .property('title', '{page['title']}')
                     .property('content', '{json.dumps(page['content'])}')
                     .property('tables', '{json.dumps(page['tables'])}')
    )
    """
    gremlin_client.submitAsync(query).result()

# Function to add relationships
def add_relationships(page):
    if page['parent_id']:
        parent_query = f"""
        g.V('{page['parent_id']}').as('parent')
         .V('{page['page_id']}').coalesce(
             __.inE('ParentOf').where(outV().as('parent')),
             addE('ParentOf').from('parent')
         )
        """
        gremlin_client.submitAsync(parent_query).result()

    for child_id in page['links']:
        child_query = f"""
        g.V('{page['page_id']}').as('parent')
         .V('{child_id}').coalesce(
             __.inE('ChildOf').where(outV().as('parent')),
             addE('ChildOf').from('parent')
         )
        """
        gremlin_client.submitAsync(child_query).result()

# Main execution to populate graph
for page in confluence_pages:
    add_page_vertex(page)

for page in confluence_pages:
    add_relationships(page)

# Close the client after operations
gremlin_client.close()
```

### Explanation

**Vertex creation** (`add_page_vertex`) defines each Confluence page as a node with properties:
- `page_id`, `title`, `content`, and serialized `tables`

**Relationships** (`add_relationships`) are represented using edges:
- `ParentOf` edges link parent to child pages
- `ChildOf` edges link pages based on embedded links

### Important Notes

- Replace placeholders (`<your-cosmosdb-account>`, `<your-cosmosdb-key>`, etc.) with actual Azure Cosmos DB credentials
- The data (`confluence_pages`) is illustrative; replace it with your ingested page content
- This setup establishes a robust graph-based hierarchy suitable for efficient querying and retrieval within your agentic RAG-based application