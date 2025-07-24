"""
Data models for the embedding layer
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class ChunkType(Enum):
    """Types of content chunks"""
    TITLE = "title"
    BODY = "body"
    TABLE = "table"
    TABLE_SUMMARY = "table_summary"
    IMAGE_ALT = "image_alt"
    SECTION_HEADER = "section_header"
    PAGE_SUMMARY = "page_summary"


@dataclass
class EmbeddingChunk:
    """Represents a chunk of content with its embedding"""
    id: str
    page_id: str
    chunk_type: ChunkType
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default metadata"""
        self.metadata.setdefault('created_at', datetime.utcnow().isoformat())
        self.metadata.setdefault('chunk_index', 0)
        self.metadata.setdefault('total_chunks', 1)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'page_id': self.page_id,
            'chunk_type': self.chunk_type.value,
            'content': self.content,
            'embedding': self.embedding,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmbeddingChunk':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            page_id=data['page_id'],
            chunk_type=ChunkType(data['chunk_type']),
            content=data['content'],
            embedding=data.get('embedding'),
            metadata=data.get('metadata', {})
        )


@dataclass
class RetrievalResult:
    """Result from a search operation"""
    chunk_id: str
    page_id: str
    content: str
    score: float
    chunk_type: ChunkType
    metadata: Dict[str, Any]
    breadcrumb: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'chunk_id': self.chunk_id,
            'page_id': self.page_id,
            'content': self.content,
            'score': self.score,
            'chunk_type': self.chunk_type.value,
            'metadata': self.metadata,
            'breadcrumb': self.breadcrumb
        }


@dataclass
class PageContext:
    """Context for a page with its chunks and hierarchy"""
    page_id: str
    title: str
    breadcrumb: List[str]
    chunks: List[RetrievalResult]
    ancestors: List[Dict[str, str]] = field(default_factory=list)
    children: List[Dict[str, str]] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_top_chunks(self, limit: int = 5) -> List[RetrievalResult]:
        """Get top scoring chunks"""
        return sorted(self.chunks, key=lambda x: x.score, reverse=True)[:limit]
    
    def get_chunks_by_type(self, chunk_type: ChunkType) -> List[RetrievalResult]:
        """Get chunks of a specific type"""
        return [chunk for chunk in self.chunks if chunk.chunk_type == chunk_type]


@dataclass
class SearchRequest:
    """Request for a search operation"""
    query: str
    space_filter: Optional[str] = None
    page_filter: Optional[List[str]] = None
    use_semantic_ranker: bool = True
    include_graph_data: bool = True
    top_k: int = 10


@dataclass
class SearchResponse:
    """Response from a search operation"""
    answer: str
    confidence: float
    page_id: str
    ancestors: List[Dict[str, str]]
    children: List[Dict[str, str]]
    chunks: List[Dict[str, Any]]
    links: Dict[str, str]
    fallback_used: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingStats:
    """Statistics for processing operations"""
    pages_processed: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    chunks_indexed: int = 0
    errors: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Embedding-specific stats
    total_chunks: int = 0
    successful_chunks: int = 0
    failed_chunks: int = 0
    api_calls: int = 0
    tokens_processed: int = 0
    embedding_time: float = 0.0
    
    def start(self):
        """Start timing"""
        self.start_time = datetime.utcnow()
    
    def end(self):
        """End timing"""
        self.end_time = datetime.utcnow()
    
    @property
    def duration(self) -> Optional[float]:
        """Get processing duration in seconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'pages_processed': self.pages_processed,
            'chunks_created': self.chunks_created,
            'embeddings_generated': self.embeddings_generated,
            'chunks_indexed': self.chunks_indexed,
            'errors': self.errors,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration
        } 