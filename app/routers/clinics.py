"""Clinic management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.auth import get_admin, get_current_user
from app.models import Clinic, User
from pydantic import BaseModel

router = APIRouter(
    #prefix="/clinics",
    tags=["clinics"]
)

class ClinicBase(BaseModel):
    name: str
    country: str = 'RO'
    gdpr_templates: Optional[dict] = None
    retention_policies: Optional[dict] = None

class ClinicCreate(ClinicBase):
    pass

class ClinicResponse(ClinicBase):
    id: str
    created_at: str
    user_count: int
    patient_count: int
    
    class Config:
        from_attributes = True

@router.post("/", response_model=ClinicResponse)
async def create_clinic(
    clinic_data: ClinicCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin)
):
    """Create new clinic (admin only)"""
    # Default GDPR templates for Romanian clinics
    default_gdpr_templates = {
        "consent_types": [
            {"id": "treatment", "name_ro": "Îngrijire medicală", "name_en": "Medical treatment"},
            {"id": "data_processing", "name_ro": "Prelucrare date", "name_en": "Data processing"},
            {"id": "research", "name_ro": "Cercetare medicală", "name_en": "Medical research"},
            {"id": "marketing", "name_ro": "Comunicări marketing", "name_en": "Marketing communications"}
        ],
        "retention_periods": {
            "treatment": {"years": 5, "description": "Medical treatment records"},
            "administrative": {"years": 3, "description": "Administrative data"},
            "research": {"years": 10, "description": "Research data"}
        }
    }
    
    new_clinic = Clinic(
        name=clinic_data.name,
        country=clinic_data.country,
        gdpr_templates=clinic_data.gdpr_templates or default_gdpr_templates,
        retention_policies=clinic_data.retention_policies or {}
    )
    
    db.add(new_clinic)
    db.commit()
    db.refresh(new_clinic)
    
    # Get counts for response
    user_count = db.query(User).filter(User.clinic_id == new_clinic.id).count()
    patient_count = 0  # Will implement when Patient model is ready
    
    return ClinicResponse(
        id=new_clinic.id,
        name=new_clinic.name,
        country=new_clinic.country,
        gdpr_templates=new_clinic.gdpr_templates,
        retention_policies=new_clinic.retention_policies,
        created_at=new_clinic.created_at.isoformat(),
        user_count=user_count,
        patient_count=patient_count
    )

@router.get("/my-clinic", response_model=ClinicResponse)
async def get_my_clinic(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's clinic information"""
    clinic = db.query(Clinic).filter(Clinic.id == current_user.clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    
    # Get counts
    user_count = db.query(User).filter(User.clinic_id == clinic.id).count()
    patient_count = 0  # Will implement when Patient model is ready
    
    return ClinicResponse(
        id=clinic.id,
        name=clinic.name,
        country=clinic.country,
        gdpr_templates=clinic.gdpr_templates,
        retention_policies=clinic.retention_policies,
        created_at=clinic.created_at.isoformat(),
        user_count=user_count,
        patient_count=patient_count
    )