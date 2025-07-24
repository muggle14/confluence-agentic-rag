#!/usr/bin/env python3
"""
Configuration Management for Graph Population Module
Handles environment variables, connection strings, and settings validation
"""

import os
from typing import Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SearchConfig:
    """Configuration for Azure AI Search and Function App integration"""
    
    # Azure AI Search settings
    search_service: str
    search_key: str
    search_endpoint: str
    
    # Azure OpenAI settings
    azure_openai_endpoint: str
    azure_openai_key: str
    
    # Function App settings (with defaults)
    # Always load from ../.env or ../env file for defaults
    search_index: str = os.environ.get('SEARCH_INDEX_V2', 'confluence-graph-embeddings-v2')
    azure_openai_deployment: str = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'text-embedding-ada-002')
    function_app_name: str = os.environ.get('FUNCTION_APP', 'func-rag-graph-enrich')
    function_key: Optional[str] = os.environ.get('GRAPH_ENRICHMENT_FUNCTION_KEY')
    function_endpoint: Optional[str] = os.environ.get('FUNCTION_ENDPOINT')
    resource_group: str = os.environ.get('RESOURCE_GROUP', 'rg-rag-confluence')
    
    @classmethod
    def from_environment(cls, env_file: Optional[str] = None) -> 'SearchConfig':
        """Create search configuration from environment variables"""
        
        # Load environment file if specified
        if env_file and os.path.exists(env_file):
            GraphConfig._load_env_file(env_file)
        else:
            # Try to find environment file
            env_files = [
                '../.env', '../env', '.env', 'env'
            ]
            for env_path in env_files:
                if os.path.exists(env_path):
                    GraphConfig._load_env_file(env_path)
                    break
        
        # Extract settings
        search_service = os.environ.get('SEARCH_SERVICE', 'srch-rag-conf')
        search_key = os.environ.get('SEARCH_KEY', '')
        resource_group = os.environ.get('RESOURCE_GROUP') or os.environ.get('AZ_RESOURCE_GROUP', 'rg-rag-confluence')
        
        # Handle Azure OpenAI key variations
        azure_openai_key = os.environ.get('AZURE_OPENAI_KEY') or os.environ.get('AZURE_OPENAI_API_KEY', '')
        
        # Build endpoints if not provided
        search_endpoint = os.environ.get('SEARCH_ENDPOINT', f"https://{search_service}.search.windows.net")
        azure_openai_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', 'https://aoai-rag-confluence.openai.azure.com/')
        
        # Function app settings
        function_app_name = os.environ.get('FUNCTION_APP', 'func-rag-graph-enrich')
        function_key = os.environ.get('GRAPH_ENRICHMENT_FUNCTION_KEY', '4Rj1HTV7aTRRCUBIHdbAdpZu9VZOMKBgL4OGDb6lFTt1AzFu0ADAbg==')
        function_endpoint = f"https://{function_app_name}.azurewebsites.net/api/graph_enrichment_skill"
        
        return cls(
            search_service=search_service,
            search_key=search_key,
            search_endpoint=search_endpoint,
            search_index=os.environ.get('SEARCH_INDEX_V2', 'confluence-graph-embeddings-v2'),
            azure_openai_endpoint=azure_openai_endpoint,
            azure_openai_key=azure_openai_key,
            azure_openai_deployment=os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'text-embedding-ada-002'),
            function_app_name=function_app_name,
            function_key=function_key,
            function_endpoint=function_endpoint,
            resource_group=resource_group
        )
    
    def get_function_url(self) -> str:
        """Get the full function URL with key if available"""
        url = self.function_endpoint
        if self.function_key:
            url += f"?code={self.function_key}"
        return url


