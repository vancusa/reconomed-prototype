"""Consultation management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import uuid
import logging
from datetime import datetime

from app.database import get_db
from app.models import Consultation, User, Patient, GDPRAuditLog
from app.schemas import ConsultationCreate, ConsultationUpdate, ConsultationResponse

router = APIRouter(
    tags=["consultations"]
)

# Reuse the loggers created in app.main
audit_logger = logging.getLogger("reconomed.audit")
app_logger=logging.getLogger("reconomed.app")

@router.post("/", response_model=ConsultationResponse)
async def create_consultation(
    consultation_data: ConsultationCreate,
    db: Session = Depends(get_db)
):
    """Create new consultation"""
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    # Verify patient exists and belongs to clinic
    patient = db.query(Patient).filter(
        Patient.id == consultation_data.patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Create consultation
    new_consultation = Consultation(
        id=str(uuid.uuid4()),
        patient_id=consultation_data.patient_id,
        clinic_id=current_user.clinic_id,
        doctor_id=current_user.id,
        consultation_type=consultation_data.consultation_type,
        consultation_date=consultation_data.consultation_date or datetime.utcnow(),
        structured_data=consultation_data.structured_data,
        audio_file_path=consultation_data.audio_file_path,
        status="draft",
        is_signed=False
    )
    
    db.add(new_consultation)
    db.commit()
    db.refresh(new_consultation)
    
    # Audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=patient.id,
        action="consultation_created",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": new_consultation.id,
            "consultation_type": consultation_data.consultation_type,
            "created_by": current_user.full_name
        }
    )
    db.add(audit_log)
    db.commit()
    
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
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
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

@router.get("/recent", response_model=List[ConsultationResponse])
async def get_recent_consultations(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get recent consultations for dashboard"""
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    consultations = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id
    ).order_by(
        Consultation.consultation_date.desc()
    ).limit(limit).all()
    
    return consultations

@router.get("/pending-discharge")
async def get_pending_discharge(db: Session = Depends(get_db)):
    """Get consultations ready for discharge (signed but not discharged)"""
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    consultations = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.is_signed == True,
        Consultation.status != "discharged"
    ).order_by(
        Consultation.consultation_date.desc()
    ).all()
    
    return {
        "consultations": consultations,
        "count": len(consultations)
    }

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

@router.get("/activity/recent")
async def get_recent_activity(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Get recent consultation activity for dashboard"""
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    # Get recent audit logs for consultations
    activities = db.query(GDPRAuditLog).filter(
        GDPRAuditLog.clinic_id == current_user.clinic_id,
        GDPRAuditLog.action.in_([
            'consultation_created',
            'consultation_updated',
            'consultation_signed',
            'discharge_generated'
        ])
    ).order_by(
        GDPRAuditLog.created_at.desc()
    ).limit(limit).all()
    
    # Format activities for frontend
    formatted_activities = []
    for activity in activities:
        icon_map = {
            'consultation_created': 'fas fa-stethoscope',
            'consultation_updated': 'fas fa-edit',
            'consultation_signed': 'fas fa-signature',
            'discharge_generated': 'fas fa-file-export'
        }
        
        formatted_activities.append({
            "id": activity.id,
            "type": activity.action,
            "title": f"{activity.action.replace('_', ' ').title()} - {activity.details.get('consultation_type', 'Unknown')}",
            "timestamp": activity.created_at.isoformat(),
            "icon": icon_map.get(activity.action, 'fas fa-info-circle')
        })
    
    return {
        "activities": formatted_activities,
        "total": len(formatted_activities)
    }

@router.get("/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """Get specific consultation"""
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # Audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action="consultation_accessed",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "accessed_by": current_user.full_name
        }
    )
    db.add(audit_log)
    db.commit()
    
    return consultation

@router.put("/{consultation_id}", response_model=ConsultationResponse)
async def update_consultation(
    consultation_id: str,
    consultation_data: ConsultationUpdate,
    db: Session = Depends(get_db)
):
    """Update consultation"""
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # Prevent editing signed consultations
    if consultation.is_signed and not consultation_data.is_signed:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify signed consultation"
        )
    
    # Update fields
    if consultation_data.consultation_type is not None:
        consultation.consultation_type = consultation_data.consultation_type
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
    
    # Audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action="consultation_updated",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "updated_by": current_user.full_name,
            "signed": consultation.is_signed
        }
    )
    db.add(audit_log)
    db.commit()
    
    return consultation

@router.delete("/{consultation_id}")
async def delete_consultation(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """Delete consultation (soft delete by marking as deleted)"""
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # Prevent deletion of signed consultations
    if consultation.is_signed:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete signed consultation"
        )
    
    # Audit log before deletion
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action="consultation_deleted",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "deleted_by": current_user.full_name,
            "consultation_type": consultation.consultation_type
        }
    )
    db.add(audit_log)
    
    db.delete(consultation)
    db.commit()
    
    return {"message": "Consultation deleted successfully"}

@router.post("/discharge/{consultation_id}")
async def generate_discharge_note(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """Generate discharge note for consultation"""
    # Get demo doctor
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    if not consultation.is_signed:
        raise HTTPException(
            status_code=400,
            detail="Consultation must be signed before discharge"
        )
    
    # Get patient details
    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()
    
    # Mock discharge note generation (replace with actual template logic)
    discharge_note = {
        "id": str(uuid.uuid4()),
        "consultation_id": consultation_id,
        "patient_name": f"{patient.given_name} {patient.family_name}",
        "patient_cnp": patient.cnp,
        "discharge_date": datetime.utcnow().isoformat(),
        "consultation_type": consultation.consultation_type,
        "summary": consultation.structured_data or {},
        "recommendations": "Follow-up as needed",
        "generated_at": datetime.utcnow().isoformat()
    }
    
    # Update consultation status
    consultation.status = "discharged"
    db.commit()
    
    # Audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action="discharge_generated",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "generated_by": current_user.full_name
        }
    )
    db.add(audit_log)
    db.commit()
    
    return {
        "message": "Discharge note generated successfully",
        "discharge_note": discharge_note
    }

@router.get("/today/stats")
async def get_today_stats(db: Session = Depends(get_db)):
    """Get today's consultation statistics"""
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    
    from datetime import date
    today = date.today()
    
    patients_today = db.query(Consultation.patient_id).filter(
        Consultation.clinic_id == current_user.clinic_id,
        func.date(Consultation.consultation_date) == today
    ).distinct().count()
    
    return {"patients_today": patients_today}
