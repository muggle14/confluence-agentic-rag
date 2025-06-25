#!/usr/bin/env python3
"""
Graph Models for Confluence Knowledge Graph
Defines node and edge structures, data validation, and serialization
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class BaseNode:
    """Base class for all graph nodes"""
    id: str
    label: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    
    def to_gremlin_properties(self) -> Dict[str, Any]:
        """Convert to Gremlin-compatible properties"""
        return {
            'id': self.id,
            'label': self.label,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'version': self.version
        }


@dataclass  
class PageNode(BaseNode):
    """Confluence page node with comprehensive metadata"""
    
    # Core page information
    title: str = ""
    space_key: str = ""
    space_name: str = ""
    
    # Content in multiple formats
    content_html: str = ""
    content_text: str = ""
    content_markdown: str = ""
    
    # Hierarchical information
    breadcrumb: List[str] = field(default_factory=list)
    ancestors: List[str] = field(default_factory=list)  # Parent page IDs
    
    # Content statistics
    sections_count: int = 0
    tables_count: int = 0
    links_count: int = 0
    images_count: int = 0
    text_length: int = 0
    
    # Processed content structures
    sections: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    
    # Processing metadata
    processing_timestamp: Optional[str] = None
    pipeline_version: str = "1.0"
    phase: str = "1_comprehensive"
    
    # Phase 2 placeholders
    image_analysis_complete: bool = False
    semantic_embeddings: List[float] = field(default_factory=list)
    
    @classmethod
    def from_processed_json(cls, page_data: Dict[str, Any]) -> 'PageNode':
        """Create PageNode from processed JSON data"""
        processing_info = page_data.get('processing', {})
        stats = processing_info.get('stats', {})
        content = page_data.get('content', {})
        
        return cls(
            id=page_data.get('pageId', ''),
            label='Page',
            title=page_data.get('title', ''),
            space_key=page_data.get('spaceKey', ''),
            space_name=page_data.get('spaceName', ''),
            content_html=content.get('html', ''),
            content_text=content.get('text', ''),
            content_markdown=content.get('markdown', ''),
            breadcrumb=page_data.get('breadcrumb', []),
            ancestors=cls._extract_ancestor_ids(page_data.get('breadcrumb', [])),
            sections_count=stats.get('sections_count', 0),
            tables_count=stats.get('tables_count', 0),
            links_count=stats.get('links_count', 0),
            images_count=stats.get('images_count', 0),
            text_length=stats.get('text_length', 0),
            sections=page_data.get('sections', []),
            tables=page_data.get('tables', []),
            links=page_data.get('links', []),
            images=page_data.get('images', []),
            processing_timestamp=processing_info.get('timestamp'),
            pipeline_version=processing_info.get('pipeline_version', '1.0'),
            phase=processing_info.get('phase', '1_comprehensive'),
            updated_at=datetime.fromisoformat(page_data.get('updated', datetime.utcnow().isoformat()).replace('Z', '+00:00'))
        )
    
    @staticmethod
    def _extract_ancestor_ids(breadcrumb: List[str]) -> List[str]:
        """Extract ancestor page IDs from breadcrumb (placeholder for now)"""
        # TODO: Implement proper breadcrumb to page ID mapping
        # For now, return empty list as we need actual page IDs, not titles
        return []
    
    def to_gremlin_properties(self) -> Dict[str, Any]:
        """Convert to Gremlin-compatible properties"""
        props = super().to_gremlin_properties()
        props.update({
            'title': self.title,
            'space_key': self.space_key,
            'space_name': self.space_name,
            'content_text': self.content_text[:1000],  # Truncate for performance
            'breadcrumb': json.dumps(self.breadcrumb),
            'sections_count': self.sections_count,
            'tables_count': self.tables_count,
            'links_count': self.links_count,
            'images_count': self.images_count,
            'text_length': self.text_length,
            'processing_timestamp': self.processing_timestamp,
            'pipeline_version': self.pipeline_version,
            'phase': self.phase,
            'image_analysis_complete': self.image_analysis_complete
        })
        return props


@dataclass
class SpaceNode(BaseNode):
    """Confluence space node"""
    
    key: str = ""
    name: str = ""
    description: str = ""
    homepage_id: Optional[str] = None
    
    # Space statistics
    pages_count: int = 0
    total_content_length: int = 0
    
    @classmethod
    def from_space_info(cls, space_key: str, space_name: str, description: str = "") -> 'SpaceNode':
        """Create SpaceNode from space information"""
        return cls(
            id=space_key,
            label='Space',
            key=space_key,
            name=space_name,
            description=description
        )
    
    def to_gremlin_properties(self) -> Dict[str, Any]:
        """Convert to Gremlin-compatible properties"""
        props = super().to_gremlin_properties()
        props.update({
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'homepage_id': self.homepage_id,
            'pages_count': self.pages_count,
            'total_content_length': self.total_content_length
        })
        return props


@dataclass
class LinkNode(BaseNode):
    """External link node"""
    
    url: str = ""
    title: str = ""
    link_type: str = ""  # external, email, etc.
    domain: str = ""
    
    # Link statistics
    referenced_by_count: int = 0
    
    @classmethod
    def from_link_data(cls, url: str, title: str, link_type: str) -> 'LinkNode':
        """Create LinkNode from link information"""
        # Extract domain from URL
        domain = ""
        if url.startswith(('http://', 'https://')):
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
            except:
                domain = "unknown"
        
        # Use URL as ID (hash it if too long)
        link_id = url
        if len(link_id) > 50:
            import hashlib
            link_id = hashlib.md5(url.encode()).hexdigest()
        
        return cls(
            id=link_id,
            label='Link',
            url=url,
            title=title or url,
            link_type=link_type,
            domain=domain
        )
    
    def to_gremlin_properties(self) -> Dict[str, Any]:
        """Convert to Gremlin-compatible properties"""
        props = super().to_gremlin_properties()
        props.update({
            'url': self.url,
            'title': self.title,
            'link_type': self.link_type,
            'domain': self.domain,
            'referenced_by_count': self.referenced_by_count
        })
        return props


@dataclass
class BaseEdge:
    """Base class for all graph edges"""
    from_id: str
    to_id: str
    label: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    weight: float = 1.0
    
    def to_gremlin_properties(self) -> Dict[str, Any]:
        """Convert to Gremlin-compatible properties"""
        return {
            'created_at': self.created_at.isoformat(),
            'weight': self.weight
        }
    
    def get_edge_id(self) -> str:
        """Generate unique edge ID"""
        return f"{self.from_id}_{self.label}_{self.to_id}"


@dataclass
class HierarchyEdge(BaseEdge):
    """Parent-child relationship between pages"""
    
    hierarchy_level: int = 0  # Depth in hierarchy
    
    def to_gremlin_properties(self) -> Dict[str, Any]:
        props = super().to_gremlin_properties()
        props['hierarchy_level'] = self.hierarchy_level
        return props


@dataclass
class LinkEdge(BaseEdge):
    """Link relationship between pages or pages and external links"""
    
    link_text: str = ""
    link_context: str = ""  # Surrounding text
    link_order: int = 0     # Order within page
    
    def to_gremlin_properties(self) -> Dict[str, Any]:
        props = super().to_gremlin_properties()
        props.update({
            'link_text': self.link_text,
            'link_context': self.link_context,
            'link_order': self.link_order
        })
        return props


@dataclass
class SpaceEdge(BaseEdge):
    """Relationship between pages and spaces"""
    
    def to_gremlin_properties(self) -> Dict[str, Any]:
        return super().to_gremlin_properties()


class GraphModelFactory:
    """Factory for creating graph models from data"""
    
    @staticmethod
    def create_page_node(page_data: Dict[str, Any]) -> PageNode:
        """Create a page node from processed data"""
        return PageNode.from_processed_json(page_data)
    
    @staticmethod
    def create_space_node(space_key: str, space_name: str, description: str = "") -> SpaceNode:
        """Create a space node"""
        return SpaceNode.from_space_info(space_key, space_name, description)
    
    @staticmethod
    def create_link_node(url: str, title: str, link_type: str) -> LinkNode:
        """Create a link node"""
        return LinkNode.from_link_data(url, title, link_type)
    
    @staticmethod
    def create_hierarchy_edges(page_node: PageNode) -> List[HierarchyEdge]:
        """Create hierarchy edges for a page"""
        edges = []
        
        # Create parent-child relationships
        for i, ancestor_id in enumerate(page_node.ancestors):
            if ancestor_id:
                # Parent -> Child relationship
                parent_edge = HierarchyEdge(
                    from_id=ancestor_id,
                    to_id=page_node.id,
                    label='ParentOf',
                    hierarchy_level=len(page_node.ancestors) - i
                )
                edges.append(parent_edge)
                
                # Child -> Parent relationship (bidirectional)
                child_edge = HierarchyEdge(
                    from_id=page_node.id,
                    to_id=ancestor_id,
                    label='ChildOf',
                    hierarchy_level=len(page_node.ancestors) - i
                )
                edges.append(child_edge)
        
        return edges
    
    @staticmethod
    def create_link_edges(page_node: PageNode) -> List[LinkEdge]:
        """Create link edges for a page"""
        edges = []
        
        for link_data in page_node.links:
            # Determine target ID
            target_id = link_data.get('internal_page_id')
            if not target_id and link_data.get('type') in ['external', 'email']:
                # Use URL as target for external links (will need LinkNode)
                target_id = link_data.get('url', '')
                if len(target_id) > 50:
                    import hashlib
                    target_id = hashlib.md5(target_id.encode()).hexdigest()
            
            if target_id:
                # Forward link
                forward_edge = LinkEdge(
                    from_id=page_node.id,
                    to_id=target_id,
                    label='LinksTo',
                    link_text=link_data.get('text', ''),
                    link_order=link_data.get('order', 0)
                )
                edges.append(forward_edge)
                
                # Backward link (bidirectional)
                backward_edge = LinkEdge(
                    from_id=target_id,
                    to_id=page_node.id,
                    label='LinkedFrom',
                    link_text=link_data.get('text', ''),
                    link_order=link_data.get('order', 0)
                )
                edges.append(backward_edge)
        
        return edges
    
    @staticmethod
    def create_space_edges(page_node: PageNode) -> List[SpaceEdge]:
        """Create space membership edges for a page"""
        edges = []
        
        if page_node.space_key:
            # Page belongs to space
            belongs_edge = SpaceEdge(
                from_id=page_node.id,
                to_id=page_node.space_key,
                label='BelongsTo'
            )
            edges.append(belongs_edge)
            
            # Space contains page (bidirectional)
            contains_edge = SpaceEdge(
                from_id=page_node.space_key,
                to_id=page_node.id,
                label='Contains'
            )
            edges.append(contains_edge)
        
        return edges


def validate_node_data(node_data: Dict[str, Any], required_fields: List[str]) -> List[str]:
    """Validate node data and return list of missing fields"""
    missing_fields = []
    for field in required_fields:
        if field not in node_data or not node_data[field]:
            missing_fields.append(field)
    return missing_fields


def serialize_for_storage(obj: Union[BaseNode, BaseEdge]) -> str:
    """Serialize node or edge for storage"""
    if hasattr(obj, 'to_gremlin_properties'):
        return json.dumps(obj.to_gremlin_properties(), default=str, ensure_ascii=False)
    else:
        return json.dumps(obj.__dict__, default=str, ensure_ascii=False) 