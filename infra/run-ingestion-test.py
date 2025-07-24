#!/usr/bin/env python3
"""
Manual Confluence Ingestion Test
"""

import os
import sys
import json
import base64
import requests
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient

def load_environment():
    """Load environment variables from file"""
    env_files = ['../.env.updated', '../.env', '.env.updated', '.env']
    
    for env_file in env_files:
        if os.path.exists(env_file):
            print(f"📋 Loading environment from: {env_file}")
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        try:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
                        except ValueError:
                            continue
            return env_file
    
    raise FileNotFoundError("No environment file found")

def get_auth_headers():
    """Create authentication headers for Confluence API"""
    email = os.environ['CONFLUENCE_EMAIL']
    token = os.environ['CONFLUENCE_TOKEN']
    
    credentials = f"{email}:{token}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    return {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/json'
    }

def fetch_all_pages():
    """Fetch all pages from Confluence"""
    print("🔍 Fetching Confluence pages...")
    
    base_url = os.environ['CONFLUENCE_BASE']
    headers = get_auth_headers()
    
    # Get all spaces
    spaces_url = f"{base_url}/space"
    print(f"🌐 Fetching spaces from: {spaces_url}")
    
    try:
        spaces_response = requests.get(spaces_url, headers=headers)
        spaces_response.raise_for_status()
        spaces_data = spaces_response.json()
        spaces = spaces_data.get('results', [])
        
        print(f"📂 Found {len(spaces)} spaces")
        
        all_pages = []
        
        # Fetch pages from each space
        for space in spaces:
            space_key = space['key']
            space_name = space.get('name', space_key)
            print(f"🔍 Processing space: {space_name} ({space_key})")
            
            # Fetch pages from this space
            pages_url = f"{base_url}/content"
            params = {
                'spaceKey': space_key,
                'type': 'page',
                'limit': 50,  # Increase limit for more pages
                'expand': 'body.storage,space,ancestors,version,history'
            }
            
            start = 0
            space_pages = []
            
            while True:
                params['start'] = start
                
                try:
                    pages_response = requests.get(pages_url, headers=headers, params=params)
                    pages_response.raise_for_status()
                    pages_data = pages_response.json()
                    
                    batch_pages = pages_data.get('results', [])
                    if not batch_pages:
                        break
                    
                    space_pages.extend(batch_pages)
                    start += len(batch_pages)
                    
                    # Check if we have more pages
                    if len(batch_pages) < params['limit']:
                        break
                        
                except requests.exceptions.RequestException as e:
                    print(f"  ❌ Error fetching pages from {space_key}: {e}")
                    break
            
            print(f"  ✅ Found {len(space_pages)} pages in {space_name}")
            all_pages.extend(space_pages)
        
        return all_pages
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching spaces: {e}")
        return []

def store_pages_in_blob(pages):
    """Store pages in Azure Blob Storage"""
    if not pages:
        print("⚠️  No pages to store")
        return 0
    
    print(f"💾 Storing {len(pages)} pages in blob storage...")
    
    # Get storage connection string from environment
    storage_account = os.environ['STORAGE_ACCOUNT']
    storage_key = os.environ['STORAGE_KEY']
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"
    
    try:
        blob_service = BlobServiceClient.from_connection_string(connection_string)
        
        stored_count = 0
        
        for i, page in enumerate(pages):
            try:
                # Enrich page data with ingestion metadata
                enriched_page = {
                    **page,
                    'ingestion_timestamp': datetime.utcnow().isoformat(),
                    'ingestion_metadata': {
                        'pipeline_version': '1.0',
                        'source': 'confluence_api',
                        'incremental_update': False,
                        'manual_trigger': True,
                        'test_run': True
                    }
                }
                
                # Store in blob storage
                blob_name = f"{page['id']}.json"
                blob_client = blob_service.get_blob_client(container='raw', blob=blob_name)
                
                blob_content = json.dumps(enriched_page, indent=2, ensure_ascii=False)
                blob_client.upload_blob(blob_content, overwrite=True)
                
                stored_count += 1
                
                # Progress indicator
                if (i + 1) % 10 == 0 or (i + 1) == len(pages):
                    print(f"  📊 Progress: {i + 1}/{len(pages)} pages stored")
                
            except Exception as e:
                print(f"  ❌ Failed to store page {page.get('id', 'unknown')}: {e}")
        
        # Store ingestion metadata
        metadata = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_pages_processed': stored_count,
            'total_pages_found': len(pages),
            'status': 'completed',
            'trigger_type': 'manual_test_all_spaces',
            'spaces_processed': list(set(page.get('space', {}).get('key', 'unknown') for page in pages))
        }
        
        metadata_blob = f"ingestion_test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        metadata_client = blob_service.get_blob_client(container='metadata', blob=metadata_blob)
        metadata_client.upload_blob(json.dumps(metadata, indent=2), overwrite=True)
        
        print(f"💾 Successfully stored {stored_count}/{len(pages)} pages")
        print(f"📝 Metadata stored: {metadata_blob}")
        
        return stored_count
        
    except Exception as e:
        print(f"❌ Error connecting to blob storage: {e}")
        return 0

def main():
    """Main function"""
    print("🚀 Confluence Ingestion Pipeline Test")
    print("=" * 50)
    
    try:
        # Load environment
        env_file = load_environment()
        
        # Required environment variables
        required_vars = ['CONFLUENCE_BASE', 'CONFLUENCE_EMAIL', 'CONFLUENCE_TOKEN', 
                        'STORAGE_ACCOUNT', 'STORAGE_KEY']
        
        missing_vars = [var for var in required_vars if var not in os.environ]
        if missing_vars:
            print(f"❌ Missing environment variables: {missing_vars}")
            return
        
        print(f"🔗 Confluence URL: {os.environ['CONFLUENCE_BASE']}")
        print(f"👤 Email: {os.environ['CONFLUENCE_EMAIL']}")
        print(f"💾 Storage Account: {os.environ['STORAGE_ACCOUNT']}")
        
        # Fetch all pages from Confluence
        pages = fetch_all_pages()
        
        if not pages:
            print("⚠️  No pages retrieved from Confluence")
            return
        
        print(f"\n📊 Summary of fetched data:")
        print(f"  Total pages: {len(pages)}")
        
        # Group by space for summary
        spaces = {}
        for page in pages:
            space_key = page.get('space', {}).get('key', 'unknown')
            space_name = page.get('space', {}).get('name', space_key)
            if space_key not in spaces:
                spaces[space_key] = {'name': space_name, 'count': 0}
            spaces[space_key]['count'] += 1
        
        print(f"  Spaces processed: {len(spaces)}")
        for space_key, info in spaces.items():
            print(f"    - {info['name']} ({space_key}): {info['count']} pages")
        
        # Store pages in blob storage
        stored_count = store_pages_in_blob(pages)
        
        print(f"\n✅ Ingestion completed successfully!")
        print(f"📊 Final summary:")
        print(f"  - Pages found: {len(pages)}")
        print(f"  - Pages stored: {stored_count}")
        print(f"  - Success rate: {(stored_count/len(pages)*100):.1f}%")
        
        # Verify storage
        print(f"\n🔍 Verifying storage...")
        storage_account = os.environ['STORAGE_ACCOUNT']
        storage_key = os.environ['STORAGE_KEY']
        connection_string = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"
        
        blob_service = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service.get_container_client('raw')
        
        blob_count = len(list(container_client.list_blobs()))
        print(f"📁 Total blobs in 'raw' container: {blob_count}")
        
    except Exception as e:
        print(f"❌ Error during ingestion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main() 