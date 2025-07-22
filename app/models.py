from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

# SQLAlchemy Models (Database Tables)
class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    birth_date = Column(String(10))  # YYYY-MM-DD format
    phone = Column(String(20))
    email = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship to documents
    documents = relationship("Document", back_populates="patient")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(100))  # lab_result, ecg, discharge_note, etc.
    ocr_text = Column(Text)
    extracted_data = Column(Text)  # JSON string of extracted fields
    is_validated = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship to patient
    patient = relationship("Patient", back_populates="documents")

# Pydantic Models (API Request/Response)
class PatientBase(BaseModel):
    name: str
    birth_date: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    document_type: Optional[str] = None
    ocr_text: Optional[str] = None
    extracted_data: Optional[str] = None

class DocumentCreate(DocumentBase):
    patient_id: int
    filename: str

class DocumentResponse(DocumentBase):
    id: int
    patient_id: int
    filename: str
    is_validated: bool
    created_at: datetime
    
    class Config:
        from_attributes = True