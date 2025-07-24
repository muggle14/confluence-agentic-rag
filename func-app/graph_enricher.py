"""
Graph Enricher for Confluence embeddings.
Integrates with Cosmos DB graph to provide enhanced context and relationships.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
import json
from datetime import datetime
import os
import sys

# Add parent directory to path to import notebooks modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from gremlin_python.driver import client, serializer
    from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
    from gremlin_python.process.anonymous_traversal import traversal
    from gremlin_python.process.graph_traversal import __
    from gremlin_python.process.traversal import T, P, Order
    GREMLIN_AVAILABLE = True
except ImportError:
    GREMLIN_AVAILABLE = False
    logging.warning("Gremlin Python not available. Graph enrichment will be disabled.")

# Import from notebooks for graph compatibility
from notebooks.config import GraphConfig

# Keep original imports commented for reference
# from .config import EmbeddingConfig
# from .models import (
#     RetrievalResult, PageContext, ChunkType, ProcessingStats
# )

logger = logging.getLogger(__name__)

class GraphEnricher:
    """Enhances search results with graph-based context and relationships."""
    
    def __init__(self, config: GraphConfig):
        self.config = config
        self.client = None
        self.g = None
        self.stats = {'queries': 0, 'enriched': 0, 'errors': 0}
        
        if GREMLIN_AVAILABLE:
            self._initialize_graph_connection()
        else:
            logger.warning("Graph enrichment disabled - gremlin_python not available")
    
    @classmethod
    def from_env(cls) -> 'GraphEnricher':
        """Create GraphEnricher from environment variables."""
        config = GraphConfig.from_environment()
        return cls(config)
    
    def _initialize_graph_connection(self):
        """Initialize connection to Cosmos DB Gremlin API."""
        try:
            # Use the Gremlin endpoint format from notebooks config
            # The cosmos_endpoint in GraphConfig is already in the correct format
            connection_string = (
                f"wss://{self.config.cosmos_endpoint.replace('https://', '').rstrip('/')}"
                f"/gremlin"
            )
            
            # Create connection using same pattern as notebooks
            self.client = client.Client(
                connection_string,
                'g',
                username=f"/dbs/{self.config.cosmos_database}/colls/{self.config.cosmos_container}",
                password=self.config.cosmos_key,
                message_serializer=serializer.GraphSONSerializersV2d0()
            )
            
            logger.info(f"Graph connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize graph connection: {e}")
            self.client = None
            self.g = None
    
    async def enrich_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich page data with graph relationships from Cosmos DB.
        This method wraps enrich_page_context for Azure Function compatibility.
        
        Args:
            data: Page data with at minimum page_id
            
        Returns:
            Enriched data with graph metadata
        """
        return await self.enrich_page_context(data)
    
    async def enrich_page_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich page data with graph-based relationships.
        
        Args:
            data: Page data dictionary with at minimum page_id
            
        Returns:
            Enhanced page data with graph metadata
        """
        logger.info(f"ENRICHER: Starting enrich_page_context with data: {data}")
        page_id = data.get('page_id')
        logger.info(f"ENRICHER: page_id extracted: {page_id}")
        logger.info(f"ENRICHER: _is_available(): {self._is_available()}")
        logger.info(f"ENRICHER: client status: {self.client}")
        logger.info(f"ENRICHER: GREMLIN_AVAILABLE: {GREMLIN_AVAILABLE}")
        
        # FORCE EXECUTION - Remove conditional checks
        # if not page_id or not self._is_available():
        #     return data
        
        try:
            logger.info(f"ENRICHER: Starting enrichment for page: {page_id}")
            
            # Get page relationships - FORCE EXECUTION
            logger.info("ENRICHER: Getting ancestors...")
            ancestors = await self._get_page_ancestors(page_id)
            logger.info(f"ENRICHER: Got {len(ancestors)} ancestors: {ancestors}")
            
            logger.info("ENRICHER: Getting children...")
            children = await self._get_page_children(page_id)
            logger.info(f"ENRICHER: Got {len(children)} children: {children}")
            
            logger.info("ENRICHER: Getting siblings...")
            siblings = await self._get_page_siblings(page_id)
            logger.info(f"ENRICHER: Got {len(siblings)} siblings: {siblings}")
            
            logger.info("ENRICHER: Getting related pages...")
            related_pages = await self._get_related_pages(page_id)
            logger.info(f"ENRICHER: Got {len(related_pages)} related pages: {related_pages}")
            
            # Build breadcrumb
            logger.info("ENRICHER: Building breadcrumb...")
            breadcrumb = [ancestor.get('title', '') for ancestor in ancestors]
            if data.get('title'):
                breadcrumb.append(data['title'])
            logger.info(f"ENRICHER: Breadcrumb: {breadcrumb}")
            
            # Calculate hierarchy depth
            hierarchy_depth = len(ancestors)
            logger.info(f"ENRICHER: Hierarchy depth: {hierarchy_depth}")
            
            # Calculate centrality score
            base_confidence = data.get('confidence', 0.5)
            logger.info(f"ENRICHER: Base confidence: {base_confidence}")
            centrality_score = self._calculate_enhanced_confidence(
                base_confidence,
                ancestors,
                children,
                related_pages
            )
            logger.info(f"ENRICHER: Centrality score: {centrality_score}")
            
            # Build enriched data
            enriched = {
                # Original data
                **data,
                # Graph-derived fields
                "hierarchy_depth": hierarchy_depth,
                "hierarchy_path": " > ".join(breadcrumb),
                "breadcrumb": json.dumps(breadcrumb),  # Store as JSON string for indexer
                "parent_page_id": ancestors[-1]['id'] if ancestors else None,
                "parent_page_title": ancestors[-1]['title'] if ancestors else None,
                "has_children": len(children) > 0,
                "child_count": len(children),
                "sibling_count": len(siblings),
                "related_page_count": len(related_pages),
                "graph_centrality_score": centrality_score,
                # Additional metadata
                "graph_metadata": json.dumps({
                    "ancestors": ancestors,
                    "children": [{"id": c['id'], "title": c['title']} for c in children[:5]],  # Limit to 5
                    "siblings": [{"id": s['id'], "title": s['title']} for s in siblings[:5]],
                    "related_pages": [{"id": r['id'], "title": r['title']} for r in related_pages[:5]]
                })
            }
            
            logger.info(f"ENRICHER: Enrichment complete. Original keys: {list(data.keys())}")
            logger.info(f"ENRICHER: Enriched keys: {list(enriched.keys())}")
            logger.info(f"ENRICHER: New fields added: {set(enriched.keys()) - set(data.keys())}")
            logger.info(f"ENRICHER: Final enriched data: {enriched}")
            
            self.stats['enriched'] += 1
            return enriched
            
        except Exception as e:
            logger.error(f"Failed to enrich page {page_id}: {e}")
            self.stats['errors'] += 1
            # Return original data if enrichment fails
            return data
    
    async def _get_page_ancestors(self, page_id: str) -> List[Dict[str, str]]:
        """Get ancestor pages (parent hierarchy)."""
        if not self._is_available():
            return []
        
        try:
            # Query for ancestors using ChildOf relationships (matching notebooks implementation)
            query = f"""
                g.V('{page_id}')
                .repeat(out('ChildOf'))
                .until(not(out('ChildOf')))
                .path()
                .by(valueMap('id', 'title', 'space_key'))
            """
            
            result = await self._execute_query(query)
            
            ancestors = []
            if result:
                # Extract path and reverse to get root->leaf order
                path_data = result[0] if result else []
                
                for node_data in reversed(path_data[:-1]):  # Exclude the page itself
                    ancestors.append({
                        'id': str(node_data.get('id', [''])[0]),
                        'title': str(node_data.get('title', [''])[0]),
                        'space_key': str(node_data.get('space_key', [''])[0])
                    })
            
            return ancestors
            
        except Exception as e:
            logger.error(f"Failed to get ancestors for {page_id}: {e}")
            return []
    
    async def _get_page_children(self, page_id: str) -> List[Dict[str, str]]:
        """Get direct child pages."""
        if not self._is_available():
            return []
        
        try:
            # Query using ParentOf relationship (matching notebooks implementation)
            query = f"""
                g.V('{page_id}')
                .out('ParentOf')
                .valueMap('id', 'title', 'space_key')
            """
            
            result = await self._execute_query(query)
            
            children = []
            for child_data in result:
                children.append({
                    'id': str(child_data.get('id', [''])[0]),
                    'title': str(child_data.get('title', [''])[0]),
                    'space_key': str(child_data.get('space_key', [''])[0])
                })
            
            return children
            
        except Exception as e:
            logger.error(f"Failed to get children for {page_id}: {e}")
            return []
    
    async def _get_page_siblings(self, page_id: str) -> List[Dict[str, str]]:
        """Get sibling pages (same parent)."""
        if not self._is_available():
            return []
        
        try:
            # Query using ChildOf/ParentOf relationships (matching notebooks implementation)
            query = f"""
                g.V('{page_id}')
                .out('ChildOf')
                .out('ParentOf')
                .where(neq('{page_id}'))
                .valueMap('id', 'title', 'space_key')
                .limit(10)
            """
            
            result = await self._execute_query(query)
            
            siblings = []
            for sibling_data in result:
                siblings.append({
                    'id': str(sibling_data.get('id', [''])[0]),
                    'title': str(sibling_data.get('title', [''])[0]),
                    'space_key': str(sibling_data.get('space_key', [''])[0])
                })
            
            return siblings
            
        except Exception as e:
            logger.error(f"Failed to get siblings for {page_id}: {e}")
            return []
    
    async def _get_related_pages(self, page_id: str) -> List[Dict[str, str]]:
        """Get related pages through links and references."""
        if not self._is_available():
            return []
        
        try:
            # Get pages that link to this page or are linked from this page
            # Using LinksTo/LinkedFrom relationships (matching notebooks implementation)
            query = f"""
                g.V('{page_id}')
                .union(
                    out('LinksTo').limit(5),
                    in('LinksTo').limit(5),
                    out('LinkedFrom').limit(5),
                    in('LinkedFrom').limit(5)
                )
                .dedup()
                .valueMap('id', 'title', 'space_key')
            """
            
            result = await self._execute_query(query)
            
            related = []
            for related_data in result:
                related.append({
                    'id': str(related_data.get('id', [''])[0]),
                    'title': str(related_data.get('title', [''])[0]),
                    'space_key': str(related_data.get('space_key', [''])[0])
                })
            
            return related
            
        except Exception as e:
            logger.error(f"Failed to get related pages for {page_id}: {e}")
            return []
    
    def _calculate_enhanced_confidence(self, 
                                     base_confidence: float,
                                     ancestors: List[Dict[str, str]],
                                     children: List[Dict[str, str]],
                                     related_pages: List[Dict[str, str]]) -> float:
        """
        Calculate enhanced confidence based on graph relationships.
        
        Args:
            base_confidence: Original confidence score
            ancestors: List of ancestor pages
            children: List of child pages
            related_pages: List of related pages
            
        Returns:
            Enhanced confidence score
        """
        # Boost confidence based on rich graph context
        boost_factor = 1.0
        
        # Boost for having ancestors (shows page is part of hierarchy)
        if ancestors:
            boost_factor += 0.05 * min(len(ancestors), 3)
        
        # Boost for having children (shows page is a hub)
        if children:
            boost_factor += 0.03 * min(len(children), 5)
        
        # Boost for having related pages (shows page is well-connected)
        if related_pages:
            boost_factor += 0.02 * min(len(related_pages), 5)
        
        # Cap the boost to prevent over-inflation
        boost_factor = min(boost_factor, 1.2)
        
        enhanced_confidence = base_confidence * boost_factor
        return min(enhanced_confidence, 1.0)  # Cap at 1.0
    
    async def get_page_breadcrumb(self, page_id: str) -> List[str]:
        """
        Get breadcrumb path for a page.
        
        Args:
            page_id: Page ID
            
        Returns:
            List of page titles from root to current page
        """
        ancestors = await self._get_page_ancestors(page_id)
        breadcrumb = [ancestor['title'] for ancestor in ancestors]
        
        # Add current page title
        try:
            query = f"g.V('{page_id}').valueMap('title')"
            result = await self._execute_query(query)
            if result:
                current_title = str(result[0].get('title', [''])[0])
                breadcrumb.append(current_title)
        except:
            pass
        
        return breadcrumb
    
    async def find_path_between_pages(self, 
                                    source_page_id: str, 
                                    target_page_id: str,
                                    max_hops: int = 4) -> Optional[List[Dict[str, str]]]:
        """
        Find shortest path between two pages.
        
        Args:
            source_page_id: Source page ID
            target_page_id: Target page ID
            max_hops: Maximum number of hops to search
            
        Returns:
            Path as list of page info or None if no path found
        """
        if not self._is_available():
            return None
        
        try:
            query = f"""
                g.V('{source_page_id}')
                .repeat(
                    union(out('parent'), in('parent'), out('links_to'), in('links_to'))
                    .simplePath()
                )
                .until(hasId('{target_page_id}').or().loops().is(gt({max_hops})))
                .hasId('{target_page_id}')
                .path()
                .by(valueMap('id', 'title'))
                .limit(1)
            """
            
            result = await self._execute_query(query)
            
            if result:
                path_data = result[0]
                path = []
                for node_data in path_data:
                    path.append({
                        'id': str(node_data.get('id', [''])[0]),
                        'title': str(node_data.get('title', [''])[0])
                    })
                return path
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to find path between {source_page_id} and {target_page_id}: {e}")
            return None
    
    async def get_popular_pages(self, space_key: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most popular pages based on incoming link count.
        
        Args:
            space_key: Optional space filter
            limit: Number of pages to return
            
        Returns:
            List of popular page info with link counts
        """
        if not self._is_available():
            return []
        
        try:
            if space_key:
                query = f"""
                    g.V()
                    .has('space_key', '{space_key}')
                    .project('page', 'link_count')
                    .by(valueMap('id', 'title', 'space_key'))
                    .by(inE('links_to').count())
                    .order().by(select('link_count'), desc)
                    .limit({limit})
                """
            else:
                query = f"""
                    g.V()
                    .project('page', 'link_count')
                    .by(valueMap('id', 'title', 'space_key'))
                    .by(inE('links_to').count())
                    .order().by(select('link_count'), desc)
                    .limit({limit})
                """
            
            result = await self._execute_query(query)
            
            popular_pages = []
            for item in result:
                page_data = item.get('page', {})
                link_count = item.get('link_count', 0)
                
                popular_pages.append({
                    'id': str(page_data.get('id', [''])[0]),
                    'title': str(page_data.get('title', [''])[0]),
                    'space_key': str(page_data.get('space_key', [''])[0]),
                    'link_count': int(link_count)
                })
            
            return popular_pages
            
        except Exception as e:
            logger.error(f"Failed to get popular pages: {e}")
            return []
    
    async def _execute_query(self, query: str) -> List[Any]:
        """Execute Gremlin query and return results."""
        if not self.client:
            return []
        
        try:
            # Execute synchronously since we're using the same client pattern as notebooks
            result = self.client.submit(query).all().result()
            self.stats['queries'] += 1
            return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            self.stats['errors'] += 1
            return []
    
    def _is_available(self) -> bool:
        """Check if graph enrichment is available."""
        return GREMLIN_AVAILABLE and self.client is not None
    
    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = {'queries': 0, 'enriched': 0, 'errors': 0}
    
    def close(self):
        """Close graph connections."""
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logger.error(f"Error closing graph connection: {e}")

async def create_graph_enricher(config: GraphConfig) -> GraphEnricher:
    """
    Factory function to create a graph enricher.
    
    Args:
        config: Graph configuration from notebooks
        
    Returns:
        Graph enricher instance
    """
    enricher = GraphEnricher(config)
    
    if enricher._is_available():
        logger.info("Graph enricher created and ready")
    else:
        logger.warning("Graph enricher created but disabled (missing dependencies or connection)")
    
    return enricher
