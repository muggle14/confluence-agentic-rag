#!/usr/bin/env python3
"""
Utility Classes for Graph Population Module
Provides helper functions for progress tracking, validation, and analysis
"""

import time
import hashlib
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ProgressTracker:
    """Track progress of graph population operations"""
    
    total_items: int = 0
    processed_items: int = 0
    start_time: Optional[datetime] = None
    last_update_time: Optional[datetime] = None
    update_interval: float = 5.0  # seconds
    
    def start(self, total_items: int) -> None:
        """Start tracking progress"""
        self.total_items = total_items
        self.processed_items = 0
        self.start_time = datetime.utcnow()
        self.last_update_time = self.start_time
        print(f"📈 Starting progress tracking for {total_items} items")
    
    def update(self, increment: int = 1) -> None:
        """Update progress and optionally print status"""
        self.processed_items += increment
        current_time = datetime.utcnow()
        
        # Print progress at intervals or when complete
        if (self.last_update_time and 
            (current_time - self.last_update_time).total_seconds() >= self.update_interval) or \
           self.processed_items >= self.total_items:
            
            self._print_progress()
            self.last_update_time = current_time
    
    def finish(self) -> Dict[str, Any]:
        """Finish tracking and return summary"""
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0
        
        summary = {
            'total_items': self.total_items,
            'processed_items': self.processed_items,
            'duration_seconds': duration,
            'items_per_second': self.processed_items / duration if duration > 0 else 0,
            'completion_rate': self.processed_items / self.total_items if self.total_items > 0 else 0
        }
        
        print(f"✅ Progress complete: {self.processed_items}/{self.total_items} in {duration:.2f}s")
        return summary
    
    def _print_progress(self) -> None:
        """Print current progress status"""
        if self.total_items > 0:
            percentage = (self.processed_items / self.total_items) * 100
            print(f"  📊 Progress: {self.processed_items}/{self.total_items} ({percentage:.1f}%)")


