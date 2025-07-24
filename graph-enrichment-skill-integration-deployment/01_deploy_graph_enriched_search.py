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