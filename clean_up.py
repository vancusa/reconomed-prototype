#!/usr/bin/env python3
"""

ReconoMed Document Cleanup Script - SQLite Version
Safely removes all documents for a specific patient from both database and filesystem

-----------------------------------------------------------------------------------
USAGE:
    python clean_up.py --dry-run    # Preview changes"
    python clean_up.py --force      # Execute cleanup"
-----------------------------------------------------------------------------------

"""

import os
import sys
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Configuration
DATABASE_PATH = "./reconomed.db"  # Database file path
UPLOADS_BASE_DIR = Path("./uploads")  # Uploads directory path
TEST_PATIENT_ID = "252a143e-3187-40bf-8b37-39e1140a7e8a"


class SQLiteDocumentCleanupManager:
    def __init__(self, db_path: str, uploads_dir: Path):
        self.db_path = db_path
        self.uploads_dir = uploads_dir
        self.deleted_files = []
        self.failed_files = []
        self.table_columns = None
        
    def _get_table_columns(self, conn: sqlite3.Connection) -> List[str]:
        """Get the actual columns in the documents table"""
        if self.table_columns is None:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(documents)")
            columns_info = cursor.fetchall()
            self.table_columns = [col[1] for col in columns_info]  # col[1] is column name
            print(f"📋 Found table columns: {', '.join(self.table_columns)}")
        return self.table_columns
        
    def cleanup_patient_documents(self, patient_id: str, dry_run: bool = True) -> dict:
        """
        Clean up all documents for a specific patient
        
        Args:
            patient_id: UUID string of the patient
            dry_run: If True, only shows what would be deleted without actually deleting
            
        Returns:
            dict: Summary of cleanup operations
        """
        print(f"{'DRY RUN: ' if dry_run else ''}Cleaning documents for patient: {patient_id}")
        print("-" * 60)
        
        # Check if database file exists
        if not os.path.exists(self.db_path):
            print(f"❌ Database file not found: {self.db_path}")
            return {"documents_deleted": 0, "files_deleted": 0, "errors": [f"Database file not found: {self.db_path}"]}
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # This makes rows behave like dictionaries
        
        try:
            # Check table structure first
            columns = self._get_table_columns(conn)
            
            # 1. Get all document records with file paths
            documents = self._get_patient_documents(conn, patient_id, columns)
            print(f"Found {len(documents)} document records")
            
            if not documents:
                print("No documents found for this patient")
                return {"documents_deleted": 0, "files_deleted": 0, "errors": []}
            
            # 2. Display what will be deleted
            self._display_documents(documents)
            
            if dry_run:
                print("\n🔍 DRY RUN - No actual deletions performed")
                return {"documents_deleted": 0, "files_deleted": 0, "errors": [], "dry_run": True}
            
            # 3. Confirm deletion (if not dry run)
            if not self._confirm_deletion():
                print("❌ Deletion cancelled by user")
                return {"documents_deleted": 0, "files_deleted": 0, "errors": ["User cancelled"]}
            
            # 4. Delete physical files first
            self._delete_physical_files(documents)
            
            # 5. Delete database records
            deleted_count = self._delete_database_records(conn, patient_id)
            
            # 6. Clean up audit logs (optional)
            audit_deleted = self._clean_audit_logs(conn, patient_id)
            
            return {
                "documents_deleted": deleted_count,
                "files_deleted": len(self.deleted_files),
                "files_failed": len(self.failed_files),
                "audit_logs_cleaned": audit_deleted,
                "errors": self.failed_files
            }
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            return {"documents_deleted": 0, "files_deleted": 0, "errors": [str(e)]}
            
        finally:
            conn.close()
    
    def _get_patient_documents(self, conn: sqlite3.Connection, patient_id: str, columns: List[str]) -> List[Dict]:
        """Get all document records for the patient using actual table columns"""
        cursor = conn.cursor()
        
        # Build query with only existing columns
        select_columns = []
        
        # Always include these if they exist
        essential_columns = ['id', 'patient_id']
        optional_columns = [
            'filename', 'file_path', 'ocr_file_path', 'document_type', 
            'upload_date', 'created_at', 'file_size', 'validation_status',
            'ocr_text', 'ocr_confidence', 'is_validated'
        ]
        
        for col in essential_columns:
            if col in columns:
                select_columns.append(col)
        
        for col in optional_columns:
            if col in columns:
                select_columns.append(col)
        
        if not select_columns:
            raise Exception("Could not find essential columns (id, patient_id) in documents table")
        
        query = f"""
        SELECT {', '.join(select_columns)}
        FROM documents 
        WHERE patient_id = ?
        ORDER BY {('upload_date' if 'upload_date' in columns else 'created_at' if 'created_at' in columns else 'id')} DESC
        """
        
        print(f"🔍 Query: {query}")
        cursor.execute(query, (patient_id,))
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def _display_documents(self, documents: List[Dict]):
        """Display documents that will be deleted"""
        print("\n📋 Documents to be deleted:")
        print("-" * 60)
        
        total_size = 0
        for i, doc in enumerate(documents, 1):
            print(f"{i}. ID: {doc.get('id', 'Unknown')}")
            
            # Show available fields
            if 'filename' in doc:
                print(f"   Filename: {doc['filename']}")
            if 'document_type' in doc:
                print(f"   Type: {doc['document_type'] or 'Unknown'}")
            if 'upload_date' in doc:
                print(f"   Upload Date: {doc['upload_date']}")
            elif 'created_at' in doc:
                print(f"   Created: {doc['created_at']}")
            if 'file_size' in doc:
                print(f"   Size: {self._format_file_size(doc['file_size'])}")
                if doc['file_size']:
                    total_size += doc['file_size']
            if 'validation_status' in doc:
                print(f"   Status: {doc['validation_status'] or 'Pending'}")
            elif 'is_validated' in doc:
                print(f"   Validated: {doc['is_validated']}")
            if 'file_path' in doc:
                print(f"   File Path: {doc['file_path']}")
            if 'ocr_file_path' in doc and doc['ocr_file_path']:
                print(f"   OCR Path: {doc['ocr_file_path']}")
            print()
        
        if total_size > 0:
            print(f"💾 Total size to be freed: {self._format_file_size(total_size)}")
    
    def _confirm_deletion(self) -> bool:
        """Ask user to confirm deletion"""
        print("\n⚠️  WARNING: This will permanently delete all files and database records!")
        response = input("Type 'DELETE' to confirm deletion: ").strip()
        return response == 'DELETE'
    
    def _delete_physical_files(self, documents: List[Dict]):
        """Delete physical files from filesystem"""
        print("\n🗑️  Deleting physical files...")
        
        for doc in documents:
            # Delete main file
            if doc.get('file_path'):
                filename = doc.get('filename', f"Document {doc.get('id')}")
                self._delete_single_file(doc['file_path'], f"Main file: {filename}")
            
            # Delete OCR file if exists
            if doc.get('ocr_file_path'):
                filename = doc.get('filename', f"Document {doc.get('id')}")
                self._delete_single_file(doc['ocr_file_path'], f"OCR file for: {filename}")
    
    def _delete_single_file(self, file_path: str, description: str):
        """Delete a single file with error handling"""
        try:
            # Handle both absolute and relative paths
            if os.path.isabs(file_path):
                full_path = Path(file_path)
            else:
                full_path = self.uploads_dir / file_path
            
            if full_path.exists():
                os.remove(full_path)
                self.deleted_files.append(str(file_path))
                print(f"   ✅ Deleted: {description}")
            else:
                print(f"   ⚠️  File not found: {description} (Path: {full_path})")
                
        except Exception as e:
            error_msg = f"Failed to delete {description}: {e}"
            self.failed_files.append(error_msg)
            print(f"   ❌ {error_msg}")
    
    def _delete_database_records(self, conn: sqlite3.Connection, patient_id: str) -> int:
        """Delete document records from database"""
        print("\n🗃️  Deleting database records...")
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE patient_id = ?", (patient_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        
        print(f"   ✅ Deleted {deleted_count} document records")
        return deleted_count
    
    def _clean_audit_logs(self, conn: sqlite3.Connection, patient_id: str) -> int:
        """Clean up related audit logs (optional)"""
        print("\n📜 Cleaning audit logs...")
        
        cursor = conn.cursor()
        
        # Check if audit table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gdpr_audit_log'")
        if not cursor.fetchone():
            print("   ⚠️  No audit log table found - skipping")
            return 0
        
        cursor.execute("""
        DELETE FROM gdpr_audit_log 
        WHERE patient_id = ? 
        AND (action LIKE '%document%' OR action LIKE '%upload%' OR action LIKE '%ocr%')
        """, (patient_id,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        print(f"   ✅ Cleaned {deleted_count} audit log entries")
        return deleted_count
    
    @staticmethod
    def _format_file_size(size_bytes: Optional[int]) -> str:
        """Format file size in human readable format"""
        if not size_bytes:
            return "Unknown"
            
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


def main():
    """Main execution function"""
    print("🏥 ReconoMed Document Cleanup Tool (SQLite - Fixed)")
    print("=" * 55)
    
    # Check if database exists
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Database file not found: {DATABASE_PATH}")
        return
    
    print(f"📁 Using database: {DATABASE_PATH}")
    
    # Initialize cleanup manager
    cleanup_manager = SQLiteDocumentCleanupManager(DATABASE_PATH, UPLOADS_BASE_DIR)
    
    # Parse command line arguments
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    force = "--force" in sys.argv or "-f" in sys.argv
    
    if not dry_run and not force:
        print("⚠️  Add --dry-run to preview changes or --force to execute")
        print("   Example: python cleanup_patient_docs_sqlite.py --dry-run")
        return
    
    # Run cleanup
    try:
        result = cleanup_manager.cleanup_patient_documents(
            TEST_PATIENT_ID, 
            dry_run=dry_run
        )
        
        # Print summary
        print("\n" + "=" * 55)
        print("📊 CLEANUP SUMMARY")
        print("=" * 55)
        
        if result.get("dry_run"):
            print("🔍 DRY RUN COMPLETED - No changes made")
        else:
            print(f"📄 Documents deleted: {result['documents_deleted']}")
            print(f"🗑️  Files deleted: {result['files_deleted']}")
            if result.get('files_failed', 0) > 0:
                print(f"❌ Files failed: {result['files_failed']}")
            if result.get('audit_logs_cleaned', 0) > 0:
                print(f"📜 Audit logs cleaned: {result['audit_logs_cleaned']}")
        
        if result.get('errors'):
            print(f"\n⚠️  Errors encountered:")
            for error in result['errors']:
                print(f"   - {error}")
        
        print("\n✅ Cleanup completed!")
        
    except KeyboardInterrupt:
        print("\n❌ Cleanup interrupted by user")
    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")


if __name__ == "__main__":
    print("Usage:")
    print("  python cleanup_patient_docs_sqlite.py --dry-run    # Preview changes")
    print("  python cleanup_patient_docs_sqlite.py --force      # Execute cleanup")
    print()
    
    main()