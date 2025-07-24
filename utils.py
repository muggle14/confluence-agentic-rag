# utils.py
"""
Utility functions and configuration for Confluence Q&A system
"""

import os
import re
import json
import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import logging
from functools import lru_cache
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """System configuration"""
    # Azure resources
    subscription_id: str
    resource_group: str
    location: str
    
    # Cosmos DB
    cosmos_account: str
    cosmos_db: str
    cosmos_graph: str
    
    # Storage
    storage_account: str
    
    # Azure AI Search
    search_service: str
    search_index: str
    search_endpoint: str
    
    # Azure OpenAI
    aoai_resource: str
    aoai_endpoint: str
    aoai_embed_deploy: str
    aoai_chat_deploy: str
    
    # Confluence
    confluence_base: str
    confluence_org: str
    
    # Q&A System settings
    max_hops: int = 3
    confidence_threshold: float = 0.7
    max_search_results: int = 25
    rerank_top_k: int = 8
    chunk_size: int = 512
    chunk_overlap: int = 128
    
    # Agent settings
    agent_timeout: int = 30
    max_clarification_rounds: int = 2
    thinking_process_enabled: bool = True
    
    # Edge types for graph traversal
    edge_types: List[str] = field(default_factory=lambda: ['ParentOf', 'LinksTo', 'References'])
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables"""
        return cls(
            subscription_id=os.getenv('AZ_SUBSCRIPTION_ID', ''),
            resource_group=os.getenv('AZ_RESOURCE_GROUP', 'rg-rag-confluence'),
            location=os.getenv('AZ_LOCATION', 'westeurope'),
            cosmos_account=os.getenv('COSMOS_ACCOUNT', 'cosmos-rag-conf'),
            cosmos_db=os.getenv('COSMOS_DB', 'confluence'),
            cosmos_graph=os.getenv('COSMOS_GRAPH', 'pages'),
            storage_account=os.getenv('STORAGE_ACCOUNT', 'stgragconf'),
            search_service=os.getenv('SEARCH_SERVICE', 'srch-rag-conf'),
            search_index=os.getenv('SEARCH_INDEX', 'confluence-idx'),
            search_endpoint=os.getenv('SEARCH_ENDPOINT', ''),
            aoai_resource=os.getenv('AOAI_RESOURCE', 'aoai-rag-conf'),
            aoai_endpoint=os.getenv('AOAI_ENDPOINT', ''),
            aoai_embed_deploy=os.getenv('AOAI_EMBED_DEPLOY', 'text-embedding-3-large'),
            aoai_chat_deploy=os.getenv('AOAI_CHAT_DEPLOY', 'gpt-4o'),
            confluence_base=os.getenv('CONFLUENCE_BASE', ''),
            confluence_org=os.getenv('CONFLUENCE_ORG', 'your-org'),
            max_hops=int(os.getenv('MAX_HOPS', '3')),
            confidence_threshold=float(os.getenv('CONFIDENCE_THRESHOLD', '0.7')),
            edge_types=os.getenv('EDGE_TYPES', 'ParentOf,LinksTo,References').split(',')
        )
    
    @classmethod
    def from_yaml(cls, path: str) -> 'Config':
        """Load configuration from YAML file"""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)


class CitationExtractor:
    """Extract and validate citations from text"""
    
    CITATION_PATTERN = re.compile(r'\[\[([^\]]+)\]\]')
    
    @classmethod
    def extract_citations(cls, text: str) -> List[str]:
        """Extract all citations from text"""
        return cls.CITATION_PATTERN.findall(text)
    
    @classmethod
    def validate_citations(cls, text: str, valid_ids: Set[str]) -> Dict[str, Any]:
        """Validate citations against known document IDs"""
        citations = cls.extract_citations(text)
        
        valid_citations = [c for c in citations if c in valid_ids]
        invalid_citations = [c for c in citations if c not in valid_ids]
        
        # Find statements without citations (heuristic: sentences ending with period)
        sentences = text.split('.')
        uncited_statements = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and not cls.CITATION_PATTERN.search(sentence):
                # Check if it's a factual claim (contains specific info)
                if any(word in sentence.lower() for word in ['is', 'are', 'was', 'were', 'has', 'have', 'can', 'must', 'should']):
                    uncited_statements.append(sentence)
        
        return {
            'total_citations': len(citations),
            'valid_citations': valid_citations,
            'invalid_citations': invalid_citations,
            'uncited_statements': uncited_statements,
            'citation_coverage': len(valid_citations) / max(len(sentences), 1)
        }
    
    @classmethod
    def add_citations(cls, text: str, claims_to_citations: Dict[str, str]) -> str:
        """Add citations to uncited claims"""
        result = text
        for claim, citation in claims_to_citations.items():
            if claim in result and f'[[{citation}]]' not in result:
                result = result.replace(claim, f'{claim} [[{citation}]]')
        return result


class DocumentChunker:
    """Chunk documents for processing"""
    
    def __init__(self, chunk_size: int = 512, overlap: int = 128):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Chunk text with metadata"""
        words = text.split()
        chunks = []
        
        i = 0
        chunk_id = 0
        while i < len(words):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            chunk_data = {
                'id': f"{metadata.get('page_id', 'unknown')}-{metadata.get('section', 0)}-{chunk_id}",
                'text': chunk_text,
                'chunk_id': chunk_id,
                'start_word': i,
                'end_word': i + len(chunk_words),
                'metadata': metadata or {}
            }
            
            chunks.append(chunk_data)
            
            # Move forward by chunk_size - overlap
            i += self.chunk_size - self.overlap
            chunk_id += 1
        
        return chunks
    
    def chunk_with_headers(self, text: str, headers: List[str], metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Chunk text preserving header context"""
        chunks = []
        sections = self._split_by_headers(text, headers)
        
        for section in sections:
            section_metadata = {
                **(metadata or {}),
                'section_title': section['title'],
                'section_level': section['level']
            }
            
            section_chunks = self.chunk_text(section['content'], section_metadata)
            chunks.extend(section_chunks)
        
        return chunks
    
    def _split_by_headers(self, text: str, headers: List[str]) -> List[Dict[str, Any]]:
        """Split text by header patterns"""
        # Simple implementation - in production use more sophisticated parsing
        sections = []
        current_section = {'title': 'Introduction', 'level': 0, 'content': ''}
        
        lines = text.split('\n')
        for line in lines:
            is_header = False
            for level, header_pattern in enumerate(headers):
                if line.startswith(header_pattern):
                    # Save current section
                    if current_section['content'].strip():
                        sections.append(current_section)
                    
                    # Start new section
                    current_section = {
                        'title': line.replace(header_pattern, '').strip(),
                        'level': level,
                        'content': ''
                    }
                    is_header = True
                    break
            
            if not is_header:
                current_section['content'] += line + '\n'
        
        # Add last section
        if current_section['content'].strip():
            sections.append(current_section)
        
        return sections


class QueryPreprocessor:
    """Preprocess and enhance queries"""
    
    ABBREVIATIONS = {
        'sso': 'single sign-on',
        'api': 'application programming interface',
        'ci/cd': 'continuous integration continuous deployment',
        'k8s': 'kubernetes',
        'iam': 'identity and access management',
        'rbac': 'role-based access control'
    }
    
    @classmethod
    def expand_abbreviations(cls, query: str) -> str:
        """Expand known abbreviations"""
        result = query.lower()
        for abbr, full in cls.ABBREVIATIONS.items():
            result = re.sub(r'\b' + abbr + r'\b', f'{abbr} ({full})', result, flags=re.IGNORECASE)
        return result
    
    @classmethod
    def extract_entities(cls, query: str) -> Dict[str, List[str]]:
        """Extract entities from query"""
        entities = {
            'versions': re.findall(r'v?\d+\.\d+(?:\.\d+)?', query),
            'dates': re.findall(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b', query),
            'acronyms': re.findall(r'\b[A-Z]{2,}\b', query),
            'quoted': re.findall(r'"([^"]+)"', query),
            'code_terms': re.findall(r'`([^`]+)`', query)
        }
        return {k: v for k, v in entities.items() if v}
    
    @classmethod
    def generate_synonyms(cls, query: str) -> List[str]:
        """Generate query synonyms"""
        synonyms = [query]
        
        # Common variations
        variations = {
            'setup': ['configure', 'install', 'initialize'],
            'delete': ['remove', 'destroy', 'clean up'],
            'create': ['add', 'make', 'generate'],
            'update': ['modify', 'change', 'edit'],
            'get': ['retrieve', 'fetch', 'find']
        }
        
        for term, syns in variations.items():
            if term in query.lower():
                for syn in syns:
                    synonyms.append(query.lower().replace(term, syn))
        
        return list(set(synonyms))


class MetricsCollector:
    """Collect and track system metrics"""
    
    def __init__(self):
        self.metrics = {
            'queries_processed': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'clarifications_needed': 0,
            'avg_response_time': 0,
            'avg_hops': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self.response_times = []
        self.hop_counts = []
    
    def record_query(self, success: bool, response_time: float, hops: int = 0):
        """Record query metrics"""
        self.metrics['queries_processed'] += 1
        
        if success:
            self.metrics['successful_queries'] += 1
        else:
            self.metrics['failed_queries'] += 1
        
        self.response_times.append(response_time)
        self.hop_counts.append(hops)
        
        # Update averages
        self.metrics['avg_response_time'] = sum(self.response_times) / len(self.response_times)
        if self.hop_counts:
            self.metrics['avg_hops'] = sum(self.hop_counts) / len(self.hop_counts)
    
    def record_clarification(self):
        """Record clarification request"""
        self.metrics['clarifications_needed'] += 1
    
    def record_cache_hit(self, hit: bool):
        """Record cache hit/miss"""
        if hit:
            self.metrics['cache_hits'] += 1
        else:
            self.metrics['cache_misses'] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return {
            **self.metrics,
            'success_rate': self.metrics['successful_queries'] / max(self.metrics['queries_processed'], 1),
            'cache_hit_rate': self.metrics['cache_hits'] / max(self.metrics['cache_hits'] + self.metrics['cache_misses'], 1)
        }


class ResponseCache:
    """Cache for query responses"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.cache = {}
        self.ttl_seconds = ttl_seconds
    
    def _get_cache_key(self, query: str, context: Dict[str, Any] = None) -> str:
        """Generate cache key"""
        key_data = {
            'query': query.lower().strip(),
            'context': context or {}
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, query: str, context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Get cached response"""
        key = self._get_cache_key(query, context)
        
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.ttl_seconds:
                logger.info(f"Cache hit for query: {query[:50]}...")
                return entry['response']
            else:
                # Expired
                del self.cache[key]
        
        return None
    
    def set(self, query: str, response: Dict[str, Any], context: Dict[str, Any] = None):
        """Cache response"""
        key = self._get_cache_key(query, context)
        self.cache[key] = {
            'response': response,
            'timestamp': time.time(),
            'query': query,
            'context': context
        }
        logger.info(f"Cached response for query: {query[:50]}...")
    
    def clear_expired(self):
        """Clear expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time - entry['timestamp'] >= self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")


class ConfluencePageTree:
    """Build and manipulate Confluence page trees"""
    
    def __init__(self):
        self.nodes = {}
    
    def add_page(self, page_id: str, title: str, parent_id: str = None, url: str = None):
        """Add page to tree"""
        if page_id not in self.nodes:
            self.nodes[page_id] = {
                'id': page_id,
                'title': title,
                'parent_id': parent_id,
                'url': url or f"/wiki/pages/{page_id}",
                'children': [],
                'metadata': {}
            }
        
        if parent_id and parent_id in self.nodes:
            if page_id not in self.nodes[parent_id]['children']:
                self.nodes[parent_id]['children'].append(page_id)
    
    def get_ancestry(self, page_id: str) -> List[str]:
        """Get ancestry path from page to root"""
        path = []
        current = page_id
        
        while current and current in self.nodes:
            path.append(current)
            current = self.nodes[current].get('parent_id')
        
        return list(reversed(path))
    
    def get_descendants(self, page_id: str) -> List[str]:
        """Get all descendants of a page"""
        descendants = []
        
        def traverse(node_id):
            if node_id in self.nodes:
                for child_id in self.nodes[node_id]['children']:
                    descendants.append(child_id)
                    traverse(child_id)
        
        traverse(page_id)
        return descendants
    
    def find_common_ancestor(self, page_id1: str, page_id2: str) -> Optional[str]:
        """Find common ancestor of two pages"""
        ancestors1 = set(self.get_ancestry(page_id1))
        ancestors2 = set(self.get_ancestry(page_id2))
        
        common = ancestors1.intersection(ancestors2)
        if not common:
            return None
        
        # Return the closest common ancestor
        for page_id in self.get_ancestry(page_id1):
            if page_id in common:
                return page_id
        
        return None
    
    def render_subtree(self, root_id: str, highlight_ids: Set[str] = None, max_depth: int = None) -> str:
        """Render subtree as markdown"""
        if root_id not in self.nodes:
            return ""
        
        highlight_ids = highlight_ids or set()
        lines = []
        
        def render_node(node_id: str, level: int = 0):
            if max_depth and level > max_depth:
                return
            
            node = self.nodes[node_id]
            indent = "  " * level
            
            # Format node
            if node_id in highlight_ids:
                line = f"{indent}- **[{node['title']}]({node['url']})** ⭐"
            else:
                line = f"{indent}- [{node['title']}]({node['url']})"
            
            lines.append(line)
            
            # Render children
            for child_id in node['children']:
                render_node(child_id, level + 1)
        
        render_node(root_id)
        return "\n".join(lines)


async def test_utilities():
    """Test utility functions"""
    
    # Test configuration
    config = Config.from_env()
    print(f"Configuration loaded: {config.confluence_org}")
    
    # Test citation extraction
    text = "SSO can be enabled through the Admin Console [[page123-1]]. Navigate to Settings [[page124-2]]."
    citations = CitationExtractor.extract_citations(text)
    print(f"Citations found: {citations}")
    
    # Test chunking
    chunker = DocumentChunker(chunk_size=10, overlap=2)
    chunks = chunker.chunk_text("This is a test document with multiple sentences that should be chunked appropriately.")
    print(f"Chunks created: {len(chunks)}")
    
    # Test query preprocessing
    query = "How do I setup SSO for K8s?"
    expanded = QueryPreprocessor.expand_abbreviations(query)
    print(f"Expanded query: {expanded}")
    
    # Test metrics
    metrics = MetricsCollector()
    metrics.record_query(success=True, response_time=1.5, hops=2)
    print(f"Metrics: {metrics.get_metrics()}")
    
    # Test tree building
    tree = ConfluencePageTree()
    tree.add_page("root", "Documentation Root")
    tree.add_page("auth", "Authentication", parent_id="root")
    tree.add_page("sso", "SSO Setup", parent_id="auth")
    tree.add_page("oauth", "OAuth Guide", parent_id="auth")
    
    rendered = tree.render_subtree("root", highlight_ids={"sso"})
    print(f"Tree:\n{rendered}")


if __name__ == "__main__":
    asyncio.run(test_utilities())