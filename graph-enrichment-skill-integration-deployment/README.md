# Graph Enrichment Skill Integration Deployment

This directory contains Python scripts for integrating graph enrichment capabilities into Azure AI Search.

## Overview

The deployment creates a new search index (`confluence-graph-embeddings-v2`) that includes alhe graph relationship fields from Cosmos DB, enabling graph-aware search capabilities.

## Files

1. **`confluence-graph-embeddings-v2.json`** - Index definition with graph enrichment fields
2. **`01_deploy_graph_enriched_search.py`** - Creates index, skillset, and indexer (Steps 1-3)
3. **`02_migration_and_verification.py`** - Runs indexer and verifies migration (Steps 4-5)

## Prerequisites
3. Environment variables or `.env` file with:
   - `SEARCH_SERVICE` (default: srch-rag-conf)
   - `SEARCH_KEY`
   - `SEARCH_ENDPOINT` 
   - `RESOURCE_GROUP` (default: rg-rag-confluence)
   - `FUNCTION_APP` (default: func-rag-graph-enrich)
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_KEY`
   - `GRAPH_ENRICHMENT_FUNCTION_KEY` 

## Deployment Steps

### Step 1: Deploy Graph Enrichment Function

Ensure the graph enrichment function is deployed and running:
```bash
cd ../infra
./05-main-deploy-graph-enrichment-function.sh
```

### Step 2: Create Search Infrastructure

Run the deployment script to create index, skillset, and indexer:
```bash
python 01_deploy_graph_enriched_search.py
```

This will:
- Create `confluence-graph-embeddings-v2` index with graph fields
- Create `confluence-integrated-skillset` with graph enrichment skill
- Create `confluence-integrated-indexer` with proper field mappings

### Step 3: Run Migration and Verify

Execute the migration script to populate the new index:
```bash
python 02_migration_and_verification.py
```

This will:
- Run the indexer to process all documents
- Monitor indexer progress in real-time
- Verify graph fields are populated
- Compare document counts between old and new indexes
- Test graph-aware search functionality

## Graph Enrichment Fields

The new index includes these graph-related fields:

| Field | Type | Description |
|-------|------|-------------|
| hierarchy_depth | Int32 | Depth in page hierarchy (0 = root) |
| hierarchy_path | String | Full path in hierarchy |
| breadcrumb | String | User-friendly breadcrumb navigation |
| parent_page_id | String | ID of parent page |
| parent_page_title | String | Title of parent page |
| has_children | Boolean | Whether page has child pages |
| child_count | Int32 | Number of direct children |
| sibling_count | Int32 | Number of sibling pages |
| related_page_count | Int32 | Number of related pages |
| graph_centrality_score | Double | PageRank centrality score |
| graph_metadata | String | Additional graph metadata (JSON) |

## Graph-Aware Scoring

The index includes a `graph-aware-scoring` profile that boosts results based on:
- **Graph centrality** - Pages with high PageRank scores
- **Hierarchy depth** - Pages closer to root get higher scores
- **Child count** - Hub pages with many children are boosted

## Troubleshooting

### Function Key Issues
If you see "Function key should be set in GRAPH_ENRICHMENT_FUNCTION_KEY env var":
1. Get the function key from Azure Portal or CLI:
   ```bash
   az functionapp function keys list \
     --resource-group rg-rag-confluence \
     --name func-rag-graph-enrich \
     --function-name graph_enrichment_skill
   ```
2. Set it as environment variable:
   ```bash
   export GRAPH_ENRICHMENT_FUNCTION_KEY="your-key-here"
   ```

### Indexer Failures
Check indexer status and errors:
```bash
az search indexer status \
  --service-name srch-rag-conf \
  --name confluence-integrated-indexer
```

### Graph Fields Not Populated
Verify:
1. Function app is running
2. Cosmos DB connection is working
3. Graph data exists in Cosmos DB

## Next Steps

After successful deployment:
1. Update your application to use `confluence-graph-embeddings-v2` index
2. Test search queries with graph-aware scoring
3. Monitor search relevance and performance
4. Deprecate old index once satisfied

## Rollback

To rollback to the original index:
1. Simply update your application to use `confluence-graph-embeddings` index
2. The old index remains unchanged during this migration



 Compact summary (ctrl+r to expand)
  ⎿  Read infra/sample_page.json (241 lines)
  ⎿  Read infra/fix-indexer.sh (87 lines)
  ⎿  Read infra/update-indexer-simple.sh (73 lines)
  ⎿  Read infra/create-simple-skillset.sh (76 lines)
  ⎿  Read AZURE-SEARCH-IMPLEMENTATION-GUIDE.md (358 lines)