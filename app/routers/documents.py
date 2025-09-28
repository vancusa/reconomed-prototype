"""Document management endpoints"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import json
import os
import uuid
import logging
from datetime import datetime

from app.database import get_db
from app.schemas import UploadCreate, UploadResponse, PatientResponse, UserResponse
from app.models import Patient, Document, User, Upload
from app.services.document import EnhancedDocumentService
from app.services.romanian_document_templates import RomanianDocumentTemplates
from app.services.ocr import extract_text_from_image, extract_text_confidence
from app.services.enhanced_ocr import RomanianOCRProcessor
from app.utils.file import validate_file_type, generate_unique_filename, save_uploaded_file

router = APIRouter(
    #prefix="/documents",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)

# Reuse the loggers created in app.main
audit_logger = logging.getLogger("reconomed.audit")
app_logger=logging.getLogger("reconomed.app")

#--------------------------------------ROUTERS --------------------------------------

#------------------------------Core Upload Workflow Routes --------------------------------
# ------------------------------------
# Upload endpoint (Batch Upload)
# ------------------------------------
@router.post("/uploads", response_model=List[UploadResponse])
async def upload_file(
    request: Request,
    files: List[UploadFile] = File(...),
    patient_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug(f"Received {len(files)} files for upload (patient_id={patient_id})")
    audit_logger.info(f"user={user} action=batch_upload count={len(files)}")

    # Demo user lookup
    current_user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    if not current_user:
        raise HTTPException(status_code=500, detail="Demo user not found")

    uploaded_files: List[Upload] = []

    for file in files:
        try:
            content = await file.read()
            if not content:
                app_logger.warning(f"File {file.filename} is empty, skipping.")
                continue

            if not validate_file_type(file.content_type):
                raise HTTPException(
                    status_code=400,
                    detail=f"File type {file.content_type} not supported"
                )

            unique_filename = generate_unique_filename(file.filename)
            file_path = save_uploaded_file(content, unique_filename)
            file_size = len(content)
            app_logger.debug(f"File {file.filename} saved as {unique_filename} ({file_size} bytes)")

            # Save metadata to DB (Upload model, no OCR yet)
            upload = Upload(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                clinic_id=current_user.clinic_id,
                filename=unique_filename,
                file_path=file_path,
                file_size=file_size,
                document_type="pending_ocr",
                ocr_status="pending"
            )
            db.add(upload)
            db.commit()
            db.refresh(upload)

            audit_logger.info(f"user={user} action=upload_success upload_id={upload.id} patient_id={patient_id}")
            uploaded_files.append(upload)

        except HTTPException:
            raise
        except Exception as e:
            app_logger.error(f"Unexpected error while uploading {file.filename}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    return uploaded_files

# ------------------------------------
# Get Unprocessed Uploads
# ------------------------------------
@router.get("/uploads/unprocessed", response_model=List[UploadResponse])
async def get_unprocessed_uploads(
    request: Request,
    patient_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug(f"Fetching unprocessed uploads (patient_id={patient_id})")
    audit_logger.info(f"user={user} action=list_unprocessed patient_id={patient_id}")

    try:
        query = db.query(Upload).filter(Upload.ocr_status == "pending")

        if patient_id:
            query = query.filter(Upload.patient_id == patient_id)

        uploads = query.all()
        app_logger.info(f"Found {len(uploads)} unprocessed uploads")

        return uploads

    except Exception as e:
        app_logger.error(f"Error fetching unprocessed uploads: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch unprocessed uploads")

# ------------------------------------------------------
# Assign patient to upload
# ------------------------------------------------------
@router.put("/uploads/{upload_id}/patient", response_model=UploadResponse)
async def assign_patient(
    upload_id: str,
    patient_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug(f"Assigning patient {patient_id} to upload {upload_id}")
    audit_logger.info(f"user={user} action=assign_patient upload_id={upload_id} patient_id={patient_id}")

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload.patient_id = patient_id
    db.commit()
    db.refresh(upload)
    return upload


# ------------------------------------------------------
# Set document type for an upload
# ------------------------------------------------------
@router.put("/uploads/{upload_id}/type", response_model=UploadResponse)
async def set_document_type(
    upload_id: str,
    document_type: str,
    request: Request,
    db: Session = Depends(get_db)
):
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug(f"Setting document type for upload {upload_id} -> {document_type}")
    audit_logger.info(f"user={user} action=set_document_type upload_id={upload_id} type={document_type}")

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload.document_type = document_type
    db.commit()
    db.refresh(upload)
    return upload


# ------------------------------------------------------
# Start OCR processing (batch queue)
# ------------------------------------------------------
@router.post("/uploads/batch-ocr")
async def start_batch_processing(
    request: Request,
    db: Session = Depends(get_db),
    patient_id: Optional[str] = None
):
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug(f"Starting OCR batch processing (patient_id={patient_id})")
    audit_logger.info(f"user={user} action=batch_ocr patient_id={patient_id}")

    query = db.query(Upload).filter(Upload.ocr_status == "pending")
    if patient_id:
        query = query.filter(Upload.patient_id == patient_id)

    uploads = query.all()
    for upl in uploads:
        upl.ocr_status = "queued"
        upl.expires_at = upl.expires_at or datetime.utcnow()
    db.commit()

    return {
        "message": "OCR batch processing started",
        "queued_count": len(uploads),
        "upload_ids": [upl.id for upl in uploads]
    }

#----------------------------Processing Queue Routes -----------------------------------------

# ------------------------------------------------------
# Get processing queue
# ------------------------------------------------------
@router.get("/processing-queue", response_model=List[UploadResponse])
async def get_processing_queue(
    request: Request,
    db: Session = Depends(get_db)
):
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug("Fetching OCR processing queue")
    audit_logger.info(f"user={user} action=get_processing_queue")

    uploads = db.query(Upload).filter(Upload.ocr_status.in_(["queued", "processing"])).all()
    return uploads

# ------------------------------------------------------
# Get Individual Processing Status
# ------------------------------------------------------
@router.get("/processing/{upload_id}")
async def get_processing_status(upload_id: str, request: Request, db: Session = Depends(get_db)):
    user = request.headers.get("X-User", "anonymous")
    audit_logger.info(f"user={user} action=get_processing_status upload_id={upload_id}")

    doc = db.query(Document).filter(Document.id == upload_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    return {
        "document_id": doc.id,
        "ocr_status": doc.ocr_status,
        "ocr_confidence": doc.ocr_confidence,
        "validation_status": doc.validation_status,
    }

# ------------------------------------------------------
# Cancel Processing
# ------------------------------------------------------
@router.delete("/processing/{upload_id}")
async def cancel_processing(upload_id: str, request: Request, db: Session = Depends(get_db)):
    user = request.headers.get("X-User", "anonymous")
    audit_logger.info(f"user={user} action=cancel_processing upload_id={upload_id}")

    doc = db.query(Document).filter(Document.id == upload_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    # If already processed, cannot cancel
    if doc.ocr_status not in ["pending", "processing"]:
        raise HTTPException(status_code=400, detail="Processing cannot be cancelled")

    doc.ocr_status = "cancelled"
    db.commit()
    return {"message": "Processing cancelled"}

#------------------------Validation Workflow Routes------------------------------------------------
# ------------------------------------------------------
# Get validation queue
# ------------------------------------------------------
@router.get("/validation-queue", response_model=List[UploadResponse])
async def get_validation_queue(
    request: Request,
    db: Session = Depends(get_db)
):
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug("Fetching validation queue")
    audit_logger.info(f"user={user} action=get_validation_queue")

    # In your flow, validation would normally happen on processed OCR docs.
    # Here we consider uploads with "ocr_status = completed" as ready for validation.
    uploads = db.query(Upload).filter(Upload.ocr_status == "completed").all()
    return uploads

# ------------------------------------------------------
# Get Validation Details
# ------------------------------------------------------
@router.get("/validation/{upload_id}")
async def get_validation_details(upload_id: str, request: Request, db: Session = Depends(get_db)):
    user = request.headers.get("X-User", "anonymous")
    audit_logger.info(f"user={user} action=get_validation_details upload_id={upload_id}")

    doc = db.query(Document).filter(Document.id == upload_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    return {
        "document_id": doc.id,
        "ocr_text": doc.ocr_text,
        "ocr_confidence": doc.ocr_confidence,
        "validation_status": doc.validation_status,
        "file_path": doc.file_path,  # you could serve via /static
    }

# ------------------------------------------------------
# Approve Validation
# ------------------------------------------------------
@router.post("/validation/{upload_id}/approve")
async def approve_validation(upload_id: str, body: dict, request: Request, db: Session = Depends(get_db)):
    user = request.headers.get("X-User", "anonymous")
    audit_logger.info(f"user={user} action=approve_validation upload_id={upload_id}")

    doc = db.query(Document).filter(Document.id == upload_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    corrected_fields = body.get("corrected_fields", {})
    create_patient = body.get("create_patient", False)

    # Apply corrections
    doc.extracted_data = corrected_fields
    doc.validation_status = "approved"
    db.commit()

    # Optionally, create patient logic here
    if create_patient:
        app_logger.info(f"Would create patient from document {upload_id}")

    return {
        "document_id": doc.id,
        "status": "approved",
        "extracted_data": doc.extracted_data,
    }

# ------------------------------------------------------
# Reject Validation
# ------------------------------------------------------
@router.post("/validation/{upload_id}/reject")
async def reject_validation(upload_id: str, body: dict, request: Request, db: Session = Depends(get_db)):
    user = request.headers.get("X-User", "anonymous")
    audit_logger.info(f"user={user} action=reject_validation upload_id={upload_id}")

    doc = db.query(Document).filter(Document.id == upload_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    reason = body.get("reason", "No reason provided")
    doc.validation_status = "rejected"
    db.commit()

    return {"message": f"Rejected, moved to manual entry. Reason: {reason}"}

# ----------------- Utility Routes -------------------

# ------------------------------------------------------
# Get Upload Details
# ------------------------------------------------------
@router.get("/uploads/{upload_id}")
async def get_upload_details(upload_id: str, request: Request, db: Session = Depends(get_db)):
    user = request.headers.get("X-User", "anonymous")
    audit_logger.info(f"user={user} action=get_upload_details upload_id={upload_id}")

    doc = db.query(Document).filter(Document.id == upload_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    return {
        "document_id": doc.id,
        "original_filename": doc.original_filename,
        "saved_filename": doc.filename,
        "ocr_status": doc.ocr_status,
        "validation_status": doc.validation_status,
        "file_size": doc.file_size,
    }

# ------------------------------------------------------
# Delete Upload
# ------------------------------------------------------
@router.delete("/uploads/{upload_id}")
async def delete_upload(upload_id: str, request: Request, db: Session = Depends(get_db)):
    user = request.headers.get("X-User", "anonymous")
    audit_logger.info(f"user={user} action=delete_upload upload_id={upload_id}")

    doc = db.query(Document).filter(Document.id == upload_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    db.delete(doc)
    db.commit()
    return {"message": "Upload deleted"}

# ------------------------------------------------------
# Get Supported Document Types (reuse existing)
# ------------------------------------------------------
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
                    "prescription": "Rețetă medicală",
                    "doctors_note": "Scrisoare medicală",
                    "photo":"Imagine (ex: ecografie, radiografie, curbă spirometrie, etc)"
                }.get(t.document_type, t.document_type)
            }
            for t in templates
        ],
        "usage_note": "Provide hint_type parameter to OCR endpoint for better accuracy"
    }

# ------------------------------------------------------
# Get documents for specific patient
# ------------------------------------------------------
@router.get("/patients/{patient_id}/documents", response_model=List[UploadResponse])
async def get_patient_documents(
    patient_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    user = request.headers.get("X-User", "anonymous")
    app_logger.debug(f"Fetching documents for patient {patient_id}")
    audit_logger.info(f"user={user} action=get_patient_documents patient_id={patient_id}")

    try:
        # Get uploads for this patient
        uploads = db.query(Upload).filter(Upload.patient_id == patient_id).all()
        
        # Convert to response format with status mapping
        documents = []
        for upload in uploads:
            doc_data = {
                "id": upload.id,
                "name": upload.filename,
                "original_filename": upload.filename,
                "status": upload.ocr_status or "pending",
                "file_size": upload.file_size,
                "uploaded_at": upload.uploaded_at,
                "document_type": upload.document_type
            }
            documents.append(doc_data)
        
        return documents

    except Exception as e:
        app_logger.error(f"Error fetching patient documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch patient documents")

# ------------------------------------------------------
# Download document file
# ------------------------------------------------------
@router.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    user = request.headers.get("X-User", "anonymous")
    audit_logger.info(f"user={user} action=download_document doc_id={doc_id}")

    try:
        # Find the upload record
        upload = db.query(Upload).filter(Upload.id == doc_id).first()
        if not upload:
            raise HTTPException(status_code=404, detail="Document not found")

        # Check if file exists
        if not os.path.exists(upload.file_path):
            raise HTTPException(status_code=404, detail="File not found on disk")

        # Return file for download
        from fastapi.responses import FileResponse
        return FileResponse(
            path=upload.file_path,
            filename=upload.filename,
            media_type='application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Error downloading document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Download failed")

# ------------------------------------------------------
# Validate document (approve/reject)
# ------------------------------------------------------
@router.post("/documents/{doc_id}/validate")
async def validate_document(
    doc_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    user = request.headers.get("X-User", "anonymous")
    approved = body.get("approved", False)
    
    audit_logger.info(f"user={user} action=validate_document doc_id={doc_id} approved={approved}")

    try:
        # Find the upload record
        upload = db.query(Upload).filter(Upload.id == doc_id).first()
        if not upload:
            raise HTTPException(status_code=404, detail="Document not found")

        # Update validation status
        if approved:
            upload.ocr_status = "validated"
        else:
            upload.ocr_status = "rejected"
        
        db.commit()
        db.refresh(upload)

        # Return updated document data
        return {
            "id": upload.id,
            "name": upload.filename,
            "status": upload.ocr_status,
            "validated_at": datetime.utcnow().isoformat(),
            "validated_by": user
        }

    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Error validating document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Validation failed")