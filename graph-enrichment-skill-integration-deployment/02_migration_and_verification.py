#!/usr/bin/env python3
"""
Migration and Verification for Graph-Enriched Search
Steps 4-5: Run indexer and verify data migration

DETAILS:
- Runs the indexer and verifies migration:
- Executes the indexer to process all documents
- Monitors indexer progress in real-time
- Verifies graph fields are populated correctly
- Compares document counts between old and new indexes
Tests graph-aware search functionality
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

# Add parent directory to path to import from notebooks
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration - Load from environment or .env files
def load_config() -> Dict[str, str]:
    """Load configuration from environment variables or .env files"""
    config = {}
    
    # Try to load from .env files in order of preference
    env_files = [
        '.env',
        '../.env',
        '../infra/.env.graph',
        '../infra/.env.updated',
        '../infra/.env'
    ]
    
    for env_file in env_files:
        if os.path.exists(env_file):
            print(f"Loading configuration from {env_file}")
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
            break
    
    # Override with environment variables if present
    required_vars = [
        'SEARCH_SERVICE',
        'SEARCH_KEY',
        'SEARCH_ENDPOINT',
        'RESOURCE_GROUP'
    ]
    
    for var in required_vars:
        if var in os.environ:
            config[var] = os.environ[var]
    
    # Set defaults
    config.setdefault('SEARCH_SERVICE', 'srch-rag-conf')
    config.setdefault('RESOURCE_GROUP', 'rg-rag-confluence')
    
    # Build search endpoint if not provided
    if 'SEARCH_ENDPOINT' not in config and 'SEARCH_SERVICE' in config:
        config['SEARCH_ENDPOINT'] = f"https://{config['SEARCH_SERVICE']}.search.windows.net"
    
    return config

def run_indexer(config: Dict[str, str], indexer_name: str = "confluence-graph-enriched-indexer") -> bool:
    """Run the indexer and monitor its progress"""
    print(f"\n🔄 Running indexer '{indexer_name}'...")
    
    try:
        headers = {
            'api-key': config['SEARCH_KEY']
        }
        
        # First check if indexer exists
        check_url = f"{config['SEARCH_ENDPOINT']}/indexers/{indexer_name}?api-version=2023-11-01"
        check_response = requests.get(check_url, headers=headers)
        
        if check_response.status_code != 200:
            print(f"❌ Indexer '{indexer_name}' not found. Please run 01_deploy_graph_enriched_search.py first.")
            return False
        
        # Start indexer run
        url = f"{config['SEARCH_ENDPOINT']}/indexers/{indexer_name}/run?api-version=2023-11-01"
        response = requests.post(url, headers=headers)
        
        if response.status_code not in [200, 202]:
            print(f"❌ Failed to start indexer: {response.status_code} - {response.text}")
            return False
        
        print("✅ Indexer run started successfully")
        
        # Monitor indexer status
        status_url = f"{config['SEARCH_ENDPOINT']}/indexers/{indexer_name}/status?api-version=2023-11-01"
        
        print("⏳ Monitoring indexer progress...")
        last_status = None
        
        while True:
            time.sleep(10)  # Check every 10 seconds
            
            response = requests.get(status_url, headers=headers)
            if response.status_code != 200:
                print(f"❌ Failed to get indexer status: {response.status_code}")
                return False
            
            status_data = response.json()
            execution_history = status_data.get('executionHistory', [])
            
            if execution_history:
                latest = execution_history[0]
                status = latest.get('status')
                
                # Print progress
                if status != last_status:
                    print(f"   Status: {status}")
                    last_status = status
                
                if 'itemsProcessed' in latest:
                    processed = latest.get('itemsProcessed', 0)
                    failed = latest.get('itemsFailed', 0)
                    print(f"   Progress: {processed} processed, {failed} failed")
                
                # Check if completed
                if status in ['success', 'failed']:
                    if status == 'success':
                        print("✅ Indexer run completed successfully!")
                        print(f"   Total items processed: {latest.get('itemsProcessed', 0)}")
                        print(f"   Total items failed: {latest.get('itemsFailed', 0)}")
                        return True
                    else:
                        print("❌ Indexer run failed!")
                        if 'errors' in latest:
                            for error in latest['errors'][:5]:  # Show first 5 errors
                                print(f"   Error: {error.get('message', 'Unknown error')}")
                        return False
            
    except Exception as e:
        print(f"❌ Error running indexer: {e}")
        return False

def verify_graph_fields(config: Dict[str, str], sample_size: int = 5) -> bool:
    """Verify that graph enrichment fields are populated in the new index"""
    print(f"\n🔍 Verifying graph enrichment fields...")
    
    try:
        # First check if index exists
        headers = {'api-key': config['SEARCH_KEY']}
        check_url = f"{config['SEARCH_ENDPOINT']}/indexes/confluence-graph-embeddings-v2?api-version=2023-11-01"
        check_response = requests.get(check_url, headers=headers)
        
        if check_response.status_code != 200:
            print(f"❌ Index 'confluence-graph-embeddings-v2' not found. Please run deployment first.")
            return False
        
        # Create search client for new index
        search_client = SearchClient(
            endpoint=config['SEARCH_ENDPOINT'],
            index_name="confluence-graph-embeddings-v2",
            credential=AzureKeyCredential(config['SEARCH_KEY'])
        )
        
        # Search for documents
        results = search_client.search(
            search_text="*",
            select=[
                "page_id", "title", "hierarchy_depth", "child_count", 
                "graph_centrality_score", "parent_page_title", "breadcrumb"
            ],
            top=sample_size
        )
        
        documents_checked = 0
        fields_populated = {
            'hierarchy_depth': 0,
            'child_count': 0,
            'graph_centrality_score': 0,
            'parent_page_title': 0,
            'breadcrumb': 0
        }
        
        print(f"\n📊 Sample documents with graph fields:")
        print("-" * 80)
        
        for doc in results:
            documents_checked += 1
            
            print(f"\nDocument: {doc.get('title', 'N/A')}")
            print(f"  Page ID: {doc.get('page_id', 'N/A')}")
            
            # Check each graph field
            for field in fields_populated:
                value = doc.get(field)
                if value is not None and (isinstance(value, (int, float)) or (isinstance(value, str) and value.strip())):
                    fields_populated[field] += 1
                    print(f"  {field}: {value}")
        
        print("-" * 80)
        print(f"\n📈 Field population summary (out of {documents_checked} documents):")
        
        all_populated = True
        for field, count in fields_populated.items():
            percentage = (count / documents_checked * 100) if documents_checked > 0 else 0
            status = "✅" if percentage > 80 else "⚠️" if percentage > 50 else "❌"
            print(f"  {status} {field}: {count}/{documents_checked} ({percentage:.1f}%)")
            
            if percentage < 50:
                all_populated = False
        
        return all_populated
        
    except Exception as e:
        print(f"❌ Error verifying graph fields: {e}")
        return False

def compare_indexes(config: Dict[str, str]) -> None:
    """Compare document counts between old and new indexes"""
    print(f"\n📊 Comparing indexes...")
    
    try:
        headers = {
            'api-key': config['SEARCH_KEY']
        }
        
        # Get document count for both indexes
        indexes = ["confluence-graph-embeddings", "confluence-graph-embeddings-v2"]
        counts = {}
        
        for index_name in indexes:
            url = f"{config['SEARCH_ENDPOINT']}/indexes/{index_name}/docs/$count?api-version=2023-11-01"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                counts[index_name] = response.json()
            else:
                counts[index_name] = "Error"
        
        print("\n📈 Index comparison:")
        print(f"  Original index: {counts.get('confluence-graph-embeddings', 'N/A')} documents")
        print(f"  New index: {counts.get('confluence-graph-embeddings-v2', 'N/A')} documents")
        
        if all(isinstance(c, int) for c in counts.values()):
            if counts['confluence-graph-embeddings-v2'] >= counts['confluence-graph-embeddings']:
                print("  ✅ Document count matches or exceeds original")
            else:
                print("  ⚠️ New index has fewer documents than original")
    
    except Exception as e:
        print(f"❌ Error comparing indexes: {e}")

def test_graph_aware_search(config: Dict[str, str]) -> None:
    """Test search with graph-aware scoring profile"""
    print(f"\n🔍 Testing graph-aware search...")
    
    try:
        search_client = SearchClient(
            endpoint=config['SEARCH_ENDPOINT'],
            index_name="confluence-graph-embeddings-v2",
            credential=AzureKeyCredential(config['SEARCH_KEY'])
        )
        
        # Test query
        query = "confluence"
        
        print(f"\nQuery: '{query}'")
        print("\nWith graph-aware scoring:")
        
        results = search_client.search(
            search_text=query,
            scoring_profile="graph-aware-scoring",
            select=["title", "graph_centrality_score", "hierarchy_depth", "child_count"],
            top=3
        )
        
        for i, doc in enumerate(results, 1):
            print(f"\n{i}. {doc.get('title', 'N/A')}")
            print(f"   Centrality: {doc.get('graph_centrality_score', 0):.4f}")
            print(f"   Hierarchy Depth: {doc.get('hierarchy_depth', 'N/A')}")
            print(f"   Child Count: {doc.get('child_count', 0)}")
    
    except Exception as e:
        print(f"❌ Error testing search: {e}")

def main():
    """Main migration and verification function"""
    print("🚀 Graph Enrichment Search Migration - Steps 4-5")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    
    # Validate configuration
    missing = []
    for key in ['SEARCH_KEY', 'SEARCH_ENDPOINT']:
        if key not in config or not config[key]:
            missing.append(key)
    
    if missing:
        print(f"❌ Missing required configuration: {', '.join(missing)}")
        print("Please set these in environment variables or .env file")
        return 1
    
    print(f"📋 Configuration loaded:")
    print(f"  - Search Service: {config['SEARCH_SERVICE']}")
    print(f"  - Resource Group: {config['RESOURCE_GROUP']}")
    
    # Step 4: Run the indexer
    if not run_indexer(config):
        print("\n❌ Indexer run failed. Please check the errors and try again.")
        return 1
    
    # Wait a bit for index to be fully updated
    print("\n⏳ Waiting for index to be fully updated...")
    time.sleep(30)
    
    # Step 5: Verify the migration
    print("\n" + "="*50)
    print("📋 VERIFICATION PHASE")
    print("="*50)
    
    # Compare document counts
    compare_indexes(config)
    
    # Verify graph fields are populated
    if not verify_graph_fields(config):
        print("\n⚠️ Warning: Some graph enrichment fields may not be fully populated.")
        print("This could be due to:")
        print("  - Function app not running or accessible")
        print("  - Cosmos DB connection issues")
        print("  - Some documents not having graph data")
    
    # Test search functionality
    test_graph_aware_search(config)
    
    print("\n" + "="*50)
    print("✅ Migration and verification completed!")
    print("\nNext steps:")
    print("1. Review the verification results above")
    print("2. Test search queries with your application")
    print("3. Update application to use 'confluence-graph-embeddings-v2' index")
    print("4. Monitor search performance and relevance")
    print("5. Once satisfied, the old index can be deprecated")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())