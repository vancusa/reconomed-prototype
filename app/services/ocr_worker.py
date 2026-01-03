# app/services/ocr_worker.py

import time
from app.database import SessionLocal
from app.services.upload_processing import UploadProcessingService

svc = UploadProcessingService(max_attempts=3, stale_timeout_seconds=600)

def background_ocr_worker():
    while True:
        time.sleep(2)
        db = SessionLocal()
        try:
            # optional: periodically recover stale jobs
            svc.recover_stale_jobs(db)

            upload = svc.claim_next(db)  # claims globally; later you can scope per clinic
            if upload:
                svc.process_upload(db, upload_id=upload.id)
        except Exception as e:
            print("Background OCR error:", e)
        finally:
            db.close()