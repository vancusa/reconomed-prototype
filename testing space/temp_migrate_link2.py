# Part 2: migration_step2_link.py
import sqlite3

def link_documents(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all matching pairs
    cursor.execute("""
        SELECT d.id, u.id
        FROM documents d
        JOIN uploads u ON u.file_path = d.file_path
    """)
    
    matches = cursor.fetchall()
    
    # Update in batch
    cursor.executemany(
        "UPDATE documents SET upload_id = ? WHERE id = ?",
        [(upload_id, doc_id) for doc_id, upload_id in matches]
    )
    
    conn.commit()
    conn.close()
    
    print(f"Linked {len(matches)} documents to uploads")

if __name__ == "__main__":
    link_documents("reconomed.db")
    