#!/usr/bin/env python3
"""Test chunk indexing with a single document."""

import json
import hashlib
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

# Configuration
SEARCH_ENDPOINT = "https://srch-rag-conf.search.windows.net"
SEARCH_KEY = "qLxEs0dPsL2lmCul6AHaiicNRMRBpvFQWsjvjTqTyHAzSeBx7u8Q"
AZURE_OPENAI_ENDPOINT = "https://aoai-rag-confluence.openai.azure.com/"
AZURE_OPENAI_KEY = "2N8xjmhO6M6kE6MO8Opa6KRXMvdyuzvJoJ3kqCJQDdfBaFM1qlz2JQQJ99BGACYeBjFXJ3w3AAABACOGXqVW"

# Initialize clients
search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name="confluence-chunks",
    credential=AzureKeyCredential(SEARCH_KEY)
)

# Azure OpenAI client
openai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
    api_version="2023-05-15"
)

# Test data
test_chunks = [
    {
        "chunk_id": "test_doc_1_chunk_0",
        "parent_id": "test_doc_1",
        "page_id": "test_doc_1",
        "chunk_index": 0,
        "chunk_text": "This is the first chunk of test content about SynthTrace. SynthTrace is a powerful monitoring tool.",
        "parent_title": "Test Document about SynthTrace",
        "space_key": "TEST",
        "metadata": json.dumps({"total_chunks": 2, "chunk_position": "1/2"})
    },
    {
        "chunk_id": "test_doc_1_chunk_1",
        "parent_id": "test_doc_1",
        "page_id": "test_doc_1",
        "chunk_index": 1,
        "chunk_text": "This is the second chunk. It contains information about SynthTrace pricing and features.",
        "parent_title": "Test Document about SynthTrace",
        "space_key": "TEST",
        "metadata": json.dumps({"total_chunks": 2, "chunk_position": "2/2"})
    }
]

print("Generating embeddings...")
for chunk in test_chunks:
    response = openai_client.embeddings.create(
        input=chunk["chunk_text"],
        model="text-embedding-ada-002"
    )
    chunk["chunk_embedding"] = response.data[0].embedding

print("Uploading chunks to index...")
result = search_client.upload_documents(documents=test_chunks)
print(f"Upload result: {result}")

print("\nSearching for 'SynthTrace'...")
results = search_client.search(
    search_text="SynthTrace",
    select=["chunk_id", "parent_title", "chunk_text"],
    top=3
)

for result in results:
    print(f"\nChunk ID: {result['chunk_id']}")
    print(f"Title: {result['parent_title']}")
    print(f"Text: {result['chunk_text'][:100]}...")