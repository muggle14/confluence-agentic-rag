#!/usr/bin/env python3
"""
Add metrics to existing graph without recreation
"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import GraphConfig
from common.graph_metrics import GraphMetrics


def main():
    """Add metrics to existing graph"""
    print("🔧 Adding Metrics to Existing Graph")
    print("=" * 50)
    
    try:
        # Load configuration
        config = GraphConfig.from_environment()
        
        # Create metrics calculator
        metrics = GraphMetrics(config)
        
        print("📊 Computing and adding metrics...")
        
        # Run metrics computation
        stats = metrics.run_all()
        
        print(f"\n✅ Metrics added successfully!")
        print(f"   Pages updated: {stats['pages_updated']}")
        print(f"   Unique pages: {stats['unique_pages']}")
        
        # Disconnect
        if hasattr(metrics.ops, 'disconnect'):
            metrics.ops.disconnect()
        
        print("\n🎉 Metrics have been added to the graph!")
        print("You can now see them in Cosmos DB Graph Explorer")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()