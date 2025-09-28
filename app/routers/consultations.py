"""Consultations management endpoints with mock data"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
import logging

from app.database import get_db
from app.models import User
#from app.logger import app_logger, audit_logger

router = APIRouter(
    #prefix="/consultations",
    tags=["consultations"],
    responses={404: {"description": "Not found"}},
)

# Reuse the loggers created in app.main
audit_logger = logging.getLogger("reconomed.audit")
app_logger=logging.getLogger("reconomed.app")

# Mock data for development
MOCK_CONSULTATIONS = [
    {
        "id": str(uuid.uuid4()),
        "patient_id": "patient-001",
        "patient_name": "Ion Popescu",
        "consultation_type": "general",
        "date": (datetime.now() - timedelta(hours=2)).isoformat(),
        "notes": "Regular check-up. Patient reports feeling well. Blood pressure normal.",
        "status": "completed",
        "doctor_id": "doctor-001",
        "discharge_ready": True
    },
    {
        "id": str(uuid.uuid4()),
        "patient_id": "patient-002", 
        "patient_name": "Maria Ionescu",
        "consultation_type": "followup",
        "date": (datetime.now() - timedelta(hours=4)).isoformat(),
        "notes": "Follow-up for diabetes management. HbA1c levels improved.",
        "status": "completed",
        "doctor_id": "doctor-001",
        "discharge_ready": True
    },
    {
        "id": str(uuid.uuid4()),
        "patient_id": "patient-003",
        "patient_name": "Gheorghe Popa",
        "consultation_type": "emergency",
        "date": (datetime.now() - timedelta(minutes=30)).isoformat(),
        "notes": "Chest pain evaluation. ECG normal, troponins pending.",
        "status": "in_progress",
        "doctor_id": "doctor-001",
        "discharge_ready": False
    }
]

MOCK_RECENT_ACTIVITY = [
    {
        "id": str(uuid.uuid4()),
        "type": "consultation_completed",
        "title": "Consultation completed for Ion Popescu",
        "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
        "icon": "fas fa-stethoscope"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "discharge_generated", 
        "title": "Discharge note generated for Maria Ionescu",
        "timestamp": (datetime.now() - timedelta(minutes=45)).isoformat(),
        "icon": "fas fa-file-export"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "consultation_started",
        "title": "Emergency consultation started for Gheorghe Popa", 
        "timestamp": (datetime.now() - timedelta(minutes=60)).isoformat(),
        "icon": "fas fa-ambulance"
    }
]

@router.get("/recent")
async def get_recent_consultations(
    request: Request,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get recent consultations for dashboard"""
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug(f"Fetching recent consultations (limit={limit})")
    audit_logger.info(f"user={user} action=get_recent_consultations")

    # Return mock data for now
    recent = sorted(MOCK_CONSULTATIONS, key=lambda x: x["date"], reverse=True)[:limit]
    
    return {
        "consultations": recent,
        "total": len(MOCK_CONSULTATIONS)
    }

@router.get("/pending-discharge")
async def get_pending_discharge(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get consultations ready for discharge"""
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug("Fetching consultations pending discharge")
    audit_logger.info(f"user={user} action=get_pending_discharge")

    # Filter mock consultations ready for discharge
    ready_for_discharge = [c for c in MOCK_CONSULTATIONS if c.get("discharge_ready", False)]
    
    return {
        "consultations": ready_for_discharge,
        "count": len(ready_for_discharge)
    }

@router.get("/counts")
async def get_consultation_counts(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get consultation counts for tab badges"""
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug("Fetching consultation counts")
    audit_logger.info(f"user={user} action=get_consultation_counts")

    active_count = len([c for c in MOCK_CONSULTATIONS if c["status"] == "in_progress"])
    discharge_ready_count = len([c for c in MOCK_CONSULTATIONS if c.get("discharge_ready", False)])
    review_pending_count = 2  # Mock value for patients needing review

    return {
        "active_consultations": active_count,
        "discharge_ready": discharge_ready_count, 
        "review_pending": review_pending_count
    }

@router.post("/")
async def create_consultation(
    request: Request,
    consultation_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Create new consultation (mock implementation)"""
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug("Creating new consultation")
    audit_logger.info(f"user={user} action=create_consultation patient_id={consultation_data.get('patient_id')}")

    # Demo user lookup
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")

    # Create mock consultation
    new_consultation = {
        "id": str(uuid.uuid4()),
        "patient_id": consultation_data.get("patient_id"),
        "consultation_type": consultation_data.get("consultation_type", "general"),
        "date": datetime.now().isoformat(),
        "notes": consultation_data.get("notes", ""),
        "status": "completed",
        "doctor_id": current_user.id,
        "discharge_ready": consultation_data.get("consultation_type") != "emergency"
    }

    # Add to mock data (in real implementation, save to database)
    MOCK_CONSULTATIONS.append(new_consultation)

    app_logger.info(f"Mock consultation {new_consultation['id']} created")

    return {
        "message": "Consultation created successfully",
        "consultation": new_consultation
    }

@router.get("/activity/recent")
async def get_recent_activity(
    request: Request,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """Get recent consultation activity for dashboard"""
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug(f"Fetching recent activity (limit={limit})")
    audit_logger.info(f"user={user} action=get_recent_activity")

    return {
        "activities": MOCK_RECENT_ACTIVITY[:limit],
        "total": len(MOCK_RECENT_ACTIVITY)
    }

@router.post("/discharge/{consultation_id}")
async def generate_discharge_note(
    consultation_id: str,
    request: Request,
    discharge_data: Dict[str, Any] = None,
    db: Session = Depends(get_db)
):
    """Generate discharge note for consultation"""
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug(f"Generating discharge note for consultation {consultation_id}")
    audit_logger.info(f"user={user} action=generate_discharge consultation_id={consultation_id}")

    # Find mock consultation
    consultation = next((c for c in MOCK_CONSULTATIONS if c["id"] == consultation_id), None)
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    # Mock discharge note
    discharge_note = {
        "id": str(uuid.uuid4()),
        "consultation_id": consultation_id,
        "patient_name": consultation.get("patient_name", "Unknown"),
        "discharge_date": datetime.now().isoformat(),
        "summary": f"Patient {consultation.get('patient_name')} was seen for {consultation.get('consultation_type')} consultation.",
        "recommendations": "Continue current medications. Follow-up in 2 weeks.",
        "generated_at": datetime.now().isoformat()
    }

    app_logger.info(f"Mock discharge note generated for consultation {consultation_id}")

    return {
        "message": "Discharge note generated successfully",
        "discharge_note": discharge_note
    }