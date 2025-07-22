"""Document management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json
import os

from app.database import get_db
from app.models import Patient, Document, DocumentResponse
from app.services.ocr import extract_text_from_image, extract_text_confidence
from app.services.document import detect_document_type, extract_structured_data
from app.utils.file import validate_file_type, generate_unique_filename, save_uploaded_file

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)

@router.post("/upload")
def upload_document(
    patient_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and save a document for a patient (OCR processed separately)"""
    # Check if patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Validate file type
    if not validate_file_type(file.content_type):
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not supported. Allowed: JPG, PNG, PDF, TIFF")
    
    try:
        # Read file content
        content = file.file.read()
        
        # Generate unique filename and save file
        unique_filename = generate_unique_filename(file.filename)
        file_path = save_uploaded_file(content, unique_filename)
        
        # Get file size
        file_size = len(content)
        
        # Save to database (without OCR processing)
        document = Document(
            patient_id=patient_id,
            filename=unique_filename,
            document_type="pending_ocr",  # Will be updated after OCR
            ocr_text="",  # Empty until OCR is processed
            extracted_data=json.dumps({
                "original_filename": file.filename,
                "file_size": file_size,
                "upload_status": "completed",
                "ocr_status": "pending"
            }),
            is_validated=False
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        return {
            "message": "Document uploaded successfully",
            "document_id": document.id,
            "original_filename": file.filename,
            "saved_filename": unique_filename,
            "patient_name": patient.name,
            "file_size": file_size,
            "status": "uploaded",
            "ocr_status": "pending",
            "next_steps": f"Use POST /documents/{document.id}/process-ocr to extract text"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@router.post("/{document_id}/process-ocr")
def process_document_ocr(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Process OCR for an uploaded document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if file exists
    file_path = f"uploads/{document.filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document file not found on server")
    
    try:
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail=f"File too large for OCR: {file_size/1024/1024:.1f}MB. Maximum: 10MB")
        
        print(f"Processing OCR for document {document_id}, file size: {file_size/1024:.1f}KB")
        
        # Read the saved file
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        print(f"File read successfully, starting OCR...")
        
        # Process OCR with better error handling
        try:
            ocr_result = extract_text_confidence(file_content)
            ocr_text = ocr_result['full_text']
            print(f"OCR completed. Text length: {len(ocr_text)} characters")
            print(f"OCR confidence: {ocr_result['average_confidence']}")
            print(f"First 100 chars: {ocr_text[:100]}")
        except Exception as ocr_error:
            print(f"OCR failed: {str(ocr_error)}")
            # Fallback to simple OCR without preprocessing
            try:
                from app.services.ocr_service import extract_text_from_image
                ocr_text = extract_text_from_image(file_content)
                ocr_result = {
                    'full_text': ocr_text,
                    'words': [],
                    'average_confidence': 50  # Default confidence
                }
                print(f"Fallback OCR completed. Text length: {len(ocr_text)} characters")
            except Exception as fallback_error:
                print(f"Fallback OCR also failed: {str(fallback_error)}")
                raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(fallback_error)}")
        
        # Detect document type
        doc_type = detect_document_type(ocr_text)
        print(f"Document type detected: {doc_type}")
        
        # Extract structured data
        structured_data = extract_structured_data(ocr_text, doc_type)
        
        # Add OCR metadata
        structured_data['ocr_confidence'] = ocr_result['average_confidence']
        structured_data['ocr_word_count'] = len(ocr_result['words'])
        structured_data['ocr_status'] = 'completed'
        structured_data['ocr_timestamp'] = "2024-01-15T10:30:00"
        structured_data['file_size'] = file_size
        
        # Update document
        document.document_type = doc_type
        document.ocr_text = ocr_text
        document.extracted_data = json.dumps(structured_data)
        
        db.commit()
        db.refresh(document)
        
        return {
            "message": "OCR processing completed",
            "document_id": document_id,
            "document_type": doc_type,
            "ocr_text_preview": ocr_text[:300] + "..." if len(ocr_text) > 300 else ocr_text,
            "ocr_full_text": ocr_text,  # Include full text for debugging
            "ocr_confidence": ocr_result['average_confidence'],
            "word_count": len(ocr_result['words']),
            "file_size_kb": file_size / 1024,
            "structured_data": structured_data,
            "validation_required": True,
            "debug_info": {
                "text_length": len(ocr_text),
                "detected_type": doc_type,
                "confidence": ocr_result['average_confidence']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in OCR processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR processing error: {str(e)}")

@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get document details including OCR results"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Parse structured data
    try:
        structured_data = json.loads(document.extracted_data) if document.extracted_data else {}
    except:
        structured_data = {"error": "Could not parse structured data"}
    
    return {
        "id": document.id,
        "patient_id": document.patient_id,
        "filename": document.filename,
        "document_type": document.document_type,
        "ocr_text": document.ocr_text,
        "structured_data": structured_data,
        "is_validated": document.is_validated,
        "created_at": document.created_at,
        "ocr_status": structured_data.get('ocr_status', 'unknown')
    }

@router.get("/{document_id}/validation")
def get_document_for_validation(document_id: int, db: Session = Depends(get_db)):
    """Get document with validation-specific data (OCR confidence, word boundaries, etc.)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if OCR has been processed
    if document.document_type == "pending_ocr":
        raise HTTPException(status_code=400, detail="Document OCR not yet processed. Use POST /documents/{document_id}/process-ocr first.")
    
    # Parse structured data
    try:
        structured_data = json.loads(document.extracted_data) if document.extracted_data else {}
    except:
        structured_data = {}
    
    # Create validation form based on document type
    validation_fields = create_validation_fields(document.document_type, structured_data)
    
    return {
        "document": {
            "id": document.id,
            "filename": document.filename,
            "document_type": document.document_type,
            "ocr_text": document.ocr_text,
            "is_validated": document.is_validated
        },
        "validation_fields": validation_fields,
        "ocr_confidence": structured_data.get('ocr_confidence', 0),
        "suggestions": get_validation_suggestions(document.document_type, structured_data)
    }

def create_validation_fields(doc_type: str, structured_data: dict) -> List[Dict]:
    """Create validation form fields based on document type"""
    if doc_type == "lab_result":
        return [
            {
                "field": "patient_name",
                "label": "Patient Name / Numele Pacientului",
                "type": "text",
                "value": structured_data.get("patient_name", ""),
                "required": True
            },
            {
                "field": "test_date",
                "label": "Test Date / Data Testului",
                "type": "date",
                "value": structured_data.get("test_date", ""),
                "required": True
            },
            {
                "field": "lab_id",
                "label": "Lab ID / ID Laborator",
                "type": "text",
                "value": structured_data.get("lab_id", ""),
                "required": False
            },
            {
                "field": "results",
                "label": "Test Results / Rezultate",
                "type": "object",
                "value": structured_data.get("results", {}),
                "required": True
            }
        ]
    elif doc_type in ["xray", "ct_scan", "mri", "ultrasound"]:
        return [
            {
                "field": "patient_name",
                "label": "Patient Name / Numele Pacientului",
                "type": "text",
                "value": structured_data.get("patient_name", ""),
                "required": True
            },
            {
                "field": "study_date",
                "label": "Study Date / Data Studiului",
                "type": "date",
                "value": structured_data.get("study_date", ""),
                "required": True
            },
            {
                "field": "findings",
                "label": "Findings / Concluzii",
                "type": "textarea",
                "value": structured_data.get("findings", ""),
                "required": True
            },
            {
                "field": "radiologist",
                "label": "Radiologist / Radiolog",
                "type": "text",
                "value": structured_data.get("radiologist", ""),
                "required": False
            }
        ]
    else:
        # Generic fields for other document types
        return [
            {
                "field": "patient_name",
                "label": "Patient Name / Numele Pacientului",
                "type": "text",
                "value": structured_data.get("patient_name", ""),
                "required": True
            },
            {
                "field": "date",
                "label": "Date / Data",
                "type": "date",
                "value": structured_data.get("date", ""),
                "required": True
            }
        ]

def get_validation_suggestions(doc_type: str, structured_data: dict) -> List[str]:
    """Get validation suggestions based on OCR confidence and document type"""
    suggestions = []
    
    confidence = structured_data.get('ocr_confidence', 0)
    
    if confidence < 50:
        suggestions.append("Low OCR confidence - please verify all fields carefully")
    elif confidence < 70:
        suggestions.append("Medium OCR confidence - double-check key fields")
    
    if doc_type == "lab_result":
        if not structured_data.get("results"):
            suggestions.append("No lab results detected - please add manually")
        if not structured_data.get("test_date"):
            suggestions.append("Test date missing - please verify")
    
    return suggestions

@router.post("/{document_id}/validate")
def validate_document(
    document_id: int,
    validated_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Validate and save corrected document data"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Parse existing structured data
        existing_data = json.loads(document.extracted_data) if document.extracted_data else {}
        
        # Update with validated data
        existing_data.update(validated_data)
        existing_data['validation_timestamp'] = "2024-01-15T10:30:00"  # In real app, use datetime.now()
        existing_data['validation_status'] = 'validated'
        
        # Save updated data
        document.extracted_data = json.dumps(existing_data)
        document.is_validated = True
        db.commit()
        
        return {
            "message": "Document validated successfully",
            "document_id": document_id,
            "validated_data": existing_data,
            "is_validated": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")

@router.get("/patient/{patient_id}", response_model=List[DocumentResponse])
def get_patient_documents(patient_id: int, db: Session = Depends(get_db)):
    """Get all documents for a patient"""
    documents = db.query(Document).filter(Document.patient_id == patient_id).all()
    return documents

@router.get("/pending-ocr")
def get_pending_ocr_documents(db: Session = Depends(get_db)):
    """Get all documents that need OCR processing"""
    pending_docs = db.query(Document).filter(Document.document_type == "pending_ocr").all()
    
    return {
        "pending_count": len(pending_docs),
        "documents": [
            {
                "id": doc.id,
                "patient_id": doc.patient_id,
                "filename": doc.filename,
                "created_at": doc.created_at
            }
            for doc in pending_docs
        ]
    }

@router.get("/validation/pending")
def get_pending_validations(db: Session = Depends(get_db)):
    """Get all documents that need validation"""
    pending_docs = db.query(Document).filter(
        Document.is_validated == False,
        Document.document_type != "pending_ocr"
    ).all()
    
    return {
        "pending_count": len(pending_docs),
        "documents": [
            {
                "id": doc.id,
                "patient_id": doc.patient_id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "created_at": doc.created_at
            }
            for doc in pending_docs
        ]
    }