class DataValidator:
    """Validate data integrity and consistency"""
    
    def __init__(self):
        """Initialize validator"""
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
    
    def validate_page_data(self, page_data: Dict[str, Any]) -> bool:
        """Validate a single page data structure"""
        is_valid = True
        page_id = page_data.get('pageId', 'unknown')
        
        # Required fields
        required_fields = ['pageId', 'title']
        for field in required_fields:
            if not page_data.get(field):
                self.validation_errors.append(f"Page {page_id}: Missing required field '{field}'")
                is_valid = False
        
        # Data type validation
        if 'updated' in page_data:
            try:
                datetime.fromisoformat(page_data['updated'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                self.validation_warnings.append(f"Page {page_id}: Invalid date format in 'updated' field")
        
        # Content validation
        content = page_data.get('content', {})
        if not any([content.get('html'), content.get('text'), content.get('markdown')]):
            self.validation_warnings.append(f"Page {page_id}: No content in any format")
        
        # Links validation
        links = page_data.get('links', [])
        for i, link in enumerate(links):
            if not link.get('url') and not link.get('text'):
                self.validation_warnings.append(f"Page {page_id}: Link {i} has no URL or text")
        
        return is_valid
    
    def validate_batch_data(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a batch of page data"""
        print("🔍 Validating batch data...")
        
        valid_pages = 0
        invalid_pages = 0
        
        # Track duplicates
        page_ids = set()
        duplicates = []
        
        for page_data in pages_data:
            page_id = page_data.get('pageId', '')
            
            if page_id in page_ids:
                duplicates.append(page_id)
            else:
                page_ids.add(page_id)
            
            if self.validate_page_data(page_data):
                valid_pages += 1
            else:
                invalid_pages += 1
        
        # Report duplicates
        if duplicates:
            for page_id in duplicates:
                self.validation_errors.append(f"Duplicate page ID found: {page_id}")
        
        validation_summary = {
            'total_pages': len(pages_data),
            'valid_pages': valid_pages,
            'invalid_pages': invalid_pages,
            'duplicate_pages': len(duplicates),
            'errors': self.validation_errors.copy(),
            'warnings': self.validation_warnings.copy(),
            'is_valid': invalid_pages == 0 and len(duplicates) == 0
        }
        
        if validation_summary['is_valid']:
            print(f"✅ Validation passed: {valid_pages} valid pages")
        else:
            print(f"⚠️ Validation issues: {invalid_pages} invalid, {len(duplicates)} duplicates")
            print(f"   Errors: {len(self.validation_errors)}, Warnings: {len(self.validation_warnings)}")
        
        return validation_summary
    
    def reset(self) -> None:
        """Reset validation state"""
        self.validation_errors.clear()
        self.validation_warnings.clear()


class GraphAnalyzer:
    """Analyze graph structure and provide insights"""
    
    def __init__(self):
        """Initialize analyzer"""
        self.analysis_cache: Dict[str, Any] = {}
    
    def analyze_page_relationships(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze relationships between pages"""
        print("📊 Analyzing page relationships...")
        
        # Track relationships
        page_to_space = {}
        space_to_pages = {}
        internal_links = []
        external_links = []
        page_hierarchy = {}
        
        for page_data in pages_data:
            page_id = page_data.get('pageId', '')
            space_key = page_data.get('spaceKey', '')
            
            # Space relationships
            if space_key:
                page_to_space[page_id] = space_key
                if space_key not in space_to_pages:
                    space_to_pages[space_key] = []
                space_to_pages[space_key].append(page_id)
            
            # Link analysis
            links = page_data.get('links', [])
            for link in links:
                link_type = link.get('type', '')
                if link.get('internal_page_id'):
                    internal_links.append({
                        'from': page_id,
                        'to': link['internal_page_id'],
                        'text': link.get('text', '')
                    })
                elif link_type in ['external', 'email']:
                    external_links.append({
                        'from': page_id,
                        'url': link.get('url', ''),
                        'type': link_type,
                        'text': link.get('text', '')
                    })
            
            # Hierarchy analysis (from breadcrumb)
            breadcrumb = page_data.get('breadcrumb', [])
            if len(breadcrumb) > 1:
                page_hierarchy[page_id] = {
                    'depth': len(breadcrumb) - 1,  # Exclude space
                    'path': breadcrumb
                }
        
        analysis = {
            'spaces': {
                'total_spaces': len(space_to_pages),
                'pages_per_space': {space: len(pages) for space, pages in space_to_pages.items()},
                'largest_space': max(space_to_pages.items(), key=lambda x: len(x[1])) if space_to_pages else None
            },
            'links': {
                'internal_links_count': len(internal_links),
                'external_links_count': len(external_links),
                'total_links': len(internal_links) + len(external_links),
                'pages_with_links': len(set(link['from'] for link in internal_links + external_links))
            },
            'hierarchy': {
                'pages_with_hierarchy': len(page_hierarchy),
                'max_depth': max(h['depth'] for h in page_hierarchy.values()) if page_hierarchy else 0,
                'avg_depth': sum(h['depth'] for h in page_hierarchy.values()) / len(page_hierarchy) if page_hierarchy else 0
            },
            'statistics': {
                'total_pages': len(pages_data),
                'pages_with_content': len([p for p in pages_data if p.get('content', {}).get('text', '').strip()]),
                'pages_with_tables': len([p for p in pages_data if p.get('tables', [])]),
                'pages_with_images': len([p for p in pages_data if p.get('images', [])])
            }
        }
        
        # Cache analysis
        self.analysis_cache['page_relationships'] = analysis
        
        print(f"📈 Analysis complete:")
        print(f"  - {analysis['spaces']['total_spaces']} spaces")
        print(f"  - {analysis['links']['total_links']} total links ({analysis['links']['internal_links_count']} internal)")
        print(f"  - {analysis['hierarchy']['pages_with_hierarchy']} pages with hierarchy")
        print(f"  - Max hierarchy depth: {analysis['hierarchy']['max_depth']}")
        
        return analysis
    
    def identify_orphaned_pages(self, pages_data: List[Dict[str, Any]]) -> List[str]:
        """Identify pages that have no incoming or outgoing relationships"""
        print("🔍 Identifying orphaned pages...")
        
        all_page_ids = set(p.get('pageId', '') for p in pages_data)
        linked_pages = set()
        
        # Collect all pages that are linked to or from
        for page_data in pages_data:
            page_id = page_data.get('pageId', '')
            
            # This page is linked to (it exists, so it's not orphaned by default)
            linked_pages.add(page_id)
            
            # Pages this page links to
            links = page_data.get('links', [])
            for link in links:
                if link.get('internal_page_id'):
                    linked_pages.add(link['internal_page_id'])
            
            # Pages in hierarchy (breadcrumb implies relationships)
            breadcrumb = page_data.get('breadcrumb', [])
            if len(breadcrumb) > 1:
                linked_pages.add(page_id)  # Has hierarchy context
        
        # Find orphaned pages (pages with no relationships)
        orphaned = []
        for page_data in pages_data:
            page_id = page_data.get('pageId', '')
            links = page_data.get('links', [])
            breadcrumb = page_data.get('breadcrumb', [])
            
            # Check if page has any outgoing links or hierarchy
            has_outgoing_links = any(link.get('internal_page_id') for link in links)
            has_hierarchy = len(breadcrumb) > 1
            
            if not has_outgoing_links and not has_hierarchy:
                # Check if any other page links to this one
                is_target = any(
                    any(link.get('internal_page_id') == page_id for link in p.get('links', []))
                    for p in pages_data if p.get('pageId') != page_id
                )
                
                if not is_target:
                    orphaned.append(page_id)
        
        print(f"🔍 Found {len(orphaned)} potentially orphaned pages")
        return orphaned
    
    def generate_link_recommendations(self, pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate recommendations for missing links based on content similarity"""
        print("💡 Generating link recommendations...")
        
        recommendations = []
        
        # Simple text-based similarity (could be enhanced with embeddings in Phase 2)
        for i, page1 in enumerate(pages_data):
            page1_id = page1.get('pageId', '')
            page1_title = page1.get('title', '').lower()
            page1_content = page1.get('content', {}).get('text', '').lower()
            
            for j, page2 in enumerate(pages_data[i+1:], i+1):
                page2_id = page2.get('pageId', '')
                page2_title = page2.get('title', '').lower()
                page2_content = page2.get('content', {}).get('text', '').lower()
                
                # Skip if already linked
                existing_links = {link.get('internal_page_id') for link in page1.get('links', [])}
                if page2_id in existing_links:
                    continue
                
                # Check for title mentions in content
                if page2_title in page1_content and len(page2_title) > 3:
                    recommendations.append({
                        'from_page': page1_id,
                        'to_page': page2_id,
                        'reason': f"Page 1 content mentions '{page2_title}'",
                        'confidence': 'medium'
                    })
                
                if page1_title in page2_content and len(page1_title) > 3:
                    recommendations.append({
                        'from_page': page2_id,
                        'to_page': page1_id,
                        'reason': f"Page 2 content mentions '{page1_title}'",
                        'confidence': 'medium'
                    })
        
        # Limit recommendations to avoid overwhelming output
        recommendations = recommendations[:50]
        
        print(f"💡 Generated {len(recommendations)} link recommendations")
        return recommendations
    
    def get_cached_analysis(self, analysis_type: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis results"""
        return self.analysis_cache.get(analysis_type)


def generate_content_hash(content: str) -> str:
    """Generate a hash for content to detect changes"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def extract_domain_from_url(url: str) -> str:
    """Extract domain from URL"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or 'unknown'
    except Exception:
        return 'unknown'


def format_processing_time(seconds: float) -> str:
    """Format processing time in human-readable format"""
    if seconds < 60:
        return f"{seconds:.2f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.2f} hours"


def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """Safely load JSON with fallback"""
    try:
        import json
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return default


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def batch_items(items: List[Any], batch_size: int) -> List[List[Any]]:
    """Split items into batches of specified size"""
    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i:i + batch_size])
    return batches


def normalize_page_id(page_id: str) -> str:
    """Normalize page ID for consistent storage and retrieval"""
    return str(page_id).strip()


def is_valid_url(url: str) -> bool:
    """Check if URL is valid"""
    try:
        from urllib.parse import urlparse
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False 