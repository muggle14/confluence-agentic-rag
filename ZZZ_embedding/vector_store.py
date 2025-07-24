"""
Azure AI Search Vector Store for Confluence embeddings.
Handles indexing and searching of vector embeddings with multi-vector field support.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime

from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, VectorSearch,
    HnswAlgorithmConfiguration, VectorSearchProfile, 
    SemanticConfiguration, SemanticPrioritizedFields, SemanticField,
    SemanticSearch, SearchableField, SimpleField
)
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
import numpy as np

from .config import EmbeddingConfig
from .models import EmbeddingChunk, RetrievalResult, ChunkType, ProcessingStats

logger = logging.getLogger(__name__)

class ConfluenceVectorStore:
    """Handles vector storage and retrieval using Azure AI Search."""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.credential = AzureKeyCredential(config.search_key)
        
        # Initialize clients
        self.search_client = SearchClient(
            endpoint=config.search_endpoint,
            index_name=config.search_index_name,
            credential=self.credential
        )
        
        self.index_client = SearchIndexClient(
            endpoint=config.search_endpoint,
            credential=self.credential
        )
        
        self.stats = ProcessingStats()
    
    async def create_index(self, force_recreate: bool = False) -> bool:
        """
        Create the search index with proper schema for multi-vector fields.
        
        Args:
            force_recreate: Whether to delete and recreate existing index
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Creating search index: {self.config.search_index_name}")
            
            # Check if index exists
            index_exists = False
            try:
                await self.index_client.get_index(self.config.search_index_name)
                index_exists = True
                logger.info("Index already exists")
            except:
                logger.info("Index does not exist, will create new")
            
            if index_exists and not force_recreate:
                logger.info("Index exists and force_recreate=False, skipping creation")
                return True
            
            if index_exists and force_recreate:
                logger.info("Deleting existing index for recreation")
                await self.index_client.delete_index(self.config.search_index_name)
                await asyncio.sleep(2)  # Wait for deletion to complete
            
            # Define the index schema
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SimpleField(name="page_id", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="chunk_type", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
                SearchableField(name="title", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
                SimpleField(name="space_key", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="breadcrumb", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
                
                # Vector fields for different content types
                SearchField(
                    name="content_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=self.config.embedding_dimension,
                    vector_search_profile_name="content-profile"
                ),
                SearchField(
                    name="title_vector", 
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=self.config.embedding_dimension,
                    vector_search_profile_name="title-profile"
                ),
                
                # Metadata fields
                SimpleField(name="created_at", type=SearchFieldDataType.DateTimeOffset),
                SimpleField(name="updated_at", type=SearchFieldDataType.DateTimeOffset),
                SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
                SimpleField(name="total_chunks", type=SearchFieldDataType.Int32),
                SearchableField(name="metadata", type=SearchFieldDataType.String),
            ]
            
            # Configure vector search
            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(name="hnsw-algorithm")
                ],
                profiles=[
                    VectorSearchProfile(
                        name="content-profile",
                        algorithm_configuration_name="hnsw-algorithm"
                    ),
                    VectorSearchProfile(
                        name="title-profile", 
                        algorithm_configuration_name="hnsw-algorithm"
                    )
                ]
            )
            
            # Configure semantic search
            semantic_search = SemanticSearch(
                configurations=[
                    SemanticConfiguration(
                        name="confluence-semantic-config",
                        prioritized_fields=SemanticPrioritizedFields(
                            title_field=SemanticField(field_name="title"),
                            content_fields=[
                                SemanticField(field_name="content")
                            ]
                        )
                    )
                ]
            )
            
            # Create the index
            index = SearchIndex(
                name=self.config.search_index_name,
                fields=fields,
                vector_search=vector_search,
                semantic_search=semantic_search
            )
            
            await self.index_client.create_index(index)
            logger.info(f"Successfully created index: {self.config.search_index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False
    
    async def index_chunks(self, chunks: List[EmbeddingChunk]) -> Tuple[int, int]:
        """
        Index a batch of chunks into the search index.
        
        Args:
            chunks: List of EmbeddingChunk objects with embeddings
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        if not chunks:
            return 0, 0
        
        logger.info(f"Indexing {len(chunks)} chunks")
        self.stats.start()
        
        documents = []
        for chunk in chunks:
            try:
                doc = self._chunk_to_document(chunk)
                documents.append(doc)
            except Exception as e:
                logger.error(f"Failed to convert chunk {chunk.id} to document: {e}")
                continue
        
        if not documents:
            logger.warning("No valid documents to index")
            return 0, len(chunks)
        
        try:
            # Upload documents in batches
            batch_size = 100  # Azure AI Search recommended batch size
            successful = 0
            failed = 0
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                logger.debug(f"Uploading batch {i//batch_size + 1} with {len(batch)} documents")
                
                try:
                    result = await self.search_client.upload_documents(documents=batch)
                    
                    # Count results
                    for item in result:
                        if item.succeeded:
                            successful += 1
                        else:
                            failed += 1
                            logger.error(f"Failed to index document {item.key}: {item.error_message}")
                            
                except Exception as e:
                    logger.error(f"Failed to upload batch: {e}")
                    failed += len(batch)
            
            self.stats.end()
            self.stats.chunks_indexed = successful
            self.stats.errors = failed
            
            logger.info(f"Indexing completed. Success: {successful}, Failed: {failed}")
            return successful, failed
            
        except Exception as e:
            logger.error(f"Failed to index chunks: {e}")
            return 0, len(chunks)
    
    def _chunk_to_document(self, chunk: EmbeddingChunk) -> Dict[str, Any]:
        """Convert an EmbeddingChunk to a search document."""
        
        # Determine which vector field to populate based on chunk type
        content_vector = None
        title_vector = None  
        
        if chunk.chunk_type in [ChunkType.BODY, ChunkType.PAGE_SUMMARY, ChunkType.TABLE]:
            content_vector = chunk.embedding
        elif chunk.chunk_type in [ChunkType.TITLE, ChunkType.SECTION_HEADER]:
            title_vector = chunk.embedding
        else:
            # Default to content vector
            content_vector = chunk.embedding
        
        doc = {
            "id": chunk.id,
            "page_id": chunk.page_id,
            "chunk_type": chunk.chunk_type.value,
            "content": chunk.content,
            "title": chunk.metadata.get('title', ''),
            "space_key": chunk.metadata.get('space_key', ''),
            "breadcrumb": chunk.metadata.get('breadcrumb', []),
            "created_at": chunk.metadata.get('created_at', datetime.utcnow().isoformat()),
            "updated_at": datetime.utcnow().isoformat(),
            "chunk_index": chunk.metadata.get('chunk_index', 0),
            "total_chunks": chunk.metadata.get('total_chunks', 1),
            "metadata": json.dumps(chunk.metadata),
        }
        
        # Add vector fields
        if content_vector:
            doc["content_vector"] = content_vector
        if title_vector:
            doc["title_vector"] = title_vector
        
        return doc
    
    async def search(self, 
                    query_text: str,
                    query_vector: Optional[List[float]] = None,
                    vector_fields: List[str] = None,
                    filters: Optional[str] = None,
                    top_k: int = None,
                    use_semantic_ranker: bool = True) -> List[RetrievalResult]:
        """
        Perform hybrid search combining text and vector search.
        
        Args:
            query_text: Text query for BM25 search
            query_vector: Vector for similarity search
            vector_fields: Which vector fields to search (content_vector, title_vector)
            filters: OData filter string
            top_k: Number of results to return
            use_semantic_ranker: Whether to use semantic ranker
            
        Returns:
            List of RetrievalResult objects
        """
        if top_k is None:
            top_k = self.config.top_k
            
        if vector_fields is None:
            vector_fields = ["content_vector", "title_vector"]
        
        try:
            # Prepare vector queries
            vector_queries = []
            if query_vector:
                for field in vector_fields:
                    vector_queries.append(
                        VectorizedQuery(
                            vector=query_vector, 
                            k_nearest_neighbors=top_k,
                            fields=field
                        )
                    )
            
            # Configure search parameters
            search_params = {
                "search_text": query_text,
                "top": top_k,
                "vector_queries": vector_queries if vector_queries else None,
                "filter": filters,
                "select": [
                    "id", "page_id", "chunk_type", "content", "title", 
                    "space_key", "breadcrumb", "chunk_index", "metadata"
                ]
            }
            
            # Add semantic configuration if enabled
            if use_semantic_ranker:
                search_params.update({
                    "query_type": "semantic",
                    "semantic_configuration_name": "confluence-semantic-config",
                    "query_caption": "extractive",
                    "query_answer": "extractive"
                })
            
            # Perform search
            results = await self.search_client.search(**search_params)
            
            # Convert to RetrievalResult objects
            retrieval_results = []
            async for result in results:
                try:
                    retrieval_result = self._document_to_result(result)
                    retrieval_results.append(retrieval_result)
                except Exception as e:
                    logger.error(f"Failed to convert search result: {e}")
                    continue
            
            logger.debug(f"Search returned {len(retrieval_results)} results")
            return retrieval_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def _document_to_result(self, doc: Dict[str, Any]) -> RetrievalResult:
        """Convert a search document to a RetrievalResult."""
        
        # Parse metadata
        metadata = {}
        if doc.get('metadata'):
            try:
                metadata = json.loads(doc['metadata'])
            except:
                pass
        
        return RetrievalResult(
            chunk_id=doc['id'],
            page_id=doc['page_id'],
            content=doc['content'],
            score=doc.get('@search.score', 0.0),
            chunk_type=ChunkType(doc['chunk_type']),
            metadata=metadata,
            breadcrumb=doc.get('breadcrumb', [])
        )
    
    async def get_chunks_by_page(self, page_id: str) -> List[RetrievalResult]:
        """Get all chunks for a specific page."""
        filter_expr = f"page_id eq '{page_id}'"
        return await self.search(
            query_text="*",
            filters=filter_expr,
            use_semantic_ranker=False,
            top_k=1000  # Get all chunks for the page
        )
    
    async def close(self):
        """Close the search clients."""
        await self.search_client.close()
        await self.index_client.close()

async def create_vector_store(config: EmbeddingConfig) -> ConfluenceVectorStore:
    """
    Factory function to create and initialize a vector store.
    
    Args:
        config: Embedding configuration
        
    Returns:
        Initialized vector store instance
    """
    vector_store = ConfluenceVectorStore(config)
    
    # Create index if it doesn't exist
    await vector_store.create_index(force_recreate=False)
    
    return vector_store
