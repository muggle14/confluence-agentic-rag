#!/usr/bin/env python3
"""
Direct chunking solution for Confluence documents.
This script reads documents, chunks them, and indexes each chunk as a separate document.
"""

import os
import json
import hashlib
from typing import List, Dict, Any
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
import openai
from openai import AzureOpenAI

# Configuration
STORAGE_CONNECTION = os.environ.get('STORAGE_CONNECTION', 'DefaultEndpointsProtocol=https;EndpointSuffix=core.windows.net;AccountName=stgragconf;AccountKey=K8X0N3AIJzielxnRpaTunSNIpSJMX+JIaoos9TZ/n8xfGjLhrDlandoIaZx3AImt/+Zv064pPxnc+AStaZeweQ==;BlobEndpoint=https://stgragconf.blob.core.windows.net/;FileEndpoint=https://stgragconf.file.core.windows.net/;QueueEndpoint=https://stgragconf.queue.core.windows.net/;TableEndpoint=https://stgragconf.table.core.windows.net/')
SEARCH_ENDPOINT = "https://srch-rag-conf.search.windows.net"
SEARCH_KEY = "qLxEs0dPsL2lmCul6AHaiicNRMRBpvFQWsjvjTqTyHAzSeBx7u8Q"
AZURE_OPENAI_ENDPOINT = "https://aoai-rag-confluence.openai.azure.com/"
AZURE_OPENAI_KEY = "2N8xjmhO6M6kE6MO8Opa6KRXMvdyuzvJoJ3kqCJQDdfBaFM1qlz2JQQJ99BGACYeBjFXJ3w3AAABACOGXqVW"

# Initialize clients
blob_service = BlobServiceClient.from_connection_string(STORAGE_CONNECTION)
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

def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
        
    return chunks

def generate_embedding(text: str) -> List[float]:
    """Generate embedding using Azure OpenAI."""
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

def process_document(doc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process a single document into chunks."""
    doc_id = doc_data.get('id', '')
    title = doc_data.get('title', '')
    content = doc_data.get('body', {}).get('storage', {}).get('value', '')
    space_key = doc_data.get('space', {}).get('key', '')
    
    # Remove HTML tags (simple approach)
    import re
    clean_content = re.sub('<.*?>', '', content)
    
    # Chunk the content
    chunks = chunk_text(clean_content)
    
    # Create chunk documents
    chunk_docs = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk_{i}"
        
        # Generate embedding
        embedding = generate_embedding(chunk)
        
        chunk_doc = {
            "chunk_id": chunk_id,
            "parent_id": doc_id,
            "page_id": doc_id,
            "chunk_index": i,
            "chunk_text": chunk,
            "parent_title": title,
            "space_key": space_key,
            "chunk_embedding": embedding,
            "metadata": json.dumps({
                "total_chunks": len(chunks),
                "chunk_position": f"{i+1}/{len(chunks)}"
            })
        }
        chunk_docs.append(chunk_doc)
    
    return chunk_docs

def main():
    """Main processing function."""
    # Get container client
    container_client = blob_service.get_container_client("confluence-data")
    
    # List all JSON files in raw folder
    blobs = container_client.list_blobs(name_starts_with="raw/")
    
    all_chunks = []
    
    for blob in blobs:
        if blob.name.endswith('.json'):
            print(f"Processing {blob.name}...")
            
            # Download blob
            blob_client = container_client.get_blob_client(blob.name)
            content = blob_client.download_blob().readall()
            
            # Parse JSON
            doc_data = json.loads(content)
            
            # Process into chunks
            chunks = process_document(doc_data)
            all_chunks.extend(chunks)
            
            print(f"  Created {len(chunks)} chunks")
    
    # Upload chunks to search index
    print(f"\nUploading {len(all_chunks)} chunks to search index...")
    
    # Upload in batches
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i+batch_size]
        result = search_client.upload_documents(documents=batch)
        print(f"  Uploaded batch {i//batch_size + 1}")
    
    print("Done!")

if __name__ == "__main__":
    main()