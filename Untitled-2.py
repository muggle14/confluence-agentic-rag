
01_deploy_graph_enriched_search.py

#!/usr/bin/env python3
"""
Deploy Graph-Enriched Search Infrastructure
Steps 1-3: Create index, skillset, and indexer with graph enrichment

This script creates a complete Azure AI Search infrastructure with graph enrichment:
- Creates confluence-graph-embeddings-v2 index with graph fields
- Creates confluence-graph-skillset with graph enrichment skill  
- Creates confluence-graph-indexer with proper field mappings
- Uses JSON configuration files for maintainability
- Incorporates all fixes from iterative development
"""

import os
import sys
import json
import time
import requests
import subprocess
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType, VectorSearch,
    HnswAlgorithmConfiguration, VectorSearchProfile, SemanticConfiguration,
    SemanticPrioritizedFields, SemanticField, ScoringProfile,
    TextWeights
)

# Add parent directory to path to import from notebooks
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from notebooks.config import SearchConfig
    USE_NOTEBOOKS_CONFIG = True
except ImportError:
    USE_NOTEBOOKS_CONFIG = False

def load_config() -> Dict[str, str]:
    """Load configuration with fallback to notebooks.SearchConfig"""
    
    # Try notebooks config first (from fix-deployment-with-config.py)
    if USE_NOTEBOOKS_CONFIG:
        try:
            search_config = SearchConfig.from_environment()
            # Convert to dict format expected by rest of script
            config = {
                'SEARCH_SERVICE': search_config.search_service,
                'SEARCH_KEY': search_config.search_key,
                'SEARCH_ENDPOINT': search_config.search_endpoint,
                'RESOURCE_GROUP': search_config.resource_group,
                'FUNCTION_APP': search_config.function_app_name,
                'AZURE_OPENAI_ENDPOINT': search_config.azure_openai_endpoint,
                'AZURE_OPENAI_KEY': search_config.azure_openai_key,
                'AZURE_OPENAI_DEPLOYMENT': getattr(search_config, 'azure_openai_deployment', 'text-embedding-ada-002'),
                'GRAPH_ENRICHMENT_FUNCTION_KEY': search_config.function_key,
                'GRAPH_ENRICHMENT_FUNCTION_URL': getattr(search_config, 'graph_enrichment_function_url', 'https://func-rag-conf.azurewebsites.net/api/enrich'),
                'STORAGE_CONNECTION_STRING': getattr(search_config, 'storage_connection_string', '')
            }
            print("✅ Loaded configuration from notebooks.config.SearchConfig")
            return config
        except Exception as e:
            print(f"⚠️ Could not load from notebooks config: {e}")
    
    # Fallback to manual config loading
    config = {}
    
    # Try to load from .env files in order of preference
    env_files = [
        '.env',

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
        'SEARCH_SERVICE', 'SEARCH_KEY', 'SEARCH_ENDPOINT', 'RESOURCE_GROUP',
        'FUNCTION_APP', 'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_KEY',
        'AZURE_OPENAI_API_KEY', 'STORAGE_CONNECTION_STRING'
    ]
    
    for var in required_vars:
        if var in os.environ:
            config[var] = os.environ[var]
    
    # Handle environment variable name variations
    if 'AZURE_OPENAI_API_KEY' in config and 'AZURE_OPENAI_KEY' not in config:
        config['AZURE_OPENAI_KEY'] = config['AZURE_OPENAI_API_KEY']
    
    if 'AZ_RESOURCE_GROUP' in config and 'RESOURCE_GROUP' not in config:
        config['RESOURCE_GROUP'] = config['AZ_RESOURCE_GROUP']
    
    # Set defaults
    config.setdefault('SEARCH_SERVICE', 'srch-rag-conf')
    config.setdefault('RESOURCE_GROUP', 'rg-rag-confluence')
    config.setdefault('FUNCTION_APP', 'func-rag-graph-enrich')
    config.setdefault('AZURE_OPENAI_ENDPOINT', 'https://aoai-rag-confluence.openai.azure.com/')
    config.setdefault('AZURE_OPENAI_DEPLOYMENT', 'text-embedding-ada-002')
    config.setdefault('GRAPH_ENRICHMENT_FUNCTION_URL', 'https://func-rag-conf.azurewebsites.net/api/enrich')
    config.setdefault('GRAPH_ENRICHMENT_FUNCTION_KEY', 'I4PX3ZZiSUanVIA6L_5FntHJqxioNeyAJJY8sYjzzigzAzFuZXRGLg==')
    
    # Build search endpoint if not provided
    if 'SEARCH_ENDPOINT' not in config and 'SEARCH_SERVICE' in config:
        config['SEARCH_ENDPOINT'] = f"https://{config['SEARCH_SERVICE']}.search.windows.net"
    
    return config

