# app/schemas.py
from pydantic import BaseModel, Field, conint,  ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum

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

class ConsentStatusResponse(BaseModel):
    message: str
    consent_status: Dict[str, Any]

class ConsentHistoryItem(BaseModel):
    timestamp: str
    action: str
    details: Dict[str, Any]

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

class CurrentUserInfoResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    specialties: Optional[List[str]] = []
    clinic_id: str
    clinic_name: Optional[str] = None

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
    audio_transcript: Optional[str] = None
    audio_duration_seconds: Optional[int] = None

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

class ConsultationCountsResponse(BaseModel):
    active_consultations: int
    discharge_ready: int
    review_pending: int

class ConsultationTodayStatsResponse(BaseModel):
    patients_today: int

class ConsultationTodayQueueItem(BaseModel):
    id: str
    patient_name: str
    specialty: str
    consultation_date: datetime
    status: str

    class Config:
        from_attributes = True

class ConsultationTodayQueueResponse(BaseModel):
    remaining: List[ConsultationTodayQueueItem]
    completed: List[ConsultationTodayQueueItem]

class ConsultationAudioUploadResponse(BaseModel):
    message: str
    audio_file_path: str
    audio_duration_seconds: Optional[int]

class ConsultationAudioProcessResponse(BaseModel):
    message: str
    transcript: str
    extracted_data: Dict[str, Any]
    audio_deleted: bool

class ConsultationTranscriptResponse(BaseModel):
    consultation_id: str
    transcript: Optional[str]
    duration_seconds: Optional[int]

class ApiMessageResponse(BaseModel):
    message: str

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

#------------------------------
# GDPR logs
#-------------------------------
class GDPRAuditLogBase(BaseModel):
    action: str
    legal_basis: Optional[str] = None
    data_category: Optional[str] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class GDPRAuditLogCreate(GDPRAuditLogBase):
    clinic_id: str
    user_id: Optional[str] = None
    patient_id: Optional[str] = None

class GDPRAuditLogResponse(GDPRAuditLogBase):
    id: str
    clinic_id: str
    user_id: Optional[str] = None
    patient_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# ----------------------------
# Enums
# ----------------------------

