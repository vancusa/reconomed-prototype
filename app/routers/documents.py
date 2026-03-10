# app/routers/documents.py
# Upload-centric Documents router (MVP)
#
# Public API surface is Upload-first:
# - Upload a file -> Upload row created with job_state=queued
# - Worker claims and OCRs -> creates/updates 1 Document per Upload
# - Doctor sees items by tab (derived server-side) -> assigns patient & completes
# - Reject deletes immediately (Upload + Document + file)
#
# Internal/technical state:
#   Upload.job_state: queued | processing | ocr_done | ocr_failed
#
# Human/clinical state:
#   Document.validation_status: pending | approved | rejected
#   Upload.patient_id indicates association
#
# Tabs are derived (not stored):
# - unprocessed: job_state == queued
# - processing: job_state == processing
# - validation: job_state == ocr_done AND (patient_id is null OR document.validation_status != approved)
# - completed: job_state == ocr_done AND patient_id not null AND document.validation_status == approved
# - error: job_state == ocr_failed

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Upload, Document, Patient, User
from app.auth import get_user_from_header

from app.schemas import (
    # Enums
    JobState, ValidationStatus, TabName,
    # Upload list/detail schemas
    UploadCardResponse, UploadListResponse,
    UploadDocumentSummary, UploadDetailResponse,
    UploadOCRResponse,
    # Workflow actions
    UploadCompleteRequest, UploadCompleteResponse,
    UploadRejectResponse,
    UploadBatchAssignRequest,
    UploadBatchTypeRequest,
    # Patient document list item
    PatientDocumentListItem,
    DocumentTextResponse,
)

# File utils (adjust these imports to your actual module paths/names)
from app.utils.file import validate_file_type, save_uploaded_file

# OCR processing service (Step 2)
from app.services.upload_processing import UploadProcessingService

router = APIRouter(tags=["documents"])

processing_svc = UploadProcessingService(max_attempts=3, stale_timeout_seconds=600)

# ----------------------------
# Helpers
# ----------------------------

def _preview_url(upload_id: str) -> str:
    """
    UI can use this as a stable link for preview/download.
    Adjust if your frontend expects another URL.
    """
    return f"/api/documents/uploads/{upload_id}/download"

def _make_upload_card(db: Session, upload: Upload) -> UploadCardResponse:
    """
    Build UploadCardResponse, including optional OCR snippet from the linked Document.
    """
    doc = db.query(Document).filter(Document.upload_id == upload.id).first()
    snippet = None
    if doc and getattr(doc, "ocr_text", None):
        snippet = (doc.ocr_text or "")[:500]

    patient_name = None
    if upload.patient:
        patient_name = " ".join(
            part for part in [upload.patient.given_name, upload.patient.family_name] if part
        ).strip() or None

    return UploadCardResponse(
        id=upload.id,
        clinic_id=upload.clinic_id,
        filename=upload.filename,
        file_size=getattr(upload, "file_size", None),
        document_type=getattr(upload, "document_type", None) or getattr(doc, "document_type", None),
        job_state=upload.job_state,
        uploaded_at=upload.uploaded_at,
        expires_at=upload.expires_at,
        patient_id=getattr(upload, "patient_id", None),
        patient_name=patient_name,
        validated_at=getattr(doc, "validated_at", None),
        preview_url=_preview_url(upload.id),
        ocr_snippet=snippet,
    )

def _make_upload_detail(db: Session, upload: Upload) -> UploadDetailResponse:
    """
    Build UploadDetailResponse with document summary (if exists).
    """
    doc = db.query(Document).filter(Document.upload_id == upload.id).first()
    doc_summary = None
    if doc:
        doc_summary = UploadDocumentSummary(
            id=doc.id,
            upload_id=doc.upload_id,
            validation_status=doc.validation_status,
            validated_by=getattr(doc, "validated_by", None),
            validated_at=getattr(doc, "validated_at", None),
        )

    return UploadDetailResponse(
        id=upload.id,
        clinic_id=upload.clinic_id,
        filename=upload.filename,
        file_path=upload.file_path,
        file_size=getattr(upload, "file_size", None),
        document_type=getattr(upload, "document_type", None),
        job_state=upload.job_state,
        attempts=getattr(upload, "attempts", 0) or 0,
        claimed_at=getattr(upload, "claimed_at", None),
        claimed_by=getattr(upload, "claimed_by", None),
        error_message=getattr(upload, "error_message", None),
        patient_id=getattr(upload, "patient_id", None),
        uploaded_at=upload.uploaded_at,
        expires_at=upload.expires_at,
        preview_url=_preview_url(upload.id),
        document=doc_summary,
    )

