from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
from datetime import datetime
import uuid
from PIL import Image
import io

from app.database import get_db, create_tables
from app.models import Patient, Document, PatientCreate, PatientResponse, DocumentCreate, DocumentResponse

# Create FastAPI app
app = FastAPI(
    title="ReconoMed API",
    description="Healthcare Document Processing Platform",
    version="0.1.0"
)

# Create upload directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables on startup
@app.on_event("startup")
def startup_event():
    create_tables()

# Simple OCR function (we'll enhance this later)
def extract_text_from_image(image_file):
    """Extract text from image using OCR (mock function for now)"""
    try:
        # For now, return mock OCR text - we'll implement real OCR later
        # This simulates what Tesseract would return
        mock_ocr_text = f"""
        MEDICAL LABORATORY REPORT
        Patient: John Doe
        Date: 2024-01-15
        Lab ID: LAB001
        
        Blood Test Results:
        - Hemoglobin: 14.2 g/dL (Normal: 12-16)
        - White Blood Cells: 7,500 /μL (Normal: 4,000-11,000)
        - Platelets: 250,000 /μL (Normal: 150,000-400,000)
        
        Doctor: Dr. Smith
        """
        return mock_ocr_text.strip()
    except Exception as e:
        return f"OCR Error: {str(e)}"

def detect_document_type(text):
    """Detect document type based on OCR text"""
    text_lower = text.lower()
    if "lab" in text_lower or "blood" in text_lower or "test results" in text_lower:
        return "lab_result"
    elif "ecg" in text_lower or "electrocardiogram" in text_lower:
        return "ecg"
    elif "discharge" in text_lower:
        return "discharge_note"
    elif "prescription" in text_lower:
        return "prescription"
    else:
        return "general"

def extract_structured_data(text, doc_type):
    """Extract structured data based on document type"""
    # Mock structured data extraction - we'll enhance this with LLM later
    if doc_type == "lab_result":
        return {
            "patient_name": "John Doe",
            "test_date": "2024-01-15",
            "lab_id": "LAB001",
            "results": {
                "hemoglobin": "14.2 g/dL",
                "wbc": "7,500 /μL",
                "platelets": "250,000 /μL"
            }
        }
    return {"type": doc_type, "status": "processed"}

# Health check endpoint
@app.get("/")
def read_root():
    return {
        "message": "ReconoMed API is running!",
        "version": "0.1.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ReconoMed API"}

# Patient endpoints
@app.post("/patients", response_model=PatientResponse)
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    """Create a new patient"""
    db_patient = Patient(**patient.dict())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient

@app.get("/patients", response_model=List[PatientResponse])
def get_patients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all patients"""
    patients = db.query(Patient).offset(skip).limit(limit).all()
    return patients

@app.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    """Get a specific patient"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

@app.put("/patients/{patient_id}", response_model=PatientResponse)
def update_patient(patient_id: int, patient: PatientCreate, db: Session = Depends(get_db)):
    """Update a patient"""
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    for key, value in patient.dict().items():
        setattr(db_patient, key, value)
    
    db.commit()
    db.refresh(db_patient)
    return db_patient

@app.delete("/patients/{patient_id}")
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    """Delete a patient"""
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    db.delete(db_patient)
    db.commit()
    return {"message": "Patient deleted successfully"}

# Document upload endpoint (enhanced with OCR)
@app.post("/documents/upload")
def upload_document(
    patient_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process a document for a patient"""
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/jpg", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="File type not supported")
    
    try:
        # Generate unique filename
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = f"uploads/{unique_filename}"
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)
        
        # Process image and extract text
        ocr_text = extract_text_from_image(content)
        doc_type = detect_document_type(ocr_text)
        structured_data = extract_structured_data(ocr_text, doc_type)
        
        # Save to database
        document = Document(
            patient_id=patient_id,
            filename=unique_filename,
            document_type=doc_type,
            ocr_text=ocr_text,
            extracted_data=str(structured_data),  # Convert dict to string for now
            is_validated=False
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        return {
            "message": "Document processed successfully",
            "document_id": document.id,
            "filename": file.filename,
            "patient": patient.name,
            "document_type": doc_type,
            "ocr_preview": ocr_text[:200] + "..." if len(ocr_text) > 200 else ocr_text,
            "structured_data": structured_data,
            "validation_required": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

# Get document with OCR results
@app.get("/documents/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get document details including OCR results"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": document.id,
        "patient_id": document.patient_id,
        "filename": document.filename,
        "document_type": document.document_type,
        "ocr_text": document.ocr_text,
        "extracted_data": document.extracted_data,
        "is_validated": document.is_validated,
        "created_at": document.created_at
    }

# Validate document endpoint
@app.post("/documents/{document_id}/validate")
def validate_document(
    document_id: int,
    corrections: dict = None,
    db: Session = Depends(get_db)
):
    """Validate and optionally correct document data"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Apply corrections if provided
    if corrections:
        document.extracted_data = str(corrections)
    
    # Mark as validated
    document.is_validated = True
    db.commit()
    
    return {
        "message": "Document validated successfully",
        "document_id": document_id,
        "is_validated": True
    }

@app.get("/patients/{patient_id}/documents", response_model=List[DocumentResponse])
def get_patient_documents(patient_id: int, db: Session = Depends(get_db)):
    """Get all documents for a patient"""
    documents = db.query(Document).filter(Document.patient_id == patient_id).all()
    return documents

# Search patients and documents
@app.get("/search")
def search(
    q: str = None,
    patient_name: str = None,
    document_type: str = None,
    db: Session = Depends(get_db)
):
    """Search patients and documents"""
    results = {"patients": [], "documents": []}
    
    if q or patient_name:
        # Search patients
        patient_query = db.query(Patient)
        if patient_name:
            patient_query = patient_query.filter(Patient.name.ilike(f"%{patient_name}%"))
        if q:
            patient_query = patient_query.filter(Patient.name.ilike(f"%{q}%"))
        results["patients"] = patient_query.limit(10).all()
    
    if q or document_type:
        # Search documents
        doc_query = db.query(Document)
        if document_type:
            doc_query = doc_query.filter(Document.document_type == document_type)
        if q:
            doc_query = doc_query.filter(Document.ocr_text.ilike(f"%{q}%"))
        results["documents"] = doc_query.limit(10).all()
    
    return results

# Test database connection
@app.get("/test-db")
def test_database(db: Session = Depends(get_db)):
    """Test database connection"""
    try:
        from sqlalchemy import text
        # Simple query to test connection
        result = db.execute(text("SELECT 1 as test")).fetchone()
        return {"database": "connected", "test_query": result[0]}
    except Exception as e:
        return {"database": "error", "message": str(e)}