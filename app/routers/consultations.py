
"""Consultation management endpoints - Phase 4A"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
import uuid
import logging
from datetime import datetime

from app.database import get_db
from app.models import Consultation, User, Patient, GDPRAuditLog, Document
from app.schemas import (
    ConsultationStart, ConsultationAutoSave, ConsultationCreate, 
    ConsultationUpdate, ConsultationResponse, ConsultationListItem
)

router = APIRouter(tags=["consultations"])

# Loggers
audit_logger = logging.getLogger("reconomed.audit")
app_logger = logging.getLogger("reconomed.app")

# ----------------------------
# Helper: Get Current User
# ----------------------------
def get_current_user(db: Session) -> User:
    """Get demo doctor for MVP"""
    user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    return user

#--------------
# Get counts
#------------------
@router.get("/counts")
async def get_consultation_counts(db: Session = Depends(get_db)):
    """Get consultation counts for tab badges"""
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    active_count = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.status == "in_progress"
    ).count()
    
    discharge_ready_count = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.is_signed == True,
        Consultation.status != "discharged"
    ).count()
    
    # Review pending - patients with consultations but needing follow-up
    review_pending_count = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.status == "completed",
        Consultation.is_signed == False
    ).count()
    
    return {
        "active_consultations": active_count,
        "discharge_ready": discharge_ready_count,
        "review_pending": review_pending_count
    }


# ----------------------------
# Start New Consultation (Creates Draft)
# ----------------------------
@router.post("/start", response_model=ConsultationResponse)
async def start_consultation(
    data: ConsultationStart,
    db: Session = Depends(get_db)
):
    """
    Start new consultation - creates draft with patient and specialty.
    Called from: "Add New Consult" button or consultation search flow.
    """
    current_user = get_current_user(db)
    
    # Verify patient exists
    patient = db.query(Patient).filter(
        Patient.id == data.patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Verify specialty is valid for doctor
    if current_user.specialties and data.specialty not in current_user.specialties:
        raise HTTPException(
            status_code=400, 
            detail=f"Doctor not authorized for specialty: {data.specialty}"
        )
    
    # Create draft consultation
    new_consultation = Consultation(
        id=str(uuid.uuid4()),
        patient_id=data.patient_id,
        clinic_id=current_user.clinic_id,
        doctor_id=current_user.id,
        specialty=data.specialty,
        consultation_date=datetime.utcnow(),
        structured_data={},
        status="draft",
        is_signed=False,
        last_autosave_at=datetime.utcnow()
    )
    
    db.add(new_consultation)
    db.commit()
    db.refresh(new_consultation)
    
    # Audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=patient.id,
        action="consultation_started",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": new_consultation.id,
            "specialty": data.specialty,
            "status": "draft"
        }
    )
    db.add(audit_log)
    db.commit()
    
    return new_consultation

# ----------------------------
# Auto-Save Consultation
# ----------------------------
@router.put("/{consultation_id}/auto-save", response_model=ConsultationResponse)
async def auto_save_consultation(
    consultation_id: str,
    data: ConsultationAutoSave,
    db: Session = Depends(get_db)
):
    """
    Auto-save consultation data every 60 seconds from frontend.
    Updates structured_data, audio fields, and last_autosave_at timestamp.
    """
    current_user = get_current_user(db)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # Prevent auto-save on completed/discharged consultations
    if consultation.status in ["completed", "discharged"]:
        raise HTTPException(
            status_code=400, 
            detail="Cannot auto-save completed/discharged consultation"
        )
    
    # Update fields
    if data.structured_data is not None:
        consultation.structured_data = data.structured_data
    if data.audio_file_path is not None:
        consultation.audio_file_path = data.audio_file_path
    if data.audio_duration_seconds is not None:
        consultation.audio_duration_seconds = data.audio_duration_seconds
    
    consultation.last_autosave_at = datetime.utcnow()
    
    db.commit()
    db.refresh(consultation)
    
    app_logger.info(f"Auto-saved consultation {consultation_id} for doctor {current_user.id}")
    
    return consultation

# ----------------------------
# Change Specialty Mid-Consultation
# ----------------------------
@router.put("/{consultation_id}/specialty", response_model=ConsultationResponse)
async def update_consultation_specialty(
    consultation_id: str,
    specialty: str,
    db: Session = Depends(get_db)
):
    """
    Change specialty mid-consultation.
    Validates doctor has access to new specialty.
    """
    current_user = get_current_user(db)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # Verify specialty is valid for doctor
    if current_user.specialties and specialty not in current_user.specialties:
        raise HTTPException(
            status_code=400,
            detail=f"Doctor not authorized for specialty: {specialty}"
        )
    
    old_specialty = consultation.specialty
    consultation.specialty = specialty
    consultation.last_autosave_at = datetime.utcnow()
    
    db.commit()
    db.refresh(consultation)
    
    # Audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action="consultation_specialty_changed",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "old_specialty": old_specialty,
            "new_specialty": specialty
        }
    )
    db.add(audit_log)
    db.commit()
    
    return consultation

# ----------------------------
# Update Consultation Status
# ----------------------------
@router.put("/{consultation_id}/status", response_model=ConsultationResponse)
async def update_consultation_status(
    consultation_id: str,
    status: str,
    db: Session = Depends(get_db)
):
    """
    Update consultation status: draft → in_progress → completed
    Validates status transitions.
    """
    current_user = get_current_user(db)
    
    valid_statuses = ["draft", "in_progress", "completed", "discharged", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # Validate status transitions
    valid_transitions = {
        "draft": ["in_progress", "cancelled"],
        "in_progress": ["completed", "draft", "cancelled"],
        "completed": ["discharged"],
        "discharged": [],  # Terminal state
        "cancelled": []  # Terminal state
    }
    
    if status not in valid_transitions.get(consultation.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {consultation.status} to {status}"
        )
    
    old_status = consultation.status
    consultation.status = status
    
    # If completing, require signature
    if status == "completed" and not consultation.is_signed:
        consultation.is_signed = True
        consultation.signed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(consultation)
    
    # Audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action=f"consultation_status_changed",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "old_status": old_status,
            "new_status": status,
            "signed": consultation.is_signed
        }
    )
    db.add(audit_log)
    db.commit()
    
    return consultation

# ----------------------------
# Get Draft Consultations
# ----------------------------
@router.get("/drafts", response_model=List[ConsultationListItem])
async def get_draft_consultations(
    db: Session = Depends(get_db)
):
    """
    Get all draft consultations for current doctor.
    Used for "Resume Draft" functionality.
    """
    current_user = get_current_user(db)
    
    drafts = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id,
        Consultation.status == "draft"
    ).order_by(
        Consultation.last_autosave_at.desc()
    ).all()
    
    return drafts

# ----------------------------
# Cancel Consultation (Soft Delete)
# ----------------------------
@router.delete("/{consultation_id}/cancel")
async def cancel_consultation(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """
    Cancel consultation (soft delete - sets status to cancelled).
    Only allowed for draft/in_progress consultations.
    """
    current_user = get_current_user(db)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # Only allow cancellation of non-completed consultations
    if consultation.status in ["completed", "discharged"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel completed/discharged consultation"
        )
    
    consultation.status = "cancelled"
    db.commit()
    
    # Audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action="consultation_cancelled",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "cancelled_by": current_user.full_name
        }
    )
    db.add(audit_log)
    db.commit()
    
    return {"message": "Consultation cancelled successfully"}

# ----------------------------
# Get Patient History for Split View
# ----------------------------
@router.get("/{consultation_id}/patient-history")
async def get_patient_history_for_consultation(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """
    Get patient's previous consultations and documents.
    Used for left panel in Step 2 split view.
    Returns same structure as View Patient Modal's Documents & History tab.
    """
    current_user = get_current_user(db)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()
    
    # Get previous consultations (exclude current one)
    previous_consultations = db.query(Consultation).filter(
        Consultation.patient_id == consultation.patient_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.id != consultation_id,
        Consultation.status.in_(["completed", "discharged"])
    ).order_by(
        Consultation.consultation_date.desc()
    ).all()
    
    # Get documents
    documents = db.query(Document).filter(
        Document.patient_id == consultation.patient_id,
        Document.clinic_id == current_user.clinic_id,
        Document.validation_status == "validated"
    ).order_by(
        Document.created_at.desc()
    ).all()
    
    return {
        "patient": {
            "id": patient.id,
            "given_name": patient.given_name,
            "family_name": patient.family_name,
            "birth_date": patient.birth_date,
            "cnp": patient.cnp
        },
        "consultations": [
            {
                "id": c.id,
                "specialty": c.specialty,
                "consultation_date": c.consultation_date.isoformat(),
                "structured_data": c.structured_data,
                "is_signed": c.is_signed
            }
            for c in previous_consultations
        ],
        "documents": [
            {
                "id": d.id,
                "filename": d.original_filename,
                "document_type": d.document_type,
                "created_at": d.created_at.isoformat(),
                "file_path": d.file_path,
                "extracted_data": d.extracted_data
            }
            for d in documents
        ]
    }

# ----------------------------
# EXISTING ENDPOINTS (Keep for backward compatibility)
# ----------------------------

@router.post("/", response_model=ConsultationResponse)
async def create_consultation(
    consultation_data: ConsultationCreate,
    db: Session = Depends(get_db)
):
    """Legacy endpoint - use /start instead"""
    current_user = get_current_user(db)
    
    patient = db.query(Patient).filter(
        Patient.id == consultation_data.patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    new_consultation = Consultation(
        id=str(uuid.uuid4()),
        patient_id=consultation_data.patient_id,
        clinic_id=current_user.clinic_id,
        doctor_id=current_user.id,
        specialty=consultation_data.specialty,
        consultation_date=consultation_data.consultation_date or datetime.utcnow(),
        structured_data=consultation_data.structured_data,
        audio_file_path=consultation_data.audio_file_path,
        status="draft",
        is_signed=False
    )
    
    db.add(new_consultation)
    db.commit()
    db.refresh(new_consultation)
    
    return new_consultation

@router.get("/", response_model=List[ConsultationResponse])
async def get_consultations(
    patient_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get consultations with optional filters"""
    current_user = get_current_user(db)
    
    query = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id
    )
    
    if patient_id:
        query = query.filter(Consultation.patient_id == patient_id)
    
    if status:
        query = query.filter(Consultation.status == status)
    
    consultations = query.order_by(
        Consultation.consultation_date.desc()
    ).offset(skip).limit(limit).all()
    
    return consultations