def _require_same_clinic(user: User, upload: Upload) -> None:
    """
    Multi-tenant guard: user can only act within their clinic.
    """
    if upload.clinic_id != user.clinic_id:
        raise HTTPException(status_code=403, detail="Forbidden (wrong clinic)")

def _remove_upload_file(upload: Upload) -> None:
    if not upload.file_path:
        return
    try:
        file_path = Path(upload.file_path)
        if file_path.exists():
            file_path.unlink()
        if file_path.parent.exists() and not any(file_path.parent.iterdir()):
            file_path.parent.rmdir()
    except Exception:
        # In MVP: do not block delete if file removal fails.
        pass

def _document_has_original_file(upload: Upload | None) -> bool:
    if not upload or not upload.file_path:
        return False
    return os.path.exists(upload.file_path)

def _make_document_snippet(text: str | None, length: int = 300) -> str:
    if not text:
        return ""
    return text.strip()[:length]

# ----------------------------
# Upload endpoints
# ----------------------------

@router.post("/uploads", response_model=List[UploadCardResponse])
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload one or multiple files (no patient required).
    Behavior:
    - Saves file to disk
    - Creates Upload rows in DB
    - Sets job_state=queued immediately (server-side auto OCR)
    - Returns UploadCardResponse cards for UI rendering
    """
    user = get_user_from_header(db, request)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    created: List[Upload] = []

    for f in files:
        # Validate file type (pdf/jpg/png/etc.)
        if not validate_file_type(f.content_type, f.filename):
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {f.filename}")

        # Save to disk
        upload_id = str(uuid4())
        file_path, file_size = await save_uploaded_file(
            f,
            clinic_id=user.clinic_id,
            upload_id=upload_id,
        )

        # Create upload row (auto-queue)
        upload = Upload(
            id=upload_id,
            clinic_id=user.clinic_id,
            filename=f.filename,
            file_path=file_path,
            file_size=file_size,
            document_type=None,
            patient_id=None,
            job_state=JobState.QUEUED.value,
            attempts=0,
            claimed_at=None,
            claimed_by=None,
            error_message=None,
            uploaded_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db.add(upload)
        created.append(upload)

    db.commit()

    # refresh to get IDs
    for u in created:
        db.refresh(u)

    # Return cards (UI can drop them into Unprocessed tab)
    return [_make_upload_card(db, u) for u in created]

@router.get("/uploads", response_model=UploadListResponse)
def list_uploads_by_tab(
    request: Request,
    tab: TabName = Query(TabName.UNPROCESSED),
    db: Session = Depends(get_db),
):
    """
    List uploads for a specific UI tab.
    This is the *single* contract the UI should use for tab content.

    Tab derivation rules (server-side):
    - unprocessed: job_state == queued
    - processing: job_state == processing
    - validation: job_state == ocr_done AND (patient_id is null OR document.validation_status != approved)
    - completed: job_state == ocr_done AND patient_id not null AND document.validation_status == approved
    - error: job_state == ocr_failed
    """
    user = get_user_from_header(db, request)

    processing_svc.cleanup_expired_uploads(db, clinic_id=user.clinic_id)

    q = db.query(Upload).filter(Upload.clinic_id == user.clinic_id)

    if tab == TabName.UNPROCESSED:
        q = q.filter(Upload.job_state == JobState.QUEUED.value)

    elif tab == TabName.PROCESSING:
        q = q.filter(Upload.job_state == JobState.PROCESSING.value)

    elif tab == TabName.ERROR:
        q = q.filter(Upload.job_state == JobState.OCR_FAILED.value)

    elif tab in (TabName.VALIDATION, TabName.COMPLETED):
        # job_state must be OCR_DONE for both validation/completed
        q = q.filter(Upload.job_state == JobState.OCR_DONE.value)

        # Now apply validation/patient logic via Document join
        # One Document per Upload, but join is safe.
        q = q.outerjoin(Document, Document.upload_id == Upload.id)

        if tab == TabName.VALIDATION:
            # Needs action if patient not assigned OR doc not approved (or doc missing)
            q = q.filter(
                (Upload.patient_id == None) |  # noqa: E711
                (Document.id == None) |         # noqa: E711
                (Document.validation_status != ValidationStatus.APPROVED.value)
            )
        else:
            # COMPLETED: patient assigned AND doc approved
            q = q.filter(
                (Upload.patient_id != None) &  # noqa: E711
                (Document.validation_status == ValidationStatus.APPROVED.value)
            )

    # order newest first for UI
    uploads = q.order_by(Upload.uploaded_at.desc()).all()
    items = [_make_upload_card(db, u) for u in uploads]

    return UploadListResponse(items=items, total=len(items))

@router.post("/uploads/batch/assign", response_model=UploadListResponse)
def batch_assign_uploads(
    request: Request,
    payload: UploadBatchAssignRequest,
    db: Session = Depends(get_db),
):
    """
    Assign a patient to multiple uploads in a single call.
    Updates associated Document.patient_id when present.
    """
    user = get_user_from_header(db, request)

    patient = db.query(Patient).filter(
        Patient.id == payload.patient_id,
        Patient.clinic_id == user.clinic_id,
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    upload_ids = list(dict.fromkeys(payload.upload_ids))
    uploads = db.query(Upload).filter(
        Upload.clinic_id == user.clinic_id,
        Upload.id.in_(upload_ids),
    ).all()

    if len(uploads) != len(upload_ids):
        raise HTTPException(status_code=404, detail="One or more uploads not found")

    for upload in uploads:
        upload.patient_id = patient.id
        if upload.document:
            upload.document.patient_id = patient.id

    db.commit()

    items = [_make_upload_card(db, u) for u in uploads]
    return UploadListResponse(items=items, total=len(items))

@router.post("/uploads/batch/type", response_model=UploadListResponse)
def batch_update_upload_type(
    request: Request,
    payload: UploadBatchTypeRequest,
    db: Session = Depends(get_db),
):
    """
    Update document_type for multiple uploads in a single call.
    Updates associated Document.document_type when present.
    """
    user = get_user_from_header(db, request)

    upload_ids = list(dict.fromkeys(payload.upload_ids))
    uploads = db.query(Upload).filter(
        Upload.clinic_id == user.clinic_id,
        Upload.id.in_(upload_ids),
    ).all()

    if len(uploads) != len(upload_ids):
        raise HTTPException(status_code=404, detail="One or more uploads not found")

    for upload in uploads:
        upload.document_type = payload.document_type
        if upload.document:
            upload.document.document_type = payload.document_type

    db.commit()

    items = [_make_upload_card(db, u) for u in uploads]
    return UploadListResponse(items=items, total=len(items))

@router.get("/uploads/{upload_id}", response_model=UploadDetailResponse)
def get_upload_detail(
    upload_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Fetch upload details + document summary.
    Used by the Validation screen when opening a card.
    """
    user = get_user_from_header(db, request)

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    _require_same_clinic(user, upload)
    return _make_upload_detail(db, upload)

