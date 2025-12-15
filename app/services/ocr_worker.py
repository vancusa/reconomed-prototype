# app/services/ocr_worker.py

import time
from app.database import SessionLocal
from app.models import Upload
from app.routers.documents import _run_ocr_for_upload

def background_ocr_worker():
    while True:
        time.sleep(2)
        db = SessionLocal()
        try:
            upload = (
                db.query(Upload)
                .filter(Upload.ocr_status == "queued")
                .order_by(Upload.uploaded_at.asc())
                .first()
            )
            if upload:
                upload.ocr_status = "processing"
                db.commit()
                _run_ocr_for_upload(upload, db)
        except Exception as e:
            print("Background OCR error:", e)
        finally:
            db.close()
