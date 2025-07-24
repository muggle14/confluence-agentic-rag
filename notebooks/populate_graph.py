#!/usr/bin/env python3
"""
Main Graph Population Script for Confluence Knowledge Graph
Orchestrates the conversion of processed content into a comprehensive knowledge graph
"""

import os
import sys
import json
import time
import asyncio
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import traceback


# Azure Storage
from azure.storage.blob import BlobServiceClient

# Local imports
from common.config import GraphConfig, ContainerNames, NodeTypes, EdgeTypes
from common.graph_models import (
    PageNode, SpaceNode, LinkNode, 
    GraphModelFactory, validate_node_data
)
from common.graph_operations import GraphOperations
from common.graph_metrics import GraphMetrics
from notebooks.utils import ProgressTracker, DataValidator, GraphAnalyzer


class GraphPopulator:
    """Main class for populating the Confluence knowledge graph"""
    
    def __init__(self, config: GraphConfig):
        """Initialize graph populator with configuration"""
        self.config = config
        self.graph_ops = GraphOperations(config)
        self.blob_service = BlobServiceClient.from_connection_string(config.storage_connection_string)
        self.factory = GraphModelFactory()
        
        # Tracking and statistics
        self.progress = ProgressTracker()
        self.validator = DataValidator()
        self.analyzer = GraphAnalyzer()
        
        # Runtime state
        self.spaces_cache: Dict[str, SpaceNode] = {}
        self.processed_pages: Set[str] = set()
        self.link_nodes_cache: Dict[str, LinkNode] = {}
        
        # Statistics
        self.stats = {
            'start_time': None,
            'end_time': None,
            'pages_processed': 0,
            'spaces_created': 0,
            'links_created': 0,
            'edges_created': 0,
            'errors_count': 0,
            'warnings_count': 0,
            'processing_time_seconds': 0
        }
    
    @classmethod
    def from_environment(cls, env_file: Optional[str] = None) -> 'GraphPopulator':
        """Create GraphPopulator from environment configuration"""
        config = GraphConfig.from_environment(env_file)
        return cls(config)
    
    def populate_all(self, container_name: str = ContainerNames.PROCESSED) -> Dict[str, Any]:
        """Populate graph with all processed pages"""
        print("🚀 Starting complete graph population")
        print("=" * 60)
        
        self.stats['start_time'] = datetime.utcnow()
        
        try:
            # Connect to graph database
            if not self._connect_to_graph():
                return self._create_error_result("Failed to connect to graph database")
            
            # Load all processed pages
            processed_pages = self._load_processed_pages(container_name)
            if not processed_pages:
                return self._create_error_result("No processed pages found")
            
            print(f"📊 Found {len(processed_pages)} processed pages")
            
            # Phase 1: Create space nodes
            self._create_space_nodes(processed_pages)
            
            # Phase 2: Create page nodes
            self._create_page_nodes(processed_pages)
            
            # Phase 3: Create link nodes (for external links)
            if self.config.create_link_nodes:
                self._create_link_nodes(processed_pages)
            
            # Phase 4: Create relationships
            self._create_relationships(processed_pages)

            # Phase 5: Compute metrics
            if os.getenv("GRAPH_COMPUTE_METRICS", "true").lower() == "true":
                gm = GraphMetrics(self.config)
                gm.run_all()            
            
            # Phase 5: Validate and analyze
            # Create fresh event loop for async validation
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._validate_graph())
                loop.close()
            except Exception as e:
                print(f"⚠️ Graph validation failed: {e}")
                print("Continuing without validation...")
            
            # Final statistics
            self._finalize_stats()
            
            return self._create_success_result()
            
        except Exception as e:
            self.stats['errors_count'] += 1
            print(f"❌ Critical error during graph population: {e}")
            traceback.print_exc()
            return self._create_error_result(str(e))
        
        finally:
            self.graph_ops.disconnect()
    
    def populate_incremental(self, since: Optional[str] = None, container_name: str = ContainerNames.PROCESSED) -> Dict[str, Any]:
        """Populate graph with only changed pages since specified time"""
        print("🔄 Starting incremental graph population")
        print("=" * 60)
        
        self.stats['start_time'] = datetime.utcnow()
        
        # Determine cutoff time
        if since:
            cutoff_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
        else:
            # Default to last 24 hours
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        print(f"📅 Processing changes since: {cutoff_time.isoformat()}")
        
        try:
            # Connect to graph database
            if not self._connect_to_graph():
                return self._create_error_result("Failed to connect to graph database")
            
            # Load only changed pages
            changed_pages = self._load_changed_pages(container_name, cutoff_time)
            if not changed_pages:
                print("ℹ️ No changed pages found")
                return self._create_success_result()
            
            print(f"📊 Found {len(changed_pages)} changed pages")
            
            # Process changed pages
            self._process_changed_pages(changed_pages)
            
            # Update relationships for affected pages
            self._update_relationships(changed_pages)
            
            # Validate changes
            self._validate_incremental_changes(changed_pages)
            
            self._finalize_stats()
            
            return self._create_success_result()
            
        except Exception as e:
            self.stats['errors_count'] += 1
            print(f"❌ Critical error during incremental population: {e}")
            return self._create_error_result(str(e))
        
        finally:
            self.graph_ops.disconnect()
    
    def _connect_to_graph(self) -> bool:
        """Establish connection to graph database"""
        print("🔌 Connecting to Cosmos DB...")
        return self.graph_ops.connect()

    def _create_gremlin_node_query(self, node) -> str:
        """Create Gremlin query for node creation"""
        # Convert node to properties
        props = node.to_gremlin_properties()
        node_id = props.pop('id')
        label = props.pop('label')
        
        # Set partition key property for Cosmos DB compatibility
        PARTITION_KEY = getattr(self.config, "partition_key", "pageId")  # Configurable partition key
        if PARTITION_KEY not in props:
            props[PARTITION_KEY] = node_id
        
        # Build Gremlin query for upsert
        query_parts = [f"g.V('{node_id}').fold()"]
        query_parts.append(f".coalesce(unfold(), addV('{label}').property('id', '{node_id}').property('{PARTITION_KEY}', '{node_id}'))")
        
        # Add properties with proper type handling
        for key, value in props.items():
            if value is not None and key != PARTITION_KEY:
                if isinstance(value, str):
                    # Escape single quotes in strings
                    escaped_value = value.replace("'", "\\'")
                    query_parts.append(f".property('{key}', '{escaped_value}')")
                elif isinstance(value, bool):
                    query_parts.append(f".property('{key}', {str(value).lower()})")
                elif isinstance(value, (int, float)):
                    query_parts.append(f".property('{key}', {value})")
                else:
                    # Convert complex types to JSON strings
                    import json
                    json_value = json.dumps(value, default=str)
                    escaped_json = json_value.replace("'", "\\'")
                    query_parts.append(f".property('{key}', '{escaped_json}')")
        
        return "".join(query_parts)

    def _create_gremlin_edge_query(self, edge) -> str:
        """Create Gremlin query for edge creation"""
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
                    escaped_value = value.replace("'", "\\'")
                    query_parts.append(f".property('{key}', '{escaped_value}')")
                elif isinstance(value, (int, float, bool)):
                    query_parts.append(f".property('{key}', {value})")
                else:
                    import json
                    json_value = json.dumps(value, default=str)
                    escaped_json = json_value.replace("'", "\\'")
                    query_parts.append(f".property('{key}', '{escaped_json}')")
        
        return "".join(query_parts)
    
    def _load_processed_pages(self, container_name: str) -> List[Dict[str, Any]]:
        """Load all processed pages from storage"""
        print("📂 Loading processed pages from storage...")
        
        try:
            container_client = self.blob_service.get_container_client(container_name)
            blobs = list(container_client.list_blobs())
            
            processed_pages = []
            for blob in blobs:
                if blob.name.endswith('.json'):
                    try:
                        blob_client = container_client.get_blob_client(blob.name)
                        content = blob_client.download_blob().readall()
                        page_data = json.loads(content)
                        
                        # Validate data structure - must be dictionary with required fields
                        if not isinstance(page_data, dict):
                            raise ValueError(f"Data in {blob.name} is not a dictionary: {type(page_data)}")
                        
                        # Validate required fields exist
                        required_fields = ['page_id', 'title', 'space_key', 'spaceName']
                        missing_fields = [field for field in required_fields if field not in page_data]
                        if missing_fields:
                            raise ValueError(f"Missing required fields in {blob.name}: {missing_fields}")
                        
                        # Convert camelCase to snake_case for consistency
                        if 'spaceName' in page_data:
                            page_data['space_name'] = page_data.pop('spaceName')
                        
                        # Validate data types for critical fields
                        if not isinstance(page_data.get('page_id'), (str, int)):
                            raise ValueError(f"page_id in {blob.name} must be string or int, got {type(page_data.get('page_id'))}")
                        
                        if not isinstance(page_data.get('title'), str):
                            raise ValueError(f"title in {blob.name} must be string, got {type(page_data.get('title'))}")
                        
                        if not isinstance(page_data.get('space_key'), str):
                            raise ValueError(f"space_key in {blob.name} must be string, got {type(page_data.get('space_key'))}")
                        
                        # Validate and normalize links structure
                        if 'links' in page_data:
                            if not isinstance(page_data['links'], dict):
                                raise ValueError(f"links in {blob.name} must be dictionary, got {type(page_data['links'])}")
                            
                            expected_link_keys = ['all', 'internal', 'external']
                            for key in expected_link_keys:
                                if key not in page_data['links']:
                                    raise ValueError(f"links in {blob.name} missing required key: {key}")
                                
                                if not isinstance(page_data['links'][key], list):
                                    raise ValueError(f"links.{key} in {blob.name} must be list, got {type(page_data['links'][key])}")
                            
                            # Normalize links structure to list of dicts
                            page_data['links'] = self._normalize_links(page_data['links'])
                        
                        processed_pages.append(page_data)
                            
                    except Exception as e:
                        print(f"❌ Error loading {blob.name}: {e}")
                        self.stats['errors_count'] += 1
                        # Don't continue with invalid data - fail fast
                        raise
            
            return processed_pages
            
        except Exception as e:
            print(f"❌ Error loading processed pages: {e}")
            self.stats['errors_count'] += 1
            raise
    
    def _normalize_links(self, links_dict: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """Normalize links structure from dict to list of dicts"""
        normalized_links = []
        for link_type in ('internal', 'external'):
            for url_or_id in links_dict.get(link_type, []):
                normalized_links.append({
                    'type': link_type,
                    'url': url_or_id,
                    'text': url_or_id,  # Use URL/ID as text for now
                    'order': 0
                })
        return normalized_links
    
    def _load_changed_pages(self, container_name: str, since: datetime) -> List[Dict[str, Any]]:
        """Load only pages changed since specified time"""
        print(f"📂 Loading pages changed since {since.isoformat()}...")
        
        try:
            container_client = self.blob_service.get_container_client(container_name)
            blobs = list(container_client.list_blobs())
            
            changed_pages = []
            for blob in blobs:
                if blob.name.endswith('.json') and blob.last_modified >= since:
                    try:
                        blob_client = container_client.get_blob_client(blob.name)
                        content = blob_client.download_blob().readall()
                        page_data = json.loads(content)
                        
                        # Validate data structure - must be dictionary with required fields
                        if not isinstance(page_data, dict):
                            raise ValueError(f"Data in {blob.name} is not a dictionary: {type(page_data)}")
                        
                        # Validate required fields exist
                        required_fields = ['page_id', 'title', 'space_key', 'spaceName']
                        missing_fields = [field for field in required_fields if field not in page_data]
                        if missing_fields:
                            raise ValueError(f"Missing required fields in {blob.name}: {missing_fields}")
                        
                        # Convert camelCase to snake_case for consistency
                        if 'spaceName' in page_data:
                            page_data['space_name'] = page_data.pop('spaceName')
                        
                        # Validate data types for critical fields
                        if not isinstance(page_data.get('page_id'), (str, int)):
                            raise ValueError(f"page_id in {blob.name} must be string or int, got {type(page_data.get('page_id'))}")
                        
                        if not isinstance(page_data.get('title'), str):
                            raise ValueError(f"title in {blob.name} must be string, got {type(page_data.get('title'))}")
                        
                        if not isinstance(page_data.get('space_key'), str):
                            raise ValueError(f"space_key in {blob.name} must be string, got {type(page_data.get('space_key'))}")
                        
                        # Validate and normalize links structure
                        if 'links' in page_data:
                            if not isinstance(page_data['links'], dict):
                                raise ValueError(f"links in {blob.name} must be dictionary, got {type(page_data['links'])}")
                            
                            expected_link_keys = ['all', 'internal', 'external']
                            for key in expected_link_keys:
                                if key not in page_data['links']:
                                    raise ValueError(f"links in {blob.name} missing required key: {key}")
                                
                                if not isinstance(page_data['links'][key], list):
                                    raise ValueError(f"links.{key} in {blob.name} must be list, got {type(page_data['links'][key])}")
                            
                            # Normalize links structure to list of dicts
                            page_data['links'] = self._normalize_links(page_data['links'])
                        
                        changed_pages.append(page_data)
                            
                    except Exception as e:
                        print(f"❌ Error loading {blob.name}: {e}")
                        self.stats['errors_count'] += 1
                        # Don't continue with invalid data - fail fast
                        raise
            
            return changed_pages
            
        except Exception as e:
            print(f"❌ Error loading changed pages: {e}")
            self.stats['errors_count'] += 1
            raise
    
    def _create_space_nodes(self, processed_pages: List[Dict[str, Any]]) -> None:
        """Create space nodes from processed pages"""
        print("🏢 Creating space nodes...")
        
        # Collect unique spaces
        unique_spaces = {}
        for page_data in processed_pages:
            space_key = page_data.get('space_key', '')
            space_name = page_data.get('space_name', '')  # Now using normalized snake_case field name
            
            if space_key and space_key not in unique_spaces:
                unique_spaces[space_key] = space_name
        
        print(f"📊 Found {len(unique_spaces)} unique spaces")
        
        # Create space nodes
        space_nodes = []
        for space_key, space_name in unique_spaces.items():
            space_node = self.factory.create_space_node(space_key, space_name)
            space_nodes.append(space_node)
            self.spaces_cache[space_key] = space_node
        
        # Batch create spaces
        if space_nodes:
            # Use synchronous approach for space nodes
            created_count = 0
            for space_node in space_nodes:
                try:
                    query = self._create_gremlin_node_query(space_node)
                    self.graph_ops.client.submit(query).all().result()
                    created_count += 1
                except Exception as e:
                    print(f"⚠️  Failed to create space node {space_node.id}: {e}")
            self.stats['spaces_created'] = created_count
            print(f"✅ Created {created_count} space nodes")    
    
    def _create_page_nodes(self, processed_pages: List[Dict[str, Any]]) -> None:
        """Create page nodes from processed pages"""
        print("📄 Creating page nodes...")
        
        page_nodes = []
        for page_data in processed_pages:
            try:
                # Validate required fields
                required_fields = ['page_id', 'title']
                missing_fields = validate_node_data(page_data, required_fields)
                
                if missing_fields:
                    print(f"⚠️ Skipping page with missing fields: {missing_fields}")
                    self.stats['warnings_count'] += 1
                    continue
                
                # Ensure ancestor_ids list exists
                page_data['ancestor_ids'] = page_data.get('ancestor_ids', [])
                
                # Create page node
                page_node = self.factory.create_page_node(page_data)
                page_nodes.append(page_node)
                self.processed_pages.add(page_node.id)
                
            except Exception as e:
                print(f"⚠️ Error creating page node for {page_data.get('page_id', 'unknown')}: {e}")
                self.stats['warnings_count'] += 1
        
        print(f"📊 Created {len(page_nodes)} page node models")
        
        # Batch create pages
        if page_nodes:
            # Use synchronous approach for page nodes
            created_count = 0
            for page_node in page_nodes:
                try:
                    query = self._create_gremlin_node_query(page_node)
                    self.graph_ops.client.submit(query).all().result()
                    created_count += 1
                except Exception as e:
                    print(f"⚠️  Failed to create page node {page_node.id}: {e}")
            self.stats['pages_processed'] = created_count
            print(f"✅ Created {created_count} page nodes in graph")
    
    def _create_link_nodes(self, processed_pages: List[Dict[str, Any]]) -> None:
        """Create link nodes for external links"""
        print("🔗 Creating external link nodes...")
        
        # Collect unique external links
        unique_links = {}
        for page_data in processed_pages:
            links_data = page_data.get('links', [])
            
            # Handle the normalized links structure: list of dicts
            if isinstance(links_data, list):
                for link in links_data:
                    if link.get('type') == 'external':
                        url = link.get('url', '')
                        if url and url.startswith(('http://', 'https://')):
                            # Always hash URL for link key to avoid invalid characters in Cosmos DB
                            import hashlib
                            link_key = hashlib.md5(url.encode()).hexdigest()
                            
                            if link_key not in unique_links:
                                unique_links[link_key] = {
                                    'url': url,
                                    'title': link.get('text', url),  # Use link text or URL as title
                                    'type': 'external'
                                }
        
        print(f"📊 Found {len(unique_links)} unique external links")
        
        # Create link nodes
        link_nodes = []
        for link_key, link_data in unique_links.items():
            link_node = self.factory.create_link_node(
                link_data['url'],
                link_data['title'],
                link_data['type']
            )
            link_nodes.append(link_node)
            self.link_nodes_cache[link_key] = link_node
        
        # Batch create links
        if link_nodes:
            # Use synchronous approach for link nodes
            created_count = 0
            for link_node in link_nodes:
                try:
                    query = self._create_gremlin_node_query(link_node)
                    self.graph_ops.client.submit(query).all().result()
                    created_count += 1
                except Exception as e:
                    print(f"⚠️  Failed to create link node {link_node.id}: {e}")
            self.stats['links_created'] = created_count
            print(f"✅ Created {created_count} link nodes")
    
    def _create_relationships(self, processed_pages: List[Dict[str, Any]]) -> None:
        """Create all relationships between nodes"""
        print("🔗 Creating relationships...")
        
        all_edges = []
        
        for page_data in processed_pages:
            try:
                page_node = self.factory.create_page_node(page_data)
                
                # Create space relationships
                if self.config.enable_space_hierarchy:
                    space_edges = self.factory.create_space_edges(page_node)
                    all_edges.extend(space_edges)
                
                # Create hierarchy relationships  
                if self.config.bidirectional_relationships:
                    hierarchy_edges = self.factory.create_hierarchy_edges(page_node)
                    all_edges.extend(hierarchy_edges)
                
                # Create link relationships
                link_edges = self.factory.create_link_edges(page_node)
                all_edges.extend(link_edges)
                
            except Exception as e:
                print(f"⚠️ Error creating relationships for page {page_data.get('page_id', 'unknown')}: {e}")
                self.stats['warnings_count'] += 1
        
        print(f"📊 Created {len(all_edges)} relationship models")
        
        # Batch create edges
        if all_edges:
            # Use synchronous approach for edges
            created_count = 0
            for edge in all_edges:
                try:
                    query = self._create_gremlin_edge_query(edge)
                    self.graph_ops.client.submit(query).all().result()
                    created_count += 1
                except Exception as e:
                    print(f"⚠️  Failed to create edge {edge.get_edge_id()}: {e}")
            self.stats['edges_created'] = created_count
            print(f"✅ Created {created_count} relationships in graph")
    
    def _process_changed_pages(self, changed_pages: List[Dict[str, Any]]) -> None:
        """Process changed pages for incremental update"""
        print("🔄 Processing changed pages...")
        
        # Update page nodes
        page_nodes = []
        for page_data in changed_pages:
            try:
                page_node = self.factory.create_page_node(page_data)
                page_nodes.append(page_node)
                self.processed_pages.add(page_node.id)
            except Exception as e:
                print(f"⚠️ Error processing changed page {page_data.get('page_id', 'unknown')}: {e}")
                self.stats['warnings_count'] += 1
        
        # Update nodes in graph
        if page_nodes:
            # Use synchronous approach for page nodes
            created_count = 0
            for page_node in page_nodes:
                try:
                    query = self._create_gremlin_node_query(page_node)
                    self.graph_ops.client.submit(query).all().result()
                    created_count += 1
                except Exception as e:
                    print(f"⚠️  Failed to update page node {page_node.id}: {e}")
            self.stats['pages_processed'] = created_count
            print(f"✅ Updated {created_count} page nodes")
    
    def _update_relationships(self, changed_pages: List[Dict[str, Any]]) -> None:
        """Update relationships for changed pages"""
        print("🔗 Updating relationships for changed pages...")
        
        # For each changed page, recreate its relationships
        all_edges = []
        
        for page_data in changed_pages:
            try:
                page_node = self.factory.create_page_node(page_data)
                
                # Remove existing edges for this page (simplified - would need more sophisticated approach)
                # For now, just add new edges (Gremlin upsert will handle duplicates)
                
                # Create all relationship types
                space_edges = self.factory.create_space_edges(page_node)
                hierarchy_edges = self.factory.create_hierarchy_edges(page_node)
                link_edges = self.factory.create_link_edges(page_node)
                
                all_edges.extend(space_edges + hierarchy_edges + link_edges)
                
            except Exception as e:
                print(f"⚠️ Error updating relationships for {page_data.get('page_id', 'unknown')}: {e}")
                self.stats['warnings_count'] += 1
        
        # Batch update edges
        if all_edges:
            # Use synchronous approach for edges
            created_count = 0
            for edge in all_edges:
                try:
                    query = self._create_gremlin_edge_query(edge)
                    self.graph_ops.client.submit(query).all().result()
                    created_count += 1
                except Exception as e:
                    print(f"⚠️  Failed to update edge {edge.get_edge_id()}: {e}")
            self.stats['edges_created'] = created_count
            print(f"✅ Updated {created_count} relationships")
    
    async def _validate_graph(self) -> None:
        """Validate graph integrity"""
        print("🔍 Validating graph integrity...")
        
        validation_results = await self.graph_ops.validate_graph_integrity()
        
        if validation_results['valid']:
            print("✅ Graph validation passed")
        else:
            print(f"⚠️ Graph validation found {validation_results.get('issues_found', 0)} issues")
            for issue in validation_results.get('issues', []):
                print(f"  - {issue['type']}: {issue['count']} instances")
    
    def _validate_incremental_changes(self, changed_pages: List[Dict[str, Any]]) -> None:
        """Validate incremental changes"""
        print("🔍 Validating incremental changes...")
        
        # Simple validation - check that all changed pages exist in graph
        missing_pages = []
        for page_data in changed_pages:
            page_id = page_data.get('page_id', '')
            if page_id:
                node = self.graph_ops.find_node(page_id)
                if not node:
                    missing_pages.append(page_id)
        
        if missing_pages:
            print(f"⚠️ {len(missing_pages)} pages not found in graph after update")
            self.stats['warnings_count'] += len(missing_pages)
        else:
            print("✅ All changed pages validated in graph")
    
    def _finalize_stats(self) -> None:
        """Finalize processing statistics"""
        self.stats['end_time'] = datetime.utcnow()
        if self.stats['start_time']:
            duration = self.stats['end_time'] - self.stats['start_time']
            self.stats['processing_time_seconds'] = duration.total_seconds()
        
        # Get final graph statistics
        graph_stats = self.graph_ops.get_graph_statistics()
        self.stats['final_graph_stats'] = graph_stats
        
        print("\n📊 Processing Complete!")
        print("=" * 40)
        print(f"Pages processed: {self.stats['pages_processed']}")
        print(f"Spaces created: {self.stats['spaces_created']}")
        print(f"Links created: {self.stats['links_created']}")
        print(f"Edges created: {self.stats['edges_created']}")
        print(f"Processing time: {self.stats['processing_time_seconds']:.2f} seconds")
        print(f"Warnings: {self.stats['warnings_count']}")
        print(f"Errors: {self.stats['errors_count']}")
    
    def _create_success_result(self) -> Dict[str, Any]:
        """Create success result dictionary"""
        return {
            'success': True,
            'message': 'Graph population completed successfully',
            'statistics': self.stats,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Create error result dictionary"""
        return {
            'success': False,
            'error': error_message,
            'statistics': self.stats,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    # Query methods
    def find_page(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Find a page by ID"""
        if not self.graph_ops.client:
            self._connect_to_graph()
        return self.graph_ops.find_node(page_id)
    
    def get_page_hierarchy(self, page_id: str) -> Dict[str, Any]:
        """Get page hierarchy"""
        if not self.graph_ops.client:
            self._connect_to_graph()
        return self.graph_ops.get_node_hierarchy(page_id)
    
    def find_related_pages(self, page_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """Find related pages"""
        if not self.graph_ops.client:
            self._connect_to_graph()
        return self.graph_ops.find_related_pages(page_id, depth)
    
    def get_space_statistics(self, space_key: str) -> Dict[str, Any]:
        """Get space statistics"""
        if not self.graph_ops.client:
            self._connect_to_graph()
        return self.graph_ops.get_space_statistics(space_key)
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get overall graph statistics"""
        if not self.graph_ops.client:
            self._connect_to_graph()
        return self.graph_ops.get_graph_statistics()
    
    def cleanup_graph(self, confirm: bool = True) -> Dict[str, Any]:
        """Clean up all nodes and edges from the graph"""
        print("🧹 Cleaning up existing graph...")
        
        try:
            if not self.graph_ops.client:
                self._connect_to_graph()
            
            # Get initial counts using direct Gremlin queries
            initial_nodes = self.graph_ops.client.submit("g.V().count()").all().result()[0]
            initial_edges = self.graph_ops.client.submit("g.E().count()").all().result()[0]
            
            print(f"📊 Current graph: {initial_nodes} nodes, {initial_edges} edges")
            
            if initial_nodes == 0 and initial_edges == 0:
                print("✅ Graph is already empty")
                return {'success': True, 'message': 'Graph already empty'}
            
            # Confirm if needed
            if confirm:
                response = input(f"⚠️  Delete ALL {initial_nodes} nodes and {initial_edges} edges? (yes/no): ")
                if response.lower() != 'yes':
                    return {'success': False, 'message': 'Cleanup cancelled by user'}
            
            # Delete all edges first
            print("🔗 Deleting all edges...")
            self.graph_ops.client.submit("g.E().drop()").all().result()
            
            # Delete all nodes
            print("📄 Deleting all nodes...")
            self.graph_ops.client.submit("g.V().drop()").all().result()
            
            # Verify using direct Gremlin queries
            final_nodes = self.graph_ops.client.submit("g.V().count()").all().result()[0]
            final_edges = self.graph_ops.client.submit("g.E().count()").all().result()[0]
            
            if final_nodes == 0 and final_edges == 0:
                print("✅ Graph cleanup successful!")
                return {
                    'success': True,
                    'deleted': {'nodes': initial_nodes, 'edges': initial_edges}
                }
            else:
                print(f"⚠️  Incomplete cleanup: {final_nodes} nodes, {final_edges} edges remain")
                return {
                    'success': False,
                    'message': f'Incomplete cleanup: {final_nodes} nodes, {final_edges} edges remain'
                }
                
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            return {'success': False, 'error': str(e)}


def main():
    """Main execution function for script usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Confluence Knowledge Graph Population Tool')
    parser.add_argument('--recreate', action='store_true', 
                        help='Clean existing graph before populating')
    parser.add_argument('--no-confirm', action='store_true',
                        help='Skip confirmation prompts')
    parser.add_argument('--incremental', action='store_true',
                        help='Run incremental update instead of full population')
    parser.add_argument('--since', type=str,
                        help='For incremental update, process changes since this datetime')
    parser.add_argument('--skip-metrics', action='store_true',
                        help='Skip graph metrics computation')
    
    args = parser.parse_args()
    
    print("🚀 Confluence Knowledge Graph Population Tool")
    print("=" * 60)
    
    try:
        # Initialize from environment
        populator = GraphPopulator.from_environment()
        
        # Handle metrics flag
        if args.skip_metrics:
            os.environ["GRAPH_COMPUTE_METRICS"] = "false"
        else:
            os.environ["GRAPH_COMPUTE_METRICS"] = "true"
        
        # Handle recreation
        if args.recreate:
            print("\n📌 Step 1: Cleaning existing graph")
            print("-" * 40)
            cleanup_result = populator.cleanup_graph(confirm=not args.no_confirm)
            
            if not cleanup_result.get('success'):
                print(f"❌ Cleanup failed: {cleanup_result.get('error', cleanup_result.get('message', 'Unknown error'))}")
                sys.exit(1)
            
            print(f"✅ Cleaned {cleanup_result.get('deleted', {}).get('nodes', 0)} nodes and {cleanup_result.get('deleted', {}).get('edges', 0)} edges")
            
            # Wait for cleanup to propagate
            print("\n⏳ Waiting 5 seconds for cleanup to propagate...")
            time.sleep(5)
            
            print("\n📌 Step 2: Populating fresh graph")
            print("-" * 40)
        
        # Run population
        if args.incremental:
            results = populator.populate_incremental(since=args.since)
        else:
            results = populator.populate_all()
        
        if results['success']:
            print("\n🎉 Graph population completed successfully!")
            
            # Display key statistics
            stats = results.get('statistics', {})
            if args.recreate:
                print("\n📊 Recreation Summary:")
                print(f"   Pages: {stats.get('pages_processed', 0)}")
                print(f"   Spaces: {stats.get('spaces_created', 0)}")
                print(f"   Links: {stats.get('links_created', 0)}")
                print(f"   Edges: {stats.get('edges_created', 0)}")
                print(f"   Time: {stats.get('processing_time_seconds', 0):.2f}s")
        else:
            print(f"\n❌ Graph population failed: {results.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 