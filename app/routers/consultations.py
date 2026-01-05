
"""Consultation management endpoints - Phase 4A"""
from fastapi import APIRouter, Depends, HTTPException, Query,UploadFile, File, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional, Dict, Any
import uuid
import aiofiles
import logging
from datetime import datetime
from pathlib import Path
import os

from app.database import get_db
from app.auth import get_user_from_header
from app.models import Consultation, User, Patient, GDPRAuditLog, Document
from app.schemas import (
    ConsultationStart, ConsultationAutoSave, ConsultationCreate, 
    ConsultationUpdate, ConsultationResponse, ConsultationListItem
)
from app.services.template_service import TemplateService
from app.services.audio_service import AudioTranscriptionService
from app.services.llm_extraction_service import LLMExtractionService
from app.services.template_service import TemplateService


router = APIRouter(tags=["consultations"])

# Loggers
audit_logger = logging.getLogger("reconomed.audit")
app_logger = logging.getLogger("reconomed.app")


# Initialize services (use environment variables in production)
audio_service = AudioTranscriptionService(api_key=os.getenv("OPENAI_API_KEY"))
llm_service = LLMExtractionService(api_key=os.getenv("OPENAI_API_KEY"))

#--------------
# Get counts
#------------------
@router.get("/counts")
async def get_consultation_counts(request:Request,db: Session = Depends(get_db)):
    """Get consultation counts for tab badges"""
    # Get demo doctor
    current_user = get_user_from_header(db, request)

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
    request:Request,
    db: Session = Depends(get_db)
):
    """
    Start new consultation - creates draft with patient and specialty.
    Called from: "Add New Consult" button or consultation search flow.
    """
    current_user = get_user_from_header(db, request)
    
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
    request:Request,
    db: Session = Depends(get_db)
):
    """
    Auto-save consultation data every 60 seconds from frontend.
    Updates structured_data, audio fields, and last_autosave_at timestamp.
    """
    current_user = get_user_from_header(db,request)
    
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
    request:Request,
    db: Session = Depends(get_db)
):
    """
    Change specialty mid-consultation.
    Validates doctor has access to new specialty.
    """
    current_user = get_user_from_header(db,request)
    
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
    request:Request,
    db: Session = Depends(get_db)
):
    """
    Update consultation status: draft → in_progress → completed
    Validates status transitions.
    """
    current_user = get_user_from_header(db, request)
    
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
    request:Request,
    db: Session = Depends(get_db)
):
    """
    Get all draft consultations for current doctor.
    Used for "Resume Draft" functionality.
    """
    current_user = get_user_from_header(db, request)
    
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
    request:Request,
    db: Session = Depends(get_db)
):
    """
    Cancel consultation (soft delete - sets status to cancelled).
    Only allowed for draft/in_progress consultations.
    """
    current_user = get_user_from_header(db, request)
    
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
    request:Request,
    db: Session = Depends(get_db)
):
    """
    Get patient's previous consultations and documents.
    Used for left panel in Step 2 split view.
    Returns same structure as View Patient Modal's Documents & History tab.
    """
    current_user = get_user_from_header(db, request)
    
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
    request:Request,
    db: Session = Depends(get_db)
):
    """Legacy endpoint - use /start instead"""
    current_user = get_user_from_header(db, request)
    
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
    request:Request,
    patient_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get consultations with optional filters"""
    current_user = get_user_from_header(db, request)
    
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
    request:Request,
    db: Session = Depends(get_db),
):
    """Get specific consultation"""
    current_user = get_user_from_header(db, request)
    
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
    request:Request,
    db: Session = Depends(get_db)
):
    """Update consultation - legacy endpoint"""
    current_user = get_user_from_header(db, request)
    
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
async def get_today_stats(request:Request, db: Session = Depends(get_db)):
    """Get today's consultation statistics"""
    current_user = get_user_from_header(db, request)
    
    from datetime import date
    today = date.today()
    
    patients_today = db.query(Consultation.patient_id).filter(
        Consultation.clinic_id == current_user.clinic_id,
        func.date(Consultation.consultation_date) == today
    ).distinct().count()
    
    return {"patients_today": patients_today}