@dataclass
class GraphConfig:
    """Configuration container for graph population operations"""
    
    # Azure Cosmos DB (Gremlin API) settings
    cosmos_endpoint: str
    cosmos_key: str
    cosmos_database: str
    cosmos_container: str
    
    # Azure Storage settings
    storage_account: str
    storage_key: str
    storage_connection_string: str
    
    # Processing options
    batch_size: int = 50
    enable_rich_content: bool = True
    track_versions: bool = True
    max_retries: int = 3
    timeout_seconds: int = 30
    
    # Content options
    preserve_html: bool = True
    create_link_nodes: bool = True
    bidirectional_relationships: bool = True
    enable_space_hierarchy: bool = True
    
    # Phase 2 features (placeholders)
    enable_image_analysis: bool = False
    enhanced_link_resolution: bool = False
    
    @classmethod
    def from_environment(cls, env_file: Optional[str] = None) -> 'GraphConfig':
        """Create configuration from environment variables"""
        
        # Load environment file if specified
        if env_file and os.path.exists(env_file):
            cls._load_env_file(env_file)
        else:
            # Try to find environment file
            env_files = [
                '.env', '.env.updated', '../.env', '../.env.updated',
                'infra/.env.graph', 'infra/.env.updated', 'infra/.env',
                'notebooks/.env', 'notebooks/.env.updated'
            ]
            for env_path in env_files:
                if os.path.exists(env_path):
                    cls._load_env_file(env_path)
                    break
        
        # Extract required settings
        cosmos_endpoint = os.environ.get('COSMOS_ENDPOINT')
        cosmos_key = os.environ.get('COSMOS_KEY')
        storage_account = os.environ.get('STORAGE_ACCOUNT')
        storage_key = os.environ.get('STORAGE_KEY')
        
        # Build storage connection string if not provided
        storage_connection_string = os.environ.get('STORAGE_CONNECTION_STRING')
        if not storage_connection_string and storage_account and storage_key:
            storage_connection_string = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={storage_account};"
                f"AccountKey={storage_key};"
                f"EndpointSuffix=core.windows.net"
            )
        
        # Validate required settings
        missing_vars = []
        if not cosmos_endpoint:
            missing_vars.append('COSMOS_ENDPOINT')
        if not cosmos_key:
            missing_vars.append('COSMOS_KEY')
        if not storage_account:
            missing_vars.append('STORAGE_ACCOUNT')
        if not storage_key:
            missing_vars.append('STORAGE_KEY')
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # At this point, all variables are guaranteed to be non-None due to validation above
        assert cosmos_endpoint is not None
        assert cosmos_key is not None  
        assert storage_account is not None
        assert storage_key is not None
        assert storage_connection_string is not None
        
        return cls(
            cosmos_endpoint=cosmos_endpoint,
            cosmos_key=cosmos_key,
            cosmos_database=os.environ.get('COSMOS_DATABASE', 'confluence-graph'),
            cosmos_container=os.environ.get('COSMOS_CONTAINER', 'knowledge-graph'),
            storage_account=storage_account,
            storage_key=storage_key,
            storage_connection_string=storage_connection_string,
            batch_size=int(os.environ.get('GRAPH_BATCH_SIZE', '50')),
            enable_rich_content=os.environ.get('GRAPH_ENABLE_RICH_CONTENT', 'true').lower() == 'true',
            track_versions=os.environ.get('GRAPH_TRACK_VERSIONS', 'true').lower() == 'true',
            max_retries=int(os.environ.get('GRAPH_MAX_RETRIES', '3')),
            timeout_seconds=int(os.environ.get('GRAPH_TIMEOUT_SECONDS', '30')),
            preserve_html=os.environ.get('GRAPH_PRESERVE_HTML', 'true').lower() == 'true',
            create_link_nodes=os.environ.get('GRAPH_CREATE_LINK_NODES', 'true').lower() == 'true',
            bidirectional_relationships=os.environ.get('GRAPH_BIDIRECTIONAL_RELATIONSHIPS', 'true').lower() == 'true',
            enable_space_hierarchy=os.environ.get('GRAPH_ENABLE_SPACE_HIERARCHY', 'true').lower() == 'true',
            enable_image_analysis=os.environ.get('GRAPH_ENABLE_IMAGE_ANALYSIS', 'false').lower() == 'true',
            enhanced_link_resolution=os.environ.get('GRAPH_ENHANCED_LINK_RESOLUTION', 'false').lower() == 'true',
        )
    
    @staticmethod
    def _load_env_file(env_path: str) -> None:
        """Load environment variables from file"""
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            # Fallback to manual parsing if python-dotenv not available
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        try:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
                        except ValueError:
                            continue
    
    def validate(self) -> Dict[str, Any]:
        """Validate configuration and return status"""
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        # Check Cosmos DB endpoint format
        if not self.cosmos_endpoint.startswith('https://'):
            validation_results['warnings'].append("Cosmos endpoint should use HTTPS")
        
        if not self.cosmos_endpoint.endswith('.gremlin.cosmos.azure.com:443/'):
            validation_results['warnings'].append("Cosmos endpoint should be Gremlin API format")
        
        # Check batch size
        if self.batch_size > 100:
            validation_results['warnings'].append("Large batch size may cause timeouts")
        elif self.batch_size < 1:
            validation_results['errors'].append("Batch size must be at least 1")
            validation_results['valid'] = False
        
        # Check timeout
        if self.timeout_seconds < 5:
            validation_results['warnings'].append("Very short timeout may cause failures")
        
        return validation_results
    
    def get_cosmos_connection_string(self) -> str:
        """Get formatted Cosmos DB connection string"""
        return f"AccountEndpoint={self.cosmos_endpoint};AccountKey={self.cosmos_key};"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excludes sensitive data)"""
        return {
            'cosmos_endpoint': self.cosmos_endpoint[:50] + "..." if len(self.cosmos_endpoint) > 50 else self.cosmos_endpoint,
            'cosmos_database': self.cosmos_database,
            'cosmos_container': self.cosmos_container,
            'storage_account': self.storage_account,
            'batch_size': self.batch_size,
            'enable_rich_content': self.enable_rich_content,
            'track_versions': self.track_versions,
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds,
            'preserve_html': self.preserve_html,
            'create_link_nodes': self.create_link_nodes,
            'bidirectional_relationships': self.bidirectional_relationships,
            'enable_space_hierarchy': self.enable_space_hierarchy,
            'enable_image_analysis': self.enable_image_analysis,
            'enhanced_link_resolution': self.enhanced_link_resolution
        }


class ContainerNames:
    """Standard container names for Azure Storage"""
    RAW = 'raw'
    PROCESSED = 'processed'
    METADATA = 'metadata'
    IMAGES = 'images'  # Phase 2
    EMBEDDINGS = 'embeddings'  # Phase 2


class NodeTypes:
    """Standard node types for the knowledge graph"""
    PAGE = 'Page'
    SPACE = 'Space'
    LINK = 'Link'
    IMAGE = 'Image'  # Phase 2
    USER = 'User'    # Phase 2


class EdgeTypes:
    """Standard edge types for the knowledge graph"""
    # Hierarchical relationships (bidirectional)
    PARENT_OF = 'ParentOf'
    CHILD_OF = 'ChildOf'
    
    # Link relationships (bidirectional)
    LINKS_TO = 'LinksTo'
    LINKED_FROM = 'LinkedFrom'
    
    # Space relationships (bidirectional)
    BELONGS_TO = 'BelongsTo'
    CONTAINS = 'Contains'
    
    # External link relationships
    REFERENCES_EXTERNAL = 'ReferencesExternal'
    REFERENCED_BY = 'ReferencedBy'
    
    # Phase 2 relationships
    MENTIONS_IMAGE = 'MentionsImage'  # Page -> Image
    CREATED_BY = 'CreatedBy'          # Page -> User
    MODIFIED_BY = 'ModifiedBy'        # Page -> User


def get_sample_config() -> GraphConfig:
    """Get a sample configuration for testing"""
    return GraphConfig(
        cosmos_endpoint="https://sample.gremlin.cosmos.azure.com:443/",
        cosmos_key="sample-key",
        cosmos_database="confluence-graph",
        cosmos_container="knowledge-graph",
        storage_account="sampleaccount",
        storage_key="sample-key",
        storage_connection_string="DefaultEndpointsProtocol=https;AccountName=sample;AccountKey=key;EndpointSuffix=core.windows.net",
        batch_size=25,
        enable_rich_content=True,
        track_versions=True
    ) 