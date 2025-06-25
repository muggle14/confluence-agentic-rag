# Agentic RAG on Confluence – End-to-End Code Base

> **Goal**: Automate resource provisioning, data ingestion, graph population, embedding & indexing on Azure.
> Use this as the starter repo – each step is independent but wired together via environment variables.

## Table of Contents
- [0. Prerequisites](#0-prerequisites-envexample)
- [1. Resource Provisioning (Bicep)](#1-resource-provisioning-bicep--cost-optimised)
- [2. Ingestion (Azure Functions)](#2-ingestion-azure-functions--python-v4)
- [3. Process & Graph Population](#3-process--graph-population-adf--python-notebook)
- [4. Embedding & Indexing](#4-embedding--indexing-python-script)
- [5. CI/CD](#5-cicd--github-actions-snippet)
- [6. Agentic Orchestration & Prompt Engineering](#6-agentic-orchestration--prompt-engineering-copilot-studio)
- [7. Copilot Wiring](#7-copilot-wiring--step-by-step)
- [8. Next Steps](#8-next-steps)

---

## 0. Prerequisites (.env.example)

> 🏷️ **Cost-savvy tips for a personal dev sub**
> • Choose the lowest-cost SKUs (`F2` App Service, `Serverless` Cosmos, Search `basic`) unless performance tests say otherwise.
> • Re-use an existing **Resource Group**, **Storage V2 account**, or **Application Insights** instance if one is already in your dev sub – just point the Bicep parameters at the existing names.

```bash
# Azure Subscription details
AZ_SUBSCRIPTION_ID=<your-subscription-id>
AZ_RESOURCE_GROUP=rg-rag-confluence
AZ_LOCATION=westeurope

# Cosmos DB
COSMOS_ACCOUNT=cosmos-rag-conf
COSMOS_KEY=<autofill by script>
COSMOS_DB=confluence
COSMOS_GRAPH=pages

# Storage
STORAGE_ACCOUNT=stgragconf

# Azure AI Search
SEARCH_SERVICE=srch-rag-conf
SEARCH_INDEX=confluence-idx

# Azure OpenAI
AOAI_RESOURCE=aoai-rag-conf
AOAI_EMBED_DEPLOY=text-embedding-3-large
AOAI_CHAT_DEPLOY=gpt-4o

# Function App
FUNC_APP=func-rag-conf

# Confluence
CONFLUENCE_BASE=https://<org>.atlassian.net/wiki/rest/api
CONFLUENCE_TOKEN=<pat>
```

Create an `.env` in repo-root and fill in real values.

---

## 1. Resource Provisioning (Bicep – **cost-optimised**)

### 1.1 `main.bicep` (single-file quick start)

Below is a **compressed, cheapest-tier** template that stands up every service in one shot. Adjust parameters to point at pre-existing resources if you already have them (→ 💸 **zero cost** for re-use).

```bicep
@description('Location for all resources')
param location string = resourceGroup().location
@description('Reuse existing Storage Account? Leave blank to create new.')
param existingStorage string = ''
@description('Storage account name when new one is created')
param storageAccountName string = 'stgragconf'

// ===== Storage (Raw + Processed) =====
var storageName = existingStorage == '' ? storageAccountName : existingStorage
resource storage 'Microsoft.Storage/storageAccounts@2022-09-01' = if (existingStorage == '') {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    isHnsEnabled: true // ADLS gen2
  }
}

// ===== Function App (Timer-trigger ingestion) – Consumption Plan =====
param functionAppName string = 'func-rag-conf'
resource plan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: '${functionAppName}-plan'
  location: location
  sku: {
    name: 'Y1' // Consumption, cheapest
    tier: 'Dynamic'
  }
}
resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsStorage'
          value: storage.properties.primaryEndpoints.blob
        }
      ]
    }
  }
}

// ===== Cosmos DB (Gremlin) – Serverless =====
param cosmosAccountName string = 'cosmos-rag-conf'
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  tags: {
    CostTier: 'Dev'
  }
  properties: {
    capabilities: [{ name: 'EnableGremlin' }]
    databaseAccountOfferType: 'Serverless' // 🚀 pay-per-request
  }
}
resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmos
  name: 'confluence'
  properties: {}
}
// Graph container omitted for brevity – create at runtime.

// ===== Azure AI Search – FREE tier if available =====
param searchServiceName string = 'srch-rag-conf'
resource search 'Microsoft.Search/searchServices@2023-10-01-preview' = {
  name: searchServiceName
  location: location
  sku: {
    name: 'free' // (1 replica, 1 partition, 3 indexes) – upgrade later
  }
  properties: {}
}

// ===== Azure OpenAI – S0 is the only tier =====
param aoaiName string = 'aoai-rag-conf'
resource aoai 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: aoaiName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'OpenAI'
  properties: {
    apiProperties: {
      kind: 'OpenAI'
    }
  }
}

// ===== App Service (React UI) – F1 free tier =====
param webAppName string = 'rag-ui-conf'
resource appPlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: '${webAppName}-plan'
  location: location
  sku: {
    name: 'F1' // Free tier
    tier: 'Free'
  }
}
resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appPlan.id
    httpsOnly: true
  }
}
```

### 1.2 Deploy via AZ CLI (with reuse flags)

If you already have a dev storage account or App Insights resource, pass their names to reuse them and **skip new cost**.

```bash
az deployment group create \
  --resource-group $AZ_RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters \
    location=$AZ_LOCATION \
    existingStorage=$EXISTING_STORAGE_ACCOUNT   # optional reuse
```

```bash
az deployment group create \
  --resource-group $AZ_RESOURCE_GROUP \
  --template-file main.bicep \
  --parameters \
    cosmosAccountName=$COSMOS_ACCOUNT \
    storageAccountName=$STORAGE_ACCOUNT \
    searchServiceName=$SEARCH_SERVICE \
    aoaiName=$AOAI_RESOURCE \
    functionAppName=$FUNC_APP
```

---

## 2. Ingestion (Azure Functions – Python v4)

### 2.1 `ingest/__init__.py`

```python
import os, json, logging, requests
from azure.storage.blob import BlobClient

def main(mytimer):
    base = os.environ['CONFLUENCE_BASE']
    token = os.environ['CONFLUENCE_TOKEN']
    headers = {"Authorization": f"Bearer {token}"}
    page = 0
    while True:
        resp = requests.get(f"{base}/content", params={"limit":100, "start":page*100}, headers=headers)
        data = resp.json()
        if not data.get('results'): break
        for item in data['results']:
            save_to_blob(item)
        page += 1

def save_to_blob(page_json):
    storage_url = os.environ['STORAGE_CONN']
    container = 'raw'
    blob_name = f"{page_json['id']}.json"
    bc = BlobClient.from_connection_string(storage_url, container, blob_name)
    bc.upload_blob(json.dumps(page_json), overwrite=True)
```

### 2.2 `function.json`

```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "name": "mytimer",
      "type": "timerTrigger",
      "direction": "in",
      "schedule": "0 */6 * * * *"  // every 6 hours
    }
  ]
}
```

Deploy with:

```bash
func azure functionapp publish $FUNC_APP --python
```

---

## 3. Process & Graph Population (ADF + Python Notebook)

**Option A Data Factory** – create a mapping data flow: Blob → Notebook activity → Cosmos.

**Option B Standalone Notebook** – example snippet filling Cosmos Graph 🎯

### 3.1 `notebooks/populate_graph.py`

```python
import os, json, glob
from gremlin_python.driver import client, serializer

client = client.Client(
    f"wss://{os.environ['COSMOS_ACCOUNT']}.gremlin.cosmos.azure.com:443/",
    'g',
    username=f"/dbs/{os.environ['COSMOS_DB']}/colls/{os.environ['COSMOS_GRAPH']}",
    password=os.environ['COSMOS_KEY'],
    message_serializer=serializer.GraphSONSerializersV2d0()
)

def upsert_page(page):
    q = (
        "g.V('%s').fold().coalesce(" % page['id'] +
        "unfold(), addV('page').property('id','%s').property('title', '%s')" % (page['id'], page['title'].replace("'","""")) +
        ".property('content', '%s')" % page['body']['storage']['value'].replace("'","""")) +
        ")"
    )
    client.submit(q).all().result()

for f in glob.glob('/mnt/data/raw/*.json'):
    page = json.load(open(f))
    upsert_page(page)
    # Parent/child edges can be added similarly
```

---

## 4. Embedding & Indexing (Python script)

### 4.1 `embed/index.py`

```python
import os, json, glob, textwrap
from azure.search.documents import SearchClient, SearchIndexClient
from azure.search.documents.indexes.models import (
    ComplexField, SearchIndex, SearchFieldDataType, VectorSearch,
    VectorSearchAlgorithmConfiguration, HnswParameters, SearchableField)
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAIEmbeddings

credential = DefaultAzureCredential()
search_admin = SearchIndexClient(os.environ['SEARCH_ENDPOINT'], credential)

# --- 1. Ensure index exists ---
index_name = os.environ['SEARCH_INDEX']
if index_name not in [i.name for i in search_admin.list_indexes()]:
    index = SearchIndex(
        name=index_name,
        fields=[
            SearchableField(name='id', type=SearchFieldDataType.String, key=True),
            SearchableField(name='pageId', type=SearchFieldDataType.String),
            SearchableField(name='title', type=SearchFieldDataType.String),
            SearchableField(name='vectorType', type=SearchFieldDataType.String),
            ComplexField(name='content', type=SearchFieldDataType.String, searchable=True),
            ComplexField(name='embedding', type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                vector_search_dimensions=1536, vector_search_configuration='default', searchable=True)
        ],
        vector_search=VectorSearch(configurations=[
            VectorSearchAlgorithmConfiguration(name='default', kind='hnsw', parameters=HnswParameters())
        ])
    )
    search_admin.create_index(index)

search = SearchClient(os.environ['SEARCH_ENDPOINT'], index_name, credential)

aoai = AzureOpenAIEmbeddings(
    deployment=os.environ['AOAI_EMBED_DEPLOY'],
    api_version='2025-05-15',
    azure_endpoint=os.environ['AOAI_ENDPOINT'],
    azure_ad_token_provider=credential.get_token
)

# --- 2. Chunk & embed ---

def chunk(text, size=512, overlap=128):
    words = text.split()
    i = 0
    while i < len(words):
        yield ' '.join(words[i:i+size])
        i += size - overlap

batch = []
for f in glob.glob('/mnt/data/processed/*.json'):
    page = json.load(open(f))
    for section in page['sections']:
        chunks = chunk(section.get('text',''))
        for i, c in enumerate(chunks):
            emb = aoai.embed_documents([c])[0]
            batch.append({
                'id': f"{page['pageId']}-{section['order']}-{i}",
                'pageId': page['pageId'],
                'title': section.get('heading',''),
                'vectorType': 'body',
                'content': c,
                'embedding': emb
            })
    if len(batch) >= 1000:
        search.upload_documents(batch)
        batch.clear()

if batch:
    search.upload_documents(batch)
```

---

## 5. CI/CD – GitHub Actions snippet `.github/workflows/deploy.yml`

```yaml
name: Deploy RAG Pipeline
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      - name: Deploy Bicep
        run: |
          az deployment group create \
            --resource-group $AZ_RESOURCE_GROUP \
            --template-file main.bicep \
            --parameters cosmosAccountName=$COSMOS_ACCOUNT ...
      - name: Publish Function App
        run: |
          pushd ingestion
          func azure functionapp publish $FUNC_APP --python
          popd
```

### 5.1 Folder Layout

```
/infra
  └─ main.bicep
/ingestion
  ├─ __init__.py
  └─ function.json
/notebooks
  └─ populate_graph.py
/embed
  └─ index.py
.github/workflows/deploy.yml
.env.example
```

---

## 6. Agentic Orchestration & Prompt Engineering (Copilot Studio)

Below is a thin-slice implementation you can drop into Copilot Studio **without leaving the Azure stack**. It adds query-decomposition, multi-hop retrieval, and hallucination-guard rails on top of the pipeline you already provisioned.

### 6.1 Agent Graph (logical)

| Role | Tooling | Purpose |
| ---- | ------- | ------- |
| QueryAnalyser | Copilot Studio *function* | Decide if the user query is atomic / decomposable / needs clarification. Outputs JSON. |
| Decomposer | Azure OpenAI | Produce ordered sub-questions when required. |
| PathPlanner | Copilot Studio *function* (small GPT call) | Calculate traversal strategy: chooses edge types (e.g., `ParentOf`, `LinksTo`, custom), applies `MAX_HOPS`, returns filter list for each hop. |
| Retriever | Azure AI Search (vector + BM25) | Executes hybrid search with filters from PathPlanner. |
| Reranker | `aoai://semantic_reranker_v2` | Cross-encoder rerank. |
| Synthesiser | Azure OpenAI (GPT-4o) | Generates answer with citations. |
| Verifier | Azure OpenAI (GPT-4o) | Hallucination / coverage check. |

> **Max-Hop Control**
> `PathPlanner` honours an env-var `MAX_HOPS` (default = 3). If the chain length set by Decomposer exceeds this, it truncates and marks `truncated=true` in its JSON so Synthesiser can add a note.

### 6.2 Prompt Templates

#### 6.2.1 System Prompt (shared)

```text
You are ConfluenceRAG-Bot, an expert on <ORG> documentation.
• Cite sources as [[pageId-chunk]] after each claim.
• If confidence < τ or verifier flags risk, reply:  
  "I'm not fully certain — here's the closest parent page and links you might explore." and provide the breadcrumb.
```

#### 6.2.2 Decomposition Prompt

```text
Return JSON:
{"subquestions": ["…", "…"], "requires_multihop": true|false}
```

#### 6.2.3 Retrieval Prompt (implicit)

The Retriever simply embeds each sub-question; **metadata filter** on `pageId` used for iterative multi-hop chains (e.g., hop-2 filters to children of hop-1).^1

#### 6.2.4 Synthesis Prompt

```text
Context chunks (with [[source]] tags) are provided.
Answer the original user question **only** from context.
If context is insufficient, say so and recommend parent breadcrumb.
```

### 6.3 Python Helper – Query Decomposition, **Path Planning**, Multi-hop

```python
import os, json, itertools
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential

MAX_HOPS = int(os.getenv('MAX_HOPS', 3))                  # <- global limit
EDGE_TYPES = os.getenv('EDGE_TYPES', 'ParentOf,LinksTo')   # comma-sep
EDGE_TYPES = [e.strip() for e in EDGE_TYPES.split(',')]

openai_client = AzureOpenAI(
    azure_endpoint=os.environ['AOAI_ENDPOINT'],
    deployment=os.environ['AOAI_CHAT_DEPLOY'],
    api_version='2025-05-15'
)
search = SearchClient(os.environ['SEARCH_ENDPOINT'], os.environ['SEARCH_INDEX'], DefaultAzureCredential())

def analyse_query(q):
    resp = openai_client.chat.completions.create(
        messages=[{"role":"system","content":"You are QueryAnalyser"},
                  {"role":"user","content":q}],
        temperature=0
    )
    return json.loads(resp.choices[0].message.content)

# --- NEW ---

def plan_path(prev_page_id: str|None, hop_idx:int):
    """Returns metadata filter dict for Azure Search based on EDGE_TYPES and hop count."""
    if hop_idx == 0 or not prev_page_id:
        return {}
    if hop_idx >= MAX_HOPS:
        return {"truncate": True}  # Synthesiser will see this flag
    edge_filter = " or ".join([f"edgeType eq '{et}'" for et in EDGE_TYPES])
    return {
        "filter": f"(parentId eq '{prev_page_id}' and ({edge_filter}))"
    }

# Hybrid retrieval (vector + BM25) using Azure Search SDK

def hybrid_retrieve(sub_q, prev_page_id=None, hop_idx=0):
    extra_filter = plan_path(prev_page_id, hop_idx)
    if extra_filter.get("truncate"):
        return []
    vector = openai_client.embeddings.create(
        deployment=os.environ['AOAI_EMBED_DEPLOY'],
        input=[sub_q]
    ).data[0].embedding
    results = search.search(
        sub_q,
        search_mode="semanticHybrid",
        vector=dict(value=vector, k=15, fields="embedding"),
        filter=extra_filter.get("filter")
    )
    return [doc for doc in results]

def multi_hop(user_q):
    plan = analyse_query(user_q)
    subqs = plan.get('subquestions', [user_q])[:MAX_HOPS]
    all_chunks = []
    prev_page = None
    for hop_idx, sq in enumerate(subqs):
        docs = hybrid_retrieve(sq, prev_page, hop_idx)
        if not docs:
            break
        all_chunks.extend(docs)
        # pick the highest-score pageId to guide next hop
        prev_page = docs[0]['pageId']
    return synthesise(user_q, all_chunks)
```

### 6.4 Hallucination Guardrails

1. **Source completeness** `Synthesiser` must include at least one citation for every factual clause (cheap regex check).
2. **Verifier checklist** LLM prompt: *Does the draft answer claim things not present in [[source]]? If yes, flag.*
3. **Fallback** If verifier → `risk=true`, call `breadcrumb_parent(pageId)` and return summary + links only.

---

^1 Implemented by adding `parentId`/`childIds` metadata in vector docs and passing a filter like `parentId eq '{prevPageId}'` to Azure AI Search.

### 6.5 Deeper Prompt Strategies

Below are refined prompt designs for each agent role. Copy these verbatim into Copilot Studio prompt blocks or parameterise via environment variables.

| Role | Prompt Skeleton | Key Controls |
| ---- | --------------- | ------------ |
| **System (global)** | `You are ConfluenceRAG-Bot… {policy}. Answer only from provided sources. Cite [[src]]` | • Insert `{policy}` = short, org-approved disclaimer.<br>• Add `temperature=0`, `top_p=0.1` for determinism. |
| **QueryAnalyser** | ```Classify the user query into {Atomic \| NeedsDecomposition \| Clarification}. If decomposition, suggest ≤4 disjoint sub-questions covering the intent. JSON output only.``` | • Use `response_format = "json_object"` in Copilot.<br>• Add few-shot examples: classification edge cases. |
| **Decomposer** | `Break the question into ordered, minimally overlapping sub-questions solvable from documentation. Provide JSON: {"subquestions": [...], "ordered":true}` | • `temperature=0.2` to allow wording variance.<br>• Provide 2-3 chain-of-thought exemplars inside the *system* section but instruct model to hide thoughts (`DELIMITED`). |
| **Retriever (vector filter prompt)** | *implicit* – depends on Azure Search. | • Always pass `searchMode=semanticHybrid` & `speller=lexicon`.<br>• Vector K=15, BM25 K=25 before rerank. |
| **Reranker** | Azure semantic reranker v2. | • Set `cap=15`, use `logprobs` for thresholding. |
| **Synthesiser** | `Given QUESTION and CONTEXT [{chunkID: ... text ... }], create answer with bullet-proof citations (use [[chunkID]]). Do **not** invent info.` | • Add tool instruction: *If context coverage <70%, refuse with parent breadcrumb*. |
| **Verifier** | `Check ANSWER against CONTEXT. If any sentence lacks corroboration, output: {"risk":true, "reason":"…"}. Else {"risk":false}` | • `response_format=json_object`, `temperature=0`. |

### Few-Shot Example for QueryAnalyser

```jsonc
{"query":"How do I enable SSO?","classification":"Atomic"}
{"query":"What changed between v1 and v2 release?","classification":"NeedsDecomposition","subquestions":["What is new in v2?","What was removed from v1?"]}
```

### 6.6 API Layer Helpers – Reranking & Cosmos Graph

Below is a minimal Express-style TypeScript handler you can drop into the Web App's `/api/search.ts` route (or Copilot custom action) so the UI calls `/api/ask?q=…` and receives a fully reranked, graph-aware answer.

```typescript
import { SearchClient } from "@azure/search-documents";
import { DefaultAzureCredential } from "@azure/identity";
import { AzureKeyCredential, OpenAIClient } from "@azure/openai";
import gremlin from "gremlin";
import type { Request, Response } from "express";

// === Azure Search ===
const search = new SearchClient(
  process.env.SEARCH_ENDPOINT!,
  process.env.SEARCH_INDEX!,
  new DefaultAzureCredential()
);

// === Reranker (AOAI) ===
const openai = new OpenAIClient(
  process.env.AOAI_ENDPOINT!,
  new AzureKeyCredential(process.env.AOAI_KEY!)
);

// === Cosmos Gremlin ===
const g = new gremlin.driver.Client(
  `wss://${process.env.COSMOS_ACCOUNT}.gremlin.cosmos.azure.com:443/`,
  {
    authenticator: new gremlin.driver.auth.PlainTextSaslAuthenticator(
      `/dbs/${process.env.COSMOS_DB}/colls/${process.env.COSMOS_GRAPH}`,
      process.env.COSMOS_KEY!
    ),
    traversalSource: "g",
    rejectUnauthorized: true,
  }
);

// --- Helper: get breadcrumb for a pageId ---
async function breadcrumb(pageId: string) {
  const query = `g.V('${pageId}').repeat(out('ParentOf')).emit().values('title')`;
  const res = await g.submit(query);
  return res._items.reverse();
}

export async function ask(req: Request, res: Response) {
  const userQ = req.query.q as string;

  /* 1️⃣  Hybrid search */
  const vector = await openai.getEmbeddings("text-embedding-3-small", [userQ]);
  const hybrid = await search.search(userQ, {
    searchMode: "semanticHybrid",
    vector: { value: vector[0].embedding, k: 15, fields: "embedding" },
    top: 25,
  });
  const docs = await hybrid.nextPage();

  /* 2️⃣  Rerank (cross-encoder) */
  const rerankInput = docs.map((d) => ({ id: d.id, text: d.content }));
  const rerank = await openai.getRerankerRanking("semantic_reranker_v2", rerankInput, userQ);
  const topDocs = rerank.slice(0, 8); // cap 8 chunks

  /* 3️⃣  Breadcrumb & Graph context for top page */
  const topPageId = topDocs[0]?.pageId;
  const path = topPageId ? await breadcrumb(topPageId) : [];

  /* 4️⃣  Synthesis */
  const contextBlocks = topDocs
    .map((d, i) => `[[${d.id}]] ${d.text}`)
    .join("\n\n");
  const system =
    "You are ConfluenceRAG-Bot. Cite sources as [[id]]. Only use given context.";
  const chat = await openai.getChatCompletions(
    process.env.AOAI_CHAT_DEPLOY!,
    [{ role: "system", content: system },
     { role: "user", content: `${contextBlocks}\n\nQUESTION: ${userQ}` }],
    { temperature: 0.2 }
  );
  const answer = chat.choices[0].message.content;

  res.json({ answer, breadcrumb: path });
}
```

#### Points to Note

- **Reranker** is invoked via `getRerankerRanking` (REST under the hood). You can toggle model to `cross-encoder-v1` if available in your region.
- **Graph query** retrieves parent chain for breadcrumb display.
- The route reuses the existing **FREE AI Search** and **Serverless Cosmos DB**—no extra cost.

---

## 7. Copilot Wiring – Step-by-Step

Follow these instructions inside **Azure Copilot Studio**.

1. **Create New Copilot Project** → choose *Blank* template.
2. **Add Environment Variables**
   - SEARCH_ENDPOINT, SEARCH_INDEX
   - AOAI_ENDPOINT, AOAI_KEY, AOAI_EMBED_DEPLOY, AOAI_CHAT_DEPLOY.
3. **Drag Skill Blocks** in this order:
   1. **QueryAnalyser** (OpenAI GPT) – paste prompt; set JSON response.
   2. **Decomposer** (OpenAI GPT) – conditional on `QueryAnalyser.outputs.classification == "NeedsDecomposition"`.
   3. **Retriever** (Azure AI Search) – configure endpoint/index; map sub-question input.
   4. **Reranker** (OpenAI Rerank) – connect Search results.
   5. **Synthesiser** (OpenAI GPT) – feed top-N reranked chunks + user query.
   6. **Verifier** (OpenAI GPT) – feed Synthesiser answer + context.
4. **Branch Logic**
   *Add Decision Node* after Verifier:
   ```
   if Verifier.outputs.risk == true → Fallback Node
   else → Final Answer Node
   ```
5. **Fallback Node** (OpenAI GPT) – prompt: "Explain we're unsure; show parent breadcrumb. Don't hallucinate."
6. **Output Node** → Deliver either final answer or fallback.
7. **Parameters**
   *Confidence Threshold τ* – store in project settings, reference in Synthesiser.
8. **Test Harness** – Use Copilot's built-in chat; enable "Show tool logs" to inspect each hop.
9. **Publish** – Deploy to *Dev* channel first; hook into your Web App via REST endpoint.

**Diagram (quick view):**

```
User → QueryAnalyser ─┬─> Decomposer
                     └─> Retriever → Reranker → Synthesiser → Verifier ─┬──> Final ✓
                                                                         └──> Fallback (breadcrumb)
```

> **Tip** Track latency by enabling Application Insights telemetry for each cloud function; optimise K values if P99 > 2 s.

---

## 8. Next Steps

1. **Build Data Factory mapping flow** if you prefer managed pipelines.
2. Add **reranking** & **Cosmos Graph queries** inside the API layer that your React or Copilot UI calls.
3. Instrument with **Application Insights**.

This repo is now a fully scripted starting point – replace the placeholders, deploy, and iterate.
