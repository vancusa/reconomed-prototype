# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.sqlite import JSON 
from app.database import Base
import uuid
from datetime import datetime

# ----------------------------
# Clinics
# ----------------------------
class Clinic(Base):
    __tablename__ = "clinics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    country = Column(String(10), default="RO")
    gdpr_templates = Column(JSON)
    retention_policies = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    max_uploads = Column(Integer, default=20)
    current_upload_count = Column(Integer, default=0)

    # Relationships
    users = relationship("User", back_populates="clinic")
    patients = relationship("Patient", back_populates="clinic")
    documents = relationship("Document", back_populates="clinic")
    consultations = relationship("Consultation", back_populates="clinic")
    gdpr_logs = relationship("GDPRAuditLog", back_populates="clinic")
    uploads = relationship("Upload", back_populates="clinic")

# ----------------------------
# Users
# ----------------------------
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    specialties = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    clinic = relationship("Clinic", back_populates="users")
    consultations = relationship("Consultation", back_populates="doctor")
    validated_documents = relationship("Document", back_populates="validator")
    gdpr_logs = relationship("GDPRAuditLog", back_populates="user")

# ----------------------------
# Patients
# ----------------------------
class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)

    family_name = Column(String(100), nullable=False)
    given_name = Column(String(100), nullable=False)
    birth_date = Column(String(10))
    cnp = Column(String(13))
    insurance_number = Column(String(20))
    insurance_house = Column(String(100))
    phone = Column(String(20))
    email = Column(String(255))
    address = Column(JSON)
    gdpr_consents = Column(MutableDict.as_mutable(JSON))
    consent_withdrawn_at = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    clinic = relationship("Clinic", back_populates="patients")
    documents = relationship("Document", back_populates="patient")
    consultations = relationship("Consultation", back_populates="patient")
    gdpr_logs = relationship("GDPRAuditLog", back_populates="patient")
    uploads = relationship("Upload", back_populates="patient")

# ----------------------------
# Consultations
# ----------------------------
class Consultation(Base):
    __tablename__ = "consultations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("users.id"), nullable=False)
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)

    consultation_type = Column(String(100), nullable=False)
    consultation_date = Column(DateTime, default=datetime.utcnow)
    structured_data = Column(JSON)
    audio_transcript = Column(Text)
    audio_file_path = Column(String(500))
    status = Column(String(20), default="draft")
    is_signed = Column(Boolean, default=False)
    signed_at = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="consultations")
    doctor = relationship("User", back_populates="consultations")
    clinic = relationship("Clinic", back_populates="consultations")

# ----------------------------
# Documents
# ----------------------------
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)

    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    document_type = Column(String(100))
    document_subtype = Column(String(100))
    ocr_text = Column(Text)
    ocr_confidence = Column(Integer, default=0)
    ocr_status = Column(String(20), default="pending")
    extracted_data = Column(JSON)
    validation_status = Column(String(20), default="pending")
    validated_by = Column(String, ForeignKey("users.id"))
    validated_at = Column(DateTime)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    patient = relationship("Patient", back_populates="documents")
    clinic = relationship("Clinic", back_populates="documents")
    validator = relationship("User", back_populates="validated_documents")

# ----------------------------
# GDPR Audit Logs
# ----------------------------
class GDPRAuditLog(Base):
    __tablename__ = "gdpr_audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clinic_id = Column(String, ForeignKey("clinics.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"))
    patient_id = Column(String, ForeignKey("patients.id"))

    action = Column(String(100), nullable=False)
    legal_basis = Column(String(100))
    data_category = Column(String(100))
    details = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    clinic = relationship("Clinic", back_populates="gdpr_logs")
    user = relationship("User", back_populates="gdpr_logs")
    patient = relationship("Patient", back_populates="gdpr_logs")

# ----------------------------
# Uploads
# ----------------------------
class Upload(Base):
    __tablename__ = "uploads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clinic_id = Column(String, ForeignKey("clinics.id"))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime)
    patient_id = Column(String, ForeignKey("patients.id"))
    document_type = Column(String)
    ocr_status = Column(String, default="pending")

    # Relationships
    clinic = relationship("Clinic", back_populates="uploads")
    patient = relationship("Patient", back_populates="uploads")
    