"""Document management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import json
import os
import uuid
from datetime import datetime

from app.database import get_db
from app.models import Patient, Document, DocumentResponse, User, GDPRAuditLog 
from app.services.document import EnhancedDocumentService
from app.services.romanian_document_templates import RomanianDocumentTemplates
from app.services.ocr import extract_text_from_image, extract_text_confidence
from app.utils.file import validate_file_type, generate_unique_filename, save_uploaded_file
#from app.services.document import detect_document_type, extract_structured_data
from app.services.enhanced_ocr import RomanianOCRProcessor

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)

@router.post("/upload")
async def upload_document(
    patient_id: Optional[str] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    print(f"DEBUG STEP 1: File received - name: {file.filename}, type: {file.content_type}")
    
    # Debug file size before reading
    print(f"DEBUG STEP 2: About to read file content")
    content = await file.read() #THIS is the only reading of the stream, any more and we empty the stream!!!!
    print(f"DEBUG STEP 3: Read {len(content)} bytes from upload")

    # Debug first few bytes to ensure it's real image data
    if len(content) > 0:
        print(f"DEBUG STEP 4: First 20 bytes: {content[:20]}")
    else:
        print(f"DEBUG STEP 4: Content is empty!")
        return {"error": "File content is empty"}
    
    print(f"DEBUG: Upload started for patient_id: {patient_id}")
    print(f"DEBUG: File info: {file.filename}, {file.content_type}")
    
    try:
        # Check if patient exists
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        print(f"DEBUG: Patient found: {patient is not None}")
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Get demo user
        current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
        print(f"DEBUG: User found: {current_user is not None}")
        if not current_user:
            raise HTTPException(status_code=500, detail="Demo user not found")
        
        # File validation
        print(f"DEBUG: Starting file validation")
        if not validate_file_type(file.content_type):
            print(f"DEBUG: File type validation failed")
            raise HTTPException(status_code=400, detail=f"File type {file.content_type} not supported")
        
        print(f"DEBUG: Generating unique filename")
        unique_filename = generate_unique_filename(file.filename)
        print(f"DEBUG: Generated filename: {unique_filename}")
        
        print(f"DEBUG: Saving file")
        file_path = save_uploaded_file(content, unique_filename)
        print(f"DEBUG: File saved to: {file_path}")
        
        # TEMP demo user lookup
        current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
        if not current_user:
            raise HTTPException(status_code=500, detail="Demo user not found")

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
            
            # Generate unique filename and save file
            unique_filename = generate_unique_filename(file.filename)
            file_path = save_uploaded_file(content, unique_filename)
            
            # Get file size
            file_size = len(content)
            
            # Save to database (without OCR processing)
            document = Document(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                clinic_id=current_user.clinic_id,
                filename=unique_filename,
                original_filename=file.filename,
                file_path=file_path,
                file_size=len(content),
                document_type="pending_ocr",
                ocr_text="",
                ocr_confidence=0,
                ocr_status="pending",
                extracted_data=json.dumps({
                    "original_filename": file.filename,
                    "file_size": len(content),
                    "upload_status": "completed",
                    "ocr_status": "pending"
                }),
                validation_status="pending"  # Use validation_status instead of is_validated
            )
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            return {
                "message": "Document uploaded successfully",
                "document_id": document.id,
                "original_filename": file.filename,
                "saved_filename": unique_filename,
                "patient_given_name": patient.given_name,
                "patient_family_name":patient.family_name,
                "file_size": file_size,
                "status": "uploaded",
                "ocr_status": "pending",
                "next_steps": f"Use POST /documents/{document.id}/process-ocr to extract text"
            }
        
        except HTTPException as he:
            print(f"DEBUG: HTTP Exception: {he.detail}")
            raise
    except Exception as e:
        print(f"DEBUG: Unexpected exception type: {type(e)}")
        print(f"DEBUG: Exception args: {e.args}")
        print(f"DEBUG: Exception str: {str(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")

@router.post("/{document_id}/process-ocr")
async def process_document_ocr(
    document_id: str,
    hint_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Process OCR with enhanced Romanian template recognition"""
    
    # Step 1: Validate document and user
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")
    
    if document.clinic_id != current_user.clinic_id:
        raise HTTPException(status_code=403, detail="Access denied to this document")
    
    # Step 2: Check file exists
    file_path = f"uploads/{document.filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document file not found")
    
    try:
        print(f"TRACE 1: Processing OCR for document {document_id}")
        
        # Step 3: Read file
        with open(file_path, 'rb') as f:
            file_content = f.read()
        print(f"TRACE 2: Read {len(file_content)} bytes")
        
        # Step 4: Process with enhanced service
        enhanced_service = EnhancedDocumentService()
        print(f"TRACE 3: Created EnhancedDocumentService")
        print(f"TRACE 3.1: EnhancedDocumentService methods: {[method for method in dir(enhanced_service) if not method.startswith('_')]}")
        print(f"TRACE 3.2: OCR processor type: {type(enhanced_service.ocr_processor)}")
        print(f"TRACE 3.3: OCR processor methods: {[method for method in dir(enhanced_service.ocr_processor) if not method.startswith('_')]}")        
        print(f"TRACE 3.4: All OCR processor attributes: {dir(enhanced_service.ocr_processor)}")

        #TEMPORARY - to be removed once the testing ends
        hint_type="romanian_id"

        processing_result = enhanced_service.process_document_with_templates(
            file_content, hint_type
        )
        
        print(f"TRACE 4: Processing result success: {processing_result.get('success')}")
        
        if not processing_result["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"OCR failed: {processing_result.get('error', 'Unknown error')}"
            )
        
        # Step 5: Update database
        document.document_type = processing_result["document_type"]
        document.ocr_text = processing_result["ocr_text"]
        document.ocr_confidence = processing_result["confidence_score"]
        document.ocr_status = "completed"
        document.extracted_data = json.dumps(processing_result["structured_data"])
        db.commit()
        
        print(f"TRACE 5: Database updated successfully")
        
        return {
            "message": "OCR processing completed",
            "document_type": processing_result["document_type"],
            "confidence_score": processing_result["confidence_score"],
            "template_matched": processing_result.get("template_match", {}).get("matched", False)
        }
        
    except Exception as e:
        print(f"TRACE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

# Endpoint to get available document types
@router.get("/document-types")
async def get_supported_document_types():
    """Get list of supported Romanian document types"""
    templates = RomanianDocumentTemplates.get_all_templates()
    
    return {
        "supported_types": [
            {
                "template_id": t.template_id,
                "document_type": t.document_type,
                "language": t.language,
                "confidence_threshold": t.confidence_threshold,
                "description": {
                    "romanian_id": "Carte de identitate românească",
                    "lab_result": "Rezultate analize medicale", 
                    "prescription": "Rețetă medicală"
                }.get(t.document_type, t.document_type)
            }
            for t in templates
        ],
        "usage_note": "Provide hint_type parameter to OCR endpoint for better accuracy"
    }

@router.get("/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)):
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
def get_document_for_validation(document_id: str, db: Session = Depends(get_db)):
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
    document_id: str,
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
def get_patient_documents(patient_id: str, db: Session = Depends(get_db)):
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