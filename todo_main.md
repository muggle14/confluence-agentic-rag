TODO: 
# PRINCIPLES: INSTEAD OF FASTAPI USE AZURE ECOSYSTEM LIKE AZURE WEBAPP

## refer to agent_README.md and refine the architecture to use webapp instead of FastAPI
## refer to agent_quickstart_guide.md and refer the quickstart guide 

## do we need redis, what is the similar equivalent in the azure ecosystem 
## similarly #Himanshu to understand if docker container is needed.
## compare if main.bicep is different from the configuration of infra files??? used to provision & deploy the resources
## 

---

# AZURE SEARCH IMPLEMENTATION - OUTSTANDING TASKS

## Phase 1: Complete Current Implementation (Priority: High)
- [ ] Clean up remaining deprecated files in infra/ directory
  - [ ] deploy-phase1-*.sh files
  - [ ] deploy-graph-*.sh files
  - [ ] Old documentation files (ingestion-README-*.md, processing-README.md)
- [ ] Update main README.md with new search implementation details
- [ ] Document the new chunking approach in claude.md

## Phase 2: Integrate Smart Features from embedding/ folder (Priority: High)
- [ ] Integrate smart chunker (chunker.py) as Azure custom skill
  - [ ] Preserve paragraph boundaries
  - [ ] Handle tables properly (markdown conversion)
  - [ ] Implement chunk type classification (TITLE, BODY, TABLE, etc.)
- [ ] Add graph enrichment from graph_enricher.py
  - [ ] Create custom skill for Cosmos DB integration
  - [ ] Implement hierarchical context (ancestors, siblings)
  - [ ] Add confidence boosting based on connectivity
- [ ] Migrate configuration to use config.py patterns
  - [ ] Centralized settings management
  - [ ] Environment validation

## Phase 3: Production Readiness (Priority: Medium)
- [ ] Implement incremental indexing
  - [ ] Track last indexed timestamp
  - [ ] Only process new/modified documents
  - [ ] Handle deletions properly
- [ ] Add monitoring and alerting
  - [ ] Application Insights integration
  - [ ] Custom metrics for chunk processing
  - [ ] Alert on indexing failures
- [ ] Performance optimization
  - [ ] Implement caching layer (Azure Cache for Redis)
  - [ ] Optimize embedding batch sizes
  - [ ] Add connection pooling

## Phase 4: Azure Native Migration (Priority: Medium)
- [ ] Convert Python chunking solution to Azure Function
  - [ ] Trigger on blob storage events
  - [ ] Automatic chunk processing
  - [ ] Error handling and retry logic
- [ ] Implement Knowledge Store properly
  - [ ] Project chunks as separate documents
  - [ ] Enable automatic indexing from Knowledge Store
  - [ ] Remove need for manual Python script
- [ ] Add semantic search capabilities
  - [ ] Configure semantic configurations
  - [ ] Add answer extraction
  - [ ] Implement query understanding

## Phase 5: Advanced Features (Priority: Low)
- [ ] Multi-language support
  - [ ] Language detection in chunker
  - [ ] Language-specific analyzers
  - [ ] Cross-language search
- [ ] Advanced query features
  - [ ] Query expansion with synonyms
  - [ ] Faceted search by space/type
  - [ ] Search result highlighting
- [ ] Security and compliance
  - [ ] Document-level security trimming
  - [ ] Audit logging for searches
  - [ ] PII detection and redaction

## Infrastructure as Code (Priority: High)
- [ ] Complete Bicep templates
  - [ ] Validate main.bicep against current deployment
  - [ ] Add missing resources (chunk index, custom skills)
  - [ ] Parameterize all configurations
- [ ] GitHub Actions pipeline
  - [ ] Automated testing of search functionality
  - [ ] Deployment pipeline for all components
  - [ ] Environment promotion (dev/staging/prod)
- [ ] Terraform alternative (if needed)
  - [ ] Convert Bicep to Terraform
  - [ ] Add state management
  - [ ] Multi-region deployment support

## Documentation Updates (Priority: High)
- [ ] Update CLAUDE.md with search implementation
- [ ] Create API documentation for search endpoints
- [ ] Add troubleshooting guide for common issues
- [ ] Create performance tuning guide
- [ ] Document cost optimization strategies

## Testing and Validation (Priority: High)
- [ ] Create comprehensive test suite
  - [ ] Unit tests for chunking logic
  - [ ] Integration tests for search pipeline
  - [ ] Performance benchmarks
- [ ] Implement search quality metrics
  - [ ] Relevance scoring validation
  - [ ] A/B testing framework
  - [ ] User feedback collection

## Migration from Existing System
- [ ] Data migration strategy
  - [ ] Migrate existing embeddings if any
  - [ ] Preserve document relationships
  - [ ] Validate data integrity
- [ ] Cutover plan
  - [ ] Parallel run period
  - [ ] Rollback procedures
  - [ ] Success criteria definition

## Available but Unused Infrastructure (Added: 2025-01-13)

### Overview
There are two parallel Azure AI Search implementations in the codebase:
1. **Currently Active**: Basic document-level indexing (confluence-graph-embeddings index)
2. **Available but Unused**: Advanced chunk-level indexing (confluence-chunks index)

### Unused Chunk-Based Infrastructure

#### Components:
1. **Index: confluence-chunks**
   - More sophisticated structure for chunk-level search
   - Fields: chunk_id, parent_id, page_id, chunk_index, chunk_text, parent_title, space_key, chunk_embedding, metadata
   - Better suited for granular search and retrieval
   - Includes scoring profiles for chunk relevance

2. **Skillset: confluence-chunk-skillset**
   - Advanced chunking with text splitting (2000 chars)
   - Shaper skill for structured chunk documents
   - Embedding generation per chunk
   - Knowledge Store projection capability

3. **Associated Scripts** (Renamed with TODO_ prefix):
   - `infra/TODO_create-chunk-index.sh` - Creates the chunk-level index with proper schema
   - `infra/TODO_create-chunk-skillset.sh` - Creates skillset with chunking and Knowledge Store
   - `infra/TODO_create-chunk-indexer.sh` - Would create indexer for chunk processing
   - `infra/TODO_create-chunking-solution.py` - Python script for manual chunk processing
   - `infra/TODO_run-chunking-solution.sh` - Wrapper to run the Python chunking
   - `infra/TODO_deploy-graph-aware-search-integrated.sh` - Main script that creates integrated skillset with graph enrichment
   - `infra/create-chunk-skillset-fixed.sh` - Fixed version of chunk skillset (not renamed)
   - `infra/update-indexer-chunking.sh` - Updates indexer for chunking (not renamed)

### Why It's Not Being Used:
- The deployment focused on simpler document-level approach first
- Chunk-based approach requires more complex indexer configuration
- Knowledge Store integration adds complexity
- Current indexer (`confluence-graph-indexer`) points to document-level index

### Migration Path to Chunk-Based:
1. Create new indexer pointing to confluence-chunks index
2. Use confluence-chunk-skillset for processing
3. Add graph enrichment to chunk skillset
4. Update field mappings for chunk structure
5. Implement chunk reassembly for search results

### Benefits of Chunk-Based Approach:
- More precise search results (finds exact passages)
- Better handling of long documents
- Improved relevance scoring at chunk level
- Each chunk can inherit graph metadata from parent
- Supports incremental updates per chunk

### Integration with Graph Enrichment:
The chunk-based approach would work better with graph enrichment because:
- Graph metadata applies at document level
- Each chunk inherits parent's graph properties
- Search can boost chunks from high-centrality documents
- Maintains context while enabling precise retrieval 