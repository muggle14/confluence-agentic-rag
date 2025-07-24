

# 5. Flow Diagram (High-level)

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


          ┌─────────────────────┐
          │   Confluence API    │
          └────────┬────────────┘
                   ↓
          ┌─────────────────────┐
          │ Azure Function (ETL)│
          │ func-rag-conf       │
          └────────┬────────────┘
                   ↓
          ┌─────────────────────┐
          │ Blob Storage        │
          │ (raw JSON)          │
          └────────┬────────────┘
            ┌──────┴───────┐
            ↓              ↓
┌────────────────┐   ┌─────────────────────┐
│Graph data      │   │Python Chunk Script  │
│Indexer         │   │(create-chunking...) │
└──────┬─────────┘   └────────┬────────────┘
       ↓                      ↓
┌──────────────┐      ┌──────────────┐
│              │      │ Azure OpenAI │
│ VectorSkills │      │ (Embeddings) │
└──────┬───────┘      └──────┬───────┘
       ↓                     ↓
┌──────────────┐      ┌──────────────┐
│ Document     │      │ Chunk        │
│ Index        │      │ Index        │
│ (confluence- │      │ (confluence- │
│ graph-embed) │      │ chunks)      │
└──────┬───────┘      └──────┬───────┘
       ↓                     ↓
       └──────┬──────────────┘
              ↓
     ┌──────────────────────┐
     │ Agentic RAG Workflow │
     │ (Retrieval + GPT)    │
     └────────┬─────────────┘
              ↓
     ┌──────────────────────┐
     │ Frontend (React UI)  │
     └──────────────────────┘


## resource names

| Resource Type     | Naming Pattern              | Example                    |
|-------------------|-----------------------------|----------------------------|
| Resource Group    | `rg-{project}-{env}`        | `rg-rag-confluence`        |
| Storage Account   | `stg{project}{env}`         | `stgragconf`               |
| Search Service    | `srch-{project}-{env}`      | `srch-rag-conf`            |
| Azure OpenAI      | `aoai-{project}-{env}`      | `aoai-rag-confluence`      |
| Function App      | `func-{project}-{env}`      | `func-rag-conf`            |
| Index             | `{content}-{type}`          | `confluence-chunks`        |
| Skillset          | `{content}-{type}-skillset` | `confluence-graph-skillset`|