import sqlite3
import shutil
from datetime import datetime

def backup_database(db_path):
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return backup_path

def link_uploads_to_documents(db_path):
    backup_path = backup_database(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Step 1: Add column
        print("Adding upload_id column...")
        cursor.execute("ALTER TABLE documents ADD COLUMN upload_id TEXT")
        
        # Step 2: Fetch all documents and their matching uploads
        print("Finding upload matches...")
        cursor.execute("""
            SELECT 
                d.id as doc_id,
                u.id as upload_id
            FROM documents d
            INNER JOIN uploads u ON u.file_path = d.file_path
        """)
        
        matches = cursor.fetchall()
        print(f"Found {len(matches)} matches")
        
        # Step 3: Update documents one by one (works in all SQLite versions)
        print("Linking documents to uploads...")
        for doc_id, upload_id in matches:
            cursor.execute(
                "UPDATE documents SET upload_id = ? WHERE id = ?",
                (upload_id, doc_id)
            )
        
        # Step 4: Verify results
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(upload_id) as linked,
                COUNT(*) - COUNT(upload_id) as unlinked
            FROM documents
        """)
        total, linked, unlinked = cursor.fetchone()
        
        print(f"\nResults:")
        print(f"  Total documents: {total}")
        print(f"  Linked to uploads: {linked}")
        print(f"  Unlinked: {unlinked}")
        
        if unlinked > 0:
            print(f"\n⚠ Warning: {unlinked} documents couldn't be linked")
            cursor.execute("""
                SELECT id, file_path, patient_id
                FROM documents
                WHERE upload_id IS NULL
                LIMIT 5
            """)
            print("\nExample unlinked documents:")
            for row in cursor.fetchall():
                print(f"  ID: {row[0]}, Path: {row[1]}, Patient: {row[2]}")
            
            response = input("\nContinue with commit? (yes/no): ")
            if response.lower() != 'yes':
                conn.rollback()
                print("Migration rolled back")
                return False
        
        conn.commit()
        print("\n✓ Migration completed successfully!")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        print(f"Restore from: {backup_path}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    db_path = "reconomed.db"  # Update with your actual path
    link_uploads_to_documents(db_path)