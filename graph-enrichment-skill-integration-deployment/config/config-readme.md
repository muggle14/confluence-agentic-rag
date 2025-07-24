confluence-blob-datasource.json (Source)
           ↓
confluence-graph-indexer.json (Orchestrator)
           ↓
confluence-graph-skillset.json (Processor)
           ↓
confluence-graph-embeddings-v2.json (Destination)



Purpose of Each JSON File in the config:

1. confluence-graph-embeddings-v2.json 
Purpose: Azure AI Search Index Definition
Defines the search index schema with all graph enrichment fields
Contains vector search configuration for embeddings
Includes semantic search configuration
Defines field types, searchability, filterability, and sortability
This is essential - it's the core index definition that the indexer populates

2. confluence-graph-skillset.json 
Purpose: Azure AI Search Skillset Definition
Defines the AI enrichment pipeline
Contains ShaperSkill for nested field extraction
Includes Azure OpenAI embedding skills for content and title
Contains GraphEnrichmentSkill for adding graph data
This is essential - it defines how documents are processed and enriched

3. confluence-graph-indexer.json 
Purpose: Azure AI Search Indexer Definition
Defines how data flows from source to index
Contains field mappings from source to target
Defines output field mappings from skillset to index
This is essential - it orchestrates the entire indexing process

4. confluence-blob-datasource.json 
Purpose: Azure AI Search Data Source Definition
Defines the connection to Azure Blob Storage
Specifies which container and path to read from
This is essential - it defines where the source data comes from