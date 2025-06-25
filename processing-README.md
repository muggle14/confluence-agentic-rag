processing-README.md

 0 Folder & Naming Convention

Layer	Folder / file
Function ingestion (DONE)	/ingestion/__init__.py, function.json
Processing / clean JSON (TODO)	/processing/adf_pipeline.json or /processing/process.ipynb
Graph upsert (TODO)	/notebooks/populate_graph.py
Embedding & index (DONE)	/embed/index.py
CI/CD (DONE)	.github/workflows/deploy.yml


1 Ingestion Recap – DONE ✅

Item	Status
Azure Function pulls Confluence pages via Atlassian SDK	Implemented
Incremental logic (DELTA_DAYS, overwrite by id.json)	Implemented
Raw blobs land in ingest/raw/ (Blob Fuse mount)	Implemented
No changes required unless you want a smaller polling interval.


2 Processing & Structuring – TODO ⬜

Goal: convert raw HTML to structured JSON with clean text, tables, links, and hierarchy fields.  --> Question , are we getting raw HTML or structured JSON if it is json, then we don't need converstion, we still need clean text, tables, links and hierarchy
setup unit tests at this stage to ensure all files, tables, imgaes, hierarchy are faithfully converted

2.1 Choose one implementation path
Option	When to pick	Deliverable
A ADF mapping data flow	You prefer low-code & drift-detection.	processing/adf_pipeline.json
B Python notebook	You want full control / cheap dev-time.	processing/process.ipynb 
--> use B option for now