@router.get("/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """Get specific consultation"""
    current_user = get_current_user(db)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    return consultation

@router.put("/{consultation_id}", response_model=ConsultationResponse)
async def update_consultation(
    consultation_id: str,
    consultation_data: ConsultationUpdate,
    db: Session = Depends(get_db)
):
    """Update consultation - legacy endpoint"""
    current_user = get_current_user(db)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # Update fields
    if consultation_data.specialty is not None:
        consultation.specialty = consultation_data.specialty
    if consultation_data.consultation_date is not None:
        consultation.consultation_date = consultation_data.consultation_date
    if consultation_data.structured_data is not None:
        consultation.structured_data = consultation_data.structured_data
    if consultation_data.audio_transcript is not None:
        consultation.audio_transcript = consultation_data.audio_transcript
    if consultation_data.status is not None:
        consultation.status = consultation_data.status
    if consultation_data.is_signed is not None:
        consultation.is_signed = consultation_data.is_signed
        if consultation_data.is_signed:
            consultation.signed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(consultation)
    
    return consultation

@router.get("/today/stats")
async def get_today_stats(db: Session = Depends(get_db)):
    """Get today's consultation statistics"""
    current_user = get_current_user(db)
    
    from datetime import date
    today = date.today()
    
    patients_today = db.query(Consultation.patient_id).filter(
        Consultation.clinic_id == current_user.clinic_id,
        func.date(Consultation.consultation_date) == today
    ).distinct().count()
    
    return {"patients_today": patients_today}