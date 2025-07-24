"""
Configuration for the embedding layer
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class EmbeddingConfig:
    """Configuration for the embedding system"""
    
    # Azure OpenAI settings
    aoai_endpoint: str
    aoai_key: str
    embedding_deployment: str  # "text-embedding-3-large" or "text-embedding-ada-002"
    
    # Azure AI Search settings
    search_endpoint: str
    search_key: str
    
    # Cosmos DB settings
    cosmos_endpoint: str
    cosmos_key: str
    
    # Storage settings
    storage_connection_string: str
    
    # Optional settings with defaults
    embedding_dimension: int = 1536  # 3072 for large, 1536 for ada
    search_index_name: str = "confluence-embeddings"
    cosmos_database: str = "confluence"
    cosmos_container: str = "pages"
    
    # Chunking parameters
    chunk_size: int = 512
    chunk_overlap: int = 128
    min_chunk_size: int = 100
    
    # Retrieval settings
    similarity_threshold: float = 0.75
    top_k: int = 10
    rerank_top_k: int = 5
    
    # Batch processing
    batch_size: int = 16
    max_retries: int = 3
    retry_delay: int = 1
    batch_delay: float = 0.5  # Delay between batches in seconds
    max_tokens: int = 8000  # Max tokens per chunk
    
    # Azure OpenAI API version
    azure_openai_api_version: str = "2024-02-01"
    
    @classmethod
    def from_env(cls) -> 'EmbeddingConfig':
        """Load configuration from environment variables"""
        return cls(
            aoai_endpoint=os.getenv('AOAI_ENDPOINT', ''),
            aoai_key=os.getenv('AOAI_KEY', ''),
            embedding_deployment=os.getenv('AOAI_EMBED_DEPLOY', 'text-embedding-3-large'),
            embedding_dimension=int(os.getenv('EMBEDDING_DIMENSION', '1536')),
            search_endpoint=os.getenv('SEARCH_ENDPOINT', ''),
            search_key=os.getenv('SEARCH_KEY', ''),
            search_index_name=os.getenv('SEARCH_INDEX', 'confluence-embeddings'),
            cosmos_endpoint=os.getenv('COSMOS_ENDPOINT', ''),
            cosmos_key=os.getenv('COSMOS_KEY', ''),
            cosmos_database=os.getenv('COSMOS_DB', 'confluence'),
            cosmos_container=os.getenv('COSMOS_GRAPH', 'pages'),
            storage_connection_string=os.getenv('STORAGE_CONN', ''),
            chunk_size=int(os.getenv('CHUNK_SIZE', '512')),
            chunk_overlap=int(os.getenv('CHUNK_OVERLAP', '128')),
            similarity_threshold=float(os.getenv('SIMILARITY_THRESHOLD', '0.75')),
            top_k=int(os.getenv('TOP_K', '10')),
            batch_size=int(os.getenv('BATCH_SIZE', '16'))
        )
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of missing fields"""
        missing = []
        
        if not self.aoai_endpoint:
            missing.append('AOAI_ENDPOINT')
        if not self.aoai_key:
            missing.append('AOAI_KEY')
        if not self.search_endpoint:
            missing.append('SEARCH_ENDPOINT')
        if not self.search_key:
            missing.append('SEARCH_KEY')
        if not self.cosmos_endpoint:
            missing.append('COSMOS_ENDPOINT')
        if not self.cosmos_key:
            missing.append('COSMOS_KEY')
        if not self.storage_connection_string:
            missing.append('STORAGE_CONN')
        
        return missing
    
    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        return len(self.validate()) == 0 