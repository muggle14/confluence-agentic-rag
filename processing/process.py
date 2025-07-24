#!/usr/bin/env python3
"""
process.py
==========

Copy & transform Confluence page JSON from the *raw* blob container
to the *processed* container in the same storage account.

Prereqs
-------
pip install azure-storage-blob beautifulsoup4 html2text

ENV (from ../env file)
---
STORAGE_ACCOUNT                    Azure storage account name
STORAGE_KEY                       Azure storage account key
CONFLUENCE_DOMAIN                 e.g. "hchaturvedi14.atlassian.net/wiki"
RAW_CONTAINER                     raw container name (default: raw)
PROC_CONTAINER                    dest container name (default: processed)
"""

import os
import json
import re
import asyncio
import datetime
from typing import Dict, Any, List
from pathlib import Path

from azure.storage.blob.aio import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
from bs4 import BeautifulSoup
import html2text
from azure.storage.blob import ContentSettings

# --------------------------------------------------------------------
# Config
# --------------------------------------------------------------------
def load_env_from_file():
    """Load environment variables from ../env file"""
    env_files = ['../.env', '../env', '.env', 'env']
    
    for env_path in env_files:
        if os.path.exists(env_path):
            print(f"📋 Loading environment from: {env_path}")
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        try:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
                        except ValueError:
                            continue
            return env_path
    # If the loop completes without returning, no env file was found
    return None

# Load environment
env_file = load_env_from_file()
if not env_file:
    print("❌ No environment file found")
    print("   Looking for: ../.env, ../env, .env, env")
    exit(1)

# Get configuration from environment
STORAGE_ACCOUNT = os.getenv("STORAGE_ACCOUNT")
STORAGE_KEY = os.getenv("STORAGE_KEY")
CONFLUENCE_DOMAIN = os.getenv("CONFLUENCE_DOMAIN")
RAW_CONTAINER = os.getenv("RAW_CONTAINER", "raw")
PROC_CONTAINER = os.getenv("PROC_CONTAINER", "processed")

# Validate required environment variables
if not STORAGE_ACCOUNT or not STORAGE_KEY:
    print("❌ Missing required environment variables: STORAGE_ACCOUNT, STORAGE_KEY")
    print(f"   STORAGE_ACCOUNT: {STORAGE_ACCOUNT}")
    print(f"   STORAGE_KEY: {'***' if STORAGE_KEY else 'NOT SET'}")
    exit(1)

# Build connection string
CONN_STR = f"DefaultEndpointsProtocol=https;AccountName={STORAGE_ACCOUNT};AccountKey={STORAGE_KEY};EndpointSuffix=core.windows.net"

# HTML to text converter settings
H2T = html2text.HTML2Text()
H2T.ignore_links = True
H2T.ignore_images = True
H2T.body_width = 0  # no line-wrap

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def to_abs(path_or_url: str) -> str:
    """Convert relative path to absolute URL"""

    return path_or_url if path_or_url.startswith("http") else f"https://{CONFLUENCE_DOMAIN}{path_or_url}"

def plain_text(html: str, max_len=65_000) -> str:
    """Convert HTML to plain text with length limit"""
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(" ", strip=True)[:max_len]

def headings(soup: BeautifulSoup) -> List[str]:
    """Extract all headings from HTML"""
    return [h.get_text(" ", strip=True) for h in soup.find_all(re.compile(r"h[1-6]"))]

def links(soup: BeautifulSoup) -> List[str]:
    """Extract all links from HTML"""
    return [a["href"] for a in soup.find_all("a", href=True)]

def images(soup: BeautifulSoup) -> List[str]:
    """Extract all image sources from HTML"""
    return [img["src"] for img in soup.find_all("img", src=True)]

