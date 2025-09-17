"""Enhanced patient management with Romanian fields and GDPR compliance"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.database import get_db
from app.auth import get_current_user, get_any_staff
from app.models import Patient, User, PatientCreate, PatientResponse, GDPRAuditLog
from app.utils.romanian_validation import (
    validate_cnp, extract_birth_date_from_cnp, extract_gender_from_cnp,
    validate_romanian_phone, validate_insurance_number, normalize_romanian_address
)
from app.utils.gdpr_utils import (
    get_default_romanian_consents, check_required_consents, is_consent_valid
)

router = APIRouter(
    prefix="/patients",
    tags=["patients"],
    #dependencies=[Depends(get_any_staff)]  # Require staff authentication
)

@router.post("/", response_model=PatientResponse)
async def create_patient(
    patient_data: PatientCreate,
    #current_user: User = Depends(get_current_user), #This is commented out for now
    db: Session = Depends(get_db)
):
    #TEMPORAY CURRENT USER DEPENDANCE
    # Get demo doctor for testing
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")

    #TEMPORARY OUTPUT OF ERRORS:
    print(f"Received patient data: {patient_data}")

    """Create new patient with Romanian validation and GDPR compliance"""
    
    # Validate Romanian-specific fields
    validation_errors = []
    
    # CNP validation
    if patient_data.cnp:
        is_valid_cnp, cnp_error = validate_cnp(patient_data.cnp)
        if not is_valid_cnp:
            validation_errors.append(f"CNP: {cnp_error}")
        else:
            # Auto-extract birth date if not provided
            if not patient_data.birth_date:
                patient_data.birth_date = extract_birth_date_from_cnp(patient_data.cnp)
    
    # Phone validation
    if patient_data.phone:
        is_valid_phone, phone_error = validate_romanian_phone(patient_data.phone)
        if not is_valid_phone:
            validation_errors.append(f"Phone: {phone_error}")
    
    # Insurance validation
    if patient_data.insurance_number:
        is_valid_insurance, insurance_error = validate_insurance_number(patient_data.insurance_number)
        if not is_valid_insurance:
            validation_errors.append(f"Insurance: {insurance_error}")
    
    if validation_errors:
        print(f"Validation errors: {validation_errors}")  # Debug line
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation errors: {', '.join(validation_errors)}"
        )
    
    # Check for duplicate CNP within clinic
    if patient_data.cnp:
        existing_cnp = db.query(Patient).filter(
            Patient.cnp == patient_data.cnp,
            Patient.clinic_id == current_user.clinic_id
        ).first()
        if existing_cnp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A patient with this CNP already exists in your clinic"
            )
    
    # Setup GDPR consents
    gdpr_consents = patient_data.gdpr_consents or get_default_romanian_consents()
    
    # Validate required consents
    consents_valid, missing_consents = check_required_consents(gdpr_consents)
    if not consents_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required consents: {', '.join(missing_consents)}"
        )
    
    # Normalize address
    normalized_address = normalize_romanian_address(patient_data.address)
    
    # Create patient
    new_patient = Patient(
        id=str(uuid.uuid4()),
        clinic_id=current_user.clinic_id,
        family_name=patient_data.family_name.strip().title(),
        given_name=patient_data.given_name.strip().title(),
        birth_date=patient_data.birth_date,
        cnp=patient_data.cnp,
        insurance_number=patient_data.insurance_number,
        insurance_house=patient_data.insurance_house,
        phone=patient_data.phone,
        email=patient_data.email.lower() if patient_data.email else None,
        address=normalized_address,
        gdpr_consents=gdpr_consents
    )
    
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    
    # Create GDPR audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=new_patient.id,
        action="patient_created",
        legal_basis="consent",
        data_category="personal_medical",
        details={
            "consents_granted": list(gdpr_consents.keys()),
            "created_by": current_user.full_name,
            "creation_method": "manual_entry"
        }
    )
    db.add(audit_log)
    db.commit()
    
    return PatientResponse(
        id=new_patient.id,
        clinic_id=new_patient.clinic_id,
        family_name=new_patient.family_name,
        given_name=new_patient.given_name,
        birth_date=new_patient.birth_date,
        cnp=new_patient.cnp,
        insurance_number=new_patient.insurance_number,
        insurance_house=new_patient.insurance_house,
        phone=new_patient.phone,
        email=new_patient.email,
        address=new_patient.address,
        gdpr_consents=new_patient.gdpr_consents,
        created_at=new_patient.created_at
    )

@router.get("/", response_model=List[PatientResponse])
async def get_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, min_length=2, max_length=100),
    #current_user: User = Depends(get_current_user), #This is commented out for now
    db: Session = Depends(get_db)
):
    #TEMPORAY CURRENT USER DEPENDENCE
    # Get demo doctor for testing
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")

    """Get patients for current user's clinic with search capability"""
    
    # Base query - clinic isolation
    query = db.query(Patient).filter(Patient.clinic_id == current_user.clinic_id)
    
    # Add search filter
    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            db.or_(
                Patient.family_name.ilike(search_term),
                Patient.given_name.ilike(search_term),
                Patient.cnp.like(f"%{search.strip()}%"),
                Patient.phone.like(f"%{search.strip()}%")
            )
        )
    
    # Apply pagination and ordering
    patients = query.order_by(Patient.family_name, Patient.given_name).offset(skip).limit(limit).all()
    
    return [
        PatientResponse(
            id=patient.id,
            clinic_id=patient.clinic_id,
            family_name=patient.family_name,
            given_name=patient.given_name,
            birth_date=patient.birth_date,
            cnp=patient.cnp,
            insurance_number=patient.insurance_number,
            insurance_house=patient.insurance_house,
            phone=patient.phone,
            email=patient.email,
            address=patient.address,
            gdpr_consents=patient.gdpr_consents,
            created_at=patient.created_at
        )
        for patient in patients
    ]