@router.get("/templates/{specialty}")
async def get_consultation_template(
    specialty: str,
    db: Session = Depends(get_db)
):
    """Get template definition for specialty"""
    template_service = TemplateService(db)
    try:
        template = template_service.get_template(specialty)
        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{consultation_id}/pre-fill")
async def pre_fill_consultation(
    consultation_id: str,
    request:Request,
    selected_documents: Optional[List[str]] = None,
    db: Session = Depends(get_db)
):
    """
    Pre-fill consultation with patient history.
    Called after doctor selects which documents to include.
    """
    current_user = get_user_from_header(db, request)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    template_service = TemplateService(db)
    pre_filled_data = template_service.pre_fill_template(
        consultation.patient_id,
        consultation.specialty,
        selected_documents
    )
    
    # Merge with existing data (don't overwrite manual entries)
    existing_data = consultation.structured_data or {}
    merged_data = {**pre_filled_data, **existing_data}
    
    consultation.structured_data = merged_data
    consultation.last_autosave_at = datetime.utcnow()
    
    db.commit()
    db.refresh(consultation)
    
    return consultation
    
@router.post("/{consultation_id}/audio/upload")
async def upload_consultation_audio(
    consultation_id: str,
    request:Request,
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload audio file for consultation.
    Stores file temporarily for processing.
    """
    current_user = get_user_from_header(db, request)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    # Validate file type
    allowed_formats = [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"]
    file_ext = Path(audio_file.filename).suffix.lower()
    if file_ext not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format. Allowed: {', '.join(allowed_formats)}"
        )
    
    # Create uploads directory if not exists
    upload_dir = Path("uploads/audio/temp")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    audio_filename = f"{consultation_id}_{uuid.uuid4()}{file_ext}"
    audio_path = upload_dir / audio_filename
    
    # Save file
    async with aiofiles.open(audio_path, 'wb') as f:
        content = await audio_file.read()
        await f.write(content)
    
    # Get audio duration (if available)
    audio_duration = None
    try:
        import wave
        if file_ext == ".wav":
            with wave.open(str(audio_path), 'rb') as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                audio_duration = int(frames / rate)
    except:
        pass  # Duration optional for now
    
    # Update consultation
    consultation.audio_file_path = str(audio_path)
    consultation.audio_duration_seconds = audio_duration
    consultation.last_autosave_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "Audio uploaded successfully",
        "audio_file_path": str(audio_path),
        "audio_duration_seconds": audio_duration
    }

@router.post("/{consultation_id}/audio/process")
async def process_consultation_audio(
    consultation_id: str,
    request:Request,
    db: Session = Depends(get_db)
):
    """
    Process uploaded audio: transcribe and extract fields.
    This is the main endpoint called when doctor clicks "End Recording".
    
    Steps:
    1. Transcribe audio using Whisper API
    2. Extract structured fields using GPT-4
    3. Extract ICD-10 codes from diagnosis
    4. Update consultation with extracted data
    5. Delete audio file (GDPR requirement)
    """
    current_user = get_user_from_header(db, request)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id,
        Consultation.doctor_id == current_user.id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    if not consultation.audio_file_path:
        raise HTTPException(status_code=400, detail="No audio file uploaded")
    
    try:
        # Step 1: Transcribe audio
        app_logger.info(f"Transcribing audio for consultation {consultation_id}")
        transcript = await audio_service.transcribe_audio(
            consultation.audio_file_path,
            language="ro"
        )
        
        consultation.audio_transcript = transcript
        db.commit()
        
        # Step 2: Get template for field extraction
        template_service = TemplateService(db)
        template = template_service.get_template(consultation.specialty)
        
        # Step 3: Extract fields from transcript
        app_logger.info(f"Extracting fields for consultation {consultation_id}")
        extracted_data = await llm_service.extract_fields_from_transcript(
            transcript=transcript,
            template=template,
            existing_data=consultation.structured_data
        )
        
        # Step 4: Extract ICD-10 codes if diagnosis mentioned
        if "diagnosis" in extracted_data and extracted_data["diagnosis"].get("diagnoses"):
            diagnosis_text = extracted_data["diagnosis"]["diagnoses"]
            app_logger.info(f"Extracting ICD-10 codes for consultation {consultation_id}")
            
            icd10_codes = await llm_service.extract_icd10_codes(
                diagnosis_text=diagnosis_text,
                icd10_database=""  # Load from CSV or use LLM's knowledge
            )
            
            extracted_data["diagnosis"]["icd10_codes"] = icd10_codes
        
        # Step 5: Merge extracted data with existing (don't overwrite manual entries)
        existing_data = consultation.structured_data or {}
        
        # Deep merge: extracted data goes in, but existing manual entries stay
        merged_data = self._deep_merge_with_confidence(existing_data, extracted_data)
        
        consultation.structured_data = merged_data
        consultation.last_autosave_at = datetime.utcnow()
        
        db.commit()
        
        # Step 6: Delete audio file (GDPR requirement - keep only transcript)
        try:
            audio_path = Path(consultation.audio_file_path)
            if audio_path.exists():
                audio_path.unlink()
                app_logger.info(f"Deleted audio file for consultation {consultation_id}")
            consultation.audio_file_path = None  # Clear path after deletion
            db.commit()
        except Exception as e:
            app_logger.error(f"Failed to delete audio file: {str(e)}")
        
        # Audit log
        audit_log = GDPRAuditLog(
            clinic_id=current_user.clinic_id,
            user_id=current_user.id,
            patient_id=consultation.patient_id,
            action="audio_processed_and_deleted",
            legal_basis="consent",
            data_category="medical_consultation",
            details={
                "consultation_id": consultation_id,
                "transcript_length": len(transcript),
                "fields_extracted": list(extracted_data.keys()),
                "audio_deleted": True
            }
        )
        db.add(audit_log)
        db.commit()
        
        return {
            "message": "Audio processed successfully",
            "transcript": transcript,
            "extracted_data": merged_data,
            "audio_deleted": True
        }
        
    except Exception as e:
        app_logger.error(f"Audio processing failed for consultation {consultation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audio processing failed: {str(e)}")

def _deep_merge_with_confidence(
    existing: Dict[str, Any],
    extracted: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deep merge extracted data with existing data.
    
    Rules:
    - If field exists in 'existing' and not in 'extracted': keep existing
    - If field exists in 'extracted' with high confidence: use extracted
    - If field exists in both with medium/low confidence: keep existing (doctor manually entered)
    - If field only in extracted: add it
    """
    merged = dict(existing)
    
    for section_id, section_data in extracted.items():
        if section_id not in merged:
            merged[section_id] = section_data
        else:
            # Merge section-level data
            merged_section = dict(merged[section_id])
            
            for field_id, field_value in section_data.items():
                # Skip confidence fields
                if field_id.endswith("_confidence"):
                    continue
                
                # Check confidence
                confidence_key = f"{field_id}_confidence"
                confidence = section_data.get(confidence_key, "medium")
                
                # If field doesn't exist, add it
                if field_id not in merged_section:
                    merged_section[field_id] = field_value
                    if confidence_key in section_data:
                        merged_section[confidence_key] = section_data[confidence_key]
                
                # If field exists and extracted has high confidence, consider updating
                elif confidence == "high":
                    # Only update if existing value is empty/null
                    if not merged_section[field_id]:
                        merged_section[field_id] = field_value
                        if confidence_key in section_data:
                            merged_section[confidence_key] = section_data[confidence_key]
            
            merged[section_id] = merged_section
    
    return merged

@router.get("/{consultation_id}/audio/transcript")
async def get_consultation_transcript(
    consultation_id: str,
    request:Request,
    db: Session = Depends(get_db)
):
    """Get audio transcript for consultation (for review/editing)"""
    current_user = get_user_from_header(db, request)
    
    consultation = db.query(Consultation).filter(
        Consultation.id == consultation_id,
        Consultation.clinic_id == current_user.clinic_id
    ).first()
    
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    
    return {
        "consultation_id": consultation_id,
        "transcript": consultation.audio_transcript,
        "duration_seconds": consultation.audio_duration_seconds
    }