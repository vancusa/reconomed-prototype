# app/schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

# ----------------------------
# Patient Schemas
# ----------------------------
class PatientBase(BaseModel):
    family_name: str
    given_name: str
    birth_date: Optional[str] = None
    cnp: Optional[str] = None
    insurance_number: Optional[str] = None
    insurance_house: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[dict] = None

class PatientCreate(PatientBase):
    gdpr_consents: Optional[dict] = None

class PatientResponse(PatientBase):
    id: str
    clinic_id: str
    gdpr_consents: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PatientUpdate(PatientBase):
    gdpr_consents: Optional[dict] = None

class PaginatedPatientsResponse(BaseModel):
    patients: List[PatientResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

# ----------------------------
# User Schemas
# ----------------------------
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str
    clinic_id: str
    specialties: Optional[List[str]] = []

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    clinic_id: str
    specialties: Optional[List[str]] = []
    
    class Config:
        from_attributes = True

# ----------------------------
# Consultation Schemas
# ----------------------------
class ConsultationBase(BaseModel):
    patient_id: str
    consultation_type: str
    structured_data: Optional[dict] = None
    audio_transcript: Optional[str] = None

class ConsultationCreate(ConsultationBase):
    pass

class ConsultationResponse(ConsultationBase):
    id: str
    doctor_id: str
    clinic_id: str
    status: str
    is_signed: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------------------
# Document Schemas
# ----------------------------
class DocumentBase(BaseModel):
    filename: str
    document_type: Optional[str] = None
    document_subtype: Optional[str] = None
    ocr_text: Optional[str] = None
    extracted_data: Optional[dict] = None

class DocumentCreate(DocumentBase):
    patient_id: str
    clinic_id: str
    file_path: str
    file_size: Optional[int] = None

class DocumentResponse(DocumentBase):
    id: str
    patient_id: str
    clinic_id: str
    original_filename: str
    file_path: str
    file_size: Optional[int] = None
    ocr_confidence: int
    ocr_status: str
    validation_status: str
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None
    created_at: datetime
    extracted_data: Optional[Union[dict, str]] = None

    class Config:
        from_attributes = True

# ----------------------------
# Upload Schemas
# ----------------------------
class UploadBase(BaseModel):
    filename: str
    file_path: str
    file_size: Optional[int] = None
    document_type: Optional[str] = None
    ocr_status: Optional[str] = "pending"

class UploadCreate(UploadBase):
    clinic_id: str
    patient_id: Optional[str] = None

class UploadResponse(UploadBase):
    id: str
    clinic_id: str
    patient_id: Optional[str] = None
    uploaded_at: datetime
    expires_at: Optional[datetime] = None
    original_filename: Optional[str] = None

    class Config:
        from_attributes = True
