# app/models.py - Complete Premium MVP Schema
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
import uuid

# Core User Management
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # doctor, helper, admin, billing
    specialties = Column(JSON)  # Array of medical specialties
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    clinic = relationship("Clinic", back_populates="users")
    consultations = relationship("Consultation", back_populates="doctor")

class Clinic(Base):
    __tablename__ = "clinics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    country = Column(String(10), default='RO')
    gdpr_templates = Column(JSON)  # GDPR consent templates
    retention_policies = Column(JSON)  # Data retention rules
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    users = relationship("User", back_populates="clinic")
    patients = relationship("Patient", back_populates="clinic")

# Enhanced Patient Model
class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)
    
    # Core identity
    family_name = Column(String(100), nullable=False)
    given_name = Column(String(100), nullable=False)
    birth_date = Column(String(10))  # YYYY-MM-DD
    
    # Romanian specific fields
    cnp = Column(String(13))  # Cod Numeric Personal
    insurance_number = Column(String(20))
    insurance_house = Column(String(100))
    
    # Contact
    phone = Column(String(20))
    email = Column(String(255))
    address = Column(JSON)  # Structured Romanian address
    
    # GDPR compliance
    gdpr_consents = Column(JSON)  # Active consents
    consent_withdrawn_at = Column(DateTime)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    clinic = relationship("Clinic", back_populates="patients")
    documents = relationship("Document", back_populates="patient")
    consultations = relationship("Consultation", back_populates="patient")

# Consultation Model with openEHR structure
class Consultation(Base):
    __tablename__ = "consultations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("users.id"), nullable=False)
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)
    
    consultation_type = Column(String(100), nullable=False)  # internal_medicine, cardiology, etc.
    
    # Structured consultation data (openEHR-like)
    structured_data = Column(JSON)  # Specialty-specific consultation fields
    audio_transcript = Column(Text)  # Transcribed audio
    audio_file_path = Column(String(500))
    
    # Status
    status = Column(String(20), default='draft')  # draft, completed, signed
    is_signed = Column(Boolean, default=False)
    signed_at = Column(DateTime)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    patient = relationship("Patient", back_populates="consultations")
    doctor = relationship("User", back_populates="consultations")

# Enhanced Document Model
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)
    
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    
    # Document classification
    document_type = Column(String(100))  # romanian_id, lab_result, xray, etc.
    document_subtype = Column(String(100))  # More specific classification
    
    # OCR processing
    ocr_text = Column(Text)
    ocr_confidence = Column(Integer, default=0)
    ocr_status = Column(String(20), default='pending')  # pending, processing, completed, failed
    
    # Extracted structured data
    extracted_data = Column(JSON)  # Template-based extracted fields
    validation_status = Column(String(20), default='pending')  # pending, validated, rejected
    validated_by = Column(String, ForeignKey("users.id"))
    validated_at = Column(DateTime)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    patient = relationship("Patient", back_populates="documents")

# GDPR Audit Trail
class GDPRAuditLog(Base):
    __tablename__ = "gdpr_audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"))
    patient_id = Column(String, ForeignKey("patients.id"))
    
    action = Column(String(100), nullable=False)  # access, modify, export, delete
    legal_basis = Column(String(100))  # consent, treatment, legal_obligation
    data_category = Column(String(100))  # personal, medical, financial
    
    details = Column(JSON)  # Additional context
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Pydantic Models for API requests/responses
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
    extracted_data: Optional[Union[dict, str]] = None  # Accept both dict and string
    
    class Config:
        from_attributes = True