@router.get("/uploads/{upload_id}/ocr", response_model=UploadOCRResponse)
def get_upload_ocr_text(
    upload_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Fetch full OCR text for an upload.
    This is separate from list endpoints to keep list payloads small.
    """
    user = get_user_from_header(db, request)

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    _require_same_clinic(user, upload)

    doc = db.query(Document).filter(Document.upload_id == upload_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="OCR not available yet")

    if upload.job_state != JobState.OCR_DONE.value:
        raise HTTPException(status_code=409, detail=f"OCR not finished (state={upload.job_state})")

    return UploadOCRResponse(
        upload_id=upload_id,
        document_id=doc.id,
        ocr_text=doc.ocr_text or "",
        ocr_metadata=None,
    )

@router.post("/uploads/{upload_id}/complete", response_model=UploadCompleteResponse)
def complete_upload_assign_and_approve(
    upload_id: str,
    payload: UploadCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Doctor primary action (Option C):
    - Assign patient
    - Approve validation
    - Optional: edit OCR text
    - Optional: set document_type

    This is the only doctor-facing "complete" action required for MVP.
    """
    user = get_user_from_header(db, request)

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    _require_same_clinic(user, upload)

    if upload.job_state != JobState.OCR_DONE.value:
        raise HTTPException(status_code=409, detail=f"Upload not ready for completion (state={upload.job_state})")

    # Verify patient exists and belongs to same clinic
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.clinic_id != user.clinic_id:
        raise HTTPException(status_code=403, detail="Forbidden (patient in different clinic)")

    doc = db.query(Document).filter(Document.upload_id == upload_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found for upload")

    # Apply edits
    upload.patient_id = payload.patient_id
    doc.patient_id = payload.patient_id

    # Mark validation as approved
    doc.validation_status = ValidationStatus.APPROVED.value
    doc.validated_by = user.email
    doc.validated_at = datetime.utcnow()

    if payload.document_type:
        upload.document_type = payload.document_type
        doc.document_type = payload.document_type

    if payload.edited_ocr_text is not None:
        doc.ocr_text = payload.edited_ocr_text

    db.commit()
    db.refresh(upload)

    _remove_upload_file(upload)

    return UploadCompleteResponse(upload=_make_upload_detail(db, upload))

@router.delete("/uploads/{upload_id}", response_model=UploadRejectResponse)
def reject_and_delete_upload(
    upload_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Doctor rejection behavior for MVP:
    - Immediate deletion of Upload + linked Document + file on disk.
    No reason/motive required in v1.
    """
    user = get_user_from_header(db, request)

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    _require_same_clinic(user, upload)

    # delete linked Document (if cascade isn't configured)
    doc = db.query(Document).filter(Document.upload_id == upload_id).first()
    if doc:
        db.delete(doc)

    # delete file from disk
    _remove_upload_file(upload)

    db.delete(upload)
    db.commit()

    return UploadRejectResponse(deleted=True, upload_id=upload_id)

@router.get("/uploads/{upload_id}/download")
def download_upload_file(
    upload_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Download the original uploaded file.
    Useful for previewing in UI (PDF) and for debugging OCR.
    """
    user = get_user_from_header(db, request)

    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    _require_same_clinic(user, upload)

    if not upload.file_path or not os.path.exists(upload.file_path):
        raise HTTPException(status_code=404, detail="File unavailable")

    return FileResponse(
        upload.file_path,
        filename=upload.filename,
        media_type="application/octet-stream",
    )

@router.get("", response_model=List[PatientDocumentListItem])
def list_patient_documents(
    request: Request,
    patient_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """List documents for a given patient.

    Used by the patient "Documents & History" view.
    Only returns documents for the caller's clinic.
    """
    # print a log to confirm the function is called and patient_id is received
    #print(f"Listing documents for patient ID: {patient_id}")
    user = get_user_from_header(db, request)

    # Ensure patient exists in this clinic (prevents cross-clinic leakage)
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.clinic_id == user.clinic_id)
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    docs = (
        db.query(Document)
        .filter(Document.patient_id == patient_id, Document.clinic_id == user.clinic_id)
        .order_by(Document.created_at.desc())
        .all()
    )

    items: List[PatientDocumentListItem] = []
    for doc in docs:
        ocr_text = getattr(doc, "ocr_text", None) or ""
        has_full_text = bool(ocr_text.strip())
        has_original_file = _document_has_original_file(doc.upload)
        items.append(
            PatientDocumentListItem(
                id=doc.id,
                filename=doc.filename or doc.original_filename,
                document_type=getattr(doc, "document_type", None),
                created_at=doc.created_at,
                text_snippet=_make_document_snippet(ocr_text),
                has_full_text=has_full_text,
                has_original_file=has_original_file,
                download_url=_preview_url(doc.upload_id)
                if getattr(doc, "upload_id", None) and has_original_file
                else None,
                full_text_url=f"/api/documents/{doc.id}/text",
            )
        )

    #log the document list for debugging
    #print(f"Patient {patient_id} has {len(items)} documents")
    #print(f"Documents: {[item.id for item in items]}")
    return items

@router.get("/{document_id}/text", response_model=DocumentTextResponse)
def get_document_text(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Return full OCR text for a document."""
    user = get_user_from_header(db, request)

    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.clinic_id == user.clinic_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentTextResponse(
        id=doc.id,
        text=(doc.ocr_text or ""),
    )

# ----------------------------
# Optional debug/admin endpoints (keep for now, can remove later)
# ----------------------------

@router.post("/processing/run-next")
def run_next_ocr_job_for_clinic(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Debug/admin endpoint:
    - Claims next queued job for the current clinic and processes it.
    In production, the background worker should handle this automatically.
    """
    user = get_user_from_header(db, request)

    # Optional stale recovery for this clinic
    processing_svc.recover_stale_jobs(db, clinic_id=user.clinic_id)

    upl = processing_svc.claim_next(db, clinic_id=user.clinic_id)
    if not upl:
        return {"processed": False, "message": "No queued uploads"}

    result = processing_svc.process_upload(db, upload_id=upl.id)
    return {
        "processed": result.processed,
        "upload_id": result.upload_id,
        "document_id": result.document_id,
        "state": result.state,
        "message": result.message,
    }
