from __future__ import annotations
#!/usr/bin/env python3
"""
Graph Operations for Confluence Knowledge Graph
Handles all Gremlin database operations with Azure Cosmos DB
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import json

# Gremlin for Azure Cosmos DB
from gremlin_python.driver import client, serializer
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import T, Order, Scope

from common.config import GraphConfig, NodeTypes, EdgeTypes
from common.graph_models import BaseNode, BaseEdge, PageNode, SpaceNode, LinkNode

__all__ = [
    'GraphOperations',
    'get_children_ids',
    'get_sibling_ids',
    'get_adjacent_ids',
    'get_graph_props'
]

# Export helper functions for Flask/FastAPI
def get_children_ids(graph_ops: GraphOperations, page_id: str) -> list[str]:
    """Helper function wrapper for get_children_ids"""
    return graph_ops.get_children_ids(page_id)

def get_sibling_ids(graph_ops: GraphOperations, page_id: str) -> list[str]:
    """Helper function wrapper for get_sibling_ids"""
    return graph_ops.get_sibling_ids(page_id)

def get_adjacent_ids(graph_ops: GraphOperations, page_id: str) -> list[str]:
    """Helper function wrapper for get_adjacent_ids"""
    return graph_ops.get_adjacent_ids(page_id)

def get_graph_props(graph_ops: GraphOperations, page_id: str) -> dict[str, Any]:
    """Helper function wrapper for get_graph_props"""
    return graph_ops.get_graph_props(page_id)

class GraphOperations:
    """Core graph operations for Azure Cosmos DB Gremlin API"""
    
    def __init__(self, config: GraphConfig):
        """Initialize graph operations with configuration"""
        self.config = config
        self.client: Optional[Any] = None  # gremlin_python.driver.client.Client
        self.g = None
        self._connection_info = None
        self._stats = {
            'operations_count': 0,
            'nodes_created': 0,
            'edges_created': 0,
            'nodes_updated': 0,
            'edges_updated': 0,
            'queries_executed': 0,
            'errors_count': 0
        }
    
    def connect(self) -> bool:
        """Establish connection to Cosmos DB Gremlin API"""
        try:
            # Build connection string
            connection_string = (
                f"wss://{self.config.cosmos_endpoint.replace('https://', '').rstrip('/')}"
                f"/gremlin"
            )
            
            # Initialize Gremlin client without explicit event loop
            # This should use the default event loop from the current context
            self.client = client.Client(
                connection_string,
                'g',
                username=f"/dbs/{self.config.cosmos_database}/colls/{self.config.cosmos_container}",
                password=self.config.cosmos_key,
                message_serializer=serializer.GraphSONSerializersV2d0()
            )
            
            # Test connection using synchronous method to avoid event loop conflicts
            test_result = self.client.submit("g.V().limit(1).count()").all().result()
            print(f"✅ Connected to Cosmos DB. Current vertex count: {test_result[0] if test_result else 0}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to Cosmos DB: {e}")
            self._stats['errors_count'] += 1
            return False
    
    def disconnect(self) -> None:
        """Close connection to Cosmos DB"""
        if self.client:
            try:
                self.client.close()
                print("🔌 Disconnected from Cosmos DB")
            except Exception as e:
                print(f"⚠️ Error during disconnect: {e}")
    
    async def create_node(self, node: BaseNode) -> bool:
        """Create or update a single node"""
        try:
            # Convert node to properties
            props = node.to_gremlin_properties()
            node_id = props.pop('id')
            label = props.pop('label')
            
            # TODO: PARTITION_KEY_FIX - Current workaround for Cosmos DB partition key requirements
            # Future improvement: Recreate Cosmos DB without partition key constraints for simpler graph operations
            # This is a temporary fix to handle the "Cannot add vertex with null partition key" error
            
            # PARTITION_KEY_FIX: Set pageId as partition key property for Cosmos DB compatibility
            if 'pageId' not in props:
                props['pageId'] = node_id  # Use vertex ID as partition key value
            
            # Build Gremlin query for upsert with proper partition key handling
            query_parts = [f"g.V('{node_id}').fold()"]
            # PARTITION_KEY_FIX: Use addV without explicit partition key property setting
            query_parts.append(f".coalesce(unfold(), addV('{label}').property('id', '{node_id}').property('pageId', '{node_id}'))")
            
            # Add properties with proper type handling
            for key, value in props.items():
                if value is not None and key != 'pageId':  # PARTITION_KEY_FIX: Skip pageId as it's already set
                    if isinstance(value, str):
                        escaped_value = self._escape_string(value)
                        query_parts.append(f".property('{key}', '{escaped_value}')")
                    elif isinstance(value, bool):
                        query_parts.append(f".property('{key}', {str(value).lower()})")
                    elif isinstance(value, (int, float)):
                        query_parts.append(f".property('{key}', {value})")
                    else:
                        # Convert complex types to JSON strings
                        json_value = json.dumps(value, default=str)
                        escaped_json = self._escape_string(json_value)
                        query_parts.append(f".property('{key}', '{escaped_json}')")
            
            query = "".join(query_parts)
            
            # Execute query
            result = await self.client.submit(query).all()
            
            self._stats['operations_count'] += 1
            if result:
                self._stats['nodes_created'] += 1
                return True
            else:
                self._stats['nodes_updated'] += 1
                return True
                
        except Exception as e:
            print(f"❌ Error creating node {node.id}: {e}")
            self._stats['errors_count'] += 1
            return False
    
    async def create_edge(self, edge: BaseEdge) -> bool:
        """Create or update a single edge"""
        try:
            # Get edge properties
            props = edge.to_gremlin_properties()
            
            # Build Gremlin query for edge upsert
            query_parts = [
                f"g.V('{edge.from_id}').as('from')",
                f".V('{edge.to_id}').as('to')",
                f".coalesce(",
                f"  __.select('from').outE('{edge.label}').where(inV().as('to')),",
                f"  __.select('from').addE('{edge.label}').to('to')",
                f")"
            ]
            
            # Add properties to edge
            for key, value in props.items():
                if value is not None:
                    if isinstance(value, str):
                        query_parts.append(f".property('{key}', '{self._escape_string(value)}')")
                    elif isinstance(value, (int, float, bool)):
                        query_parts.append(f".property('{key}', {value})")
                    else:
                        json_value = json.dumps(value, default=str)
                        query_parts.append(f".property('{key}', '{self._escape_string(json_value)}')")
            
            query = "".join(query_parts)
            
            # Execute query
            result = await self.client.submit(query).all()
            
            self._stats['operations_count'] += 1
            self._stats['edges_created'] += 1
            return True
                
        except Exception as e:
            print(f"❌ Error creating edge {edge.from_id} -> {edge.to_id}: {e}")
            self._stats['errors_count'] += 1
            return False
    
    async def batch_create_nodes(self, nodes: List[BaseNode], batch_size: Optional[int] = None) -> Dict[str, int]:
        """Create multiple nodes in batches"""
        batch_size = batch_size or self.config.batch_size
        results = {'success': 0, 'failed': 0}
        
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            print(f"📦 Processing node batch {i//batch_size + 1}/{(len(nodes) + batch_size - 1)//batch_size}")
            
            for node in batch:
                if await self.create_node(node):
                    results['success'] += 1
                else:
                    results['failed'] += 1
            
            # Small delay between batches to avoid throttling
            if i + batch_size < len(nodes):
                time.sleep(0.1)
        
        return results
    
    async def batch_create_edges(self, edges: List[BaseEdge], batch_size: Optional[int] = None) -> Dict[str, int]:
        """Create multiple edges in batches"""
        batch_size = batch_size or self.config.batch_size
        results = {'success': 0, 'failed': 0}
        
        for i in range(0, len(edges), batch_size):
            batch = edges[i:i + batch_size]
            print(f"🔗 Processing edge batch {i//batch_size + 1}/{(len(edges) + batch_size - 1)//batch_size}")
            
            for edge in batch:
                if await self.create_edge(edge):
                    results['success'] += 1
                else:
                    results['failed'] += 1
            
            # Small delay between batches
            if i + batch_size < len(edges):
                time.sleep(0.1)
        
        return results
    
    async def find_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Find a node by ID"""
        try:
            result = await self.client.submit(query).all()
            
            self._stats['queries_executed'] += 1
            
            if result:
                return result[0]
            return None
            
        except Exception as e:
            print(f"❌ Error finding node {node_id}: {e}")
            self._stats['errors_count'] += 1
            return None
    
    async def find_nodes_by_label(self, label: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Find nodes by label"""
        try:
            query = f"g.V().hasLabel('{label}').limit({limit}).valueMap()"
            result = await self.client.submit(query).all()
            
            self._stats['queries_executed'] += 1
            return result
            
        except Exception as e:
            print(f"❌ Error finding nodes by label {label}: {e}")
            self._stats['errors_count'] += 1
            return []
    
    async def find_edges_from_node(self, node_id: str, edge_label: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find all edges from a specific node"""
        try:
            if edge_label:
                query = f"g.V('{node_id}').outE('{edge_label}').valueMap()"
            else:
                query = f"g.V('{node_id}').outE().valueMap()"
            
            result = await self.client.submit(query).all()
            
            self._stats['queries_executed'] += 1
            return result
            
        except Exception as e:
            print(f"❌ Error finding edges from node {node_id}: {e}")
            self._stats['errors_count'] += 1
            return []
    
    async def get_node_hierarchy(self, node_id: str, max_depth: int = 5) -> Dict[str, Any]:
        """Get the complete hierarchy for a node (parents and children)"""
        try:
            # Get parents (recursive up)
            parent_query = f"""
            g.V('{node_id}').repeat(
                out('ChildOf')
            ).until(
                outE('ChildOf').count().is(0)
            ).limit({max_depth}).path().by(elementMap())
            """
            
            # Get children (recursive down)
            children_query = f"""
            g.V('{node_id}').repeat(
                out('ParentOf')
            ).until(
                outE('ParentOf').count().is(0)
            ).limit({max_depth}).path().by(elementMap())
            """
            
            parents = await self.client.submit(parent_query).all()
            children = await self.client.submit(children_query).all()
            
            self._stats['queries_executed'] += 2
            
            return {
                'node_id': node_id,
                'parents': parents,
                'children': children,
                'hierarchy_depth': max(len(parents), len(children))
            }
            
        except Exception as e:
            print(f"❌ Error getting hierarchy for node {node_id}: {e}")
            self._stats['errors_count'] += 1
            return {'node_id': node_id, 'parents': [], 'children': [], 'hierarchy_depth': 0}
    
    async def find_related_pages(self, node_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """Find pages related through various relationships"""
        try:
            query = f"""
            g.V('{node_id}').repeat(
                both('LinksTo', 'LinkedFrom', 'ParentOf', 'ChildOf')
            ).times({depth}).dedup().hasLabel('Page').limit(50).elementMap()
            """
            
            result = await self.client.submit(query).all()
            
            self._stats['queries_executed'] += 1
            return result
            
        except Exception as e:
            print(f"❌ Error finding related pages for {node_id}: {e}")
            self._stats['errors_count'] += 1
            return []
    
    async def get_space_statistics(self, space_key: str) -> Dict[str, Any]:
        """Get comprehensive statistics for a space"""
        try:
            # Pages count in space
            pages_query = f"g.V('{space_key}').out('Contains').hasLabel('Page').count()"
            pages_count = self.client.submit(pages_query).all().result()[0]
            
            # Links count (internal and external)
            links_query = f"g.V('{space_key}').out('Contains').outE('LinksTo').count()"
            links_count = (await self.client.submit(links_query).all())[0]
            
            # Tables count
            tables_query = f"g.V('{space_key}').out('Contains').hasLabel('Page').values('tables_count').sum()"
            tables_count = self.client.submit(tables_query).all().result()[0] if self.client.submit(tables_query).all().result() else 0
            
            # Total content length
            content_query = f"g.V('{space_key}').out('Contains').hasLabel('Page').values('text_length').sum()"
            content_length = (await self.client.submit(content_query).all())[0] if await self.client.submit(content_query).all() else 0
            
            self._stats['queries_executed'] += 4
            
            return {
                'space_key': space_key,
                'pages_count': pages_count,
                'links_count': links_count,
                'tables_count': tables_count,
                'total_content_length': content_length,
                'average_page_length': content_length / pages_count if pages_count > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Error getting space statistics for {space_key}: {e}")
            self._stats['errors_count'] += 1
            return {'space_key': space_key, 'error': str(e)}
    
    async def get_graph_statistics(self) -> Dict[str, Any]:
        """Get overall graph statistics"""
        try:
            # Node counts by type
            pages_count = await self.client.submit("g.V().hasLabel('Page').count()").all()
            spaces_count = await self.client.submit("g.V().hasLabel('Space').count()").all()
            links_count = await self.client.submit("g.V().hasLabel('Link').count()").all()
            
            # Edge counts by type
            hierarchy_edges = await self.client.submit("g.E().hasLabel('ParentOf').count()").all()
            link_edges = await self.client.submit("g.E().hasLabel('LinksTo').count()").all()
            space_edges = await self.client.submit("g.E().hasLabel('BelongsTo').count()").all()
            
            # Total counts
            total_nodes = await self.client.submit("g.V().count()").all()
            total_edges = await self.client.submit("g.E().count()").all()
            
            self._stats['queries_executed'] += 7
            
            return {
                'nodes': {
                    'total': total_nodes,
                    'pages': pages_count,
                    'spaces': spaces_count,
                    'links': links_count
                },
                'edges': {
                    'total': total_edges,
                    'hierarchy': hierarchy_edges,
                    'links': link_edges,
                    'space_membership': space_edges
                },
                'operations_stats': self._stats.copy(),
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error getting graph statistics: {e}")
            self._stats['errors_count'] += 1
            return {'error': str(e), 'operations_stats': self._stats.copy()}
    
    async def validate_graph_integrity(self) -> Dict[str, Any]:
        """Validate graph integrity and find issues"""
        issues = []
        
        try:
            # Find orphaned nodes (nodes without any edges)
            orphaned_query = "g.V().where(bothE().count().is(0)).elementMap()"
            orphaned_nodes = await self.client.submit(orphaned_query).all()
            
            # Find dangling edges (edges pointing to non-existent nodes)
            dangling_edges_query = """
            g.E().as('e').inV().as('in').select('e').outV().as('out')
            .select('e').where(
                select('in').count().is(0).or().select('out').count().is(0)
            ).elementMap()
            """
            
            # Find duplicate edges (same from, to, label)
            duplicate_edges_query = """
            g.E().group().by(
                project('from', 'to', 'label').by(outV().id()).by(inV().id()).by(label())
            ).unfold().where(select(values).count(local).is(gt(1)))
            """
            
            self._stats['queries_executed'] += 2
            
            if orphaned_nodes:
                issues.append({
                    'type': 'orphaned_nodes',
                    'count': len(orphaned_nodes),
                    'samples': orphaned_nodes[:5]
                })
            
            return {
                'valid': len(issues) == 0,
                'issues_found': len(issues),
                'issues': issues,
                'validation_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error validating graph integrity: {e}")
            self._stats['errors_count'] += 1
            return {
                'valid': False,
                'error': str(e),
                'validation_timestamp': datetime.utcnow().isoformat()
            }
    
    def cleanup_orphaned_nodes(self) -> int:
        """Remove orphaned nodes (nodes with no relationships)"""
        try:
            # Find and delete orphaned nodes
            query = "g.V().where(bothE().count().is(0)).drop()"
            result = self.client.submit(query).all().result()
            
            self._stats['operations_count'] += 1
            print(f"🧹 Cleaned up orphaned nodes")
            
            return len(result) if result else 0
            
        except Exception as e:
            print(f"❌ Error cleaning up orphaned nodes: {e}")
            self._stats['errors_count'] += 1
            return 0
    
    def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its edges"""
        try:
            query = f"g.V('{node_id}').drop()"
            self.client.submit(query).all().result()
            
            self._stats['operations_count'] += 1
            return True
            
        except Exception as e:
            print(f"❌ Error deleting node {node_id}: {e}")
            self._stats['errors_count'] += 1
            return False
    
    def _escape_string(self, value: str) -> str:
        """Escape string for Gremlin query"""
        return value.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
    
    def get_operations_stats(self) -> Dict[str, Any]:
        """Get current operations statistics"""
        return self._stats.copy()
    
    def reset_stats(self) -> None:
        """Reset operations statistics"""
        self._stats = {
            'operations_count': 0,
            'nodes_created': 0,
            'edges_created': 0,
            'nodes_updated': 0,
            'edges_updated': 0,
            'queries_executed': 0,
            'errors_count': 0
        }
    
    def add_metrics_to_pages(self) -> Dict[str, int]:
        """Add graph metrics to existing Page nodes"""
        print("📊 Adding metrics to Page nodes...")
        
        results = {'updated': 0, 'failed': 0, 'total': 0}
        
        try:
            # Get all pages with true flag to get id as value not list
            query = "g.V().hasLabel('Page').valueMap(true)"
            pages = self.client.submit(query).all().result()
            results['total'] = len(pages)
            
            print(f"Found {len(pages)} pages to update with metrics")
            
            for i, page in enumerate(pages):
                # Get id (direct value) and title (in list)
                page_id = page.get('id')
                title_value = page.get('title', [])
                
                title = title_value[0] if title_value else 'Unknown'
                
                if not page_id:
                    results['failed'] += 1
                    continue
                
                # Calculate simple metrics based on title patterns
                hierarchy_depth, child_count, centrality = self._calculate_page_metrics(title)
                
                # Update the node with metrics
                update_query = f"""
                g.V('{page_id}')
                 .property('hierarchy_depth', {hierarchy_depth})
                 .property('child_count', {child_count})
                 .property('graph_centrality_score', {centrality})
                """
                
                try:
                    self.client.submit(update_query).all().result()
                    results['updated'] += 1
                    self._stats['nodes_updated'] += 1
                    
                    if (i + 1) % 5 == 0:  # Progress indicator
                        print(f"  Progress: {i + 1}/{len(pages)} pages updated...")
                        
                except Exception as e:
                    print(f"  ⚠️ Failed to update '{title[:30]}...': {e}")
                    results['failed'] += 1
                    self._stats['errors_count'] += 1
            
            # Verify metrics were added
            verify_query = """
            g.V().hasLabel('Page')
             .has('hierarchy_depth')
             .has('child_count')
             .has('graph_centrality_score')
             .count()
            """
            verified_count = self.client.submit(verify_query).all().result()[0]
            
            print(f"\n✅ Metrics update complete:")
            print(f"   - Total pages: {results['total']}")
            print(f"   - Successfully updated: {results['updated']}")
            print(f"   - Failed: {results['failed']}")
            print(f"   - Verified with metrics: {verified_count}")
            
            self._stats['queries_executed'] += len(pages) + 2
            
        except Exception as e:
            print(f"❌ Error adding metrics: {e}")
            self._stats['errors_count'] += 1
            results['error'] = str(e)
        
        return results
    
    def _calculate_page_metrics(self, title: str) -> Tuple[int, int, float]:
        """Calculate simple metrics based on page title patterns"""
        title_lower = title.lower()
        
        # Hierarchy depth based on title patterns
        if any(word in title_lower for word in ['overview', 'index', 'home', 'introduction']):
            hierarchy_depth = 0
            child_count = 5
            centrality = 0.045
        elif any(word in title_lower for word in ['guide', 'setup', 'installation', 'getting started']):
            hierarchy_depth = 1
            child_count = 3
            centrality = 0.032
        elif any(word in title_lower for word in ['configuration', 'api', 'reference']):
            hierarchy_depth = 1
            child_count = 2
            centrality = 0.025
        elif any(word in title_lower for word in ['troubleshooting', 'faq', 'examples']):
            hierarchy_depth = 2
            child_count = 0
            centrality = 0.015
        else:
            # Default for detail pages
            hierarchy_depth = 2
            child_count = 0
            centrality = 0.008
        
        return hierarchy_depth, child_count, round(centrality, 6)

    # === helper façade used by WebApi Skill & AutoGen ===
    def get_children_ids(self, page_id: str) -> list[str]:
        """
        Returns direct children IDs only.
        """
        query = f"g.V('{page_id}').out('ParentOf').values('id')"
        return [x for x in self.client.submit(query).all().result()]

    def get_sibling_ids(self, page_id: str) -> list[str]:
        """
        Returns sibling IDs (pages with same parent).
        """
        query = (
          f"g.V('{page_id}').out('ChildOf')"
          ".in('ChildOf').values('id').where(neq('{page_id}'))"
        )
        return [x for x in self.client.submit(query).all().result()]

    def get_adjacent_ids(self, page_id: str) -> list[str]:
        """
        Returns parent + children + siblings (1-hop) IDs.
        """
        query = (
           f"g.V('{page_id}')"  # Use vertex ID directly instead of property lookup
           ".both('ParentOf','ChildOf').values('id').dedup()"  # Use 'id' instead of 'page_id'
        )
        return [row for row in self.client.submit(query).all().result()]

    def get_graph_props(self, page_id: str) -> dict[str, Any]:
        """
        Fetch hierarchy_depth, graph_centrality_score already stored on the vertex;
        fallback to 0 if null.
        """
        query = (
          f"g.V('{page_id}')"  # Use vertex ID directly
          ".project('parent_page_id','hierarchy_depth','graph_centrality_score')"
          ".by(values('parent_page_id').fold().coalesce(unfold(),constant('')))"  # Get parent_page_id property
          ".by(values('hierarchy_depth').fold().coalesce(unfold(),constant(0)))"
          ".by(values('graph_centrality_score').fold().coalesce(unfold(),constant(0)))"
        )
        res = self.client.submit(query).all().result()
        return res[0] if res else {} 