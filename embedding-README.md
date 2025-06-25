# Confluence Q&A System - Embedding Strategy Blueprint

## Table of Contents
- [Overview](#overview)
- [1. Why a Specialized Embedding Strategy is Needed](#1-why-a-specialized-embedding-strategy-is-needed)
- [2. Chunking & Embedding Flow](#2-chunking--embedding-flow)
- [3. Retrieval Logic](#3-retrieval-logic)
- [4. Implementation Snapshot](#4-implementation-snapshot)

---

## Overview

This document provides a practical blueprint for producing high-quality, "hierarchy-aware" embeddings that work well with Confluence pages containing headings, body text, tables, images, and cross-links. The plan follows Azure AI Search and Cosmos DB conventions, so it plugs cleanly into the pipeline you already sketched.

---

## 1. Why a Specialized Embedding Strategy is Needed

| Confluence Artefact | Risk if Naïvely Embedded | Recommended Handling |
| ------------------- | ------------------------ | -------------------- |
| **Titles / H-tags** | Lost when buried inside large chunks | Separate "title vectors" so short, high-salience text can dominate scoring |
| **Body paragraphs** | Long pages blow past token limits; dense sections drown sparse ones | Sliding-window chunking (≈ 512 tokens, 128-token overlap) with paragraph boundary snapping |
| **Tables** | Cell order & header semantics lost; LLM answers break if a row is retrieved without context | Convert each table to (a) **compact Markdown** string and (b) an **LLM-generated summary sentence**; store both as child vectors |
| **Images / diagrams** | No representation, so answers may omit crucial content | Run GPT-4o Vision (or Azure CogSvc OCR) → alt-text → embed like normal text |
| **Links / hierarchy** | Retrieval may surface orphan chunks with no sense of path | Keep breadcrumb path in metadata; create "page-level" parent vector + graph edges so you can walk up when confidence is low |

---

## 2. Chunking & Embedding Flow

### 2.1 Extract & Normalize

Use the ETL in Azure AI Foundry to output a JSON doc per Confluence page:

```json
{
  "pageId": "123",
  "title": "Release Process",
  "breadcrumb": "Home › Engineering › DevOps",
  "sections": [
    {"heading": "Overview", "text": "...", "order": 0},
    {"heading": "Checklist", "table": "...", "order": 1},
    ...
  ]
}
```

### 2.2 Generate Child Chunks

| Child Vector Type | Payload | Notes |
| ----------------- | ------- | ----- |
| `titleVector` | `title` | Short (< 100 tokens) |
| `bodyVector` | Sliding windows of `text` | 512 tokens with 128 overlap ([learn.microsoft.com](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents?utm_source=chatgpt.com "Chunk documents in vector search - Azure AI Search - Learn Microsoft")) |
| `tableVector` | Markdown table string | Keep row/col headers |
| `tableSummaryVector` | LLM-generated 1-2 sentence abstract | Helps when tables are large ([medium.com](https://medium.com/%40sudhanshu.bhargav/advanced-rag-embedded-tables-c29ab5e3bd5b?utm_source=chatgpt.com "Advanced RAG: Embedded Tables - by Sudhanshu Bhargav - Medium")) |
| `imageVector` (optional) | Alt-text or caption | Multimodal embeddings ([medium.com](https://medium.com/%40adnanmasood/optimizing-chunking-embedding-and-vectorization-for-retrieval-augmented-generation-ea3b083b68f7?utm_source=chatgpt.com "Optimizing Chunking, Embedding, and Vectorization for Retrieval ...")) |

### 2.3 Embed with text-embedding-3-large

Embed with `text-embedding-3-large` (or small for cost) and write the result into multi-vector fields in Azure AI Search index.

Store metadata alongside every child vector:

```json
{
  "vectorType": "tableVector",
  "pageId": "123",
  "sectionHeading": "Checklist",
  "breadcrumb": "Home › Engineering › DevOps",
  "position": 1
}
```

### 2.4 Graph Links

In Cosmos DB Graph, keep the edges you already created (`ParentOf`, `ChildOf`, `LinksTo`). Embed one additional "page-level" vector (concatenate title + abstract) so you can fall back to the parent node when needed.

---

## 3. Retrieval Logic

### 3.1 Hybrid Query

Fire one BM25 full-text sub-query and one vector sub-query in a single request; Azure AI Search fuses them with Reciprocal Rank Fusion (RRF).

### 3.2 Confidence Gate

```python
if top_child_vector_similarity >= threshold:
    return answer_with_direct_page_link
else:
    # Walk one hop up in Cosmos Graph
    # Re-query using the parent vector + child vectors of siblings
    # Surface breadcrumb tree in the UI so the user can drill down
    return parent_page_fallback
```

### 3.3 Context Assembly

Group retrieved chunks by `pageId`; feed the agent prompt:

```
Context (titles → body → table summaries): …
Graph path: Home › … › CurrentPage
User query: …
```

This "small-to-big" ordering helps the LLM exploit hierarchy.

---

## 4. Implementation Snapshot (Python)

```python
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAIEmbeddings

search = SearchClient(endpoint, index_name, DefaultAzureCredential())

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    embeddings = AzureOpenAIEmbeddings(
        deployment="text-embedding-3-large",
        api_version="2025-05-15"
    )
    return embeddings.embed_documents(chunks)

# Example: body windows
windows = sliding_window(section_text, size=512, overlap=128)
vectors = embed_chunks(windows)

docs = [{
    "id": f"{page_id}-{i}",
    "pageId": page_id,
    "vectorType": "bodyVector",
    "content": windows[i],
    "bodyVector": vectors[i],  # multi-vector child field
    "breadcrumb": breadcrumb,
    "sectionHeading": heading,
    "position": i
} for i in range(len(windows))]

search.upload_documents(docs)
```

### Key Implementation Notes

1. **Multi-vector Fields**: Use Azure AI Search's multi-vector field support for storing different types of embeddings
2. **Sliding Window**: Implement 512-token windows with 128-token overlap for optimal chunking
3. **Metadata Preservation**: Store breadcrumb paths and section information for context
4. **Graph Integration**: Maintain parent-child relationships in Cosmos DB for fallback scenarios

### Performance Considerations

- **Batch Processing**: Process embeddings in batches to optimize API calls
- **Caching**: Cache frequently accessed embeddings to reduce latency
- **Parallel Processing**: Use async operations for large-scale embedding generation
- **Cost Optimization**: Consider using `text-embedding-3-small` for non-critical content

---

## Best Practices

### Embedding Strategy
- **Separate title vectors** for high-salience content
- **Sliding window chunking** for body text
- **Table-specific handling** with both raw and summary vectors
- **Image content extraction** using OCR or vision models
- **Hierarchy preservation** through breadcrumb metadata

### Retrieval Optimization
- **Hybrid search** combining BM25 and vector similarity
- **Confidence-based fallback** to parent pages
- **Context-aware assembly** for LLM prompts
- **Graph-based navigation** for user exploration

### Integration Points
- **Azure AI Foundry**: For ETL and data processing
- **Azure AI Search**: For vector storage and retrieval
- **Cosmos DB Graph**: For hierarchical relationships
- **Azure OpenAI**: For embedding generation and text processing 