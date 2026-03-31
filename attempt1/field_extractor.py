#!/usr/bin/env python3
"""
Field extraction script that uses LLM to extract specific text sections from documents
based on category definitions from categories.json.
Stores extracted fields in a new database table.
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from database_manager import DocumentDatabase
from llm_models import llm_call


class FieldExtractor:
    """Extracts specific fields from documents using LLM based on category definitions."""
    
    def __init__(self, db_path: str = "storage/documents.db", categories_file: str = "categories.json",
                 api_key: str = None, base_url: str = None):
        """
        Initialize field extractor with database, categories, and LLM configuration.
        
        Args:
            db_path: Path to SQLite database
            categories_file: Path to categories configuration file
            api_key: LLM API key
            base_url: LLM base URL
        """
        self.db = DocumentDatabase(db_path)
        self.categories_file = categories_file
        self.categories = self.load_categories()
        self.api_key = api_key or "test-key"
        self.base_url = base_url or "http://localhost:8000/v1"
        self.create_extraction_table()
    
    def load_categories(self) -> Dict[str, Any]:
        """
        Load categories from JSON file.
        
        Returns:
            Categories dictionary
        """
        try:
            with open(self.categories_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('categories', {})
        except FileNotFoundError:
            print(f"Categories file not found: {self.categories_file}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing categories file: {e}")
            return {}
    
    def create_extraction_table(self):
        """Create the document_fields table for storing extracted fields."""
        query = """
        CREATE TABLE IF NOT EXISTS document_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            category_key TEXT NOT NULL,
            field_name TEXT NOT NULL,
            extracted_text TEXT,
            extraction_method TEXT,
            confidence_score REAL,
            start_position INTEGER,
            end_position INTEGER,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
        """
        
        try:
            self.db.connection.execute(query)
            self.db.connection.commit()
            print("Document fields table created/verified successfully")
        except Exception as e:
            print(f"Error creating document_fields table: {e}")
            raise
    
    def extract_field_with_llm(self, full_text: str, field_name: str, category_key: str) -> Optional[Dict[str, Any]]:
        """
        Use LLM to extract specific field content from document text.
        
        Args:
            full_text: Full document text
            field_name: Name of the field to extract
            category_key: Category key for context
            
        Returns:
            Extraction result with text and metadata
        """
        # Truncate text if too long for LLM context
        max_chars = 15000
        truncated_text = full_text[:max_chars] + "..." if len(full_text) > max_chars else full_text
        
        # Get category context
        category_data = self.categories.get(category_key, {})
        category_description = category_data.get('description', '')
        category_keywords = category_data.get('keywords', [])
        
        system_prompt = f"""You are an expert document analyst specializing in extracting specific information from {category_description} documents.

Your task is to extract the content for the field "{field_name}" from the provided document text.

Extraction Guidelines:
1. Extract ONLY the content that directly corresponds to the "{field_name}" field
2. Do not generate or invent any content - only extract what exists in the document
3. If the field contains multiple sections (like introduction), extract the complete section
4. If the field is a single value (like date), extract just that value
5. Preserve the original formatting and structure
6. If the field is not found in the document, respond with "FIELD_NOT_FOUND"

Category Context: {category_description}
Keywords for this category: {', '.join(category_keywords)}

Respond with a JSON object containing:
{{
  "extracted_text": "The exact text extracted from the document",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of how you found this content"
}}"""
        
        user_prompt = f"""Document Category: {category_key}
Field to Extract: {field_name}

Document Text:
{truncated_text}

