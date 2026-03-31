#!/usr/bin/env python3
"""
Database manager for storing document metadata and text content.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from document_reader import read_storage_folder


class DocumentDatabase:
    """SQLite database manager for document storage."""
    
    def __init__(self, db_path: str = "storage/documents.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.connection = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Establish database connection."""
        try:
            self.connection = sqlite3.connect(str(self.db_path))
            self.connection.row_factory = sqlite3.Row  # Enable dict-like access
        except Exception as e:
            print(f"Error connecting to database: {e}")
            raise
    
    def create_tables(self):
        """Create the documents and document_categories tables if they don't exist."""
        documents_query = """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_name TEXT NOT NULL,
            file_extension TEXT NOT NULL,
            file_size INTEGER,
            created_at TIMESTAMP,
            modified_at TIMESTAMP,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            full_text TEXT,
            text_length INTEGER,
            status TEXT DEFAULT 'processed',
            error_message TEXT
        )
        """
        
        categories_query = """
        CREATE TABLE IF NOT EXISTS document_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            category_key TEXT NOT NULL,
            category_name TEXT NOT NULL,
            confidence_score REAL,
            classification_reason TEXT,
            classified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
            UNIQUE(document_id)
        )
        """
        
        try:
            self.connection.execute(documents_query)
            self.connection.execute(categories_query)
            self.connection.commit()
            print("Database tables created/verified successfully")
        except Exception as e:
            print(f"Error creating tables: {e}")
            raise
    
    def insert_document(self, file_path: str, full_text: str, error_message: str = None) -> bool:
        """
        Insert or update a document in the database.
        
        Args:
            file_path: Path to the document file
            full_text: Extracted text content
            error_message: Any error that occurred during processing
            
        Returns:
            True if successful, False otherwise
        """
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            print(f"File not found: {file_path}")
            return False
        
        # Get file metadata
        stat = file_path_obj.stat()
        file_name = file_path_obj.name
        file_extension = file_path_obj.suffix.lower()
        file_size = stat.st_size
        created_at = datetime.fromtimestamp(stat.st_ctime)
        modified_at = datetime.fromtimestamp(stat.st_mtime)
        text_length = len(full_text) if full_text else 0
        status = 'error' if error_message else 'processed'
        
        query = """
        INSERT OR REPLACE INTO documents 
        (file_path, file_name, file_extension, file_size, created_at, 
         modified_at, full_text, text_length, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            self.connection.execute(query, (
                str(file_path_obj.absolute()),
                file_name,
                file_extension,
                file_size,
                created_at,
                modified_at,
                full_text,
                text_length,
                status,
                error_message
            ))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error inserting document {file_path}: {e}")
            return False
    
    def get_document(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a document from the database.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Document data as dictionary or None if not found
        """
        query = "SELECT * FROM documents WHERE file_path = ?"
        
        try:
            cursor = self.connection.execute(query, (file_path,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"Error retrieving document {file_path}: {e}")
            return None
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """
        Retrieve all documents from the database.
        
        Returns:
            List of document dictionaries
        """
        query = "SELECT * FROM documents ORDER BY processed_at DESC"
        
        try:
            cursor = self.connection.execute(query)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error retrieving all documents: {e}")
            return []
    
    def search_documents(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Search for documents containing the search term.
        
        Args:
            search_term: Text to search for in full_text
            
        Returns:
            List of matching document dictionaries
        """
        query = """
        SELECT * FROM documents 
        WHERE full_text LIKE ? 
        ORDER BY processed_at DESC
        """
        
        try:
            cursor = self.connection.execute(query, (f"%{search_term}%",))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []
    
    def delete_document(self, file_path: str) -> bool:
        """
        Delete a document from the database.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            True if successful, False otherwise
        """
        query = "DELETE FROM documents WHERE file_path = ?"
        
        try:
            cursor = self.connection.execute(query, (file_path,))
            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting document {file_path}: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = {}
        
        try:
            # Total documents
            cursor = self.connection.execute("SELECT COUNT(*) FROM documents")
            stats['total_documents'] = cursor.fetchone()[0]
            
            # Documents by type
            cursor = self.connection.execute("""
                SELECT file_extension, COUNT(*) as count 
                FROM documents 
                GROUP BY file_extension
            """)
            stats['by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Total text length
            cursor = self.connection.execute("SELECT SUM(text_length) FROM documents")
            stats['total_characters'] = cursor.fetchone()[0] or 0
            
            # Processing status
            cursor = self.connection.execute("""
                SELECT status, COUNT(*) as count 
                FROM documents 
                GROUP BY status
            """)
            stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}
            
        except Exception as e:
            print(f"Error getting statistics: {e}")
        
        return stats
    
    def assign_document_category(self, document_id: int, category_key: str, category_name: str, 
                              confidence_score: float = None, classification_reason: str = None) -> bool:
        """
        Assign a category to a document.
        
        Args:
            document_id: ID of the document
            category_key: Category key from categories.json
            category_name: Human-readable category name
            confidence_score: Classification confidence (0-1)
            classification_reason: Reason for classification
            
        Returns:
            True if successful, False otherwise
        """
        query = """
        INSERT OR REPLACE INTO document_categories 
        (document_id, category_key, category_name, confidence_score, classification_reason)
        VALUES (?, ?, ?, ?, ?)
        """
        
        try:
            self.connection.execute(query, (document_id, category_key, category_name, 
                                          confidence_score, classification_reason))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error assigning category to document {document_id}: {e}")
            return False
    
    def get_document_category(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the category assignment for a document.
        
        Args:
            document_id: ID of the document
            
        Returns:
            Category assignment data or None if not found
        """
        query = "SELECT * FROM document_categories WHERE document_id = ?"
        
        try:
            cursor = self.connection.execute(query, (document_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"Error retrieving category for document {document_id}: {e}")
            return None
    
    def get_documents_by_category(self, category_key: str) -> List[Dict[str, Any]]:
        """
        Get all documents assigned to a specific category.
        
        Args:
            category_key: Category key to filter by
            
        Returns:
            List of documents with their category assignments
        """
        query = """
        SELECT d.*, dc.category_key, dc.category_name, dc.confidence_score, 
               dc.classification_reason, dc.classified_at
        FROM documents d
        LEFT JOIN document_categories dc ON d.id = dc.document_id
        WHERE dc.category_key = ?
        ORDER BY dc.classified_at DESC
        """
        
        try:
            cursor = self.connection.execute(query, (category_key,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error retrieving documents for category {category_key}: {e}")
            return []
    
    def get_all_categories_summary(self) -> Dict[str, Any]:
        """
        Get summary of all category assignments.
        
        Returns:
            Dictionary with category statistics
        """
        query = """
        SELECT category_key, category_name, COUNT(*) as document_count,
               AVG(confidence_score) as avg_confidence
        FROM document_categories
        GROUP BY category_key, category_name
        ORDER BY document_count DESC
        """
        
        try:
            cursor = self.connection.execute(query)
            categories = {}
            for row in cursor.fetchall():
                categories[row[0]] = {
                    'name': row[1],
                    'count': row[2],
                    'avg_confidence': row[3]
                }
            return categories
        except Exception as e:
            print(f"Error getting categories summary: {e}")
            return {}
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def process_and_store_documents(storage_path: str = "storage", db_path: str = "storage/documents.db"):
    """
    Process all documents in storage folder and store them in database.
    
    Args:
        storage_path: Path to storage folder
        db_path: Path to database file
    """
    print(f"Processing documents from {storage_path}...")
    
    # Read all documents
    documents = read_storage_folder(storage_path)
    
    if not documents:
        print("No documents found to process")
        return
    
    # Store in database
    with DocumentDatabase(db_path) as db:
        for file_path, content in documents.items():
            success = db.insert_document(file_path, content)
            if success:
                print(f"✓ Stored: {file_path}")
            else:
                print(f"✗ Failed to store: {file_path}")
        
        # Show statistics
        stats = db.get_statistics()
        print(f"\nDatabase Statistics:")
        print(f"Total documents: {stats.get('total_documents', 0)}")
        print(f"Total characters: {stats.get('total_characters', 0):,}")
        print(f"By type: {stats.get('by_type', {})}")


if __name__ == "__main__":
    # Example usage
    process_and_store_documents()
