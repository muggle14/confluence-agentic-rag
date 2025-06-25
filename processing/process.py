#!/usr/bin/env python3
"""
Confluence Content Processing Pipeline - Phase 1
Converts raw Confluence JSON to structured, searchable format
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import base64

# HTML processing
from bs4 import BeautifulSoup, Tag
import html2text

# Azure Storage
from azure.storage.blob import BlobServiceClient

class ConfluenceProcessor:
    """Main processor for Confluence content transformation"""
    
    def __init__(self, storage_connection_string: str):
        """Initialize processor with Azure storage connection"""
        self.blob_service = BlobServiceClient.from_connection_string(storage_connection_string)
        self.raw_container = 'raw'
        self.processed_container = 'processed'
        
        # HTML to text converter settings
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.ignore_tables = False
        self.h2t.body_width = 0  # No line wrapping
        
        # Statistics
        self.stats = {
            'processed_count': 0,
            'error_count': 0,
            'tables_extracted': 0,
            'links_extracted': 0,
            'images_found': 0
        }
    
    def process_all_pages(self) -> Dict[str, Any]:
        """Process all pages in the raw container"""
        print("🔄 Starting Confluence content processing...")
        
        # Ensure processed container exists
        self._ensure_container_exists(self.processed_container)
        
        # List all blobs in raw container
        raw_blobs = list(self.blob_service.get_container_client(self.raw_container).list_blobs())
        total_pages = len(raw_blobs)
        
        print(f"📊 Found {total_pages} pages to process")
        
        for i, blob in enumerate(raw_blobs):
            if blob.name.endswith('.json'):
                try:
                    self._process_single_page(blob.name)
                    self.stats['processed_count'] += 1
                    
                    # Progress indicator
                    if (i + 1) % 5 == 0 or (i + 1) == total_pages:
                        print(f"  📊 Progress: {i + 1}/{total_pages} pages processed")
                        
                except Exception as e:
                    print(f"  ❌ Error processing {blob.name}: {e}")
                    self.stats['error_count'] += 1
        
        # Store processing metadata
        self._store_processing_metadata()
        
        return self.stats
    
    def _process_single_page(self, blob_name: str) -> None:
        """Process a single page from raw to processed format"""
        # Download raw page
        blob_client = self.blob_service.get_blob_client(container=self.raw_container, blob=blob_name)
        raw_content = blob_client.download_blob().readall()
        raw_page = json.loads(raw_content)
        
        # Extract page ID for filename
        page_id = raw_page.get('id', blob_name.replace('.json', ''))
        
        # Transform to processed format
        processed_page = self._transform_page(raw_page)
        
        # Store processed page
        processed_blob_name = f"{page_id}.json"
        processed_client = self.blob_service.get_blob_client(
            container=self.processed_container, 
            blob=processed_blob_name
        )
        
        processed_client.upload_blob(
            json.dumps(processed_page, indent=2, ensure_ascii=False),
            overwrite=True
        )
    
    def _transform_page(self, raw_page: Dict[str, Any]) -> Dict[str, Any]:
        """Transform raw page to processed format"""
        
        # Extract basic metadata
        page_id = raw_page.get('id', '')
        title = raw_page.get('title', '')
        updated = raw_page.get('version', {}).get('when', '')
        space = raw_page.get('space', {})
        
        # Extract content
        storage_content = raw_page.get('body', {}).get('storage', {}).get('value', '')
        
        # Process HTML content
        content_analysis = self._analyze_content(storage_content)
        
        # Extract breadcrumb from ancestors
        breadcrumb = self._extract_breadcrumb(raw_page.get('ancestors', []), space)
        
        # Build processed page structure
        processed_page = {
            "pageId": page_id,
            "title": title,
            "spaceKey": space.get('key', ''),
            "spaceName": space.get('name', ''),
            "updated": updated,
            "breadcrumb": breadcrumb,
            
            # Multi-format content
            "content": {
                "html": storage_content,
                "text": content_analysis['text'],
                "markdown": content_analysis['markdown']
            },
            
            # Structured elements
            "sections": content_analysis['sections'],
            "tables": content_analysis['tables'],
            "links": content_analysis['links'],
            "images": content_analysis['images'],
            
            # Processing metadata
            "processing": {
                "timestamp": datetime.utcnow().isoformat(),
                "pipeline_version": "1.0",
                "phase": "1_comprehensive",
                "stats": {
                    "sections_count": len(content_analysis['sections']),
                    "tables_count": len(content_analysis['tables']),
                    "links_count": len(content_analysis['links']),
                    "images_count": len(content_analysis['images']),
                    "text_length": len(content_analysis['text'])
                }
            }
        }
        
        # Update global stats
        self.stats['tables_extracted'] += len(content_analysis['tables'])
        self.stats['links_extracted'] += len(content_analysis['links'])
        self.stats['images_found'] += len(content_analysis['images'])
        
        return processed_page
    
    def _analyze_content(self, html_content: str) -> Dict[str, Any]:
        """Comprehensive analysis of HTML content"""
        if not html_content:
            return {
                'text': '',
                'markdown': '',
                'sections': [],
                'tables': [],
                'links': [],
                'images': []
            }
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract different content types
        sections = self._extract_sections(soup)
        tables = self._extract_tables(soup)
        links = self._extract_links(soup)
        images = self._extract_images(soup)
        
        # Convert to text and markdown
        text_content = self._html_to_text(html_content)
        markdown_content = self._html_to_markdown(html_content)
        
        return {
            'text': text_content,
            'markdown': markdown_content,
            'sections': sections,
            'tables': tables,
            'links': links,
            'images': images
        }
    
    def _extract_sections(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract content sections based on headings"""
        sections = []
        current_section = {"order": 0, "heading": "", "content": ""}
        order = 0
        
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div']):
            if element.name.startswith('h'):
                # Save previous section if it has content
                if current_section["content"].strip():
                    sections.append(current_section.copy())
                
                # Start new section
                order += 1
                current_section = {
                    "order": order,
                    "heading": element.get_text().strip(),
                    "level": int(element.name[1]),
                    "content": ""
                }
            else:
                # Add content to current section
                text = element.get_text().strip()
                if text:
                    current_section["content"] += text + "\n"
        
        # Add final section
        if current_section["content"].strip():
            sections.append(current_section)
        
        # If no sections found, create a default one
        if not sections and soup.get_text().strip():
            sections.append({
                "order": 1,
                "heading": "Content",
                "level": 1,
                "content": soup.get_text().strip()
            })
        
        return sections
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract and structure table data"""
        tables = []
        
        for i, table in enumerate(soup.find_all('table')):
            table_data = {
                "order": i + 1,
                "headers": [],
                "rows": [],
                "raw_html": str(table),
                "caption": ""
            }
            
            # Extract caption if present
            caption = table.find('caption')
            if caption:
                table_data["caption"] = caption.get_text().strip()
            
            # Extract headers
            header_row = table.find('tr')
            if header_row:
                headers = header_row.find_all(['th', 'td'])
                table_data["headers"] = [header.get_text().strip() for header in headers]
            
            # Extract data rows (skip header row)
            rows = table.find_all('tr')[1:] if table.find_all('tr') else []
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_data = [cell.get_text().strip() for cell in cells]
                if any(row_data):  # Only add non-empty rows
                    table_data["rows"].append(row_data)
            
            # Generate plain text representation
            if table_data["headers"] or table_data["rows"]:
                text_repr = self._table_to_text(table_data)
                table_data["text"] = text_repr
                tables.append(table_data)
        
        return tables
    
    def _extract_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract all links with categorization"""
        links = []
        
        for i, link in enumerate(soup.find_all('a')):
            href = link.get('href', '')
            text = link.get_text().strip()
            
            if not href and not text:
                continue
            
            link_data = {
                "order": i + 1,
                "text": text,
                "url": href,
                "type": self._classify_link(href),
                "internal_page_id": self._extract_page_id_from_url(href)
            }
            
            links.append(link_data)
        
        return links
    
    def _extract_images(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract image information with placeholders"""
        images = []
        
        for i, img in enumerate(soup.find_all('img')):
            src = img.get('src', '')
            alt = img.get('alt', '')
            title = img.get('title', '')
            
            # Create placeholder text
            placeholder_text = f"[IMAGE: {alt or title or f'Image {i+1}'}]"
            
            image_data = {
                "order": i + 1,
                "src": src,
                "alt": alt,
                "title": title,
                "placeholder": placeholder_text,
                # TODO Phase 2: Add LLM analysis, download and store images
                "analysis": "TODO: LLM analysis for image understanding",
                "local_path": "TODO: Download and store locally"
            }
            
            images.append(image_data)
        
        return images
    
    def _extract_breadcrumb(self, ancestors: List[Dict], space: Dict) -> List[str]:
        """Generate breadcrumb from ancestors"""
        breadcrumb = []
        
        # Add space name as root
        if space.get('name'):
            breadcrumb.append(space['name'])
        
        # Add ancestor titles
        for ancestor in ancestors:
            title = ancestor.get('title', '')
            if title:
                breadcrumb.append(title)
        
        return breadcrumb
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to clean text"""
        if not html:
            return ""
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Replace images with placeholders
        for img in soup.find_all('img'):
            alt = img.get('alt', 'Image')
            img.replace_with(f"[IMAGE: {alt}]")
        
        return soup.get_text(separator=' ', strip=True)
    
    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to Markdown format"""
        if not html:
            return ""
        
        try:
            return self.h2t.handle(html).strip()
        except Exception:
            # Fallback to text if markdown conversion fails
            return self._html_to_text(html)
    
    def _classify_link(self, url: str) -> str:
        """Classify link as internal, external, or other"""
        if not url:
            return "empty"
        
        if url.startswith('#'):
            return "anchor"
        elif url.startswith('mailto:'):
            return "email"
        elif url.startswith(('http://', 'https://')):
            if 'atlassian.net' in url or 'confluence' in url:
                return "internal_confluence"
            else:
                return "external"
        elif url.startswith('/'):
            return "internal_relative"
        else:
            return "other"
    
    def _extract_page_id_from_url(self, url: str) -> Optional[str]:
        """Extract Confluence page ID from URL if possible"""
        if not url:
            return None
        
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
        
        return None
    
    def _table_to_text(self, table_data: Dict) -> str:
        """Convert table data to readable text format"""
        text_lines = []
        
        if table_data.get("caption"):
            text_lines.append(f"Table: {table_data['caption']}")
            text_lines.append("")
        
        # Headers
        if table_data.get("headers"):
            headers = " | ".join(table_data["headers"])
            text_lines.append(headers)
            text_lines.append("-" * len(headers))
        
        # Rows
        for row in table_data.get("rows", []):
            row_text = " | ".join(str(cell) for cell in row)
            text_lines.append(row_text)
        
        return "\n".join(text_lines)
    
    def _ensure_container_exists(self, container_name: str) -> None:
        """Ensure container exists, create if it doesn't"""
        try:
            container_client = self.blob_service.get_container_client(container_name)
            container_client.get_container_properties()
        except Exception:
            # Container doesn't exist, create it
            self.blob_service.create_container(container_name)
            print(f"📁 Created container: {container_name}")
    
    def _store_processing_metadata(self) -> None:
        """Store processing run metadata"""
        metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "pipeline_version": "1.0",
            "phase": "1_comprehensive",
            "stats": self.stats,
            "status": "completed"
        }
        
        metadata_blob = f"processing_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        metadata_client = self.blob_service.get_blob_client(
            container='metadata', 
            blob=metadata_blob
        )
        
        metadata_client.upload_blob(
            json.dumps(metadata, indent=2),
            overwrite=True
        )
        
        print(f"📝 Processing metadata stored: {metadata_blob}")


def main():
    """Main execution function"""
    print("🚀 Confluence Content Processing Pipeline - Phase 1")
    print("=" * 60)
    
    # Load environment variables
    env_files = ['../.env.updated', '../.env', '.env.updated', '.env']
    env_file = None
    
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
            env_file = env_path
            break
    
    if not env_file:
        print("❌ No environment file found")
        return
    
    # Get storage connection
    storage_account = os.environ.get('STORAGE_ACCOUNT')
    storage_key = os.environ.get('STORAGE_KEY')
    
    if not storage_account or not storage_key:
        print("❌ Missing storage configuration")
        return
    
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"
    
    try:
        # Initialize processor
        processor = ConfluenceProcessor(connection_string)
        
        # Process all pages
        stats = processor.process_all_pages()
        
        # Print summary
        print(f"\n✅ Processing completed successfully!")
        print(f"📊 Summary:")
        print(f"  - Pages processed: {stats['processed_count']}")
        print(f"  - Errors: {stats['error_count']}")
        print(f"  - Tables extracted: {stats['tables_extracted']}")
        print(f"  - Links extracted: {stats['links_extracted']}")
        print(f"  - Images found: {stats['images_found']}")
        
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main() 