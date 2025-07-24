"""
Text chunking strategies for Confluence content
"""

import tiktoken
from typing import List, Dict, Any, Tuple
import re
from .models import EmbeddingChunk, ChunkType


class ConfluenceChunker:
    """Smart chunking for Confluence pages"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 128):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoder = tiktoken.get_encoding("cl100k_base")
        
    def chunk_page(self, page_data: Dict[str, Any]) -> List[EmbeddingChunk]:
        """Generate all chunks for a page"""
        chunks = []
        page_id = page_data['pageId']
        
        # 1. Title vector (high salience)
        chunks.append(self._create_title_chunk(page_data))
        
        # 2. Page summary vector (for fallback)
        chunks.append(self._create_page_summary_chunk(page_data))
        
        # 3. Section header vectors
        chunks.extend(self._create_section_header_chunks(page_data))
        
        # 4. Body vectors (sliding window)
        chunks.extend(self._create_body_chunks(page_data))
        
        # 5. Table vectors (structured + summary)
        chunks.extend(self._create_table_chunks(page_data))
        
        # 6. Image vectors (alt text/captions)
        chunks.extend(self._create_image_chunks(page_data))
        
        return chunks
    
    def _create_title_chunk(self, page_data: Dict) -> EmbeddingChunk:
        """Create a high-salience title chunk"""
        title = page_data.get('title', '')
        breadcrumb = page_data.get('breadcrumb', [])
        
        # Combine title with breadcrumb for context
        content = f"{' › '.join(breadcrumb)} › {title}" if breadcrumb else title
        
        return EmbeddingChunk(
            id=f"{page_data['pageId']}-title",
            page_id=page_data['pageId'],
            chunk_type=ChunkType.TITLE,
            content=content,
            metadata={
                'title': title,
                'breadcrumb': breadcrumb,
                'space_key': page_data.get('spaceKey', ''),
                'space_name': page_data.get('spaceName', '')
            }
        )
    
    def _create_page_summary_chunk(self, page_data: Dict) -> EmbeddingChunk:
        """Create a page-level summary for graph fallback"""
        # Combine title with first section or abstract
        title = page_data.get('title', '')
        sections = page_data.get('sections', [])
        
        # Get first non-empty section content
        first_content = ""
        for section in sections[:3]:  # Check first 3 sections
            content = section.get('content', '').strip()
            if content and len(content) > 50:
                first_content = content[:500]  # First 500 chars
                break
        
        summary_content = f"{title}\n\n{first_content}" if first_content else title
        
        return EmbeddingChunk(
            id=f"{page_data['pageId']}-summary",
            page_id=page_data['pageId'],
            chunk_type=ChunkType.PAGE_SUMMARY,
            content=summary_content,
            metadata={
                'title': title,
                'is_fallback_vector': True
            }
        )
    
    def _create_section_header_chunks(self, page_data: Dict) -> List[EmbeddingChunk]:
        """Create chunks for section headers"""
        chunks = []
        sections = page_data.get('sections', [])
        
        for i, section in enumerate(sections):
            heading = section.get('heading', '').strip()
            if heading and heading != "Content":  # Skip default headings
                content = f"{page_data['title']} - {heading}"
                
                chunk = EmbeddingChunk(
                    id=f"{page_data['pageId']}-header-{i}",
                    page_id=page_data['pageId'],
                    chunk_type=ChunkType.SECTION_HEADER,
                    content=content,
                    metadata={
                        'section_index': i,
                        'heading': heading,
                        'heading_level': section.get('level', 1)
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    def _create_body_chunks(self, page_data: Dict) -> List[EmbeddingChunk]:
        """Create body text chunks with sliding window"""
        chunks = []
        sections = page_data.get('sections', [])
        
        for section_idx, section in enumerate(sections):
            text = section.get('content', '').strip()
            if not text:
                continue
                
            heading = section.get('heading', '')
            
            # Split into paragraphs first
            paragraphs = self._split_into_paragraphs(text)
            
            # Apply sliding window with paragraph awareness
            windows = self._sliding_window_with_boundaries(
                paragraphs, 
                self.chunk_size, 
                self.chunk_overlap
            )
            
            for window_idx, window_text in enumerate(windows):
                chunk = EmbeddingChunk(
                    id=f"{page_data['pageId']}-body-{section_idx}-{window_idx}",
                    page_id=page_data['pageId'],
                    chunk_type=ChunkType.BODY,
                    content=window_text,
                    metadata={
                        'section_index': section_idx,
                        'section_heading': heading,
                        'window_index': window_idx,
                        'total_windows': len(windows)
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    def _create_table_chunks(self, page_data: Dict) -> List[EmbeddingChunk]:
        """Create chunks for tables (raw + summary)"""
        chunks = []
        tables = page_data.get('tables', [])
        
        for table_idx, table in enumerate(tables):
            # 1. Raw table as markdown
            markdown_table = self._table_to_markdown(table)
            if markdown_table:
                raw_chunk = EmbeddingChunk(
                    id=f"{page_data['pageId']}-table-{table_idx}",
                    page_id=page_data['pageId'],
                    chunk_type=ChunkType.TABLE,
                    content=markdown_table,
                    metadata={
                        'table_index': table_idx,
                        'caption': table.get('caption', ''),
                        'rows_count': len(table.get('rows', [])),
                        'columns_count': len(table.get('headers', []))
                    }
                )
                chunks.append(raw_chunk)
            
            # 2. Table summary (to be generated by LLM in processing)
            summary_text = self._generate_table_summary(table)
            if summary_text:
                summary_chunk = EmbeddingChunk(
                    id=f"{page_data['pageId']}-table-summary-{table_idx}",
                    page_id=page_data['pageId'],
                    chunk_type=ChunkType.TABLE_SUMMARY,
                    content=summary_text,
                    metadata={
                        'table_index': table_idx,
                        'is_summary': True
                    }
                )
                chunks.append(summary_chunk)
        
        return chunks
    
    def _create_image_chunks(self, page_data: Dict) -> List[EmbeddingChunk]:
        """Create chunks for image alt texts"""
        chunks = []
        images = page_data.get('images', [])
        
        for img_idx, image in enumerate(images):
            # Combine alt text, title, and placeholder
            alt = image.get('alt', '').strip()
            title = image.get('title', '').strip()
            placeholder = image.get('placeholder', f'Image {img_idx + 1}')
            
            # Create descriptive text
            content_parts = []
            if alt:
                content_parts.append(f"Image: {alt}")
            if title and title != alt:
                content_parts.append(f"Title: {title}")
            if not content_parts:
                content_parts.append(placeholder)
            
            content = " - ".join(content_parts)
            
            chunk = EmbeddingChunk(
                id=f"{page_data['pageId']}-image-{img_idx}",
                page_id=page_data['pageId'],
                chunk_type=ChunkType.IMAGE_ALT,
                content=content,
                metadata={
                    'image_index': img_idx,
                    'src': image.get('src', ''),
                    'has_analysis': image.get('analysis', '') != 'TODO: LLM analysis for image understanding'
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs"""
        # Split on double newlines or common paragraph boundaries
        paragraphs = re.split(r'\n\s*\n', text)
        # Clean and filter
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _sliding_window_with_boundaries(
        self, 
        paragraphs: List[str], 
        window_size: int, 
        overlap: int
    ) -> List[str]:
        """Apply sliding window respecting paragraph boundaries"""
        if not paragraphs:
            return []
        
        windows = []
        current_window = []
        current_tokens = 0
        
        for paragraph in paragraphs:
            paragraph_tokens = len(self.encoder.encode(paragraph))
            
            # If adding this paragraph exceeds window size
            if current_tokens + paragraph_tokens > window_size and current_window:
                # Save current window
                windows.append('\n\n'.join(current_window))
                
                # Start new window with overlap
                overlap_tokens = 0
                new_window = []
                
                # Add paragraphs from the end until we reach overlap size
                for p in reversed(current_window):
                    p_tokens = len(self.encoder.encode(p))
                    if overlap_tokens + p_tokens <= overlap:
                        new_window.insert(0, p)
                        overlap_tokens += p_tokens
                    else:
                        break
                
                current_window = new_window
                current_tokens = overlap_tokens
            
            # Add paragraph to current window
            current_window.append(paragraph)
            current_tokens += paragraph_tokens
        
        # Add final window
        if current_window:
            windows.append('\n\n'.join(current_window))
        
        return windows
    
    def _table_to_markdown(self, table: Dict) -> str:
        """Convert table to markdown format"""
        if not table.get('headers') and not table.get('rows'):
            return ""
        
        lines = []
        
        # Add caption if present
        if table.get('caption'):
            lines.append(f"**{table['caption']}**")
            lines.append("")
        
        # Headers
        headers = table.get('headers', [])
        if headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # Rows
        for row in table.get('rows', []):
            if row:  # Skip empty rows
                # Ensure row has same number of columns as headers
                while len(row) < len(headers):
                    row.append("")
                lines.append("| " + " | ".join(str(cell) for cell in row[:len(headers)]) + " |")
        
        return "\n".join(lines)
    
    def _generate_table_summary(self, table: Dict) -> str:
        """Generate a summary for the table (placeholder for LLM generation)"""
        # This will be replaced with actual LLM generation in processing
        caption = table.get('caption', '')
        headers = table.get('headers', [])
        rows_count = len(table.get('rows', []))
        
        if caption:
            summary = f"Table: {caption}"
        elif headers:
            summary = f"Table with columns: {', '.join(headers[:5])}"
            if len(headers) > 5:
                summary += f" and {len(headers) - 5} more"
        else:
            summary = f"Table with {rows_count} rows"
        
        if rows_count > 0:
            summary += f" ({rows_count} data rows)"
        
        return summary
    
    def get_chunk_statistics(self, chunks: List[EmbeddingChunk]) -> Dict[str, Any]:
        """Get statistics about generated chunks"""
        stats = {
            'total_chunks': len(chunks),
            'by_type': {},
            'total_tokens': 0,
            'avg_tokens_per_chunk': 0
        }
        
        for chunk in chunks:
            chunk_type = chunk.chunk_type.value
            stats['by_type'][chunk_type] = stats['by_type'].get(chunk_type, 0) + 1
            
            tokens = len(self.encoder.encode(chunk.content))
            stats['total_tokens'] += tokens
        
        if chunks:
            stats['avg_tokens_per_chunk'] = stats['total_tokens'] / len(chunks)
        
        return stats 