class JobState(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    OCR_DONE = "ocr_done"
    OCR_FAILED = "ocr_failed"

class ValidationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# ----------------------------
# Upload (Public) Schemas
# ----------------------------

class UploadBase(BaseModel):
    """
    Fields describing the uploaded file and its association.
    job_state is not included here by default; it's part of response/update.
    """
    clinic_id: str
    filename: str
    file_path: str

    file_size: Optional[int] = None
    document_type: Optional[str] = None
    patient_id: Optional[str] = None

class UploadCreate(BaseModel):
    """
    Internal use: creation payload once the file is saved.
    Public API typically sends multipart/form-data; server will build this object.
    """
    clinic_id: str
    filename: str
    file_path: str
    file_size: Optional[int] = None
    document_type: Optional[str] = None
    patient_id: Optional[str] = None  # usually None in v1
    expires_at: Optional[datetime] = None  # server sets now + 30 days if omitted

class UploadUpdate(BaseModel):
    """
    Internal/system update for queue processing.
    """
    job_state: Optional[JobState] = None
    attempts: Optional[int] = None
    claimed_at: Optional[datetime] = None
    claimed_by: Optional[str] = None
    error_message: Optional[str] = None

    document_type: Optional[str] = None
    patient_id: Optional[str] = None


# ----------------------------
# Document (Internal Artifact) Schemas (reachable via Upload)
# ----------------------------

class UploadDocumentSummary(BaseModel):
    """
    Minimal document info for list/detail views.
    (Upload-centric: this is never created/updated directly by clients.)
    """
    id: str
    upload_id: str

    validation_status: ValidationStatus = ValidationStatus.PENDING
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class UploadDetailResponse(BaseModel):
    """
    Upload details + document summary.
    Recommended for: GET /uploads/{id}
    """
    id: str
    clinic_id: str
    filename: str
    file_path: str
    file_size: Optional[int] = None
    document_type: Optional[str] = None

    job_state: JobState
    attempts: int
    claimed_at: Optional[datetime] = None
    claimed_by: Optional[str] = None
    error_message: Optional[str] = None

    patient_id: Optional[str] = None
    uploaded_at: datetime
    expires_at: datetime

    preview_url: Optional[str] = None
    document: Optional[UploadDocumentSummary] = None

    model_config = ConfigDict(from_attributes=True)

class UploadOCRResponse(BaseModel):
    """
    Full OCR output payload.
    Recommended for: GET /uploads/{id}/ocr
    """
    upload_id: str
    document_id: str
    ocr_text: str
    # Optional metadata (keep non-PHI)
    ocr_metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

class PatientDocumentListItem(BaseModel):
    """Document list item for patient profile/history views."""
    id: str
    filename: str
    document_type: Optional[str] = None
    created_at: datetime
    text_snippet: str
    has_full_text: bool
    has_original_file: bool
    download_url: Optional[str] = None
    full_text_url: str

    model_config = ConfigDict(from_attributes=True)

class DocumentTextResponse(BaseModel):
    """Full extracted OCR text for a document."""
    id: str
    text: str

    model_config = ConfigDict(from_attributes=True)
    
# ----------------------------
# Public Workflow Actions (Doctor)
# ----------------------------

class UploadCompleteRequest(BaseModel):
    """
    One-button doctor action:
    - assigns patient
    - approves validation
    - optionally edits OCR text
    - optionally sets document_type
    Recommended for: POST /uploads/{id}/complete
    """
    patient_id: str = Field(..., min_length=1)
    document_type: Optional[str] = None
    edited_ocr_text: Optional[str] = None  # if doctor edited the OCR result

class UploadCompleteResponse(BaseModel):
    """
    Return updated card-friendly payload after completion.
    """
    upload: UploadDetailResponse

class UploadRejectResponse(BaseModel):
    """
    For: DELETE /uploads/{id} or POST /uploads/{id}/reject (immediate delete)
    """
    deleted: bool
    upload_id: str

class UploadBatchAssignRequest(BaseModel):
    """
    Assign a patient to multiple uploads at once.
    Recommended for: POST /uploads/batch/assign
    """
    upload_ids: List[str] = Field(..., min_length=1)
    patient_id: str = Field(..., min_length=1)

class UploadBatchTypeRequest(BaseModel):
    """
    Update document_type for multiple uploads at once.
    Recommended for: POST /uploads/batch/type
    """
    upload_ids: List[str] = Field(..., min_length=1)
    document_type: str = Field(..., min_length=1)

class UploadCardResponse(BaseModel):
    """UI-friendly upload card data."""
    id: str
    clinic_id: str
    filename: str
    file_size: Optional[int]
    document_type: Optional[str]
    job_state: JobState
    patient_id: Optional[str]
    patient_name: Optional[str] = None
    uploaded_at: datetime
    expires_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    preview_url: Optional[str]
    ocr_snippet: Optional[str]= Field(default=None, max_length=500)


    model_config = ConfigDict(from_attributes=True)

class UploadListResponse(BaseModel):
    """
    Standard list wrapper for tab content.
    """
    items: List[UploadCardResponse]
    total: int
    
# ----------------------------
# Queue/Worker (Internal)
# ----------------------------

class ClaimJobRequest(BaseModel):
    worker_id: str
    clinic_id: Optional[str] = None
    max_attempts: int = Field(default=3, ge=1, le=10)
    stale_timeout_seconds: int = Field(default=600, ge=60, le=86400)

class ClaimJobResponse(BaseModel):
    claimed: bool
    upload_id: Optional[str] = None
    message: Optional[str] = None

class JobStats(BaseModel):
    queued: int
    processing: int
    ocr_done: int
    ocr_failed: int
    total: int
    oldest_queued: Optional[datetime] = None

# ----------------------------
# Validators (optional, but helpful)
# ----------------------------

class TabName(str, Enum):
    UNPROCESSED = "unprocessed"
    PROCESSING = "processing"
    VALIDATION = "validation"
    COMPLETED = "completed"
    ERROR = "error"

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
