"""
Small helper for CRUD on the `conversations` container in Cosmos DB.
Each message = separate document → cheap range queries by conversation_id.
"""
from __future__ import annotations
import os, uuid, datetime
from typing import List, Dict, Any
from azure.cosmos import CosmosClient, exceptions

_cosmos = CosmosClient(os.getenv("COSMOS_DB_ENDPOINT"),
                       os.getenv("COSMOS_DB_KEY"))
_db  = _cosmos.get_database_client(os.getenv("COSMOS_DB_DATABASE_NAME", "ConfluenceQA"))
_convs = _db.get_container_client(os.getenv("COSMOS_DB_CONVERSATIONS_CONTAINER", "conversations"))

def append_msg(convo_id: str, *, role: str, content: str) -> None:
    _convs.upsert_item({
        "id": str(uuid.uuid4()),
        "conversation_id": convo_id,
        "role": role,
        "content": content,
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "deleted": False,
    })

def fetch_conversation(convo_id: str) -> List[Dict[str, Any]]:
    query = "SELECT * FROM c WHERE c.conversation_id=@cid AND c.deleted=false ORDER BY c.ts"
    return list(_convs.query_items(
        query=query,
        parameters=[{"name": "@cid", "value": convo_id}],
        enable_cross_partition_query=True
    ))

def soft_delete_conversation(convo_id: str) -> None:
    for doc in fetch_conversation(convo_id):
        doc["deleted"] = True
        _convs.upsert_item(doc)