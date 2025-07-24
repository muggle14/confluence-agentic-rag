#!/usr/bin/env python3
"""
Generate OpenAI embeddings for search queries
This script helps create embeddings for queries to use with vector search
"""

import os
import sys
import json
import openai
from typing import List

def generate_query_embedding(query: str, api_key: str = None) -> List[float]:
    """
    Generate embedding for a search query using OpenAI API
    
    Args:
        query: The search query text
        api_key: OpenAI API key (uses env var if not provided)
        
    Returns:
        List of embedding values
    """
    # Set API key
    if api_key:
        openai.api_key = api_key
    else:
        openai.api_key = os.environ.get("OPENAI_API_KEY")
        
    if not openai.api_key:
        raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
    
    try:
        # Generate embedding
        response = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=query
        )
        
        # Extract embedding vector
        embedding = response['data'][0]['embedding']
        return embedding
        
    except Exception as e:
        print(f"Error generating embedding: {e}", file=sys.stderr)
        return None

def create_vector_search_query(query: str, embedding: List[float], k: int = 5) -> dict:
    """
    Create a vector search query for Azure AI Search
    
    Args:
        query: The search query text
        embedding: The query embedding vector
        k: Number of results to return
        
    Returns:
        Dict containing the search query structure
    """
    return {
        "search": query,
        "vectors": [
            {
                "value": embedding,
                "k": k,
                "fields": "contentVector,titleVector"
            }
        ],
        "select": "title,content,space_key,hierarchy_path,graph_centrality_score",
        "top": k
    }

def main():
    """Main function to handle command line usage"""
    if len(sys.argv) < 2:
        print("Usage: python generate-openai-query-embedding.py \"your search query\"")
        print("\nThis will generate an embedding and output a complete search query JSON.")
        sys.exit(1)
    
    query = sys.argv[1]
    
    # Generate embedding
    print(f"Generating embedding for query: '{query}'...", file=sys.stderr)
    embedding = generate_query_embedding(query)
    
    if embedding:
        # Create search query
        search_query = create_vector_search_query(query, embedding)
        
        # Output JSON
        print(json.dumps(search_query, indent=2))
        
        # Also print curl command to stderr for convenience
        print("\nExample curl command:", file=sys.stderr)
        print(f"curl -X POST 'https://YOUR-SEARCH-SERVICE.search.windows.net/indexes/YOUR-INDEX/docs/search?api-version=2023-11-01' \\", file=sys.stderr)
        print("  -H 'api-key: YOUR-SEARCH-KEY' \\", file=sys.stderr)
        print("  -H 'Content-Type: application/json' \\", file=sys.stderr)
        print(f"  -d '{json.dumps(search_query)}'", file=sys.stderr)
    else:
        print("Failed to generate embedding", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()