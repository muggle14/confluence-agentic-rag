#futureReads.md

Of course. This is an excellent question that gets to the heart
  of why this architecture is so powerful. The plan isn't just
  about indexing the data; it's about how you leverage the merged
  data at query time.


  Here is a detailed plan for how the system will use both the blob
   (content) and Cosmos DB (graph metrics) data, with specifics on
  single-call and two-call retrieval patterns.

  The Core Principle: The Enriched Index

  First, it's crucial to remember that the indexing pipeline has
  already done the hard work. A single document in your Azure AI
  Search index (confluence-graph-embeddings-v2) now contains fields
   from both sources:


   * From Blob Storage: page_id, title, content, chunks, url, etc.
   * From Cosmos DB (via the enrichment skill): parent_page_id,
     hierarchy_depth, childrenIds, adjacentIds,
     graph_centrality_score.

  This unified document is the key. The retrieval plan is about how
   intelligently we can query these combined fields.

  ---

  The Unified Retrieval Plan

  The system will employ two distinct retrieval strategies, chosen
  by the ConfluenceQAOrchestrator based on its analysis of the
  user's query.


   1. Single-Call Retrieval (The Workhorse): For fast, direct,
      fact-based questions. This is the default and most common
      path.
   2. Two-Call / Multi-Call Retrieval (The Analyst): For complex,
      multi-hop, or contextual questions that require traversing
      the knowledge graph.


  ---

  1. Single-Call Retrieval

  This pattern answers a user's query with a single,
  highly-optimized query to the Azure AI Search index.

  When is it used?


  This is for "atomic" queries where the answer is likely contained
   within a single document or a few closely related document
  chunks. The Query Analyser Agent would classify the user's
  question as "Atomic".


  Examples:
   * "How do I enable SSO for our application?"
   * "What is the default timeout for the payment service?"
   * "Get me the document about the 2024 security audit."

  How the Search is Generated (The Single Call):

  The orchestrator constructs a single, sophisticated hybrid search
   query. This is not just a simple text search; it leverages the
  enriched index to its full potential.

  The API call to Azure AI Search will include:


   1. Vector Query: The user's query ("How do I enable SSO?") is
      converted into a vector embedding. This vector is used to
      find the most semantically similar document chunks by
      searching the contentVector field.
   2. Keyword Search: The original query text is also used for a
      traditional keyword search against fields like title and
      content. This catches important keywords that vector search
      might miss.
   3. Scoring Profile (Leveraging Graph Data): This is a critical
      use of the Cosmos DB data. A scoring profile is configured in
      the index to boost the search score of documents based on the
      graph_centrality_score. This means that if two documents are
      equally relevant based on their content, the one that is more
      "central" or important in the knowledge graph will rank
      higher.
   4. Semantic Reranking: The top ~50 results from the hybrid
      search are then passed to Azure's semantic reranker, which
      uses a more advanced language model to re-order the results
      for the highest possible relevance, providing a caption that
      helps explain why each result is relevant.

  Output of the Single Call:


  The result is a highly relevant, ranked list of document chunks
  that best answer the user's question. Each result includes the
  content, title, URL, and all the associated graph metadata
  (parent_page_id, childrenIds, etc.), which can be used to display
   breadcrumbs or related links in the UI.

  ---


  2. Two-Call / Multi-Call Retrieval

  This is a more advanced, agentic pattern for complex questions.
  It uses an initial search call to find a starting point and a
  second (or third) call to traverse the graph and gather more
  context.

  When is it used?


  This is for queries that the Query Analyser Agent classifies as
  "NeedsDecomposition" or that imply a need for hierarchy or
  relationships.


  Examples:
   * "What were the key architectural changes between v1 and v2 of
     the API, and how did that affect the security module?"
     (Requires finding multiple documents and understanding their
     relationship).
   * "Show me the page hierarchy for the 'Data Processing'
     section."
   * "Find the main deployment guide and then locate its child
     pages related to troubleshooting."

  The Overall Pattern:

  This is an orchestrated workflow managed by the
  ConfluenceQAOrchestrator.


  Call 1: Initial Retrieval (Finding the "Seed")


   * What's done: This first call is nearly identical to the
     single-call retrieval described above. The system sends a
     hybrid search query to get the best possible starting points.
   * Goal: To find the most relevant "seed" documents. For the
     query "Find the main deployment guide...", this call would
     ideally return the main deployment guide document as the top
     result.

  The "Thinking" Step (In-Memory Analysis)


   * This is not an API call. The orchestrator's Path Planner Agent
     analyzes the results from Call 1.
   * It inspects the enriched fields of the top results. For the
     main deployment guide, it would look at the childrenIds field
     and see a list of page IDs for its child pages.

  Call 2: Graph Traversal (Expanding the Context)


   * What's done: The orchestrator now makes a second, targeted call
      to gather more information. This call can take one of two
     forms:
       1. A Refined Search Query: The agent constructs a new query
          for the Azure AI Search index, but this time it uses a
          filter. Using the childrenIds it found in the "thinking"
          step, it sends a query like:
           * Query: * (search for everything)
           * Filter: search.in(page_id, 'id1,id2,id3,...')
           * This query translates to: "Fetch me the full documents 
             for all the child pages I just discovered."
       2. A Direct Graph Query: In some cases, the agent might need
          more complex relationship data. It could make a direct
          Gremlin query to the Cosmos DB instance to ask questions
          like, "Find all pages that are two hops away from this
          page and have a 'LinksTo' relationship."

  Final Step: Synthesis


   * The Synthesiser Agent now has the results from both Call 1
     (the seed document) and Call 2 (the related documents).
   * It uses the combined information from this rich context to
     generate a comprehensive answer that addresses all parts of
     the user's complex query. For example, it would list the main
     deployment guide and then summarize the troubleshooting
     information from the child pages it retrieved in the second
     call.

  Summary Table



  ┌─────┬───────────────────┬────────────────────────────┐
  │ Fea │ Single-Call Re... │ Two-Call / Multi-Call R... │
  ├─────┼───────────────────┼────────────────────────────┤
  │ **T │ Simple, "atomi... │ Complex, multi-hop, or ... │
  │ **G │ Find the singl... │ Explore relationships a... │
  │ **C │ Hybrid search ... │ Hybrid search to find t... │
  │ **C │ (Does not exist)  │ **Filtered search** on ... │
  │ **D │ All enriched f... │ All enriched fields, es... │
  │ **O │ Minimal. A sin... │ Heavy. An agentic workf... │
  │ **R │ A ranked list ... │ A synthesized answer co... │
  └─────┴───────────────────┴────────────────────────────┘

