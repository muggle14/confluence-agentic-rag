# Graph Population Module

This module handles the population and management of the Confluence knowledge graph using Azure Cosmos DB with Gremlin API.

## Overview

The graph population module converts processed Confluence content into a rich knowledge graph with:
- **Page nodes** with comprehensive metadata
- **Space nodes** for organizational hierarchy  
- **Link nodes** for external references
- **Bidirectional relationships** (ParentOf/ChildOf, LinksTo/LinkedFrom)
- **Space membership** (BelongsTo/Contains)
- **Version tracking** and incremental updates

## Architecture

```
notebooks/
├── __init__.py                 # Package initialization
├── README.md                   # This documentation
├── populate_graph.py           # Main graph population script
├── graph_models.py             # Node and edge type definitions
├── graph_operations.py         # Core Gremlin operations
├── config.py                   # Configuration management
├── utils.py                    # Utility functions
├── tests/                      # Unit tests
│   ├── __init__.py
│   ├── test_graph_models.py
│   ├── test_graph_operations.py
│   ├── test_populate_graph.py
│   └── run_tests.sh
└── examples/                   # Usage examples
    ├── quick_start.py
    ├── incremental_update.py
    └── graph_queries.py
```

## Key Features

### 1. Node Types

- **Page Nodes**: Confluence pages with full metadata
- **Space Nodes**: Confluence spaces as organizational containers
- **Link Nodes**: External links as separate entities

### 2. Relationship Types

- **ParentOf/ChildOf**: Bidirectional page hierarchy
- **LinksTo/LinkedFrom**: Bidirectional link relationships  
- **BelongsTo/Contains**: Page-space membership
- **ReferencesExternal/ReferencedBy**: External link relationships

### 3. Content Support

- **Multi-format content**: HTML, text, and markdown
- **Rich metadata**: Creation/update timestamps, versions, stats
- **Image placeholders**: Prepared for Phase 2 ML analysis
- **Table structures**: Preserved for semantic search

### 4. Incremental Updates

- **Version tracking**: Only update changed pages
- **Relationship reconciliation**: Handle link additions/removals
- **Space management**: Track space changes and moves

## Quick Start

```python
from notebooks.populate_graph import GraphPopulator
from notebooks.config import GraphConfig

# Initialize with Azure Cosmos DB connection
config = GraphConfig.from_environment()
populator = GraphPopulator(config)

# Populate all processed pages
results = populator.populate_all()
print(f"Processed {results['pages_updated']} pages")

# Incremental update (only changed pages)
results = populator.populate_incremental()
print(f"Updated {results['pages_changed']} changed pages")
```

## Configuration

Set these environment variables or use `.env` file:

```bash
# Azure Cosmos DB (Gremlin API)
COSMOS_ENDPOINT=https://your-cosmos.gremlin.cosmos.azure.com:443/
COSMOS_KEY=your-cosmos-key
COSMOS_DATABASE=confluence-graph
COSMOS_CONTAINER=knowledge-graph

# Azure Storage (for processed content)
STORAGE_ACCOUNT=your-storage-account
STORAGE_KEY=your-storage-key
STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

# Processing options
GRAPH_BATCH_SIZE=50
GRAPH_ENABLE_RICH_CONTENT=true
GRAPH_TRACK_VERSIONS=true
```

## Usage Examples

### Basic Population
```python
# Process all pages from storage
populator = GraphPopulator.from_environment()
results = populator.populate_all()
```

### Incremental Updates
```python
# Only update changed pages (based on timestamps)
results = populator.populate_incremental(
    since="2025-01-15T10:00:00Z"
)
```

### Query Examples
```python
# Find page by ID
page = populator.find_page("1343493")

# Get page hierarchy
hierarchy = populator.get_page_hierarchy("1343493")

# Find related pages
related = populator.find_related_pages("1343493", depth=2)

# Space overview
space_stats = populator.get_space_statistics("observability")
```

## Testing

Run comprehensive tests:
```bash
cd notebooks/tests
./run_tests.sh
```

Individual test suites:
```bash
python -m pytest test_graph_models.py -v
python -m pytest test_graph_operations.py -v  
python -m pytest test_populate_graph.py -v
```

## Monitoring & Validation

The module includes built-in validation:
- Node count tracking
- Relationship integrity checks  
- Orphaned node detection
- Performance metrics

View graph statistics:
```python
stats = populator.get_graph_statistics()
print(f"Total pages: {stats['page_count']}")
print(f"Total relationships: {stats['edge_count']}")
```

## Phase 2 Roadmap

- **Image Analysis**: ML-powered image understanding
- **Enhanced Link Resolution**: Improved URL to page ID mapping
- **Graph Analytics**: PageRank, clustering, similarity
- **Real-time Sync**: Event-driven updates from Confluence
- **Graph Visualization**: Interactive web interface

## Troubleshooting

Common issues and solutions:

1. **Connection Errors**: Check Cosmos DB endpoint and key
2. **Timeout Issues**: Reduce batch size or enable retry logic
3. **Missing Pages**: Verify storage container and processed files
4. **Relationship Errors**: Check page ID consistency and hierarchy

## Contributing

1. Follow the existing code structure
2. Add unit tests for new features
3. Update documentation
4. Test with sample data before production 