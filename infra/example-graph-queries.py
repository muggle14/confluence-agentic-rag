#!/usr/bin/env python3
"""
Example queries demonstrating graph-aware search capabilities
for Confluence Q&A system with Azure AI Search

Requirements:
    pip install azure-search-documents azure-core

Usage:
    export SEARCH_KEY=<your-search-admin-key>
    python example-graph-queries.py
"""

import os
import json
from typing import List, Dict, Any

try:
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential
except ImportError:
    print("Please install required packages:")
    print("pip install azure-search-documents azure-core")
    exit(1)


class GraphAwareSearchExamples:
    def __init__(self):
        # Configuration from environment
        self.search_endpoint = os.getenv("SEARCH_ENDPOINT", "https://srch-rag-conf.search.windows.net")
        self.search_key = os.getenv("SEARCH_KEY")
        self.index_name = "confluence-graph-embeddings"
        
        if not self.search_key:
            raise ValueError("SEARCH_KEY environment variable required")
        
        # Initialize search client
        self.client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.search_key)
        )
    
    def example_1_overview_pages(self):
        """Find top-level overview pages using hierarchy depth"""
        print("\n🔍 Example 1: Finding Overview Pages")
        print("=" * 50)
        
        results = self.client.search(
            search_text="getting started",
            filter="hierarchy_depth lt 3 and has_children eq true",
            scoring_profile="confluence-graph-boost",
            select=["title", "hierarchy_path", "graph_centrality_score", "child_count"],
            top=5
        )
        
        print("\nTop-level overview pages:")
        for doc in results:
            print(f"\n📄 {doc['title']}")
            print(f"   Path: {doc.get('hierarchy_path', 'N/A')}")
            print(f"   Centrality: {doc.get('graph_centrality_score', 0):.2f}")
            print(f"   Children: {doc.get('child_count', 0)}")
    
    def example_2_detailed_implementation(self):
        """Find detailed implementation pages using depth filter"""
        print("\n🔍 Example 2: Finding Detailed Implementation Pages")
        print("=" * 50)
        
        results = self.client.search(
            search_text="implementation code example",
            filter="hierarchy_depth gt 3",
            order_by=["graph_centrality_score desc"],
            select=["title", "parent_page_title", "hierarchy_depth"],
            top=5
        )
        
        print("\nDetailed implementation pages:")
        for doc in results:
            print(f"\n📝 {doc['title']}")
            print(f"   Parent: {doc.get('parent_page_title', 'N/A')}")
            print(f"   Depth: {doc.get('hierarchy_depth', 0)}")
    
    def example_3_hub_pages(self):
        """Find important hub pages with high centrality"""
        print("\n🔍 Example 3: Finding Hub Pages (Documentation Centers)")
        print("=" * 50)
        
        results = self.client.search(
            search_text="*",
            filter="graph_centrality_score gt 0.7",
            order_by=["graph_centrality_score desc"],
            select=["title", "graph_centrality_score", "child_count", "related_page_count"],
            top=10
        )
        
        print("\nMost important hub pages:")
        for doc in results:
            print(f"\n🏆 {doc['title']}")
            print(f"   Centrality Score: {doc.get('graph_centrality_score', 0):.2f}")
            print(f"   Children: {doc.get('child_count', 0)}")
            print(f"   Related Pages: {doc.get('related_page_count', 0)}")
    
    def example_4_hierarchical_navigation(self):
        """Navigate hierarchically - find all children of a page"""
        print("\n🔍 Example 4: Hierarchical Navigation")
        print("=" * 50)
        
        # First find a parent page
        parent_results = self.client.search(
            search_text="API documentation",
            filter="has_children eq true",
            select=["id", "title"],
            top=1
        )
        
        parent = next(parent_results, None)
        if parent:
            parent_id = parent['id']
            print(f"\nParent page: {parent['title']}")
            
            # Find all children
            children = self.client.search(
                search_text="*",
                filter=f"parent_page_id eq '{parent_id}'",
                order_by=["title asc"],
                select=["title", "hierarchy_depth"],
                top=20
            )
            
            print("\nChild pages:")
            for child in children:
                print(f"  └─ {child['title']} (depth: {child.get('hierarchy_depth', 0)})")
    
    def example_5_space_specific_search(self):
        """Search within a specific Confluence space"""
        print("\n🔍 Example 5: Space-Specific Search")
        print("=" * 50)
        
        results = self.client.search(
            search_text="installation guide",
            filter="space_key eq 'DOCS'",
            scoring_profile="confluence-graph-boost",
            select=["title", "space_key", "hierarchy_path", "graph_centrality_score"],
            top=5
        )
        
        print("\nResults from DOCS space:")
        for doc in results:
            print(f"\n📚 {doc['title']}")
            print(f"   Space: {doc.get('space_key', 'N/A')}")
            print(f"   Path: {doc.get('hierarchy_path', 'N/A')}")
            print(f"   Importance: {doc.get('graph_centrality_score', 0):.2f}")
    
    def example_6_related_content(self):
        """Find related content using graph relationships"""
        print("\n🔍 Example 6: Finding Related Content")
        print("=" * 50)
        
        # Find pages with many relationships
        results = self.client.search(
            search_text="configuration",
            filter="related_page_count gt 5",
            scoring_profile="confluence-graph-boost",
            select=["title", "related_page_count", "graph_centrality_score"],
            top=5
        )
        
        print("\nHighly connected configuration pages:")
        for doc in results:
            print(f"\n🔗 {doc['title']}")
            print(f"   Related pages: {doc.get('related_page_count', 0)}")
            print(f"   Centrality: {doc.get('graph_centrality_score', 0):.2f}")
    
    def example_7_breadcrumb_navigation(self):
        """Generate breadcrumb trails using hierarchy paths"""
        print("\n🔍 Example 7: Breadcrumb Navigation")
        print("=" * 50)
        
        results = self.client.search(
            search_text="REST API endpoint",
            select=["title", "hierarchy_path", "parent_page_title"],
            top=3
        )
        
        print("\nPages with breadcrumb trails:")
        for doc in results:
            print(f"\n📍 Current: {doc['title']}")
            path = doc.get('hierarchy_path', '')
            if path:
                breadcrumbs = path.split(' > ')
                print("   Breadcrumb: " + " › ".join(breadcrumbs))
    
    def example_8_orphaned_pages(self):
        """Find orphaned pages (no parent, low centrality)"""
        print("\n🔍 Example 8: Finding Orphaned Pages")
        print("=" * 50)
        
        results = self.client.search(
            search_text="*",
            filter="parent_page_id eq null and graph_centrality_score lt 0.2",
            select=["title", "graph_centrality_score", "related_page_count"],
            top=10
        )
        
        print("\nOrphaned pages (may need reorganization):")
        for doc in results:
            print(f"\n⚠️  {doc['title']}")
            print(f"   Centrality: {doc.get('graph_centrality_score', 0):.2f}")
            print(f"   Related: {doc.get('related_page_count', 0)}")
    
    def example_9_vector_search_with_graph(self):
        """Combine vector search with graph filtering"""
        print("\n🔍 Example 9: Vector Search with Graph Context")
        print("=" * 50)
        
        # This uses semantic/vector search with graph filters
        results = self.client.search(
            search_text="how to authenticate users in our system",
            query_type="semantic",
            semantic_configuration_name="default",
            filter="graph_centrality_score gt 0.3",
            scoring_profile="confluence-graph-boost",
            select=["title", "hierarchy_path", "@search.score", "graph_centrality_score"],
            top=5
        )
        
        print("\nSemantically similar pages (with graph importance):")
        for doc in results:
            print(f"\n🎯 {doc['title']}")
            print(f"   Search Score: {doc.get('@search.score', 0):.2f}")
            print(f"   Graph Importance: {doc.get('graph_centrality_score', 0):.2f}")
            print(f"   Location: {doc.get('hierarchy_path', 'N/A')}")
    
    def example_10_aggregate_stats(self):
        """Get aggregate statistics about the graph structure"""
        print("\n🔍 Example 10: Graph Structure Statistics")
        print("=" * 50)
        
        # Total documents
        total = self.client.search(
            search_text="*",
            include_total_count=True,
            top=0
        ).get_count()
        
        print(f"\nTotal documents: {total}")
        
        # Distribution analysis
        metrics = [
            ("Top-level pages (depth ≤ 2)", "hierarchy_depth le 2"),
            ("Hub pages (centrality > 0.7)", "graph_centrality_score gt 0.7"),
            ("Parent pages", "has_children eq true"),
            ("Highly connected (>10 related)", "related_page_count gt 10"),
            ("Orphaned pages", "parent_page_id eq null")
        ]
        
        print("\nDocument distribution:")
        for label, filter_expr in metrics:
            count = self.client.search(
                search_text="*",
                filter=filter_expr,
                include_total_count=True,
                top=0
            ).get_count()
            percentage = (count / total * 100) if total > 0 else 0
            print(f"  • {label}: {count} ({percentage:.1f}%)")
    
    def run_all_examples(self):
        """Run all example queries"""
        examples = [
            self.example_1_overview_pages,
            self.example_2_detailed_implementation,
            self.example_3_hub_pages,
            self.example_4_hierarchical_navigation,
            self.example_5_space_specific_search,
            self.example_6_related_content,
            self.example_7_breadcrumb_navigation,
            self.example_8_orphaned_pages,
            self.example_9_vector_search_with_graph,
            self.example_10_aggregate_stats
        ]
        
        print("🌟 Graph-Aware Search Examples for Confluence Q&A")
        print("=" * 60)
        
        for example in examples:
            try:
                example()
            except Exception as e:
                print(f"\n❌ Error in {example.__name__}: {str(e)}")
            
            print("\n" + "-" * 60)
        
        print("\n✅ All examples completed!")


def main():
    """Main function to run examples"""
    # Check for required environment variable
    if not os.getenv("SEARCH_KEY"):
        print("❌ Please set SEARCH_KEY environment variable")
        print("   export SEARCH_KEY=<your-search-admin-key>")
        return
    
    try:
        examples = GraphAwareSearchExamples()
        examples.run_all_examples()
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    main() 