#!/usr/bin/env python3
"""
Simple script to check if CSV file is in the correct format for document processing.
Expected format: content,source (or source,content)
"""

import csv
import sys
from config import CSV_FIELD_SIZE_LIMIT, SAMPLE_DATA_FILE

def check_csv_format(csv_file_path):
    """Check CSV file format and report issues."""
    
    # Set CSV field size limit
    csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
    
    print(f"Checking CSV file: {csv_file_path}")
    print("=" * 50)
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            # Try to detect delimiter
            sample = csvfile.read(1024)
            csvfile.seek(0)
            
            if '\t' in sample:
                delimiter = '\t'
                print("Detected delimiter: TAB")
            elif ',' in sample:
                delimiter = ','
                print("Detected delimiter: COMMA")
            else:
                delimiter = ','
                print("Using default delimiter: COMMA")
            
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            
            # Check headers
            headers = reader.fieldnames
            print(f"Headers found: {headers}")
            
            if not headers:
                print("ERROR: No headers found in CSV file")
                return False
            
            # Check for required columns (case-insensitive)
            content_col = None
            source_col = None
            
            for header in headers:
                header_lower = header.lower().strip()
                if header_lower in ['content', 'text', 'body', 'document']:
                    content_col = header
                elif header_lower in ['source', 'title', 'name', 'document_title']:
                    source_col = header
            
            print(f"Content column: {content_col}")
            print(f"Source column: {source_col}")
            
            if not content_col:
                print("ERROR: No content column found (expected: content, text, body, or document)")
                return False
            
            if not source_col:
                print("ERROR: No source column found (expected: source, title, name, or document_title)")
                return False
            
            # Check first few rows
            print("\nChecking first 5 rows:")
            row_count = 0
            issues = []
            
            for i, row in enumerate(reader):
                if i >= 5:  # Only check first 5 rows
                    break
                
                row_count += 1
                
                # Check if content exists
                content = row.get(content_col, '').strip()
                source = row.get(source_col, '').strip()
                
                print(f"\nRow {i+1}:")
                print(f"  Content length: {len(content)} characters")
                print(f"  Content preview: {content[:100]}...")
                print(f"  Source: '{source}'")
                
                if not content:
                    issues.append(f"Row {i+1}: Empty content")
                
                if not source:
                    issues.append(f"Row {i+1}: Empty source")
                
                if len(content) < 50:
                    issues.append(f"Row {i+1}: Content too short ({len(content)} chars)")
            
            # Count total rows
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            total_rows = sum(1 for row in reader)
            
            print(f"\nTotal rows: {total_rows}")
            
            # Report issues
            if issues:
                print("\nIssues found:")
                for issue in issues:
                    print(f"  - {issue}")
            else:
                print("\nNo issues found in first 5 rows!")
            
            # Summary
            print(f"\nSummary:")
            print(f"  Format: {'VALID' if content_col and source_col else 'INVALID'}")
            print(f"  Content column: '{content_col}'")
            print(f"  Source column: '{source_col}'")
            print(f"  Total rows: {total_rows}")
            
            return content_col and source_col and len(issues) == 0
    
    except Exception as e:
        print(f"ERROR reading CSV file: {e}")
        return False

def main():
    """Main function."""
    csv_file = SAMPLE_DATA_FILE
    
    # Allow command line argument for different file
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    is_valid = check_csv_format(csv_file)
    
    if is_valid:
        print(f"\nCSV file '{csv_file}' is in the correct format!")
        sys.exit(0)
    else:
        print(f"\nCSV file '{csv_file}' has format issues!")
        sys.exit(1)

if __name__ == "__main__":
    main()
