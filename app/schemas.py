# app/schemas.py
from pydantic import BaseModel, Field, conint
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

class ConsultationStart(BaseModel):
    """Schema for starting a new consultation (creates draft)"""
    patient_id: str
    specialty: str  # internal_medicine, cardiology, respiratory, gynecology
    
class ConsultationAutoSave(BaseModel):
    """Schema for auto-saving consultation data"""
    structured_data: Optional[dict] = None
    audio_file_path: Optional[str] = None
    audio_duration_seconds: Optional[int] = None
    
class ConsultationCreate(BaseModel):
    """Full consultation creation (for backward compatibility)"""
    patient_id: str
    specialty: str
    consultation_date: Optional[datetime] = None
    structured_data: Optional[dict] = None
    audio_file_path: Optional[str] = None

class ConsultationUpdate(BaseModel):
    """Update existing consultation"""
    specialty: Optional[str] = None
    consultation_date: Optional[datetime] = None
    structured_data: Optional[dict] = None
    audio_transcript: Optional[str] = None
    audio_duration_seconds: Optional[int] = None
    status: Optional[str] = None  # draft, in_progress, completed, discharged, cancelled
    is_signed: Optional[bool] = None

class ConsultationResponse(BaseModel):
    """Full consultation response"""
    id: str
    patient_id: str
    doctor_id: str
    clinic_id: str
    specialty: str
    consultation_date: datetime
    structured_data: Optional[dict]
    audio_transcript: Optional[str]
    audio_file_path: Optional[str]
    audio_duration_seconds: Optional[int]
    status: str
    is_signed: bool
    signed_at: Optional[datetime]
    last_autosave_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ConsultationListItem(BaseModel):
    """Lightweight consultation for lists"""
    id: str
    patient_id: str
    specialty: str
    consultation_date: datetime
    status: str
    is_signed: bool
    last_autosave_at: Optional[datetime]
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

# ----------------------------
# Clinic Schemas
# ----------------------------

class ClinicBase(BaseModel):
    """
    Base schema for clinic attributes that can be created or updated.
    """
    name: str = Field(..., max_length=255, description="The official name of the clinic.")
    country: str = Field("RO", max_length=10, description="The two-letter country code.")
    
    # GDPR templates and retention policies are JSON fields
    gdpr_templates: Optional[Dict[str, Any]] = Field(None, description="Custom GDPR consent templates (JSON data).")
    retention_policies: Optional[Dict[str, Any]] = Field(None, description="Document retention policies (JSON data).")
    
    # max_uploads can be set during creation/update
    # conint is used for constrained integers (must be >= 0)
    max_uploads: conint(ge=0) = Field(20, description="Maximum number of active documents allowed for the clinic.")

class ClinicCreate(ClinicBase):
    """
    Schema for creating a new Clinic. Inherits all fields from ClinicBase.
    """
    # No additional fields needed for simple creation over the base fields
    pass

class ClinicResponse(ClinicBase):
    """
    Schema for returning Clinic data from the API.
    Includes all DB-generated fields and relationship counts/summaries.
    """
    id: str = Field(..., description="Unique identifier for the clinic (UUID).")
    created_at: datetime = Field(..., description="Timestamp of when the clinic was created.")
    
    # Fields that track current status (managed by the application logic)
    current_upload_count: int = Field(0, description="Current number of active uploads/documents.")
    user_count: int = Field(0, description="Number of users in this clinic")
    patient_count: int = Field(0, description="Number of patients in this clinic")

    # You typically don't return the full related objects (users, patients, etc.) 
    # in the main response to prevent huge payloads, but you can include their counts.
    # If you *did* want to include them, you'd need forward references or separate schema imports.
    # For a lean schema, we'll just enable ORM mode (or from_attributes)
    
    # Pydantic Configuration for mapping to SQLAlchemy model
    class Config:
        # For Pydantic v1
        #orm_mode = True
        #For Pydantic v2
        from_attributes = True