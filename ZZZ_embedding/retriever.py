"""
Confluence Retriever for intelligent search and retrieval.
Orchestrates embedding generation, vector search, and graph enrichment.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import time

from .config import EmbeddingConfig
from .models import (
    EmbeddingChunk, RetrievalResult, ChunkType, PageContext, 
    SearchRequest, SearchResponse, ProcessingStats
)
from .embedder import ConfluenceEmbedder
from .vector_store import ConfluenceVectorStore

logger = logging.getLogger(__name__)

@dataclass
class SearchStrategy:
    """Configuration for search strategy."""
    use_vector_search: bool = True
    use_text_search: bool = True
    use_semantic_ranker: bool = True
    vector_weight: float = 0.7
    text_weight: float = 0.3
    confidence_threshold: float = 0.75
    enable_reranking: bool = True

class ConfluenceRetriever:
    """Handles intelligent retrieval with multiple search strategies."""
    
    def __init__(self, 
                 config: EmbeddingConfig,
                 embedder: ConfluenceEmbedder,
                 vector_store: ConfluenceVectorStore):
        self.config = config
        self.embedder = embedder
        self.vector_store = vector_store
        self.stats = ProcessingStats()
        
    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Perform intelligent search using multiple strategies.
        
        Args:
            request: Search request with query and parameters
            
        Returns:
            SearchResponse with results and metadata
        """
        logger.info(f"Processing search request: '{request.query}'")
        self.stats.start()
        
        try:
            # Generate query embedding
            query_vector = None
            if request.query:
                query_vector = await self.embedder.embed_single_text(request.query)
            
            # Perform vector search
            vector_results = []
            if query_vector:
                vector_results = await self.vector_store.search(
                    query_text="",  # Vector-only search first
                    query_vector=query_vector,
                    filters=self._build_filters(request),
                    top_k=request.top_k * 2,  # Get more candidates for reranking
                    use_semantic_ranker=False
                )
            
            # Perform text search
            text_results = []
            if request.query:
                text_results = await self.vector_store.search(
                    query_text=request.query,
                    query_vector=None,  # Text-only search
                    filters=self._build_filters(request),
                    top_k=request.top_k * 2,
                    use_semantic_ranker=request.use_semantic_ranker
                )
            
            # Combine and rerank results
            combined_results = self._combine_results(
                vector_results, 
                text_results,
                request.top_k
            )
            
            # Group results by page and build context
            page_contexts = await self._build_page_contexts(combined_results)
            
            # Select best page context
            best_context = self._select_best_context(page_contexts, request.query)
            
            # Generate response
            response = await self._generate_response(best_context, request)
            
            self.stats.end()
            logger.info(f"Search completed in {self.stats.duration:.2f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return SearchResponse(
                answer="I'm sorry, I encountered an error while searching. Please try again.",
                confidence=0.0,
                page_id="",
                ancestors=[],
                children=[],
                chunks=[],
                links={},
                fallback_used=True,
                metadata={"error": str(e)}
            )
    
    def _build_filters(self, request: SearchRequest) -> Optional[str]:
        """Build OData filter string from search request."""
        filters = []
        
        if request.space_filter:
            filters.append(f"space_key eq '{request.space_filter}'")
        
        if request.page_filter:
            page_filter = " or ".join([f"page_id eq '{pid}'" for pid in request.page_filter])
            filters.append(f"({page_filter})")
        
        return " and ".join(filters) if filters else None
    
    def _combine_results(self, 
                        vector_results: List[RetrievalResult],
                        text_results: List[RetrievalResult],
                        top_k: int) -> List[RetrievalResult]:
        """
        Combine vector and text search results with intelligent deduplication.
        """
        # Create lookup for deduplication
        result_map = {}
        
        # Add vector results with boosted scores
        for result in vector_results:
            result_map[result.chunk_id] = result
            result.score *= 1.2  # Boost vector scores slightly
        
        # Add text results, combining scores for duplicates
        for result in text_results:
            if result.chunk_id in result_map:
                # Combine scores using weighted average
                existing = result_map[result.chunk_id]
                combined_score = (existing.score * 0.6) + (result.score * 0.4)
                existing.score = combined_score
            else:
                result_map[result.chunk_id] = result
        
        # Sort by combined score and return top results
        combined = list(result_map.values())
        combined.sort(key=lambda x: x.score, reverse=True)
        
        return combined[:top_k]
    
    async def _build_page_contexts(self, 
                                  results: List[RetrievalResult]) -> List[PageContext]:
        """
        Group results by page and build rich page contexts.
        """
        page_groups = {}
        
        # Group chunks by page
        for result in results:
            page_id = result.page_id
            if page_id not in page_groups:
                page_groups[page_id] = []
            page_groups[page_id].append(result)
        
        # Build page contexts
        contexts = []
        for page_id, chunks in page_groups.items():
            # Calculate page-level confidence
            chunk_scores = [chunk.score for chunk in chunks]
            avg_score = sum(chunk_scores) / len(chunk_scores)
            max_score = max(chunk_scores)
            confidence = (avg_score * 0.6) + (max_score * 0.4)
            
            # Get page title from chunks
            title = ""
            breadcrumb = []
            for chunk in chunks:
                if chunk.metadata.get('title'):
                    title = chunk.metadata['title']
                if chunk.breadcrumb:
                    breadcrumb = chunk.breadcrumb
                    break
            
            context = PageContext(
                page_id=page_id,
                title=title,
                breadcrumb=breadcrumb,
                chunks=chunks,
                confidence=confidence,
                metadata={}
            )
            contexts.append(context)
        
        # Sort by confidence
        contexts.sort(key=lambda x: x.confidence, reverse=True)
        return contexts
    
    def _select_best_context(self, 
                           contexts: List[PageContext],
                           query: str) -> Optional[PageContext]:
        """
        Select the best page context based on confidence and relevance.
        """
        if not contexts:
            return None
        
        # Simple heuristic: return highest confidence context
        # that meets minimum threshold
        for context in contexts:
            if context.confidence >= self.config.similarity_threshold:
                return context
        
        # If no context meets threshold, return the best one
        # but mark as low confidence
        best_context = contexts[0]
        best_context.confidence = min(best_context.confidence, 0.5)
        return best_context
    
    async def _generate_response(self, 
                               context: Optional[PageContext],
                               request: SearchRequest) -> SearchResponse:
        """
        Generate final search response from page context.
        """
        if not context:
            return SearchResponse(
                answer="I couldn't find relevant information for your query. Please try rephrasing your question.",
                confidence=0.0,
                page_id="",
                ancestors=[],
                children=[],
                chunks=[],
                links={},
                fallback_used=True
            )
        
        # Get top chunks for answer generation
        top_chunks = context.get_top_chunks(limit=3)
        
        # Build answer from top chunks
        answer_parts = []
        for chunk in top_chunks:
            if chunk.chunk_type == ChunkType.TITLE:
                answer_parts.append(f"**{chunk.content}**")
            elif chunk.chunk_type == ChunkType.SECTION_HEADER:
                answer_parts.append(f"### {chunk.content}")
            else:
                answer_parts.append(chunk.content)
        
        answer = "\n\n".join(answer_parts)
        
        # Build chunk information for UI
        chunk_info = []
        for chunk in top_chunks:
            chunk_info.append({
                "id": chunk.chunk_id,
                "content": chunk.content,
                "type": chunk.chunk_type.value,
                "score": chunk.score,
                "metadata": chunk.metadata
            })
        
        # Build links
        links = {
            "page_url": f"/pages/{context.page_id}",
            "edit_url": f"/pages/{context.page_id}/edit"
        }
        
        return SearchResponse(
            answer=answer,
            confidence=context.confidence,
            page_id=context.page_id,
            ancestors=context.ancestors,
            children=context.children,
            chunks=chunk_info,
            links=links,
            fallback_used=context.confidence < self.config.similarity_threshold,
            metadata={
                "total_chunks": len(context.chunks),
                "search_strategy": "hybrid",
                "processing_time": self.stats.duration
            }
        )
    
    async def similar_pages(self, 
                          page_id: str, 
                          limit: int = 5) -> List[RetrievalResult]:
        """
        Find pages similar to the given page.
        
        Args:
            page_id: ID of the reference page
            limit: Number of similar pages to return
            
        Returns:
            List of similar page results
        """
        try:
            # Get chunks from the reference page
            page_chunks = await self.vector_store.get_chunks_by_page(page_id)
            
            if not page_chunks:
                return []
            
            # Get title/summary chunks for comparison
            key_chunks = [
                chunk for chunk in page_chunks 
                if chunk.chunk_type in [ChunkType.TITLE, ChunkType.PAGE_SUMMARY]
            ]
            
            if not key_chunks:
                key_chunks = page_chunks[:2]  # Fallback to first chunks
            
            # Create a combined query from key chunks
            query_text = " ".join([chunk.content for chunk in key_chunks])
            
            # Generate embedding for combined content
            query_vector = await self.embedder.embed_single_text(query_text)
            
            if not query_vector:
                return []
            
            # Search for similar content, excluding the source page
            filters = f"page_id ne '{page_id}'"
            results = await self.vector_store.search(
                query_text=query_text,
                query_vector=query_vector,
                filters=filters,
                top_k=limit * 3,  # Get more candidates
                use_semantic_ranker=True
            )
            
            # Group by page and get top pages
            page_scores = {}
            for result in results:
                pid = result.page_id
                if pid not in page_scores:
                    page_scores[pid] = []
                page_scores[pid].append(result.score)
            
            # Calculate average score per page
            page_rankings = []
            for pid, scores in page_scores.items():
                avg_score = sum(scores) / len(scores)
                page_rankings.append((pid, avg_score))
            
            # Sort and get top pages
            page_rankings.sort(key=lambda x: x[1], reverse=True)
            top_pages = page_rankings[:limit]
            
            # Get representative chunk for each top page
            similar_results = []
            for pid, score in top_pages:
                page_results = [r for r in results if r.page_id == pid]
                if page_results:
                    best_chunk = max(page_results, key=lambda x: x.score)
                    best_chunk.score = score  # Use page-level score
                    similar_results.append(best_chunk)
            
            return similar_results
            
        except Exception as e:
            logger.error(f"Failed to find similar pages: {e}")
            return []
    
    async def get_page_summary(self, page_id: str) -> Optional[str]:
        """
        Get a summary of a page based on its chunks.
        
        Args:
            page_id: ID of the page
            
        Returns:
            Summary text or None if page not found
        """
        try:
            chunks = await self.vector_store.get_chunks_by_page(page_id)
            
            if not chunks:
                return None
            
            # Look for existing summary chunk
            summary_chunks = [
                chunk for chunk in chunks 
                if chunk.chunk_type == ChunkType.PAGE_SUMMARY
            ]
            
            if summary_chunks:
                return summary_chunks[0].content
            
            # Generate summary from title and first few content chunks
            title_chunks = [
                chunk for chunk in chunks 
                if chunk.chunk_type == ChunkType.TITLE
            ]
            
            content_chunks = [
                chunk for chunk in chunks 
                if chunk.chunk_type == ChunkType.BODY
            ][:3]  # First 3 content chunks
            
            summary_parts = []
            
            if title_chunks:
                summary_parts.append(f"**{title_chunks[0].content}**")
            
            if content_chunks:
                for chunk in content_chunks:
                    # Truncate long chunks
                    content = chunk.content
                    if len(content) > 200:
                        content = content[:200] + "..."
                    summary_parts.append(content)
            
            return "\n\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Failed to get page summary: {e}")
            return None
    
    def get_stats(self) -> ProcessingStats:
        """Get processing statistics."""
        return self.stats
    
    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = ProcessingStats()

async def create_retriever(config: EmbeddingConfig) -> ConfluenceRetriever:
    """
    Factory function to create a fully configured retriever.
    
    Args:
        config: Embedding configuration
        
    Returns:
        Configured retriever instance
    """
    # Create embedder
    embedder = ConfluenceEmbedder(config)
    
    # Test embedder connection
    if not await embedder.test_connection():
        raise Exception("Failed to connect to Azure OpenAI service")
    
    # Create vector store
    vector_store = ConfluenceVectorStore(config)
    
    # Ensure index exists
    await vector_store.create_index(force_recreate=False)
    
    # Create retriever
    retriever = ConfluenceRetriever(config, embedder, vector_store)
    
    logger.info("Retriever created and ready for use")
    return retriever
