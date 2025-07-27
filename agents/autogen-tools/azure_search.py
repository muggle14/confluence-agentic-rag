from __future__ import annotations
import os, json
from typing import List, Dict

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.openai import AzureOpenAIEmbeddings   # Use Azure-specific package


# -------------------- constants --------------------
INDEX_NAME  = os.getenv("AZURE_SEARCH_INDEX_NAME", "confluence-docs")
EMBED_DEPLOY = os.getenv("AOAI_EMBED_DEPLOY")
VECTOR_FIELD = "contentVector"
TEXT_FIELD   = "content"


# -------------------- class ------------------------
class AzureAISearchTool:
    """
    Hybrid (vector + semantic + keyword) search tool usable by Autogen agents.
    """

    def __init__(
        self,
        endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT"),
        key: str = os.getenv("AZURE_SEARCH_KEY"),
    ):
        self._client = SearchClient(endpoint, INDEX_NAME, AzureKeyCredential(key))
        self._embed  = AzureOpenAIEmbeddings(deployment_name=EMBED_DEPLOY)

    # ---------- core --------------------------------
    def __call__(self, query: str, k: int = 8) -> str:
        hits = self.raw_results(query, top=k)
        return "\n\n".join(self._format(hit) for hit in hits)

    # ---------- helpers -----------------------------
    def raw_results(self, query: str, *, top: int = 3) -> List[Dict]:
        q_vec = self._embed.embed_query(query)
        return list(self._client.search(
            search_text=query,
            vector=q_vec,
            vector_fields=VECTOR_FIELD,
            top=top,
            select=[TEXT_FIELD, "title", "url",
                    "parent_page_id", "children_ids", "adjacent_ids",
                    "graph_centrality_score"]
        ))

    def by_ids(self, ids: List[str]) -> List[Dict]:
        docs = []
        for _id in ids:
            try:
                docs.append(self._client.get_document(key=_id))
            except Exception:
                continue
        return docs

    # ---------- private -----------------------------
    @staticmethod
    def _format(hit: Dict) -> str:
        preview = hit[TEXT_FIELD][:500].replace("\n", " ")
        return f"**{hit['title']}** (id:{hit['id']})\n{preview}…"