import os
import json
import logging
import base64
from datetime import datetime, timedelta
import azure.functions as func
from azure.storage.blob import BlobServiceClient

def main(mytimer: func.TimerRequest) -> None:
    """
    Azure Function to ingest Confluence pages incrementally
    Triggered every 24 hours to fetch pages modified in the last day
    """
    logging.info('Starting Confluence data ingestion pipeline')
    
    try:
        # Get configuration from environment variables
        confluence_base = os.environ['CONFLUENCE_BASE']
        confluence_token = os.environ['CONFLUENCE_TOKEN']
        confluence_email = os.environ['CONFLUENCE_EMAIL']
        storage_conn = os.environ['STORAGE_CONN']
        
        # Ingestion settings
        delta_days = int(os.environ.get('DELTA_DAYS', '1'))
        space_keys = [s.strip() for s in os.environ.get('CONFLUENCE_SPACE_KEYS', '').split(',') if s.strip()]
        
        # Calculate time range for incremental updates
        since_date = (datetime.utcnow() - timedelta(days=delta_days)).isoformat() + "Z"
        
        logging.info(f'Fetching pages modified since: {since_date}')
        logging.info(f'Target spaces: {space_keys if space_keys else "ALL"}')
        
        # Initialize blob service client
        try:
            blob_service_client = BlobServiceClient.from_connection_string(storage_conn)
        except Exception as e:
            logging.error(f'Failed to initialize blob service client: {str(e)}')
            raise
        
        container_name = 'raw'
        
        # Create Basic Auth header for Confluence API
        auth_string = f"{confluence_email}:{confluence_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        # Headers for Confluence API
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Accept": "application/json"
        }
        
        # Import requests here to avoid cold start issues
        import requests
        
        # Get spaces to process
        spaces_to_process = []
        if space_keys:
            spaces_to_process = space_keys
        else:
            # Get all spaces if none specified
            spaces_response = requests.get(
                f"{confluence_base}/space",
                headers=headers,
                params={"limit": 500}
            )
            if spaces_response.status_code == 200:
                all_spaces = spaces_response.json().get('results', [])
                spaces_to_process = [space['key'] for space in all_spaces]
            else:
                logging.error(f'Failed to fetch spaces: {spaces_response.status_code}')
                raise Exception(f'Failed to fetch spaces: {spaces_response.text}')
        
        total_pages_processed = 0
        
        # Process each space
        for space_key in spaces_to_process:
            logging.info(f'Processing space: {space_key}')
            
            try:
                pages_in_space = fetch_pages_from_space(
                    confluence_base, headers, space_key, since_date
                )
                
                for page in pages_in_space:
                    try:
                        # Store page in blob storage
                        store_page_data(blob_service_client, container_name, page)
                        total_pages_processed += 1
                        
                        if total_pages_processed % 10 == 0:
                            logging.info(f'Processed {total_pages_processed} pages so far...')
                            
                    except Exception as e:
                        logging.error(f'Error processing page {page.get("id", "unknown")}: {str(e)}')
                        continue
                        
            except Exception as e:
                logging.error(f'Error processing space {space_key}: {str(e)}')
                continue
        
        logging.info(f'Confluence ingestion completed. Total pages processed: {total_pages_processed}')
        
        # Store ingestion metadata
        store_ingestion_metadata(blob_service_client, total_pages_processed, spaces_to_process)
        
    except Exception as e:
        logging.error(f'Critical error in Confluence ingestion: {str(e)}')
        raise

def fetch_pages_from_space(confluence_base, headers, space_key, since_date):
    """
    Fetch all pages from a specific space with pagination
    """
    import requests
    
    pages = []
    start = 0
    limit = 100
    
    while True:
        params = {
            "spaceKey": space_key,
            "start": start,
            "limit": limit,
            "expand": "body.storage,space,ancestors,version,history",
            "status": "current"
        }
        
        # Add date filter for incremental updates
        if since_date:
            params["lastModified"] = f">={since_date}"
        
        response = requests.get(
            f"{confluence_base}/content",
            headers=headers,
            params=params
        )
        
        if response.status_code != 200:
            logging.error(f'Failed to fetch pages from space {space_key}: {response.status_code}')
            break
        
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            break
        
        # Filter pages by space (API sometimes returns pages from other spaces)
        space_pages = [page for page in results if page.get('space', {}).get('key') == space_key]
        pages.extend(space_pages)
        
        logging.info(f'Fetched {len(space_pages)} pages from space {space_key} (batch {start//limit + 1})')
        
        # Check if we've reached the end
        if len(results) < limit:
            break
            
        start += limit
    
    return pages

def store_page_data(blob_service_client, container_name, page):
    """
    Store page data in blob storage with enriched metadata
    """
    page_id = page['id']
    
    # Enrich page data with additional metadata
    enriched_page = {
        'id': page_id,
        'title': page.get('title', ''),
        'type': page.get('type', ''),
        'status': page.get('status', ''),
        'space': {
            'key': page.get('space', {}).get('key', ''),
            'name': page.get('space', {}).get('name', '')
        },
        'body': page.get('body', {}),
        'ancestors': page.get('ancestors', []),
        'version': {
            'number': page.get('version', {}).get('number', 0),
            'when': page.get('version', {}).get('when', ''),
            'by': page.get('version', {}).get('by', {})
        },
        'history': page.get('history', {}),
        '_links': page.get('_links', {}),
        'ingestion_timestamp': datetime.utcnow().isoformat(),
        'ingestion_metadata': {
            'pipeline_version': '1.0',
            'source': 'confluence_api',
            'incremental_update': True
        }
    }
    
    # Create blob name
    blob_name = f"{page_id}.json"
    
    # Get blob client
    blob_client = blob_service_client.get_blob_client(
        container=container_name,
        blob=blob_name
    )
    
    # Upload the enriched page data
    blob_client.upload_blob(
        json.dumps(enriched_page, indent=2, ensure_ascii=False),
        overwrite=True,
        content_type='application/json'
    )
    
    logging.debug(f'Stored page: {page_id} - {page.get("title", "No title")}')

def store_ingestion_metadata(blob_service_client, total_pages, spaces_processed):
    """
    Store metadata about the ingestion run
    """
    metadata = {
        'ingestion_timestamp': datetime.utcnow().isoformat(),
        'total_pages_processed': total_pages,
        'spaces_processed': spaces_processed,
        'pipeline_version': '1.0',
        'status': 'completed'
    }
    
    # Store in metadata container
    blob_client = blob_service_client.get_blob_client(
        container='metadata',
        blob=f"ingestion_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    )
    
    blob_client.upload_blob(
        json.dumps(metadata, indent=2),
        overwrite=True,
        content_type='application/json'
    ) 