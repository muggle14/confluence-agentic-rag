"""
Azure OpenAI Embedder for Confluence content.
Handles embedding generation with batch processing and retry logic.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from openai import AsyncAzureOpenAI
from azure.core.exceptions import AzureError
import tiktoken

from .config import EmbeddingConfig
from .models import EmbeddingChunk, ChunkType, ProcessingStats

logger = logging.getLogger(__name__)

class ConfluenceEmbedder:
    """Handles embedding generation for Confluence content using Azure OpenAI."""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.client = AsyncAzureOpenAI(
            api_key=config.aoai_key,
            api_version=config.azure_openai_api_version,
            azure_endpoint=config.aoai_endpoint
        )
        self.encoding = tiktoken.encoding_for_model("text-embedding-3-large")
        self.stats = ProcessingStats()
        
    async def embed_chunks(self, chunks: List[EmbeddingChunk]) -> List[EmbeddingChunk]:
        """
        Generate embeddings for a list of chunks with batch processing.
        
        Args:
            chunks: List of EmbeddingChunk objects
            
        Returns:
            List of chunks with embeddings populated
        """
        if not chunks:
            return []
            
        logger.info(f"Starting embedding generation for {len(chunks)} chunks")
        self.stats.total_chunks = len(chunks)
        self.stats.start()  # Use the start() method instead
        
        # Process in batches
        batch_size = self.config.batch_size
        embedded_chunks = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_result = await self._process_batch(batch, i // batch_size + 1)
            embedded_chunks.extend(batch_result)
            
            # Add delay between batches to respect rate limits
            if i + batch_size < len(chunks):
                await asyncio.sleep(self.config.batch_delay)
        
        self.stats.end()  # Use the end() method instead
        self.stats.embedding_time = self.stats.duration or 0.0
        self.stats.successful_chunks = len([c for c in embedded_chunks if c.embedding is not None])
        self.stats.failed_chunks = len([c for c in embedded_chunks if c.embedding is None])
        
        logger.info(f"Embedding generation completed. Success: {self.stats.successful_chunks}, Failed: {self.stats.failed_chunks}")
        return embedded_chunks
    
    async def _process_batch(self, chunks: List[EmbeddingChunk], batch_num: int) -> List[EmbeddingChunk]:
        """Process a single batch of chunks."""
        logger.debug(f"Processing batch {batch_num} with {len(chunks)} chunks")
        
        # Prepare texts for embedding
        texts = []
        for chunk in chunks:
            # Combine different content types with appropriate weighting
            text_parts = []
            
            # Get title from metadata if available
            if chunk.metadata.get('title'):
                text_parts.append(f"Title: {chunk.metadata['title']}")
            
            if chunk.content:
                text_parts.append(f"Content: {chunk.content}")
                
            if chunk.metadata.get('table_data'):
                text_parts.append(f"Table: {chunk.metadata['table_data']}")
                
            if chunk.metadata.get('image_alt'):
                text_parts.append(f"Image: {chunk.metadata['image_alt']}")
            
            combined_text = " | ".join(text_parts)
            
            # Truncate if too long
            if self._count_tokens(combined_text) > self.config.max_tokens:
                combined_text = self._truncate_text(combined_text, self.config.max_tokens)
            
            texts.append(combined_text)
        
        # Generate embeddings with retry logic
        embeddings = await self._generate_embeddings_with_retry(texts)
        
        # Assign embeddings back to chunks
        for chunk, embedding in zip(chunks, embeddings):
            # Convert numpy array to list for compatibility
            chunk.embedding = embedding.tolist() if embedding is not None else None
            
        return chunks
    
    async def _generate_embeddings_with_retry(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Generate embeddings with retry logic for rate limiting and errors."""
        max_retries = self.config.max_retries
        base_delay = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Generating embeddings for {len(texts)} texts (attempt {attempt + 1})")
                
                response = await self.client.embeddings.create(
                    model=self.config.embedding_deployment,
                    input=texts,
                    dimensions=self.config.embedding_dimension
                )
                
                # Extract embeddings
                embeddings = []
                for i, embedding_data in enumerate(response.data):
                    vector = np.array(embedding_data.embedding, dtype=np.float32)
                    embeddings.append(vector)
                
                self.stats.api_calls += 1
                self.stats.tokens_processed += sum(self._count_tokens(text) for text in texts)
                
                logger.debug(f"Successfully generated {len(embeddings)} embeddings")
                return embeddings
                
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Failed to generate embeddings after {max_retries + 1} attempts: {e}")
                    # Return None for all texts
                    return [None] * len(texts)
                
                # Calculate delay with exponential backoff
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Embedding attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
        
        return [None] * len(texts)
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        try:
            return len(self.encoding.encode(text))
        except Exception:
            # Fallback to rough estimation
            return int(len(text.split()) * 1.3)
    
    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        try:
            tokens = self.encoding.encode(text)
            if len(tokens) <= max_tokens:
                return text
            
            # Truncate tokens and decode back
            truncated_tokens = tokens[:max_tokens]
            return self.encoding.decode(truncated_tokens)
        except Exception:
            # Fallback to character-based truncation
            estimated_chars = max_tokens * 4  # Rough estimate
            return text[:estimated_chars] + "..."
    
    async def embed_single_text(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for a single text string.
        Useful for query embeddings.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if failed
        """
        if not text.strip():
            return None
            
        embeddings = await self._generate_embeddings_with_retry([text])
        return embeddings[0] if embeddings else None
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        if embedding1 is None or embedding2 is None:
            return 0.0
            
        # Normalize vectors
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Calculate cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        return float(similarity)
    
    def calculate_batch_similarities(self, query_embedding: np.ndarray, 
                                   chunk_embeddings: List[np.ndarray]) -> List[float]:
        """
        Calculate similarities between query and multiple chunk embeddings.
        
        Args:
            query_embedding: Query embedding vector
            chunk_embeddings: List of chunk embedding vectors
            
        Returns:
            List of similarity scores
        """
        similarities = []
        for chunk_embedding in chunk_embeddings:
            similarity = self.calculate_similarity(query_embedding, chunk_embedding)
            similarities.append(similarity)
        return similarities
    
    def get_stats(self) -> ProcessingStats:
        """Get processing statistics."""
        return self.stats
    
    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = ProcessingStats()
    
    async def test_connection(self) -> bool:
        """
        Test the Azure OpenAI connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Testing Azure OpenAI connection...")
            test_embedding = await self.embed_single_text("test connection")
            
            if test_embedding is not None:
                logger.info("Azure OpenAI connection test successful")
                return True
            else:
                logger.error("Azure OpenAI connection test failed - no embedding returned")
                return False
                
        except Exception as e:
            logger.error(f"Azure OpenAI connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the Azure OpenAI client."""
        if hasattr(self.client, 'close'):
            await self.client.close()

# Utility functions for embedding operations
def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """Normalize an embedding vector to unit length."""
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return embedding / norm

def cosine_similarity_matrix(embeddings: List[np.ndarray]) -> np.ndarray:
    """
    Calculate cosine similarity matrix for a list of embeddings.
    
    Args:
        embeddings: List of embedding vectors
        
    Returns:
        2D array of similarity scores
    """
    n = len(embeddings)
    similarity_matrix = np.zeros((n, n))
    
    for i in range(n):
        for j in range(i, n):
            if embeddings[i] is not None and embeddings[j] is not None:
                sim = np.dot(embeddings[i], embeddings[j]) / (
                    np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                )
                similarity_matrix[i][j] = sim
                similarity_matrix[j][i] = sim
    
    return similarity_matrix

async def create_embedder(config: EmbeddingConfig) -> ConfluenceEmbedder:
    """
    Factory function to create and test an embedder instance.
    
    Args:
        config: Embedding configuration
        
    Returns:
        Configured embedder instance
        
    Raises:
        Exception if connection test fails
    """
    embedder = ConfluenceEmbedder(config)
    
    # Test connection
    if not await embedder.test_connection():
        raise Exception("Failed to connect to Azure OpenAI service")
    
    return embedder 