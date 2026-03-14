
"""Consultation management endpoints - Agenda & Consult rework"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, cast, Date
from typing import List, Optional
import uuid
import logging
from datetime import datetime, date

from app.database import get_db
from app.models import Consultation, User, Patient, GDPRAuditLog, Document
from app.schemas import (
    ConsultationStart, ConsultationAutoSave, ConsultationCreate,
    ConsultationUpdate, ConsultationResponse, ConsultationListItem,
    AgendaItem, ConsultationComplete
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

# ============================
# AGENDA ENDPOINTS
# ============================

@router.get("/agenda")
async def get_agenda(
    target_date: Optional[str] = Query(None, alias="date"),
    db: Session = Depends(get_db)
):
    """
    Get today's (or specified date's) consultations for the Agenda view.
    Returns time-ordered list with patient names.
    """
    current_user = get_current_user(db)

    if target_date:
        try:
            agenda_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        agenda_date = date.today()

    consultations = db.query(Consultation, Patient).join(
        Patient, Consultation.patient_id == Patient.id
    ).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id,
        cast(Consultation.consultation_date, Date) == agenda_date,
        Consultation.status != "cancelled"
    ).order_by(
        Consultation.consultation_date.asc()
    ).all()

    return [
        {
            "id": c.id,
            "patient_id": c.patient_id,
            "patient_name": f"{p.given_name} {p.family_name}",
            "specialty": c.specialty,
            "consultation_date": c.consultation_date.isoformat(),
            "status": c.status,
            "is_signed": c.is_signed,
            "has_discharge": c.discharge_text is not None
        }
        for c, p in consultations
    ]

@router.get("/agenda/needs-attention")
async def get_needs_attention(db: Session = Depends(get_db)):
    """
    Get past unfinished consultations (in_progress or pending_review from before today).
    These are consults the doctor must not miss.
    """
    current_user = get_current_user(db)
    today = date.today()

    consultations = db.query(Consultation, Patient).join(
        Patient, Consultation.patient_id == Patient.id
    ).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id,
        Consultation.status.in_(["in_progress", "pending_review"]),
        cast(Consultation.consultation_date, Date) < today
    ).order_by(
        Consultation.consultation_date.desc()
    ).all()

    return [
        {
            "id": c.id,
            "patient_id": c.patient_id,
            "patient_name": f"{p.given_name} {p.family_name}",
            "specialty": c.specialty,
            "consultation_date": c.consultation_date.isoformat(),
            "status": c.status,
            "is_signed": c.is_signed,
            "has_discharge": c.discharge_text is not None
        }
        for c, p in consultations
    ]

# ============================
# CONSULTATION WORKFLOW
# ============================

@router.get("/counts")
async def get_consultation_counts(db: Session = Depends(get_db)):
    """Get consultation counts for badges"""
    current_user = get_current_user(db)

    active_count = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.status == "in_progress"
    ).count()

    pending_review_count = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.status == "pending_review"
    ).count()

    return {
        "active_consultations": active_count,
        "pending_review": pending_review_count
    }

@router.post("/start", response_model=ConsultationResponse)
async def start_consultation(
    data: ConsultationStart,
    db: Session = Depends(get_db)
):
    """
    Start new consultation - creates scheduled consultation with patient and specialty.
    Called from Agenda '+ Add Patient' or Patient card 'Start Consult'.
    """
    current_user = get_current_user(db)

    patient = db.query(Patient).filter(
        Patient.id == data.patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if current_user.specialties and data.specialty not in current_user.specialties:
        raise HTTPException(
            status_code=400,
            detail=f"Doctor not authorized for specialty: {data.specialty}"
        )

    new_consultation = Consultation(
        id=str(uuid.uuid4()),
        patient_id=data.patient_id,
        clinic_id=current_user.clinic_id,
        doctor_id=current_user.id,
        specialty=data.specialty,
        consultation_date=datetime.utcnow(),
        structured_data={},
        status="scheduled",
        is_signed=False,
        last_autosave_at=datetime.utcnow()
    )

    db.add(new_consultation)
    db.commit()
    db.refresh(new_consultation)

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
            "status": "scheduled"
        }
    )
    db.add(audit_log)
    db.commit()

    return new_consultation

@router.put("/{consultation_id}/auto-save", response_model=ConsultationResponse)
async def auto_save_consultation(
    consultation_id: str,
    data: ConsultationAutoSave,
    db: Session = Depends(get_db)
):
    """
    Auto-save consultation data every 30 seconds from frontend.
    Updates structured_data, pinned_files, audio fields, and last_autosave_at.
    """
    current_user = get_current_user(db)

    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    if consultation.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Cannot auto-save completed consultation"
        )

    if data.structured_data is not None:
        consultation.structured_data = data.structured_data
    if data.audio_file_path is not None:
        consultation.audio_file_path = data.audio_file_path
    if data.audio_duration_seconds is not None:
        consultation.audio_duration_seconds = data.audio_duration_seconds
    if data.pinned_files is not None:
        consultation.pinned_files = data.pinned_files

    consultation.last_autosave_at = datetime.utcnow()

    db.commit()
    db.refresh(consultation)

    app_logger.info(f"Auto-saved consultation {consultation_id} for doctor {current_user.id}")

    return consultation

@router.put("/{consultation_id}/specialty", response_model=ConsultationResponse)
async def update_consultation_specialty(
    consultation_id: str,
    specialty: str,
    db: Session = Depends(get_db)
):
    """Change specialty mid-consultation."""
    current_user = get_current_user(db)

    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

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

@router.put("/{consultation_id}/status", response_model=ConsultationResponse)
async def update_consultation_status(
    consultation_id: str,
    status: str,
    db: Session = Depends(get_db)
):
    """
    Update consultation status with validated transitions.
    scheduled → in_progress → pending_review/completed
    """
    current_user = get_current_user(db)

    valid_statuses = ["scheduled", "in_progress", "pending_review", "completed", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    valid_transitions = {
        "scheduled": ["in_progress", "cancelled"],
        "in_progress": ["pending_review", "completed", "cancelled"],
        "pending_review": ["in_progress", "completed"],
        "completed": [],  # Terminal — amendments use separate endpoint
        "cancelled": []
    }

    if status not in valid_transitions.get(consultation.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {consultation.status} to {status}"
        )

    old_status = consultation.status
    consultation.status = status

    if status == "completed" and not consultation.is_signed:
        consultation.is_signed = True
        consultation.signed_at = datetime.utcnow()

    db.commit()
    db.refresh(consultation)

    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action="consultation_status_changed",
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

@router.post("/{consultation_id}/complete", response_model=ConsultationResponse)
async def complete_consultation(
    consultation_id: str,
    data: ConsultationComplete,
    db: Session = Depends(get_db)
):
    """
    Complete a consultation with discharge text.
    Sets status to completed, signs it, and stores the discharge document.
    """
    current_user = get_current_user(db)

    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    if consultation.status == "completed":
        raise HTTPException(status_code=400, detail="Consultation is already completed")

    old_status = consultation.status
    consultation.status = "completed"
    consultation.is_signed = True
    consultation.signed_at = datetime.utcnow()
    consultation.discharge_text = data.discharge_text

    db.commit()
    db.refresh(consultation)

    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action="consultation_status_changed",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "old_status": old_status,
            "new_status": "completed",
            "signed": True,
            "has_discharge": True
        }
    )
    db.add(audit_log)
    db.commit()

    return consultation

@router.post("/{consultation_id}/amend", response_model=ConsultationResponse)
async def amend_consultation(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """
    Amend a completed consultation (doctor only).
    Preserves original signature, reopens for editing.
    """
    current_user = get_current_user(db)

    if current_user.role not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Only doctors can amend consultations")

    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    if consultation.status != "completed":
        raise HTTPException(status_code=400, detail="Only completed consultations can be amended")

    # Preserve original signature in amendment history
    history = consultation.amendment_history or []
    history.append({
        "user_id": current_user.id,
        "user_name": current_user.full_name,
        "timestamp": datetime.utcnow().isoformat(),
        "original_signed_at": consultation.signed_at.isoformat() if consultation.signed_at else None,
        "action": "amendment_started"
    })
    consultation.amendment_history = history
    consultation.status = "in_progress"
    consultation.amended_at = datetime.utcnow()

    db.commit()
    db.refresh(consultation)

    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=consultation.patient_id,
        action="consult_amended",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "amended_by": current_user.full_name,
            "original_signed_at": consultation.signed_at.isoformat() if consultation.signed_at else None
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
    """
    Delete a consultation (doctor only). Hard delete with GDPR audit log.
    Only allowed for scheduled or in_progress consultations.
    """
    current_user = get_current_user(db)

    if current_user.role not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Only doctors can delete consultations")

    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    if consultation.status in ["completed"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete completed consultation"
        )

    patient_id = consultation.patient_id

    # Audit log before deletion
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=patient_id,
        action="consult_deleted",
        legal_basis="consent",
        data_category="medical_consultation",
        details={
            "consultation_id": consultation_id,
            "deleted_by": current_user.full_name,
            "original_status": consultation.status,
            "consultation_date": consultation.consultation_date.isoformat() if consultation.consultation_date else None
        }
    )
    db.add(audit_log)

    db.delete(consultation)
    db.commit()

    return {"message": "Consultation deleted successfully"}

@router.post("/{consultation_id}/generate-discharge")
async def generate_discharge(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """
    Generate a discharge summary from consultation data and pinned files.
    Uses AI (LLM) to generate Romanian-language discharge text.
    Falls back to template-based generation if AI fails.
    """
    current_user = get_current_user(db)

    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()

    # Get pinned documents
    pinned_docs = []
    if consultation.pinned_files:
        pinned_docs = db.query(Document).filter(
            Document.id.in_(consultation.pinned_files),
            Document.clinic_id == current_user.clinic_id
        ).all()

    # Build discharge from structured data (template-based fallback)
    discharge_text = _generate_template_discharge(
        patient, consultation, pinned_docs, current_user
    )

    # Try AI generation
    try:
        ai_text = await _generate_ai_discharge(patient, consultation, pinned_docs, current_user)
        if ai_text:
            discharge_text = ai_text
    except Exception as e:
        app_logger.warning(f"AI discharge generation failed, using template: {e}")

    return {"discharge_text": discharge_text}

def _generate_template_discharge(patient, consultation, pinned_docs, doctor):
    """Template-based discharge generation fallback."""
    specialty_labels = {
        "internal_medicine": "Medicină Internă",
        "cardiology": "Cardiologie",
        "respiratory": "Pneumologie",
        "gynecology": "Ginecologie"
    }

    lines = []
    lines.append("SCRISOARE MEDICALĂ / BILET DE IEȘIRE")
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Pacient: {patient.given_name} {patient.family_name}")
    if patient.cnp:
        lines.append(f"CNP: {patient.cnp}")
    if patient.birth_date:
        lines.append(f"Data nașterii: {patient.birth_date}")
    lines.append("")
    lines.append(f"Specialitate: {specialty_labels.get(consultation.specialty, consultation.specialty)}")
    lines.append(f"Data consultației: {consultation.consultation_date.strftime('%d.%m.%Y')}")
    lines.append(f"Medic: Dr. {doctor.full_name}")
    lines.append("")

    # Add structured data fields
    if consultation.structured_data:
        lines.append("CONSTATĂRI CLINICE")
        lines.append("-" * 30)
        for key, value in consultation.structured_data.items():
            if value:
                label = key.replace("_", " ").title()
                lines.append(f"{label}: {value}")
        lines.append("")

    # Add pinned documents summary
    if pinned_docs:
        lines.append("DOCUMENTE ATAȘATE")
        lines.append("-" * 30)
        for doc in pinned_docs:
            doc_type = doc.document_type or "Document"
            lines.append(f"- {doc.original_filename} ({doc_type})")
        lines.append("")

    lines.append("")
    lines.append(f"Semnătură medic: Dr. {doctor.full_name}")
    lines.append(f"Data: {datetime.utcnow().strftime('%d.%m.%Y')}")

    return "\n".join(lines)

async def _generate_ai_discharge(patient, consultation, pinned_docs, doctor):
    """AI-powered discharge generation using Anthropic API."""
    try:
        import anthropic
    except ImportError:
        app_logger.info("Anthropic SDK not installed, skipping AI discharge generation")
        return None

    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        app_logger.info("ANTHROPIC_API_KEY not set, skipping AI discharge generation")
        return None

    specialty_labels = {
        "internal_medicine": "Medicină Internă",
        "cardiology": "Cardiologie",
        "respiratory": "Pneumologie",
        "gynecology": "Ginecologie"
    }

    # Build prompt
    prompt_parts = [
        "Generează o scrisoare medicală (bilet de ieșire) în limba română, profesională și completă.",
        "",
        f"Pacient: {patient.given_name} {patient.family_name}",
    ]
    if patient.cnp:
        prompt_parts.append(f"CNP: {patient.cnp}")
    if patient.birth_date:
        prompt_parts.append(f"Data nașterii: {patient.birth_date}")
    prompt_parts.append(f"Specialitate: {specialty_labels.get(consultation.specialty, consultation.specialty)}")
    prompt_parts.append(f"Data consultației: {consultation.consultation_date.strftime('%d.%m.%Y')}")
    prompt_parts.append(f"Medic: Dr. {doctor.full_name}")
    prompt_parts.append("")

    if consultation.structured_data:
        prompt_parts.append("Date clinice din consultație:")
        for key, value in consultation.structured_data.items():
            if value:
                prompt_parts.append(f"  {key}: {value}")
        prompt_parts.append("")

    if pinned_docs:
        prompt_parts.append("Documente atașate:")
        for doc in pinned_docs:
            prompt_parts.append(f"  - {doc.original_filename} ({doc.document_type or 'document'})")
            if doc.extracted_data:
                prompt_parts.append(f"    Date extrase: {doc.extracted_data}")
        prompt_parts.append("")

    prompt_parts.append("Generează scrisoarea medicală completă, cu secțiuni standard: diagnostic, anamneza, examen clinic, investigații, tratament recomandat, recomandări la externare.")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": "\n".join(prompt_parts)}]
    )

    return message.content[0].text

# ============================
# EXISTING ENDPOINTS (Updated)
# ============================

@router.get("/drafts", response_model=List[ConsultationListItem])
async def get_draft_consultations(db: Session = Depends(get_db)):
    """Get all scheduled consultations for current doctor."""
    current_user = get_current_user(db)

    drafts = db.query(Consultation).filter(
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id,
        Consultation.status == "scheduled"
    ).order_by(
        Consultation.last_autosave_at.desc()
    ).all()

    return drafts

@router.delete("/{consultation_id}/cancel")
async def cancel_consultation(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """Cancel consultation (soft delete - sets status to cancelled)."""
    current_user = get_current_user(db)

    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    if consultation.status == "completed":
        raise HTTPException(status_code=400, detail="Cannot cancel completed consultation")

    consultation.status = "cancelled"
    db.commit()

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

@router.get("/{consultation_id}/patient-history")
async def get_patient_history_for_consultation(
    consultation_id: str,
    db: Session = Depends(get_db)
):
    """
    Get patient's previous consultations and documents for left panel.
    """
    current_user = get_current_user(db)

    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    patient = db.query(Patient).filter(Patient.id == consultation.patient_id).first()

    previous_consultations = db.query(Consultation).filter(
        Consultation.patient_id == consultation.patient_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.id != consultation_id,
        Consultation.status == "completed"
    ).order_by(
        Consultation.consultation_date.desc()
    ).all()

    # Get all documents (not just validated) for the patient
    documents = db.query(Document).filter(
        Document.patient_id == consultation.patient_id,
        Document.clinic_id == current_user.clinic_id
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
                "is_signed": c.is_signed,
                "discharge_text": c.discharge_text
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

# Legacy CRUD endpoints

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
        status="scheduled",
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
    if consultation_data.pinned_files is not None:
        consultation.pinned_files = consultation_data.pinned_files
    if consultation_data.discharge_text is not None:
        consultation.discharge_text = consultation_data.discharge_text

    db.commit()
    db.refresh(consultation)

    return consultation

@router.get("/today/stats")
async def get_today_stats(db: Session = Depends(get_db)):
    """Get today's consultation statistics"""
    current_user = get_current_user(db)

    today = date.today()

    patients_today = db.query(Consultation.patient_id).filter(
        Consultation.clinic_id == current_user.clinic_id,
        cast(Consultation.consultation_date, Date) == today
    ).distinct().count()

    return {"patients_today": patients_today}