@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    #current_user: User = Depends(get_current_user), #This is commented out for now
    db: Session = Depends(get_db)
):
    #TEMPORAY CURRENT USER DEPENDANCE
    # Get demo doctor for testing
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")


    """Get specific patient with clinic isolation and GDPR audit"""
    
    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    # Check GDPR consent validity
    consents_valid, missing_consents = check_required_consents(patient.gdpr_consents or {})
    if not consents_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Patient access restricted due to invalid consents: {', '.join(missing_consents)}"
        )
    
    # Create audit log for access
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=patient.id,
        action="patient_accessed",
        legal_basis="consent",
        data_category="personal_medical",
        details={
            "access_method": "api_endpoint",
            "accessed_by": current_user.full_name,
            "user_role": current_user.role
        }
    )
    db.add(audit_log)
    db.commit()
    
    return PatientResponse(
        id=patient.id,
        clinic_id=patient.clinic_id,
        family_name=patient.family_name,
        given_name=patient.given_name,
        birth_date=patient.birth_date,
        cnp=patient.cnp,
        insurance_number=patient.insurance_number,
        insurance_house=patient.insurance_house,
        phone=patient.phone,
        email=patient.email,
        address=patient.address,
        gdpr_consents=patient.gdpr_consents,
        created_at=patient.created_at
    )

@router.get("/validate-cnp/{cnp}")
async def validate_cnp_endpoint(cnp: str):
    """Validate Romanian CNP and extract information"""
    is_valid, error_message = validate_cnp(cnp)
    
    if not is_valid:
        return {
            "valid": False,
            "error": error_message,
            "birth_date": None,
            "gender": None
        }
    
    return {
        "valid": True,
        "error": None,
        "birth_date": extract_birth_date_from_cnp(cnp),
        "gender": extract_gender_from_cnp(cnp)
    }

@router.post("/{patient_id}/gdpr/withdraw-consent")
async def withdraw_patient_consent(
    patient_id: str,
    consent_type: str,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Withdraw specific GDPR consent for patient"""
    
    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.clinic_id == current_user.clinic_id
    ).first()
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Check if consent type exists
    if consent_type not in (patient.gdpr_consents or {}):
        raise HTTPException(
            status_code=400, 
            detail=f"Consent type '{consent_type}' not found"
        )
    
    # Prevent withdrawal of required consents
    if consent_type in ["treatment", "data_processing"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot withdraw required consent: {consent_type}"
        )
    
    # Withdraw consent
    from app.utils.gdpr_utils import withdraw_consent
    patient.gdpr_consents[consent_type] = withdraw_consent(
        patient.gdpr_consents[consent_type], 
        reason
    )
    
    db.commit()
    
    # Audit log
    audit_log = GDPRAuditLog(
        clinic_id=current_user.clinic_id,
        user_id=current_user.id,
        patient_id=patient.id,
        action="consent_withdrawn",
        legal_basis="patient_rights",
        data_category="consent_management",
        details={
            "consent_type": consent_type,
            "reason": reason,
            "withdrawn_by": current_user.full_name
        }
    )
    db.add(audit_log)
    db.commit()
    
    return {
        "message": f"Consent '{consent_type}' withdrawn successfully",
        "consent_status": patient.gdpr_consents[consent_type]
    }