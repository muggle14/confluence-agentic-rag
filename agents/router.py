"""
confluence_qa.agents.router
---------------------------
• Defines the Autogen message-router rule  "search-with-neighbours".
• Instantiates the shared AzureAISearchTool.
• Provides build_agent() → returns a QAAgent pre-wired with logging + graph feedback.
"""

from __future__ import annotations
import autogen
from autogen import Message
from typing import List
import logging

# ---------- local imports ----------
from autogen_tools.azure_search import AzureAISearchTool
from autogen_tools.neighbor_from_doc import extract_neighbor_ids, fetch_neighbor_docs
from autogen_tools.graph_feedback import upsert_edge

# ---------- logger ----------
log = logging.getLogger("confluence-qa.router")

# ---------- search tool (singleton) ----------
_search = AzureAISearchTool()

# ---------- router rule ----------
@autogen.message_router.route("search-with-neighbours")
async def search_with_neighbours(msg: Message) -> Message:
    """
    1. Run hybrid search against Azure AI Search.
    2. Pull neighbour docs via their IDs already stored in the main hit.
    3. Return a system-message containing main hit + neighbour snippets.
    """
    search_results: List[dict] = _search.raw_results(msg.content, top=1)
    if not search_results:
        return Message(role="system", content="🛈 No documents found.")

    main_document = search_results[0]
    neighbor_page_ids = extract_neighbor_ids(main_document)  
    neighbor_documents = _search.by_ids(neighbor_page_ids)

    # ---------- craft context ----------
    context_parts = [
        "# Main document\n",
        main_document["content"][:800],
        "\n\n# Neighbours"
    ] + [
        f"- **{doc['title']}**\n{doc['content'][:400]}"
        for doc in neighbor_documents
    ]

    log.info(f"Router: {len(neighbor_documents)} neighbours added") 

    return Message(role="system", content="\n\n".join(context_parts))


# ---------- custom QA agent ----------
class QAAgent(autogen.Agent):
    """
    • Logs every tool call start/end to Cosmos DB.
    • Writes `DependsOn` edges when it spawns sub-questions.
    """

    async def on_tool_start(self, tool_name: str, args):
        log.info(f"{self.name}: Starting tool {tool_name} with args {args}")

    async def on_tool_end(self, tool_name: str, result):
        log.info(f"{self.name}: Tool {tool_name} completed with result: {str(result)[:500]}")

    async def on_new_subquestion(self, parent_question: str, child_question: str):
        upsert_edge(parent_question, child_question)
        log.info(f"{self.name}: Spawned sub-question: {parent_question} -> {child_question}")


# ---------- factory ----------
def build_agent() -> QAAgent:
    """
    Returns a ready-to-use QAAgent instance.
    Import and reuse this across Azure Function endpoints to avoid cold-start spin-up.
    """
    return QAAgent(config_path=None)


# ---------- eager instance (optional, keeps global warm) ----------
agent = build_agent()

# how to use the agent
# --------------------------------------------------------------
# from agents.router import agent   # single shared instance
# answer = await agent.ask("How do I reset my VPN token?")
# --------------------------------------------------------------