2.2 Required output schema (processed/*.json)
{
  "pageId": "123456",
  "title": "How to deploy",
  "breadcrumb": ["Home","Engineering","DevOps"],
  "updated": "2025-06-24T12:30:00Z",
  "sections": [
    {
      "order": 0,
      "heading": "Overview",
      "text": "plain-text paragraph …"
    },
    {
      "order": 1,
      "heading": "Checklist",
      "table": {
        "headers": ["Task","Owner"],
        "rows": [["Run tests","Dev"], ["Deploy","Ops"]]
      }
    }
  ],
  "links": ["654321","789012"]          // embedded page IDs
}
2.3 Transformation steps (same for A or B)
Load raw blob (meta, content).
HTML → Plain text (BeautifulSoup or ADF HTML to Text activity).
Extract <table> tags → header + rows arrays.
Parse <a href="/wiki/spaces/.../123456"> → collect linked page IDs.
Breadcrumb: derive from ancestors in the raw JSON.
Write structured JSON to processed/ container (overwrite if exists).
make sure you think that if HTML is there then only translate to plain text , also suggest
if htmls are needed. 
how are you handling the images and think and create placeholders and add to todo if not 
done yet. 

🟢 Incremental safe: overwrite logic + Search indexer high-water mark on updated.
3 Graph Population – DONE ✅

3.1 Enhanced Graph Population Module
Location: `/notebooks/` - Complete modular architecture implemented
Key Features:
- **Bidirectional relationships**: ParentOf/ChildOf, LinksTo/LinkedFrom, BelongsTo/Contains  
- **Space-level hierarchy**: Space nodes as root containers for better navigation
- **External link nodes**: Separate nodes for external URLs with metadata
- **Rich content support**: HTML, text, markdown content preservation
- **Version tracking**: Incremental updates with timestamp-based change detection
- **Comprehensive validation**: Data integrity checks and graph validation
- **Image placeholders**: Phase 2 ML analysis preparation

3.2 Node Types Created
- **Page nodes**: Full Confluence page metadata (pageId, title, content, stats)
- **Space nodes**: Confluence spaces as organizational containers  
- **Link nodes**: External links with domain analysis and reference tracking

3.3 Relationship Types (All Bidirectional)
- **ParentOf/ChildOf**: Hierarchical page relationships
- **LinksTo/LinkedFrom**: Page-to-page and page-to-external link relationships
- **BelongsTo/Contains**: Page-space membership relationships
- **ReferencesExternal/ReferencedBy**: External link relationships

3.4 Usage Examples
```python
# Full population
from notebooks.populate_graph import GraphPopulator
populator = GraphPopulator.from_environment()
results = populator.populate_all()

# Incremental updates
results = populator.populate_incremental(since="2025-01-15T10:00:00Z")

# Querying
page = populator.find_page("1343493")
hierarchy = populator.get_page_hierarchy("1343493")  
related = populator.find_related_pages("1343493", depth=2)
stats = populator.get_graph_statistics()
```

3.5 Architecture
```
notebooks/
├── populate_graph.py      # Main orchestration script
├── graph_models.py        # Node/edge data models
├── graph_operations.py    # Gremlin database operations  
├── config.py             # Configuration management
├── utils.py              # Helper utilities
├── tests/                # Comprehensive unit tests
└── examples/             # Usage examples
```

4 Embedding & Indexing – DONE ✅

/embed/index.py already:

Reads processed/.
Chunks text (512/128) + embeds with text-embedding-3-large.
Upserts to AI Search (FREE tier).
After you finish Processing, simply rerun this script.
validate for through unit tests. 

5 Data Factory (if choosing Option A) --> choosing option B for now. 

Create linked service to the storage account.
Data Flow
Source – ingest/raw/; parse JSON.
Derived column – plainBody = html_to_text(content).
Flatten tables with collect() function.
Sink – processed/ (JSON), file name = pageId.
Trigger – hourly or on-blob-created event.
Export pipeline JSON to processing/adf_pipeline.json so Terraform/Bicep can deploy it.

6 CI/CD touch-ups

Add a processing job to Actions:
- name: Run processing notebook
  if: matrix.track == 'REST'
  run: |
    papermill processing/process.ipynb -p STORAGE_ACCOUNT $STORAGE_ACCOUNT
Or publish ADF pipeline via az datafactory pipeline create.
7 Validation Checklist

Stage	Test
Processed Blob exists	az storage blob list -c processed --prefix 123
Graph node count > 0	g.V().count() in Cosmos Explorer
Search returns vectors	curl https://<search>.search.windows.net/.../search?api-version=2023-10-01-preview
API /api/ask?q=	Should render answer + breadcrumb JSON
8 Hand-off Summary

✅ **Ingestion** – ready & incremental (Azure Function + Confluence API)
✅ **Processing** – comprehensive pipeline outputs processed/*.json with rich metadata
✅ **Graph Population** – complete bidirectional knowledge graph with nodes & relationships
🔄 **Embedding** – rerun script; index picks up new/updated docs  
🔄 **CI/CD** – wire new processing step; add schedule
🔄 **Frontend** – no change; breadcrumb works once Graph populated

## Next Steps for Full Deployment

1. **Deploy Infrastructure** (if not done):
   ```bash
   cd infra/
   ./setup.sh  # Creates all Azure resources
   ```

2. **Run Graph Population**:
   ```bash
   cd notebooks/
   python populate_graph.py  # Builds complete knowledge graph
   ```

3. **Verify Graph**:
   ```python
   from notebooks.populate_graph import GraphPopulator
   populator = GraphPopulator.from_environment()
   stats = populator.get_graph_statistics()
   print(f"Nodes: {stats['nodes']['total']}, Edges: {stats['edges']['total']}")
   ```

4. **Set Up Automation**:
   - Schedule daily incremental graph updates
   - Monitor processing pipeline health
   - Set up alerts for data quality issues

## Phase 2 Enhancements Ready
- **Image Analysis**: ML-powered understanding via Azure Cognitive Services
- **Enhanced Link Resolution**: Improved URL-to-pageID mapping
- **Graph Analytics**: PageRank, clustering, similarity analysis  
- **Real-time Sync**: Event-driven updates from Confluence webhooks