def extract_page_id_from_url(url: str) -> str:
    """Extract Confluence page ID from URL if possible"""
    if not url:
        return ""
    
    # Pattern for Confluence page URLs
    patterns = [
        r'/pages/(\d+)/',
        r'/content/(\d+)',
        r'pageId=(\d+)',
        r'/(\d+)/'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return ""

# --------------------------------------------------------------------
# Transform
# --------------------------------------------------------------------
def transform(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Transform raw Confluence JSON to processed format"""
    ancestors = raw.get("ancestors", [])
    ancestor_ids = [str(a["id"]) for a in ancestors]
    ancestor_titles = [a.get("title", "") for a in ancestors]
    parent_id = ancestor_ids[-1] if ancestor_ids else None

    space = raw.get("space", {})
    html_body = raw["body"]["storage"]["value"]
    soup = BeautifulSoup(html_body, "lxml")

    # Extract links and categorize them
    all_links = links(soup)
    internal_links = [link for link in all_links if 'atlassian.net' in link or 'confluence' in link]
    external_links = [link for link in all_links if link.startswith('http') and not ('atlassian.net' in link or 'confluence' in link)]

    return {
        # ── required fields for search index ──────────────────────────
        "id": str(raw["id"]),
        "page_id": str(raw["id"]),
        "title": raw.get("title", ""),
        "url": to_abs(raw["_links"]["webui"]),
        "space_key": space.get("key", ""),
        "content": { "text": plain_text(html_body) },
        
        # ── hierarchy and navigation fields ───────────────────────────
        "parent_page_id": parent_id,
        "ancestors_ids": ancestor_ids,
        "ancestor_titles": ancestor_titles,
        "depth": len(ancestor_ids),
        "childrenIds": [],  # Will be populated by graph enrichment
        "adjacentIds": [],  # Will be populated by graph enrichment
        
        # ── metadata fields ───────────────────────────────────────────
        "spaceId": str(space.get("id", "")),
        "spaceName": space.get("name", ""),
        "updated": raw["version"]["when"],
        "created": raw["history"]["createdDate"],
        "version": raw["version"]["number"],
        
        # ── content formats ───────────────────────────────────────────
        "html_content": html_body,
        "markdown_content": H2T.handle(html_body),
        
        # ── structured content ────────────────────────────────────────
        "sections": headings(soup),
        "links": {
            "all": all_links,
            "internal": internal_links,
            "external": external_links
        },
        "images": images(soup),
        
        # ── labels and metadata ───────────────────────────────────────
        "labels": [l["name"] for l in raw.get("metadata", {}).get("labels", {}).get("results", [])],
        
        # ── processing metadata ───────────────────────────────────────
        "processing": {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": "process.py",
            "version": "2.0"
        }
    }

# --------------------------------------------------------------------
# Main async job
# --------------------------------------------------------------------
async def main():
    """Main processing function"""
    print(" Confluence Content Processing Pipeline - Phase 1")
    print("=" * 60)
    print(f"📊 Configuration:")
    print(f"  - Storage Account: {STORAGE_ACCOUNT}")
    print(f"  - Raw Container: {RAW_CONTAINER}")
    print(f"  - Processed Container: {PROC_CONTAINER}")
    print(f"  - Confluence Domain: {CONFLUENCE_DOMAIN}")
    print()

    blob_service = BlobServiceClient.from_connection_string(CONN_STR)
    src = blob_service.get_container_client(RAW_CONTAINER)
    dst = blob_service.get_container_client(PROC_CONTAINER)
    
    # Ensure processed container exists (handle version compatibility)
    try:
        await dst.create_container()
        print(f"📁 Created container: {PROC_CONTAINER}")
    except ResourceExistsError:
        print(f"📁 Container already exists: {PROC_CONTAINER}")
    except Exception as e:
        print(f"❌ Error creating container {PROC_CONTAINER}: {e}")
        return

    processed_count = 0
    skipped_count = 0
    error_count = 0

    async for blob in src.list_blobs(name_starts_with="", include=["metadata"]):
        if not blob.name.endswith(".json"):
            continue

        dest_blob = dst.get_blob_client(blob.name)
        
        try:
            # Check if processed copy is up-to-date
            dest_props = await dest_blob.get_blob_properties()
            if dest_props.metadata.get("raw_etag") == blob.etag:
                # processed copy is up-to-date
                skipped_count += 1
                if skipped_count % 10 == 0:
                    print(f"⏭️  Skipped {skipped_count} up-to-date files...")
                continue
        except Exception:
            pass  # blob not there yet

        try:
            # Download raw JSON - FIXED: Properly await the download
            download_stream = await src.download_blob(blob)
            raw_bytes = await download_stream.readall()
            raw_json = json.loads(raw_bytes)

            # Transform
            processed = transform(raw_json)
            data_bytes = json.dumps(processed, ensure_ascii=False).encode("utf-8")

            # Upload processed
            content_settings = ContentSettings(content_type="application/json")
            await dest_blob.upload_blob(
                data_bytes,
                overwrite=True,
                content_settings=content_settings,
                metadata={
                    "raw_etag": blob.etag,
                    "pageId": processed["page_id"],
                    "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            )
            
            processed_count += 1
            print(f"✅ Processed {blob.name} → {PROC_CONTAINER}/{blob.name}")
            
            # Progress indicator
            if processed_count % 5 == 0:
                print(f"📊 Progress: {processed_count} processed, {skipped_count} skipped")
                
        except Exception as e:
            error_count += 1
            print(f"❌ Error processing {blob.name}: {e}")

    # Print summary
    print(f"\n✅ Processing completed successfully!")
    print(f"📊 Summary:")
    print(f"  - Pages processed: {processed_count}")
    print(f"  - Pages skipped (up-to-date): {skipped_count}")
    print(f"  - Errors: {error_count}")
    print(f"  - Total files handled: {processed_count + skipped_count + error_count}")

if __name__ == "__main__":
    asyncio.run(main()) 