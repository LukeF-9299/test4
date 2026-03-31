#!/usr/bin/env python3
"""
Document classification script using LLM to analyze and categorize documents.
Creates summaries, identifies document types, and assigns categories from categories.json.
"""

from typing import Dict, List, Any, Optional
import json
from pathlib import Path
from datetime import datetime

from database_manager import DocumentDatabase
from llm_models import llm_call


class DocumentClassifier:
    """Classifier for document analysis and categorization."""
    
    def __init__(self, db_path: str = "storage/documents.db", api_key: str = None, base_url: str = None, 
                 categories_file: str = "categories.json"):
        """
        Initialize classifier with database, LLM configuration, and categories.
        
        Args:
            db_path: Path to SQLite database
            api_key: LLM API key
            base_url: LLM base URL
            categories_file: Path to categories configuration file
        """
        self.db = DocumentDatabase(db_path)
        self.api_key = api_key or "test-key"
        self.base_url = base_url or "http://localhost:8000/v1"
        self.categories_file = categories_file
        self.categories = self.load_categories()
    
    def load_categories(self) -> Dict[str, Any]:
        """
        Load categories from JSON file or create empty structure for building.
        
        Returns:
            Categories dictionary
        """
        try:
            with open(self.categories_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('categories', {})
        except FileNotFoundError:
            print(f"Categories file not found: {self.categories_file}. Will build during classification.")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing categories file: {e}. Will rebuild during classification.")
            return {}
    
    def build_category_from_document(self, document: Dict[str, Any], summary: str) -> Optional[Dict[str, Any]]:
        """
        Build a category definition from a document analysis.
        
        Args:
            document: Document data from database
            summary: Document summary
            
        Returns:
            Category definition or None if analysis fails
        """
        file_name = document.get('file_name', '')
        file_extension = document.get('file_extension', '')
        full_text = document.get('full_text', '')
        
        # Truncate text if too long
        max_chars = 8000
        truncated_text = full_text[:max_chars] + "..." if len(full_text) > max_chars else full_text
        
        system_prompt = """You are a document analysis expert. Based on the provided document, create a category definition.

Your task is to:
1. Identify the document type and create a category name
2. Extract keywords that would help identify similar documents
3. Identify the expected fields that should be extracted from this document type
4. Provide a description of this document category

Respond with a JSON object containing:
{
  "category_name": "Human-readable category name",
  "description": "Description of this document type",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "expected_fields": {
    "field_name": {
      "description": "What this field contains",
      "type": "text|date|amount|list|section|paragraph",
      "required": true|false
    }
  }
}

Guidelines:
- Category names should be concise and descriptive (e.g., "Invoice", "Contract", "Report")
- Keywords should be terms commonly found in this document type
- Expected fields should be the key data elements to extract
- Field types: text (short text), date (dates), amount (monetary values), list (multiple items), section (long sections), paragraph (medium text)
- Mark required fields as true, optional as false"""
        
        user_prompt = f"""Document Name: {file_name}
File Type: {file_extension}

Document Summary: {summary}

Document Content Sample:
{truncated_text}

Please analyze this document and create a category definition."""
        
        try:
            response = llm_call(
                api_key=self.api_key,
                base_url=self.base_url,
                thinking_level=8,
                temperature=0.3,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                category_def = json.loads(json_match.group())
                return category_def
            else:
                print(f"Error parsing category definition response for {file_name}")
                return None
                
        except Exception as e:
            print(f"Error building category from document {file_name}: {e}")
            return None
    
    def merge_categories(self, existing_categories: Dict[str, Any], new_category: Dict[str, Any], category_key: str) -> Dict[str, Any]:
        """
        Merge a new category into existing categories, combining fields and keywords.
        
        Args:
            existing_categories: Current categories dictionary
            new_category: New category definition to merge
            category_key: Key for the new category
            
        Returns:
            Updated categories dictionary
        """
        if category_key in existing_categories:
            # Merge with existing category
            existing = existing_categories[category_key]
            
            # Combine keywords (remove duplicates)
            existing_keywords = set(existing.get('keywords', []))
            new_keywords = set(new_category.get('keywords', []))
            merged_keywords = list(existing_keywords.union(new_keywords))
            
            # Merge expected fields
            existing_fields = existing.get('expected_fields', {})
            new_fields = new_category.get('expected_fields', {})
            
            # Combine field definitions, preferring existing descriptions if they exist
            merged_fields = existing_fields.copy()
            for field_name, field_info in new_fields.items():
                if field_name not in merged_fields:
                    merged_fields[field_name] = field_info
                else:
                    # Merge field information, keeping the more detailed description
                    existing_info = merged_fields[field_name]
                    if len(field_info.get('description', '')) > len(existing_info.get('description', '')):
                        merged_fields[field_name] = field_info
            
            # Update the category
            existing_categories[category_key] = {
                'name': new_category.get('name', existing['name']),
                'description': new_category.get('description', existing['description']),
                'keywords': merged_keywords,
                'expected_fields': merged_fields
            }
        else:
            # Add new category
            existing_categories[category_key] = new_category
        
        return existing_categories
    
    def generate_category_key(self, category_name: str) -> str:
        """
        Generate a category key from category name.
        
        Args:
            category_name: Human-readable category name
            
        Returns:
            Category key (lowercase, underscore-separated)
        """
        # Convert to lowercase and replace spaces with underscores
        key = category_name.lower().replace(' ', '_')
        
        # Remove special characters except underscores
        key = re.sub(r'[^a-z0-9_]', '', key)
        
        # Ensure it's not empty
        if not key:
            key = 'other'
        
        return key
    
    def save_categories(self, categories: Dict[str, Any]):
        """
        Save categories to JSON file.
        
        Args:
            categories: Categories dictionary to save
        """
        # Ensure 'other' category exists
        if 'other' not in categories:
            categories['other'] = {
                'name': 'Other',
                'description': 'Documents that don\'t fit into any specific category',
                'keywords': [],
                'expected_fields': {}
            }
        
        # Create full structure
        categories_data = {
            'categories': categories,
            'metadata': {
                'version': '2.0',
                'created_date': datetime.now().strftime('%Y-%m-%d'),
                'updated_date': datetime.now().strftime('%Y-%m-%d'),
                'description': 'Document classification categories with keywords, expected fields, and field descriptions',
                'auto_generated': True
            }
        }
        
        try:
            with open(self.categories_file, 'w', encoding='utf-8') as f:
                json.dump(categories_data, f, indent=2, ensure_ascii=False)
            print(f"Categories saved to: {self.categories_file}")
        except Exception as e:
            print(f"Error saving categories: {e}")
    
    def classify_document(self, document: Dict[str, Any], summary: str) -> Dict[str, Any]:
    
    def create_document_summary(self, document: Dict[str, Any]) -> str:
        """
        Create a summary of a single document using LLM.
        
        Args:
            document: Document data from database
            
        Returns:
            Document summary
        """
        file_text = document.get('full_text', '')
        file_name = document.get('file_name', '')
        file_extension = document.get('file_extension', '')
        
        # Truncate text if too long for LLM context
        max_chars = 8000
        truncated_text = file_text[:max_chars] + "..." if len(file_text) > max_chars else file_text
        
        system_prompt = """You are a document analysis expert. Analyze the provided document text and create a concise summary that includes:
1. Main purpose/topic of the document
2. Key information or data points
3. Document structure and sections
4. Any forms, fields, or structured data present
5. Document type (e.g., invoice, contract, report, form, etc.)

Keep the summary under 300 words and focus on the most important characteristics."""
        
        user_prompt = f"""Document Name: {file_name}
File Type: {file_extension}

Document Content:
{truncated_text}

Please analyze this document and provide a comprehensive summary."""
        
        summary = llm_call(
            api_key=self.api_key,
            base_url=self.base_url,
            thinking_level=8,
            temperature=0.3,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        
        return summary

Document Content:
{truncated_text}

Please analyze this document and provide a comprehensive summary."""
        
        summary = llm_call(
            api_key=self.api_key,
            base_url=self.base_url,
            thinking_level=8,
            temperature=0.3,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        
        return summary
    
    def classify_document(self, document: Dict[str, Any], summary: str) -> Dict[str, Any]:
        """
        Classify a document into one of the predefined categories.
        
        Args:
            document: Document data from database
            summary: Document summary
            
        Returns:
            Classification result with category and confidence
        """
        # Prepare categories information for LLM
        categories_info = []
        for key, cat_data in self.categories.items():
            if key != 'other':  # Skip 'other' for initial classification
                # Extract field names from the new expected_fields structure
                expected_fields = list(cat_data.get('expected_fields', {}).keys())
                cat_info = f"{key}: {cat_data['name']} - {cat_data['description']}\nKeywords: {', '.join(cat_data['keywords'])}\nExpected fields: {', '.join(expected_fields)}"
                categories_info.append(cat_info)
        
        categories_text = "\n\n".join(categories_info)
        
        file_name = document.get('file_name', '')
        file_extension = document.get('file_extension', '')
        
        system_prompt = f"""You are a document classification expert. Classify the given document into one of the predefined categories.

Available Categories:
{categories_text}

If none of these categories fit well, use 'other'.

Respond with a JSON object containing:
{{
  "category_key": "category_key",
  "category_name": "Category Name",
  "confidence_score": 0.0-1.0,
  "reasoning": "Brief explanation for the classification"
}}"""
        
        user_prompt = f"""Document Name: {file_name}
File Type: {file_extension}
Document Summary: {summary}

Please classify this document into the most appropriate category."""
        
        classification_response = llm_call(
            api_key=self.api_key,
            base_url=self.base_url,
            thinking_level=7,
            temperature=0.2,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        
        # Parse JSON response
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', classification_response, re.DOTALL)
            if json_match:
                classification = json.loads(json_match.group())
                
                # Validate category exists
                category_key = classification.get('category_key', 'other')
                if category_key not in self.categories:
                    category_key = 'other'
                    classification['category_key'] = 'other'
                    classification['category_name'] = 'Other'
                
                return classification
            else:
                # Fallback to 'other' if JSON parsing fails
                return {
                    'category_key': 'other',
                    'category_name': 'Other',
                    'confidence_score': 0.1,
                    'reasoning': 'JSON parsing failed, assigned to other'
                }
        except Exception as e:
            print(f"Error parsing classification response: {e}")
            return {
                'category_key': 'other',
                'category_name': 'Other',
                'confidence_score': 0.1,
                'reasoning': f'Error: {str(e)}'
            }
    
    def analyze_all_documents(self, build_categories: bool = True) -> Dict[str, Any]:
        """
        Analyze all documents, create summaries, and classify them.
        Optionally build categories during classification.
        
        Args:
            build_categories: Whether to build/merge categories during classification
        
        Returns:
            Dictionary with document summaries and classifications
        """
        documents = self.db.get_all_documents()
        
        if not documents:
            print("No documents found in database")
            return {}
        
        print(f"Analyzing and classifying {len(documents)} documents...")
        
        analysis_results = {}
        categories_built = 0
        
        for doc in documents:
            doc_id = doc['id']
            file_path = doc['file_path']
            
            print(f"Processing: {file_path}")
            
            # Create summary
            summary = self.create_document_summary(doc)
            
            # Build category if requested and categories are empty
            if build_categories and not self.categories:
                category_def = self.build_category_from_document(doc, summary)
                if category_def:
                    category_key = self.generate_category_key(category_def.get('category_name', 'unknown'))
                    self.categories = self.merge_categories(self.categories, category_def, category_key)
                    categories_built += 1
                    print(f"  Built category: {category_def.get('category_name', 'Unknown')}")
            
            # Classify document
            classification = self.classify_document(doc, summary)
            
            # Store classification in database
            self.db.assign_document_category(
                document_id=doc_id,
                category_key=classification['category_key'],
                category_name=classification['category_name'],
                confidence_score=classification['confidence_score'],
                classification_reason=classification['reasoning']
            )
            
            analysis_results[doc_id] = {
                'file_path': file_path,
                'file_name': doc['file_name'],
                'file_extension': doc['file_extension'],
                'file_size': doc['file_size'],
                'summary': summary,
                'classification': classification,
                'text_length': doc['text_length']
            }
        
        # Save categories if any were built
        if build_categories and categories_built > 0:
            self.save_categories(self.categories)
            print(f"Built {categories_built} new categories and saved to {self.categories_file}")
        
        return analysis_results
    
    def get_classification_summary(self) -> Dict[str, Any]:
        """
        Get summary of all document classifications.
        
        Returns:
            Classification summary with statistics
        """
        categories_summary = self.db.get_all_categories_summary()
        
        total_classified = sum(cat['count'] for cat in categories_summary.values())
        
        summary = {
            'total_classified': total_classified,
            'categories': categories_summary,
            'classification_timestamp': str(datetime.now()),
            'categories_file': self.categories_file
        }
        
        return summary
    
    def extract_document_schema(self, analysis_results: Dict[str, Any], document_type: str) -> Dict[str, Any]:
        """
        Extract expected schema/fields for a specific document type.
        
        Args:
            analysis_results: Results from document analysis
            document_type: Type of document to analyze
            
        Returns:
            Schema information for the document type
        """
        # Filter documents of this type (based on classification)
        type_documents = []
        for doc_id, data in analysis_results.items():
            # This would be enhanced with actual classification results
            type_documents.append(data)
        
        if not type_documents:
            return {"error": "No documents found for this type"}
        
        # Prepare sample documents for analysis
        sample_docs = type_documents[:3]  # Analyze up to 3 samples
        
        system_prompt = f"""You are analyzing {document_type} documents to extract the common schema and expected fields.

For these documents, identify:
1. Standard fields and their data types
2. Optional vs required fields
3. Common formats and patterns
4. Field order and structure
5. Any validation rules or constraints

Provide a structured schema definition."""
        
        user_prompt = f"""Analyze these {document_type} document samples and extract the common schema:

{json.dumps(sample_docs, indent=2)}

Please provide a detailed schema specification for this document type."""
        
        schema_result = llm_call(
            api_key=self.api_key,
            base_url=self.base_url,
            thinking_level=8,
            temperature=0.1,
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        
        return {
            'document_type': document_type,
            'schema': schema_result,
            'sample_count': len(sample_docs)
        }
    
    def run_full_classification(self) -> Dict[str, Any]:
        """
        Run complete classification pipeline.
        
        Returns:
            Complete classification results
        """
        print("Starting document classification pipeline...")
        
        # Step 1: Analyze and classify all documents
        analysis_results = self.analyze_all_documents()
        
        if not analysis_results:
            return {"error": "No documents to analyze"}
        
        # Step 2: Get classification summary
        classification_summary = self.get_classification_summary()
        
        # Step 3: Generate final report
        final_report = {
            'analysis_results': analysis_results,
            'classification_summary': classification_summary,
            'summary': {
                'total_documents': len(analysis_results),
                'total_classified': classification_summary['total_classified'],
                'categories_used': list(classification_summary['categories'].keys()),
                'classification_timestamp': classification_summary['classification_timestamp']
            }
        }
        
        return final_report
    
    def save_classification_results(self, results: Dict[str, Any], output_file: str = "storage/classification_results.json"):
        """
        Save classification results to file.
        
        Args:
            results: Classification results
            output_file: Output file path
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"Classification results saved to: {output_path}")


def main():
    """Main execution function."""
    # Initialize classifier
    classifier = DocumentClassifier()
    
    # Run classification
    results = classifier.run_full_classification()
    
    # Save results
    classifier.save_classification_results(results)
    
    # Print summary
    if 'classification' in results:
        print("\n" + "="*50)
        print("DOCUMENT CLASSIFICATION RESULTS")
        print("="*50)
        print(results['classification']['classification'])
        print("="*50)


if __name__ == "__main__":
    from datetime import datetime
    from pathlib import Path
    
    main()
