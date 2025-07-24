#!/usr/bin/env python3
"""
Safe Graph Cleanup Script for Cosmos DB
Deletes all nodes and edges from the Confluence knowledge graph
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any

# Package installed - no sys.path manipulation needed

from common.config import GraphConfig
from common.graph_operations import GraphOperations


class GraphCleanup:
    """Safely clean up all nodes and edges from Cosmos DB graph"""
    
    def __init__(self, config: GraphConfig):
        self.config = config
        self.graph_ops = GraphOperations(config)
        self.stats = {
            'start_time': None,
            'end_time': None,
            'initial_node_count': 0,
            'initial_edge_count': 0,
            'nodes_deleted': 0,
            'edges_deleted': 0,
            'final_node_count': 0,
            'final_edge_count': 0,
            'errors': []
        }
    
    def get_graph_counts(self) -> Dict[str, int]:
        """Get current node and edge counts"""
        try:
            node_count = self.graph_ops.client.submit("g.V().count()").all().result()[0]
            edge_count = self.graph_ops.client.submit("g.E().count()").all().result()[0]
            return {'nodes': node_count, 'edges': edge_count}
        except Exception as e:
            print(f"❌ Error getting graph counts: {e}")
            return {'nodes': -1, 'edges': -1}
    
    def cleanup_all(self, confirm: bool = True) -> Dict[str, Any]:
        """Delete all nodes and edges from the graph"""
        print("🧹 Cosmos DB Graph Cleanup Tool")
        print("=" * 60)
        
        self.stats['start_time'] = datetime.utcnow()
        
        try:
            # Connect to graph
            if not self.graph_ops.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect to Cosmos DB',
                    'stats': self.stats
                }
            
            # Get initial counts
            initial_counts = self.get_graph_counts()
            self.stats['initial_node_count'] = initial_counts['nodes']
            self.stats['initial_edge_count'] = initial_counts['edges']
            
            print(f"\n📊 Current Graph State:")
            print(f"   Nodes: {initial_counts['nodes']}")
            print(f"   Edges: {initial_counts['edges']}")
            
            if initial_counts['nodes'] == 0 and initial_counts['edges'] == 0:
                print("\n✅ Graph is already empty!")
                return {
                    'success': True,
                    'message': 'Graph is already empty',
                    'stats': self.stats
                }
            
            # Confirm deletion
            if confirm:
                print(f"\n⚠️  WARNING: This will delete ALL {initial_counts['nodes']} nodes and {initial_counts['edges']} edges!")
                response = input("Are you sure you want to continue? (yes/no): ")
                if response.lower() != 'yes':
                    print("❌ Cleanup cancelled by user")
                    return {
                        'success': False,
                        'error': 'Cancelled by user',
                        'stats': self.stats
                    }
            
            # Delete all edges first (required before deleting nodes)
            print("\n🔗 Deleting all edges...")
            try:
                edge_result = self.graph_ops.client.submit("g.E().drop()").all().result()
                print("✅ All edges deleted")
                self.stats['edges_deleted'] = initial_counts['edges']
            except Exception as e:
                self.stats['errors'].append(f"Edge deletion error: {e}")
                print(f"❌ Error deleting edges: {e}")
            
            # Delete all nodes
            print("\n📄 Deleting all nodes...")
            try:
                node_result = self.graph_ops.client.submit("g.V().drop()").all().result()
                print("✅ All nodes deleted")
                self.stats['nodes_deleted'] = initial_counts['nodes']
            except Exception as e:
                self.stats['errors'].append(f"Node deletion error: {e}")
                print(f"❌ Error deleting nodes: {e}")
            
            # Verify cleanup
            print("\n🔍 Verifying cleanup...")
            final_counts = self.get_graph_counts()
            self.stats['final_node_count'] = final_counts['nodes']
            self.stats['final_edge_count'] = final_counts['edges']
            
            print(f"\n📊 Final Graph State:")
            print(f"   Nodes: {final_counts['nodes']}")
            print(f"   Edges: {final_counts['edges']}")
            
            # Check if cleanup was successful
            success = (final_counts['nodes'] == 0 and final_counts['edges'] == 0)
            
            self.stats['end_time'] = datetime.utcnow()
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            
            print(f"\n⏱️  Cleanup completed in {duration:.2f} seconds")
            
            if success:
                print("✅ Graph cleanup successful - all nodes and edges removed!")
                return {
                    'success': True,
                    'message': 'Graph cleanup completed successfully',
                    'stats': self.stats
                }
            else:
                print("⚠️  Graph cleanup completed with warnings - some items may remain")
                return {
                    'success': False,
                    'error': 'Incomplete cleanup - some nodes or edges remain',
                    'stats': self.stats
                }
                
        except Exception as e:
            self.stats['errors'].append(f"Critical error: {e}")
            print(f"❌ Critical error during cleanup: {e}")
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }
        
        finally:
            self.graph_ops.disconnect()
    
    def cleanup_by_type(self, node_type: str = None, edge_type: str = None) -> Dict[str, Any]:
        """Delete specific types of nodes or edges"""
        print(f"🧹 Selective Graph Cleanup")
        print("=" * 60)
        
        try:
            if not self.graph_ops.connect():
                return {'success': False, 'error': 'Failed to connect'}
            
            deleted = {'nodes': 0, 'edges': 0}
            
            # Delete specific edge type
            if edge_type:
                print(f"🔗 Deleting edges of type '{edge_type}'...")
                count_query = f"g.E().hasLabel('{edge_type}').count()"
                count = self.graph_ops.client.submit(count_query).all().result()[0]
                
                if count > 0:
                    delete_query = f"g.E().hasLabel('{edge_type}').drop()"
                    self.graph_ops.client.submit(delete_query).all().result()
                    deleted['edges'] = count
                    print(f"✅ Deleted {count} edges of type '{edge_type}'")
                else:
                    print(f"ℹ️  No edges of type '{edge_type}' found")
            
            # Delete specific node type
            if node_type:
                print(f"📄 Deleting nodes of type '{node_type}'...")
                count_query = f"g.V().hasLabel('{node_type}').count()"
                count = self.graph_ops.client.submit(count_query).all().result()[0]
                
                if count > 0:
                    delete_query = f"g.V().hasLabel('{node_type}').drop()"
                    self.graph_ops.client.submit(delete_query).all().result()
                    deleted['nodes'] = count
                    print(f"✅ Deleted {count} nodes of type '{node_type}'")
                else:
                    print(f"ℹ️  No nodes of type '{node_type}' found")
            
            return {
                'success': True,
                'deleted': deleted
            }
            
        except Exception as e:
            print(f"❌ Error during selective cleanup: {e}")
            return {'success': False, 'error': str(e)}
        
        finally:
            self.graph_ops.disconnect()


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up Cosmos DB graph')
    parser.add_argument('--no-confirm', action='store_true', 
                        help='Skip confirmation prompt (use with caution!)')
    parser.add_argument('--node-type', type=str, 
                        help='Delete only specific node type (e.g., Page, Space, Link)')
    parser.add_argument('--edge-type', type=str,
                        help='Delete only specific edge type (e.g., ParentOf, LinksTo)')
    
    args = parser.parse_args()
    
    try:
        # Initialize from environment
        config = GraphConfig.from_environment()
        cleanup = GraphCleanup(config)
        
        # Run appropriate cleanup
        if args.node_type or args.edge_type:
            result = cleanup.cleanup_by_type(
                node_type=args.node_type,
                edge_type=args.edge_type
            )
        else:
            result = cleanup.cleanup_all(confirm=not args.no_confirm)
        
        # Print results
        if result['success']:
            print("\n🎉 Cleanup completed successfully!")
        else:
            print(f"\n❌ Cleanup failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Critical error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()