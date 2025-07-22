"""Search functionality endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Patient, Document

router = APIRouter(
    prefix="/search",
    tags=["search"],
)

@router.get("/")
def search(
    q: str = None,
    patient_name: str = None,
    document_type: str = None,
    db: Session = Depends(get_db)
):
    """Search patients and documents"""
    results = {"patients": [], "documents": []}
    
    if q or patient_name:
        # Search patients
        patient_query = db.query(Patient)
        if patient_name:
            patient_query = patient_query.filter(Patient.name.ilike(f"%{patient_name}%"))
        if q:
            patient_query = patient_query.filter(Patient.name.ilike(f"%{q}%"))
        results["patients"] = patient_query.limit(10).all()
    
    if q or document_type:
        # Search documents
        doc_query = db.query(Document)
        if document_type:
            doc_query = doc_query.filter(Document.document_type == document_type)
        if q:
            doc_query = doc_query.filter(Document.ocr_text.ilike(f"%{q}%"))
        results["documents"] = doc_query.limit(10).all()
    
    return results

@router.get("/document-types")
def get_document_types():
    """Get list of available document types"""
    return {
        "document_types": [
            {"code": "lab_result", "name": "Lab Results / Analize de laborator"},
            {"code": "xray", "name": "X-Ray / Radiografie"},
            {"code": "ct_scan", "name": "CT Scan / Tomografie computerizată"},
            {"code": "mri", "name": "MRI / Rezonanță magnetică"},
            {"code": "ultrasound", "name": "Ultrasound / Ecografie"},
            {"code": "mammography", "name": "Mammography / Mamografie"},
            {"code": "endoscopy", "name": "Endoscopy / Endoscopie"},
            {"code": "ecg", "name": "ECG / Electrocardiogramă"},
            {"code": "discharge_note", "name": "Discharge Note / Scrisoare de externare"},
            {"code": "prescription", "name": "Prescription / Rețetă"},
            {"code": "consultation", "name": "Consultation / Consultație"},
            {"code": "surgical_report", "name": "Surgical Report / Raport chirurgical"},
            {"code": "pathology_report", "name": "Pathology Report / Raport de patologie"},
            {"code": "general", "name": "General / General"}
        ]
    }