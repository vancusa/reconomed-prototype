from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.database import get_db
from app.models import Patient, Document, Upload, Consultation

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    today = datetime.now().date()
    
    return {
        "patients_seen_today": db.query(Consultation).filter(
            func.date(Consultation.created_at) == today
        ).count(),
        "documents_uploaded_today": db.query(Upload).filter(
            func.date(Upload.uploaded_at) == today
        ).count(),
        "documents_pending_processing": db.query(Upload).filter(
            Upload.ocr_status == "pending"
        ).count(),
        "documents_pending_validation": db.query(Upload).filter(
            Upload.ocr_status == "completed"
        ).count(),
        "total_patients": db.query(Patient).count(),
        "total_documents": db.query(Document).count()
    }