Please extract the content for the "{field_name}" field from this document."""
        
        try:
            response = llm_call(
                api_key=self.api_key,
                base_url=self.base_url,
                thinking_level=8,
                temperature=0.1,  # Low temperature for consistent extraction
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Check if field was found
                if result.get('extracted_text') == 'FIELD_NOT_FOUND':
                    return None
                
                # Verify the extracted text exists in original
                extracted_text = result.get('extracted_text', '')
                if self.verify_text_in_original(extracted_text, full_text):
                    return {
                        'text': extracted_text,
                        'confidence': result.get('confidence', 0.5),
                        'method': 'llm',
                        'reasoning': result.get('reasoning', 'LLM extraction')
                    }
                else:
                    print(f"Warning: LLM extracted text for field '{field_name}' not found in original document")
                    return None
            else:
                print(f"Error parsing LLM response for field '{field_name}'")
                return None
                
        except Exception as e:
            print(f"Error calling LLM for field '{field_name}': {e}")
            return None
    
    def verify_text_in_original(self, extracted_text: str, original_text: str) -> bool:
        """
        Verify that extracted text actually exists in the original document.
        
        Args:
            extracted_text: The text that was extracted
            original_text: The original document text
            
        Returns:
            True if text is verified in original, False otherwise
        """
        try:
            # Clean and normalize both texts for comparison
            extracted_clean = re.sub(r'\s+', ' ', extracted_text.strip().lower())
            original_clean = re.sub(r'\s+', ' ', original_text.strip().lower())
            
            # Check if extracted text is contained in original text
            if extracted_clean in original_clean:
                return True
            
            # Check for substantial overlap (at least 80% of extracted text)
            if len(extracted_clean) > 20:
                words_extracted = extracted_clean.split()
                words_found = 0
                for word in words_extracted:
                    if word in original_clean:
                        words_found += 1
                
                overlap_ratio = words_found / len(words_extracted)
                if overlap_ratio >= 0.8:
                    return True
            
            return False
        except Exception:
            return False
    
    def extract_fields_from_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract all expected fields from a document using LLM.
        
        Args:
            document: Document data from database
            
        Returns:
            List of extracted field results
        """
        # Get document category
        category_info = self.db.get_document_category(document['id'])
        if not category_info:
            return []
        
        category_key = category_info['category_key']
        category_data = self.categories.get(category_key, {})
        expected_fields = category_data.get('expected_fields', [])
        
        full_text = document.get('full_text', '')
        extracted_fields = []
        
        for field_name in expected_fields:
            print(f"  Extracting field: {field_name}")
            
            # Use LLM to extract the field
            field_result = self.extract_field_with_llm(full_text, field_name, category_key)
            
            if field_result:
                # Find positions in original text
                start_pos, end_pos = self.find_text_positions(field_result['text'], full_text)
                
                extracted_fields.append({
                    'field_name': field_name,
                    'extracted_text': field_result['text'],
                    'extraction_method': field_result['method'],
                    'confidence_score': field_result['confidence'],
                    'start_position': start_pos,
                    'end_position': end_pos
                })
                
                print(f"    ✓ Extracted {len(field_result['text'])} characters")
            else:
                print(f"    ✗ Field not found")
        
        return extracted_fields
    
    def find_text_positions(self, extracted_text: str, original_text: str) -> Tuple[int, int]:
        """
        Find the start and end positions of extracted text in original document.
        
        Args:
            extracted_text: The extracted text
            original_text: The original document text
            
        Returns:
            Tuple of (start_position, end_position)
        """
        try:
            # Clean both texts for searching
            extracted_clean = re.sub(r'\s+', ' ', extracted_text.strip())
            original_clean = re.sub(r'\s+', ' ', original_text.strip())
            
            # Find the position
            pos = original_clean.find(extracted_clean)
            if pos != -1:
                # Map back to original text (approximate)
                return pos, pos + len(extracted_clean)
            else:
                # Try with first few words
                words = extracted_clean.split()[:5]
                search_text = ' '.join(words)
                pos = original_clean.find(search_text)
                if pos != -1:
                    return pos, pos + len(extracted_clean)
            
            return 0, len(extracted_text)
        except Exception:
            return 0, len(extracted_text)
    
    def store_extracted_fields(self, document_id: int, category_key: str, extracted_fields: List[Dict[str, Any]]):
        """
        Store extracted fields in the database.
        
        Args:
            document_id: ID of the document
            category_key: Category key for the document
            extracted_fields: List of extracted field data
        """
        for field_data in extracted_fields:
            query = """
            INSERT INTO document_fields 
            (document_id, category_key, field_name, extracted_text, extraction_method, 
             confidence_score, start_position, end_position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            try:
                self.db.connection.execute(query, (
                    document_id,
                    category_key,
                    field_data['field_name'],
                    field_data['extracted_text'],
                    field_data['extraction_method'],
                    field_data['confidence_score'],
                    field_data.get('start_position'),
                    field_data.get('end_position')
                ))
            except Exception as e:
                print(f"Error storing field {field_data['field_name']} for document {document_id}: {e}")
        
        self.db.connection.commit()
    
    def process_all_documents(self) -> Dict[str, Any]:
        """
        Process all documents and extract fields using LLM based on their categories.
        
        Returns:
            Processing summary
        """
        documents = self.db.get_all_documents()
        
        if not documents:
            print("No documents found in database")
            return {}
        
        print(f"Processing {len(documents)} documents for field extraction...")
        
        summary = {
            'total_documents': len(documents),
            'processed_documents': 0,
            'total_fields_extracted': 0,
            'category_breakdown': {},
            'field_breakdown': {},
            'errors': []
        }
        
        for doc in documents:
            doc_id = doc['id']
            file_path = doc['file_path']
            
            print(f"\nExtracting fields from: {file_path}")
            
            try:
                # Get document category
                category_info = self.db.get_document_category(doc_id)
                if not category_info:
                    print(f"  No category found for document {doc_id}")
                    continue
                
                category_key = category_info['category_key']
                
                # Extract fields using LLM
                extracted_fields = self.extract_fields_from_document(doc)
                
                # Store fields
                if extracted_fields:
                    self.store_extracted_fields(doc_id, category_key, extracted_fields)
                    
                    # Update summary
                    summary['processed_documents'] += 1
                    summary['total_fields_extracted'] += len(extracted_fields)
                    
                    # Category breakdown
                    if category_key not in summary['category_breakdown']:
                        summary['category_breakdown'][category_key] = {'documents': 0, 'fields': 0}
                    summary['category_breakdown'][category_key]['documents'] += 1
                    summary['category_breakdown'][category_key]['fields'] += len(extracted_fields)
                    
                    # Field breakdown
                    for field in extracted_fields:
                        field_name = field['field_name']
                        if field_name not in summary['field_breakdown']:
                            summary['field_breakdown'][field_name] = 0
                        summary['field_breakdown'][field_name] += 1
                    
                    print(f"  ✓ Extracted {len(extracted_fields)} fields")
                else:
                    print(f"  ✗ No fields extracted")
                
            except Exception as e:
                error_msg = f"Error processing document {doc_id}: {e}"
                print(f"  ✗ {error_msg}")
                summary['errors'].append(error_msg)
        
        return summary
    
    def get_extraction_summary(self) -> Dict[str, Any]:
        """
        Get summary of all field extractions from database.
        
        Returns:
            Extraction summary statistics
        """
        query = """
        SELECT 
            category_key,
            field_name,
            COUNT(*) as extraction_count,
            AVG(confidence_score) as avg_confidence,
            COUNT(DISTINCT document_id) as document_count,
            AVG(LENGTH(extracted_text)) as avg_text_length
        FROM document_fields
        GROUP BY category_key, field_name
        ORDER BY category_key, extraction_count DESC
        """
        
        try:
            cursor = self.db.connection.execute(query)
            results = cursor.fetchall()
            
            summary = {}
            for row in results:
                category_key, field_name, count, avg_conf, doc_count, avg_length = row
                if category_key not in summary:
                    summary[category_key] = {}
                summary[category_key][field_name] = {
                    'extraction_count': count,
                    'avg_confidence': avg_conf,
                    'document_count': doc_count,
                    'avg_text_length': avg_length
                }
            
            return summary
        except Exception as e:
            print(f"Error getting extraction summary: {e}")
            return {}
    
    def save_extraction_results(self, summary: Dict[str, Any], output_file: str = "storage/extraction_results.json"):
        """
        Save extraction results to file.
        
        Args:
            summary: Extraction summary
            output_file: Output file path
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"Extraction results saved to: {output_path}")


def main():
    """Main execution function."""
    # Initialize field extractor
    extractor = FieldExtractor()
    
    # Process all documents
    summary = extractor.process_all_documents()
    
    # Get detailed summary
    detailed_summary = extractor.get_extraction_summary()
    
    # Combine results
    final_results = {
        'processing_summary': summary,
        'detailed_breakdown': detailed_summary,
        'timestamp': str(datetime.now())
    }
    
    # Save results
    extractor.save_extraction_results(final_results)
    
    # Print summary
    print("\n" + "="*50)
    print("FIELD EXTRACTION RESULTS")
    print("="*50)
    print(f"Documents Processed: {summary['processed_documents']}")
    print(f"Total Fields Extracted: {summary['total_fields_extracted']}")
    print(f"Errors: {len(summary['errors'])}")
    
    print("\nCategory Breakdown:")
    for category, data in summary['category_breakdown'].items():
        print(f"  {category}: {data['documents']} docs, {data['fields']} fields")
    
    print("\nTop Fields Extracted:")
    field_counts = summary['field_breakdown']
    top_fields = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for field_name, count in top_fields:
        print(f"  {field_name}: {count} times")
    
    print("="*50)


if __name__ == "__main__":
    main()
