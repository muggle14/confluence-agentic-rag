"""
Confluence Q&A Embedding Layer
Production-ready embedding system for Confluence content
"""

__version__ = "1.0.0"
__author__ = "Confluence Q&A Team"

from .config import EmbeddingConfig
from .models import (
    EmbeddingChunk, RetrievalResult, PageContext, ChunkType, 
    SearchRequest, SearchResponse, ProcessingStats
)
from .chunker import ConfluenceChunker
from .embedder import ConfluenceEmbedder, create_embedder
from .vector_store import ConfluenceVectorStore, create_vector_store
from .retriever import ConfluenceRetriever, create_retriever
from .graph_enricher import GraphEnricher, create_graph_enricher

__all__ = [
    # Configuration
    'EmbeddingConfig',
    
    # Data Models
    'EmbeddingChunk',
    'RetrievalResult', 
    'PageContext',
    'ChunkType',
    'SearchRequest',
    'SearchResponse', 
    'ProcessingStats',
    
    # Core Components
    'ConfluenceChunker',
    'ConfluenceEmbedder',
    'ConfluenceVectorStore',
    'ConfluenceRetriever',
    'GraphEnricher',
    
    # Factory Functions
    'create_embedder',
    'create_vector_store',
    'create_retriever',
    'create_graph_enricher'
] 