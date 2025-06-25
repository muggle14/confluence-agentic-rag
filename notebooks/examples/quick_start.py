#!/usr/bin/env python3
"""
Quick Start Example for Graph Population Module
Demonstrates basic usage for populating the Confluence knowledge graph
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from notebooks.populate_graph import GraphPopulator
from notebooks.config import GraphConfig


def main():
    """Quick start example"""
    print("🚀 Graph Population Quick Start Example")
    print("=" * 50)
    
    try:
        # Method 1: Initialize from environment
        print("📋 Method 1: Initialize from environment variables")
        populator = GraphPopulator.from_environment()
        
        # Check configuration
        config_dict = populator.config.to_dict()
        print(f"✅ Configuration loaded:")
        print(f"  - Cosmos DB: {config_dict['cosmos_endpoint']}")
        print(f"  - Storage Account: {config_dict['storage_account']}")
        print(f"  - Batch Size: {config_dict['batch_size']}")
        
        # Method 2: Manual configuration (for testing)
        print("\n📋 Method 2: Manual configuration")
        from notebooks.config import get_sample_config
        sample_config = get_sample_config()
        sample_populator = GraphPopulator(sample_config)
        print("✅ Sample configuration created")
        
        # Demonstrate basic operations
        print("\n🔧 Basic Operations:")
        
        # 1. Full population (would normally be used with real data)
        print("1. Full graph population:")
        print("   populator.populate_all()")
        print("   # This would process all pages from the 'processed' container")
        
        # 2. Incremental population
        print("\n2. Incremental population:")
        print("   populator.populate_incremental(since='2025-01-15T10:00:00Z')")
        print("   # This would process only pages changed since the specified time")
        
        # 3. Query operations
        print("\n3. Query operations:")
        print("   page = populator.find_page('1343493')")
        print("   hierarchy = populator.get_page_hierarchy('1343493')")
        print("   related = populator.find_related_pages('1343493', depth=2)")
        print("   stats = populator.get_graph_statistics()")
        
        # Configuration validation
        print("\n🔍 Configuration Validation:")
        validation = populator.config.validate()
        if validation['valid']:
            print("✅ Configuration is valid")
        else:
            print("⚠️ Configuration issues found:")
            for error in validation['errors']:
                print(f"  - Error: {error}")
            for warning in validation['warnings']:
                print(f"  - Warning: {warning}")
        
        # Example workflow
        print("\n📋 Example Workflow:")
        print("""
        # Complete workflow example:
        
        1. Initialize populator
        populator = GraphPopulator.from_environment()
        
        2. Run initial population
        results = populator.populate_all()
        if results['success']:
            print(f"Processed {results['statistics']['pages_processed']} pages")
        
        3. Get graph statistics
        stats = populator.get_graph_statistics()
        print(f"Total nodes: {stats['nodes']['total']}")
        print(f"Total edges: {stats['edges']['total']}")
        
        4. Query specific page
        page = populator.find_page('1343493')
        if page:
            print(f"Found page: {page.get('title', 'Unknown')}")
        
        5. Run incremental updates (daily)
        recent_results = populator.populate_incremental()
        print(f"Updated {recent_results['statistics']['pages_processed']} pages")
        """)
        
        print("\n🎉 Quick start example completed!")
        print("\nNext steps:")
        print("1. Set up your environment variables (see notebooks/README.md)")
        print("2. Run the processing pipeline to create processed/*.json files")
        print("3. Execute populator.populate_all() to build your graph")
        print("4. Use query methods to explore your knowledge graph")
        
    except Exception as e:
        print(f"❌ Error in quick start: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 