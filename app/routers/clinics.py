"""Clinic management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict

from app.database import get_db
from app.auth import get_admin, get_current_user
from app.models import Clinic, User, Patient
from app.schemas import ClinicCreate, ClinicResponse

router = APIRouter(
    #prefix="/clinics",
    tags=["clinics"]
)

# Default Romanian consent templates
DEFAULT_CONSENT_TEMPLATES = {

    "treatment_ro": """CONSIMȚĂMÂNT PENTRU TRATAMENT MEDICAL

Subsemnatul/a {{patient_name}}, cu CNP {{patient_cnp}}, declar că sunt de acord cu efectuarea tratamentului medical la {{clinic_name}}, începând cu data de {{date}}.

Înțeleg că:
- Datele mele medicale vor fi prelucrate conform GDPR
- Pot retrage acest consimțământ oricând
- Tratamentul se va efectua conform standardelor medicale

Semnătura: _______________  Data: {{date}}
""",
    "data_processing_ro": """CONSIMȚĂMÂNT PRELUCRARE DATE PERSONALE

Accept ca datele mele personale și medicale să fie prelucrate de {{clinic_name}} conform Regulamentului UE 2016/679 (GDPR) în scopul îngrijirii medicale.

Drepturile mele includ:
- Dreptul de acces la datele personale
- Dreptul la rectificare
- Dreptul la ștergere
- Dreptul la portabilitate

Semnătura: _______________  Data: {{date}}
""",
    "research_ro": """CONSIMȚĂMÂNT CERCETARE MEDICALĂ (OPȚIONAL)

Accept ca datele mele medicale anonimizate să fie utilizate în scopuri de cercetare medicală de către {{clinic_name}}.

Înțeleg că:
- Datele vor fi complet anonimizate
- Participarea este voluntară
- Pot retrage acest consimțământ oricând

Semnătura: _______________  Data: {{date}}
"""
}

DEFAULT_RETENTION_POLICY={
  "consultation_notes": {
    "retention_months": 60,
    "anonymization_months": 84,
    "legal_basis": "legal_obligation"
  },
  "lab_results": {
    "retention_months": 36,
    "anonymization_months": 48,
    "legal_basis": "consent"
  },
  "monitoring_data": {
    "retention_months": 24,
    "anonymization_months": 36,
    "legal_basis": "consent"
  },
  "billing_records": {
    "retention_months": 84,
    "legal_basis": "legal_obligation"
  }
}

@router.get("/my-clinic", response_model=ClinicResponse, summary="Get current user's clinic info with defaults")
async def get_my_clinic(db: Session = Depends(get_db)):
    """Get current user's clinic information including consent templates and retention policies, return defaults if not any"""
    
    # TODO REPLACE LATER WITH PROPER AUTHENTICATION - THE FUNCTION IS IN auth.py and is called get_current_active_user
    # TODO: current_user: User = Depends(get_current_active_user)
    # TODO clinic_service: ClinicService = Depends(get_clinic_service)

    # Get demo doctor for testing
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    # Get clinic
    clinic = db.query(Clinic).filter(Clinic.id == current_user.clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    # KEEP from here

    # If clinic doesn't have consent templates, use defaults
    gdpr_templates = clinic.gdpr_templates if hasattr(clinic, 'gdpr_templates') and clinic.gdpr_templates else DEFAULT_CONSENT_TEMPLATES
    
    # If clinic doesn't have retention policies, use defaults
    retention_policies = clinic.retention_policies if hasattr(clinic, 'retention_policies') and clinic.retention_policies else DEFAULT_RETENTION_POLICY
    
    #Compilation data:
    # Get counts
    user_count = db.query(User).filter(User.clinic_id == clinic.id).count()
    patient_count = db.query(Patient).filter(Patient.clinic_id == clinic.id).count()

    return {
        "id": clinic.id,
        "name": clinic.name,
        "country":clinic.country,
        "gdpr_templates": gdpr_templates,
        "retention_policies": retention_policies,
        "user_count":user_count,
        "patient_count":patient_count,
        "max_uploads": clinic.max_uploads,
        "current_upload_count": clinic.current_upload_count,
        "created_at": clinic.created_at.isoformat()
    }

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