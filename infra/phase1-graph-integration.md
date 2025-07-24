# Phase 1: Graph Integration with Azure AI Search

This document clarifies how Cosmos DB graph features remain central to the Phase 1 implementation while leveraging Azure AI Search native capabilities.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Confluence    │────▶│    Ingestion     │────▶│   Blob Storage  │
│     Pages       │     │    Function      │     │      (raw)      │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                        ┌─────────────────────────────────▼─-────-──┐
                        │        Azure AI Search Indexer    |       │
                        │  1. Text Split Skill (chunking)   |       │
                        │  2. Graph Enrichment Skill        |       │
                        │  3. Azure OpenAI Embedding Skill  |       │
                        └───────────────┬───────────────────┘       │
                                       │                            │
                        ┌──────────────▼────────┐     ┌─────────────▼─────┐
                        │   Search Index with   │     │    Cosmos DB      │
                        │  - Vector fields      │     │   Graph Store     │
                        │  - Graph metadata     │◀────│  - Vertices       │
                        │  - Scoring profiles   │     │  - Edges          │
                        └───────────────────────┘     │  - Hierarchies    │
                                                      └───────────────────┘
```

## Key Point: Graph Enrichment Remains Essential

### The Graph Enrichment Skill Configuration

```json
{
  "name": "confluence-graph-skillset",
  "skills": [
    {
      "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
      "name": "SplitSkill",
      "context": "/document",
      "textSplitMode": "pages",
      "maximumPageLength": 512,
      "pageOverlapLength": 128,
      "outputs": [{
        "name": "textItems",
        "targetName": "pages"
      }]
    },
    {
      "@odata.type": "#Microsoft.Skills.Custom.WebApiSkill",
      "name": "GraphEnrichment",
      "description": "Enrich with Cosmos DB graph data",
      "uri": "https://func-rag-conf.azurewebsites.net/api/graph_enrichment_skill",
      "httpMethod": "POST",
      "timeout": "PT90S",
      "batchSize": 10,
      "httpHeaders": {
        "x-functions-key": "YOUR-FUNCTION-KEY"
      },
      "context": "/document",
      "inputs": [
        {
          "name": "page_id",
          "source": "/document/id"
        },
        {
          "name": "title", 
          "source": "/document/title"
        },
        {
          "name": "space_key",
          "source": "/document/space_key"
        }
      ],
      "outputs": [
        {
          "name": "hierarchy_depth",
          "targetName": "hierarchy_depth"
        },
        {
          "name": "hierarchy_path",
          "targetName": "hierarchy_path"
        },
        {
          "name": "parent_page_id",
          "targetName": "parent_page_id"
        },
        {
          "name": "parent_page_title",
          "targetName": "parent_page_title"
        },
        {
          "name": "has_children",
          "targetName": "has_children"
        },
        {
          "name": "child_count",
          "targetName": "child_count"
        },
        {
          "name": "sibling_count",
          "targetName": "sibling_count"
        },
        {
          "name": "related_page_count",
          "targetName": "related_page_count"
        },
        {
          "name": "graph_centrality_score",
          "targetName": "graph_centrality_score"
        },
        {
          "name": "graph_metadata",
          "targetName": "graph_metadata"
        }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
      "name": "AzureOpenAIEmbedding",
      "context": "/document/pages/*",
      "resourceUri": "https://YOUR-AOAI.openai.azure.com",
      "apiKey": "YOUR-AZURE-OPENAI-KEY",
      "deploymentId": "text-embedding-ada-002",
      "inputs": [{
        "name": "text",
        "source": "/document/pages/*"
      }],
      "outputs": [{
        "name": "embedding",
        "targetName": "contentVector"
      }]
    }
  ]
}
```

## Graph-Aware Index Fields

The search index includes all graph-derived fields:

```json
{
  "name": "confluence-graph-index",
  "fields": [
    // Standard fields
    {
      "name": "id",
      "type": "Edm.String",
      "key": true
    },
    {
      "name": "content",
      "type": "Edm.String",
      "searchable": true
    },
    {
      "name": "contentVector",
      "type": "Collection(Edm.Single)",
      "dimensions": 1536,
      "vectorSearchProfile": "vector-profile"
    },
    
    // Graph-derived fields from Cosmos DB
    {
      "name": "hierarchy_depth",
      "type": "Edm.Int32",
      "filterable": true,
      "sortable": true,
      "facetable": true
    },
    {
      "name": "hierarchy_path",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true
    },
    {
      "name": "parent_page_id",
      "type": "Edm.String",
      "filterable": true
    },
    {
      "name": "parent_page_title",
      "type": "Edm.String",
      "searchable": true
    },
    {
      "name": "has_children",
      "type": "Edm.Boolean",
      "filterable": true
    },
    {
      "name": "child_count",
      "type": "Edm.Int32",
      "filterable": true,
      "sortable": true
    },
    {
      "name": "sibling_count",
      "type": "Edm.Int32",
      "filterable": true
    },
    {
      "name": "related_page_count",
      "type": "Edm.Int32",
      "filterable": true,
      "sortable": true
    },
    {
      "name": "graph_centrality_score",
      "type": "Edm.Double",
      "filterable": true,
      "sortable": true
    },
    {
      "name": "graph_metadata",
      "type": "Edm.String",
      "retrievable": true
    }
  ]
}
```

## Enhanced Scoring with Graph Data

### Scoring Profile Configuration
```json
{
  "scoringProfiles": [{
    "name": "confluence-graph-boost",
    "text": {
      "weights": {
        "title": 3.0,
        "parent_page_title": 2.0,
        "hierarchy_path": 1.5,
        "content": 1.0
      }
    },
    "functions": [
      {
        "fieldName": "graph_centrality_score",
        "type": "magnitude",
        "boost": 5.0,
        "interpolation": "quadratic",
        "magnitude": {
          "boostingRangeStart": 0.3,
          "boostingRangeEnd": 1.0,
          "constantBoostBeyondRange": true
        }
      },
      {
        "fieldName": "hierarchy_depth",
        "type": "magnitude", 
        "boost": 2.0,
        "interpolation": "logarithmic",
        "magnitude": {
          "boostingRangeStart": 5,
          "boostingRangeEnd": 1,
          "constantBoostBeyondRange": false
        }
      },
      {
        "fieldName": "child_count",
        "type": "magnitude",
        "boost": 1.5,
        "interpolation": "linear",
        "magnitude": {
          "boostingRangeStart": 0,
          "boostingRangeEnd": 10
        }
      },
      {
        "fieldName": "related_page_count",
        "type": "magnitude",
        "boost": 1.2,
        "interpolation": "linear",
        "magnitude": {
          "boostingRangeStart": 0,
          "boostingRangeEnd": 20
        }
      }
    ],
    "functionAggregation": "sum"
  }]
}
```

## Query Examples Using Graph Features

### 1. Find Top-Level Overview Pages
```python
# Search for overview content, boosted by shallow hierarchy
results = search_client.search(
    search_text="getting started guide",
    filter="hierarchy_depth lt 3 and has_children eq true",
    scoring_profile="confluence-graph-boost",
    select=["title", "hierarchy_path", "graph_centrality_score", "child_count"]
)
```

### 2. Find Detailed Implementation Pages
```python
# Search for detailed content, filtered by depth
results = search_client.search(
    search_text="implementation details",
    filter="hierarchy_depth gt 3",
    order_by=["graph_centrality_score desc"],
    select=["title", "parent_page_title", "hierarchy_path"]
)
```

### 3. Find Hub Pages (High Centrality)
```python
# Find important hub pages
results = search_client.search(
    search_text="*",
    filter="graph_centrality_score gt 0.7",
    order_by=["graph_centrality_score desc"],
    top=10
)
```

### 4. Navigate Hierarchically
```python
# Find all children of a specific page
parent_id = "12345"
results = search_client.search(
    search_text="*",
    filter=f"parent_page_id eq '{parent_id}'",
    order_by=["title asc"]
)
```

## Graph Enrichment Function Details

The `graph_enrichment_skill` function continues to:

1. **Query Cosmos DB Graph**
   ```python
   # Get ancestors (path to root)
   g.V(page_id).repeat(out('has_parent')).until(outE().count().is_(0)).path()
   
   # Get children
   g.V(page_id).in_('has_parent').values('title', 'id')
   
   # Get siblings
   g.V(page_id).out('has_parent').in_('has_parent').where(neq(page_id))
   
   # Get related pages
   g.V(page_id).out('links_to').values('title', 'id')
   ```

2. **Calculate Graph Metrics**
   ```python
   def calculate_centrality_score(page_id):
       # In-degree (pages linking to this)
       in_degree = g.V(page_id).in_().count()
       
       # Out-degree (pages this links to)
       out_degree = g.V(page_id).out('links_to').count()
       
       # Betweenness (pages on shortest paths)
       betweenness = calculate_betweenness_centrality(page_id)
       
       # Combine metrics
       centrality = (in_degree * 0.4 + out_degree * 0.2 + betweenness * 0.4) / max_score
       return centrality
   ```

3. **Return Enriched Metadata**
   ```json
   {
     "hierarchy_depth": 3,
     "hierarchy_path": "Home > Documentation > API Reference > REST API",
     "parent_page_id": "67890",
     "parent_page_title": "API Reference",
     "has_children": true,
     "child_count": 15,
     "sibling_count": 8,
     "related_page_count": 23,
     "graph_centrality_score": 0.82,
     "graph_metadata": {
       "ancestors": [...],
       "children": [...],
       "siblings": [...],
       "related_pages": [...]
     }
   }
   ```

## Benefits of Graph Integration

1. **Contextual Understanding**
   - Users searching for "installation" get the official installation guide (high centrality) not random mentions
   - Overview pages rank higher for broad queries
   - Detailed pages rank higher for specific queries

2. **Navigation Support**
   - Breadcrumb trails from hierarchy_path
   - "See also" suggestions from related_pages
   - Parent/child navigation

3. **Quality Signals**
   - Well-connected pages (hubs) get boosted
   - Orphaned pages rank lower
   - Official documentation structure preserved

4. **Space-Aware Search**
   - Different spaces have different hierarchies
   - Cross-space relationships maintained
   - Space-specific centrality scores

## Monitoring Graph Enrichment

```python
# Check graph enrichment performance
def monitor_graph_enrichment():
    # Query for pages missing graph data
    missing_graph = search_client.search(
        search_text="*",
        filter="graph_centrality_score eq null",
        select=["id", "title"],
        include_total_count=True
    )
    
    print(f"Pages missing graph data: {missing_graph.get_count()}")
    
    # Check distribution of centrality scores
    for threshold in [0.3, 0.5, 0.7, 0.9]:
        high_centrality = search_client.search(
            search_text="*",
            filter=f"graph_centrality_score gt {threshold}",
            include_total_count=True
        )
        print(f"Pages with centrality > {threshold}: {high_centrality.get_count()}")
```

## Summary

Phase 1 **enhances** rather than replaces the graph capabilities:

- ✅ **Cosmos DB graph** remains the source of truth for relationships
- ✅ **Graph enrichment** runs for every document during indexing  
- ✅ **Graph metrics** influence search ranking through scoring profiles
- ✅ **Hierarchical structure** preserved and searchable
- ✅ **Graph-based filtering** enables navigation and faceting

The only changes in Phase 1 are:
- Using Azure OpenAI skill instead of custom embedding function
- Using built-in text splitting instead of custom chunking
- Adding automatic query vectorization

All graph features remain intact and are actually more powerful with the improved scoring profiles! 