# migrate_add_upload_fk.py
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

def backup_database(db_path):
    """Create timestamped backup of database"""
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return backup_path

def migrate_documents_table(db_path):
    """Add upload_id as foreign key to documents table"""
    
    # Create backup first
    backup_path = backup_database(db_path)
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")  # Enable FK constraints
    cursor = conn.cursor()
    
    try:
        print("\nStarting migration...")
        
        # Step 1: Create new documents table with upload_id FK
        print("Creating new documents table with foreign key...")
        cursor.execute("""
            CREATE TABLE documents_new (
                id TEXT PRIMARY KEY,
                upload_id TEXT NOT NULL,
                patient_id TEXT NOT NULL,
                clinic_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                document_type TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                validation_status TEXT DEFAULT 'pending',
                validated_at TIMESTAMP,
                validated_by TEXT,
                ocr_confidence REAL,
                ocr_text TEXT,
                structured_data TEXT,
                FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE,
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (clinic_id) REFERENCES clinics(id),
                FOREIGN KEY (validated_by) REFERENCES users(id)
            )
        """)
        
        # Step 2: Get current document count
        cursor.execute("SELECT COUNT(*) FROM documents")
        old_count = cursor.fetchone()[0]
        print(f"Current documents: {old_count}")
        
        # Step 3: Copy data with upload_id lookup
        print("Copying documents with upload_id links...")
        cursor.execute("""
            INSERT INTO documents_new (
                id, upload_id, patient_id, clinic_id, file_path,
                document_type, uploaded_at, validation_status,
                validated_at, validated_by, ocr_confidence, ocr_text, structured_data
            )
            SELECT 
                d.id,
                u.id as upload_id,
                d.patient_id,
                d.clinic_id,
                d.file_path,
                d.document_type,
                d.uploaded_at,
                d.validation_status,
                d.validated_at,
                d.validated_by,
                d.ocr_confidence,
                d.ocr_text,
                d.structured_data
            FROM documents d
            INNER JOIN uploads u ON u.file_path = d.file_path
        """)
        
        # Step 4: Verify counts
        cursor.execute("SELECT COUNT(*) FROM documents_new")
        new_count = cursor.fetchone()[0]
        print(f"Migrated documents: {new_count}")
        
        if new_count != old_count:
            raise Exception(
                f"Count mismatch! Old: {old_count}, New: {new_count}\n"
                f"Some documents don't have matching uploads. Aborting."
            )
        
        # Step 5: Verify all documents have valid upload_ids
        cursor.execute("""
            SELECT COUNT(*) 
            FROM documents_new 
            WHERE upload_id NOT IN (SELECT id FROM uploads)
        """)
        invalid_fks = cursor.fetchone()[0]
        
        if invalid_fks > 0:
            raise Exception(
                f"Found {invalid_fks} documents with invalid upload_ids. Aborting."
            )
        
        print("✓ All documents successfully linked to uploads")
        
        # Step 6: Drop old table and rename new one
        print("Replacing old documents table...")
        cursor.execute("DROP TABLE documents")
        cursor.execute("ALTER TABLE documents_new RENAME TO documents")
        
        # Step 7: Recreate indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX idx_documents_patient_id ON documents(patient_id)")
        cursor.execute("CREATE INDEX idx_documents_clinic_id ON documents(clinic_id)")
        cursor.execute("CREATE INDEX idx_documents_upload_id ON documents(upload_id)")
        cursor.execute("CREATE INDEX idx_documents_validation_status ON documents(validation_status)")
        cursor.execute("CREATE INDEX idx_documents_uploaded_at ON documents(uploaded_at)")
        
        # Step 8: Verify foreign key constraints are working
        print("Verifying foreign key constraints...")
        cursor.execute("PRAGMA foreign_key_check(documents)")
        fk_violations = cursor.fetchall()
        
        if fk_violations:
            raise Exception(f"Foreign key violations found: {fk_violations}")
        
        print("✓ Foreign key constraints verified")
        
        # Commit the transaction
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print(f"   Documents migrated: {new_count}")
        print(f"   Backup available at: {backup_path}")
        
        # Show sample of migrated data
        print("\nSample migrated documents:")
        cursor.execute("""
            SELECT d.id, d.upload_id, u.filename
            FROM documents d
            JOIN uploads u ON d.upload_id = u.id
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"   Doc {row[0][:8]}... -> Upload {row[1][:8]}... ({row[2]})")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        print(f"Database unchanged. Backup at: {backup_path}")
        return False
        
    finally:
        conn.close()

def verify_schema(db_path):
    """Verify the new schema is correct"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("SCHEMA VERIFICATION")
    print("="*60)
    
    # Check documents table schema
    cursor.execute("PRAGMA table_info(documents)")
    columns = cursor.fetchall()
    
    print("\nDocuments table columns:")
    for col in columns:
        print(f"   {col[1]} ({col[2]}) {'NOT NULL' if col[3] else 'NULLABLE'}")
    
    # Check foreign keys
    cursor.execute("PRAGMA foreign_key_list(documents)")
    fks = cursor.fetchall()
    
    print("\nForeign keys:")
    for fk in fks:
        print(f"   {fk[3]} -> {fk[2]}({fk[4]}) ON DELETE {fk[6]}")
    
    # Check indexes
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND tbl_name='documents'
        ORDER BY name
    """)
    indexes = cursor.fetchall()
    
    print("\nIndexes:")
    for idx in indexes:
        print(f"   {idx[0]}")
    
    # Check data integrity
    cursor.execute("SELECT COUNT(*) FROM documents")
    doc_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) 
        FROM documents d
        JOIN uploads u ON d.upload_id = u.id
    """)
    valid_links = cursor.fetchone()[0]
    
    print(f"\nData integrity:")
    print(f"   Total documents: {doc_count}")
    print(f"   Valid upload links: {valid_links}")
    print(f"   Status: {'✓ OK' if doc_count == valid_links else '❌ BROKEN LINKS'}")
    
    conn.close()

if __name__ == "__main__":
    db_path = "reconomed.db"  # Update with your actual path
    
    # Check if database exists
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        exit(1)
    
    print("ReconoMed Database Migration")
    print("Adding upload_id foreign key to documents table")
    print("="*60)
    
    # Run migration
    success = migrate_documents_table(db_path)
    
    if success:
        # Verify the new schema
        verify_schema(db_path)
        print("\n✅ Migration complete and verified!")
    else:
        print("\n❌ Migration failed. Check errors above.")
        exit(1)