def get_function_key(config: Dict[str, str]) -> Optional[str]:
    """Get the function key for graph enrichment skill using Azure CLI"""
    # Try to get from environment first
    if 'GRAPH_ENRICHMENT_FUNCTION_KEY' in os.environ:
        return os.environ['GRAPH_ENRICHMENT_FUNCTION_KEY']
    
    # Try to get using Azure CLI
    try:
        resource_group = get_config_value(config, 'resource_group')
        function_app = get_config_value(config, 'function_app_name')
        
        if not resource_group or not function_app:
            print("⚠️ Resource group or function app name not available for CLI lookup")
            return None
            
        cmd = [
            'az', 'functionapp', 'function', 'keys', 'list',
            '--resource-group', resource_group,
            '--name', function_app,
            '--function-name', 'graph_enrichment_skill',
            '--query', 'default',
            '--output', 'tsv'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        print(f"Warning: Could not retrieve function key via Azure CLI: {e}")
    
    print("Note: Function key should be set in GRAPH_ENRICHMENT_FUNCTION_KEY env var")
    return None

def get_config_value(config: Dict[str, str], key: str) -> str:
    """Extract config value from dictionary"""
    return config.get(key, '')

def cleanup_existing_resources(config: Dict[str, str]) -> bool:
    """Delete existing skillset and indexer before creating new ones (from fix-v2-index-complete.py)"""
    
    search_endpoint = get_config_value(config, 'search_endpoint')
    search_key = get_config_value(config, 'search_key')
    
    headers = {"api-key": search_key}
    
    resources_to_delete = [
        ("skillsets", "confluence-graph-skillset"),
        ("indexers", "confluence-graph-indexer")
    ]
    
    for resource_type, resource_name in resources_to_delete:
        url = f"{search_endpoint}/{resource_type}/{resource_name}?api-version=2023-11-01"
        print(f"Deleting existing {resource_type} '{resource_name}'...")
        response = requests.delete(url, headers=headers)
        if response.status_code in [204, 404]:
            print(f"✅ {resource_type} deleted/not found")
        else:
            print(f"⚠️ Failed to delete {resource_type}: {response.status_code}")
    
    time.sleep(2)  # Allow time for cleanup
    return True

def load_and_process_json_template(template_path: str, config: Dict[str, str]) -> Dict[str, Any]:
    """Load JSON template and replace template variables with actual values"""
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")
    
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    # Replace template variables with actual values
    replacements = {
        '{{AZURE_OPENAI_ENDPOINT}}': get_config_value(config, 'azure_openai_endpoint'),
        '{{AZURE_OPENAI_KEY}}': get_config_value(config, 'azure_openai_key'),
        '{{AZURE_OPENAI_DEPLOYMENT}}': get_config_value(config, 'azure_openai_deployment'),
        '{{GRAPH_ENRICHMENT_FUNCTION_URL}}': get_config_value(config, 'GRAPH_ENRICHMENT_FUNCTION_URL'),
        '{{GRAPH_ENRICHMENT_FUNCTION_KEY}}': get_config_value(config, 'GRAPH_ENRICHMENT_FUNCTION_KEY'),
        '{{STORAGE_CONNECTION_STRING}}': get_config_value(config, 'STORAGE_CONNECTION_STRING')
    }
    
    for placeholder, value in replacements.items():
        template_content = template_content.replace(placeholder, value)
    
    return json.loads(template_content)

def create_index(config: Dict[str, str]) -> bool:
    """Create the new index with graph enrichment fields using Azure SDK"""
    print("\n📊 Creating new index with graph enrichment fields...")
    
    try:
        search_endpoint = get_config_value(config, 'search_endpoint')
        search_key = get_config_value(config, 'search_key')
        
        # Create Azure Search client
        credential = AzureKeyCredential(search_key)
        search_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
        
        # Load index definition from JSON
        index_def = load_and_process_json_template('config/confluence-graph-embeddings-v2.json', config)
        
        # Check if index exists
        try:
            existing_index = search_client.get_index(index_def['name'])
            print(f"ℹ️ Index '{index_def['name']}' already exists, skipping creation")
            return True
        except Exception:
            # Index doesn't exist, create it
            pass
        
        # Convert JSON to SearchIndex object for better validation
        # Note: For complex index definitions, we'll use the JSON directly with REST API
        # as the SDK doesn't handle all advanced features like semantic search easily
        
        # Use REST API for full control over complex index definition
        url = f"{search_endpoint}/indexes/{index_def['name']}?api-version=2023-11-01"
        headers = {
            'Content-Type': 'application/json',
            'api-key': search_key
        }
        
        response = requests.put(url, json=index_def, headers=headers)
        
        if response.status_code in [200, 201]:
            print(f"✅ Index '{index_def['name']}' created successfully")
            return True
        else:
            print(f"❌ Failed to create index: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating index: {e}")
        return False

def create_skillset(config: Dict[str, str]) -> bool:
    """Create skillset with proper field mapping and graph enrichment"""
    print("\n🧠 Creating skillset with proper field mappings...")
    
    try:
        search_endpoint = get_config_value(config, 'search_endpoint')
        search_key = get_config_value(config, 'search_key')
        
        # Get function key dynamically
        function_key = get_function_key(config)
        if function_key:
            # Update the function key in the config for template processing
            if isinstance(config, dict):
                config['GRAPH_ENRICHMENT_FUNCTION_KEY'] = function_key
            else:
                # For SearchConfig, we'll handle this in template processing
                pass
        
        # Load skillset definition from JSON
        skillset_def = load_and_process_json_template('config/confluence-graph-skillset.json', config)
        
        # If we got a function key dynamically, update the skillset definition
        if function_key:
            for skill in skillset_def.get('skills', []):
                if skill.get('name') == 'GraphEnrichmentSkill':
                    skill['httpHeaders']['x-functions-key'] = function_key
                    break
        
        # Create skillset
        url = f"{search_endpoint}/skillsets/{skillset_def['name']}?api-version=2023-11-01"
        headers = {"Content-Type": "application/json", "api-key": search_key}
        
        response = requests.put(url, json=skillset_def, headers=headers)
        
        if response.status_code in [200, 201]:
            print("✅ Skillset created successfully!")
            return True
        else:
            print(f"❌ Failed to create skillset: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Error creating skillset: {e}")
        return False

def create_indexer(config: Dict[str, str]) -> bool:
    """Create indexer with proper field mappings (from fix-v2-index-complete.py)"""
    print("\n🔄 Creating indexer with proper field mappings...")
    
    try:
        search_endpoint = get_config_value(config, 'search_endpoint')
        search_key = get_config_value(config, 'search_key')
        
        # Load indexer definition from JSON
        indexer_def = load_and_process_json_template('config/confluence-graph-indexer.json', config)
        
        # Create indexer
        url = f"{search_endpoint}/indexers/{indexer_def['name']}?api-version=2023-11-01"
        headers = {"Content-Type": "application/json", "api-key": search_key}
        
        response = requests.put(url, json=indexer_def, headers=headers)
        
        if response.status_code in [200, 201]:
            print("✅ Indexer created successfully!")
            return True
        else:
            print(f"❌ Failed to create indexer: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Error creating indexer: {e}")
        return False

def check_prerequisites(config: Union[Dict[str, str], SearchConfig]) -> bool:
    """Check if all required configuration and packages are available"""
    print("\n🔍 Checking prerequisites...")
    
    # Check required configuration
    required_configs = [
        ('search_endpoint', 'SEARCH_ENDPOINT'),
        ('search_key', 'SEARCH_KEY'),
        ('azure_openai_endpoint', 'AZURE_OPENAI_ENDPOINT'),
        ('azure_openai_key', 'AZURE_OPENAI_KEY')
    ]
    
    missing_configs = []
    for config_key, env_key in required_configs:
        value = get_config_value(config, config_key)
        if not value:
            missing_configs.append(env_key)
    
    if missing_configs:
        print(f"❌ Missing required configuration: {', '.join(missing_configs)}")
        print("Please set these environment variables or add them to your .env file")
        return False
    
    # Check if config files exist
    required_files = [
        'config/confluence-graph-embeddings-v2.json',
        'config/confluence-graph-skillset.json',
        'config/confluence-graph-indexer.json'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing required configuration files: {', '.join(missing_files)}")
        return False
    
    # Check Python packages
    print("\n📦 Checking Python packages...")
    required_packages = ['azure.search.documents', 'azure.core', 'requests']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - Install with: pip install {package.replace('.', '-')}")
            missing_packages.append(package.replace('.', '-'))
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        return False
    
    # Check Azure CLI (optional but recommended)
    print("\n🔧 Checking Azure CLI...")
    try:
        result = subprocess.run(['az', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✅ Azure CLI installed")
            
            # Check if authenticated
            result = subprocess.run(['az', 'account', 'show'], capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✅ Azure CLI authenticated")
            else:
                print("  ⚠️ Azure CLI not authenticated (run: az login)")
        else:
            print("  ⚠️ Azure CLI not found (optional, but needed for function key retrieval)")
    except FileNotFoundError:
        print("  ⚠️ Azure CLI not installed (optional, but recommended)")
    
    print("✅ All prerequisites met")
    return True

def main():
    """Main deployment function with cleanup and validation"""
    
    print("🚀 Starting Graph Enriched Search Deployment")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    
    # Check prerequisites
    if not check_prerequisites(config):
        print("❌ Prerequisites not met. Please check configuration.")
        return False
    
    # Cleanup existing resources (from fix-v2-index-complete.py)
    print("\n🧹 Cleaning up existing resources...")
    cleanup_existing_resources(config)
    
    # Create infrastructure
    success = True
    
    print("\n📊 Creating search infrastructure...")
    success &= create_index(config)
    success &= create_skillset(config)
    success &= create_indexer(config)
    
    if success:
        print("\n✅ Infrastructure deployment completed successfully!")
        print("\n📋 Next steps:")
        print("1. Run: python 02_migration_and_verification.py")
        print("2. Monitor indexer progress")
        print("3. Test search functionality")
        return True
    else:
        print("\n❌ Infrastructure deployment failed!")
        return False

if __name__ == "__main__":
    main()

02_migration_and_verification: 

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

00_deploy-driver

#!/bin/bash

# Graph Enrichment Integration Deployment Script
# This script runs both deployment steps for graph enrichment integration

set -e

echo "🚀 Starting Graph Enrichment Integration Deployment"
echo "================================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f "../.env" ] && [ ! -f ".env" ] && [ ! -f "../infra/.env" ]; then
    echo -e "${RED}❌ No .env file found. Please create one with required configuration${NC}"
    echo "Required variables:"
    echo "  - SEARCH_KEY"
    echo "  - AZURE_OPENAI_KEY" 
    echo "  - GRAPH_ENRICHMENT_FUNCTION_KEY (optional)"
    exit 1
fi

# Step 1: Deploy infrastructure
echo -e "\n${GREEN}📋 Step 1: Deploying Search Infrastructure${NC}"
echo "Creating index, skillset, and indexer..."
python3 01_deploy_graph_enriched_search.py

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Infrastructure deployment failed${NC}"
    exit 1
fi

# Ask user if they want to run the indexer
echo -e "\n${GREEN}✅ Infrastructure deployment completed successfully${NC}"
read -p "Do you want to run the indexer now? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Step 2: Run migration and verification
    echo -e "\n${GREEN}📋 Step 2: Running Migration and Verification${NC}"
    python3 02_migration_and_verification.py
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Migration failed${NC}"
        exit 1
    fi
    
    echo -e "\n${GREEN}✅ Deployment completed successfully!${NC}"
else
    echo -e "\n${GREEN}ℹ️ Infrastructure deployed. Run the following when ready:${NC}"
    echo "python3 02_migration_and_verification.py"
fi

echo -e "\n${GREEN}📚 Next Steps:${NC}"
echo "1. Verify the results in Azure Portal"
echo "2. Test search queries with graph-aware scoring"
echo "3. Update your application to use 'confluence-graph-embeddings-v2' index"