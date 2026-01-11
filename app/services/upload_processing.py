# app/services/upload_processing.py

from __future__ import annotations

import os
import socket
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models import Upload, Document
from app.services.document import DocumentService


# ---- Compatibility helpers (supports both ocr_status and job_state during migration) ----

def _get_state_field(upload: Upload) -> str:
    return "job_state" if hasattr(upload, "job_state") else "ocr_status"

def get_upload_state(upload: Upload) -> str:
    field = _get_state_field(upload)
    return getattr(upload, field)

def set_upload_state(upload: Upload, state: str) -> None:
    field = _get_state_field(upload)
    setattr(upload, field, state)


def _get_attempts(upload: Upload) -> int:
    return int(getattr(upload, "attempts", 0) or 0)

def _inc_attempts(upload: Upload) -> None:
    if hasattr(upload, "attempts"):
        upload.attempts = _get_attempts(upload) + 1

def _set_claimed(upload: Upload, worker_id: str) -> None:
    if hasattr(upload, "claimed_at"):
        upload.claimed_at = datetime.utcnow()
    if hasattr(upload, "claimed_by"):
        upload.claimed_by = worker_id
    if hasattr(upload, "error_message"):
        upload.error_message = None

def _set_error(upload: Upload, msg: str) -> None:
    if hasattr(upload, "error_message"):
        upload.error_message = (msg or "")[:500]


@dataclass
class ProcessResult:
    processed: bool
    upload_id: Optional[str] = None
    document_id: Optional[str] = None
    state: Optional[str] = None
    message: Optional[str] = None


class UploadProcessingService:
    """
    Single source of truth for:
      - claiming jobs
      - running OCR
      - creating/updating the 1:1 Document for the Upload
      - updating Upload state & debug fields
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        stale_timeout_seconds: int = 600,
    ) -> None:
        self.max_attempts = max_attempts
        self.stale_timeout_seconds = stale_timeout_seconds
        self.doc_service = DocumentService()

    def _worker_id(self) -> str:
        # good enough for MVP single-process thread; can be overridden
        return f"{socket.gethostname()}:{os.getpid()}"

    def recover_stale_jobs(self, db: Session, clinic_id: Optional[str] = None) -> int:
        """
        Re-queue uploads stuck in 'processing' beyond timeout.
        No explicit 'stale' state; we treat it as a condition.
        """
        timeout_before = datetime.utcnow() - timedelta(seconds=self.stale_timeout_seconds)

        q = db.query(Upload)
        # Only if claimed_at exists in your model; otherwise skip.
        if not hasattr(Upload, "claimed_at"):
            return 0

        q = q.filter(getattr(Upload, _get_state_field(Upload)).in_(["processing"]))  # type: ignore
        if clinic_id:
            q = q.filter(Upload.clinic_id == clinic_id)

        # claimed_at < timeout
        q = q.filter(Upload.claimed_at != None).filter(Upload.claimed_at < timeout_before)  # noqa: E711

        stale = q.all()
        count = 0
        for upl in stale:
            if _get_attempts(upl) >= self.max_attempts:
                set_upload_state(upl, "ocr_failed")
                _set_error(upl, "stale_timeout_max_attempts")
            else:
                set_upload_state(upl, "queued")
                _set_error(upl, "stale_timeout_requeued")
            count += 1

        if count:
            db.commit()
        return count

    def cleanup_expired_uploads(self, db: Session, clinic_id: Optional[str] = None) -> int:
        """
        Delete expired uploads immediately (and remove files on disk).
        """
        now = datetime.utcnow()
        q = db.query(Upload).filter(Upload.expires_at < now)
        if clinic_id:
            q = q.filter(Upload.clinic_id == clinic_id)

        expired = q.all()
        if not expired:
            return 0

        for upload in expired:
            if upload.file_path and os.path.exists(upload.file_path):
                try:
                    file_path = Path(upload.file_path)
                    file_path.unlink(missing_ok=True)
                    if file_path.parent.exists() and not any(file_path.parent.iterdir()):
                        file_path.parent.rmdir()
                except Exception:
                    pass
            db.delete(upload)

        db.commit()
        return len(expired)

    def claim_next(self, db: Session, clinic_id: Optional[str] = None, worker_id: Optional[str] = None) -> Optional[Upload]:
        """
        Claim the next queued upload.
        MVP assumes single worker thread, so a simple claim is enough.
        """
        worker_id = worker_id or self._worker_id()

        q = db.query(Upload)

        # filter queued
        # (works for both job_state and ocr_status while you migrate)
        state_field = _get_state_field(Upload)  # type: ignore
        q = q.filter(getattr(Upload, state_field) == "queued")

        if clinic_id:
            q = q.filter(Upload.clinic_id == clinic_id)

        upload = q.order_by(Upload.uploaded_at.asc()).first()
        if not upload:
            return None

        # claim it
        set_upload_state(upload, "processing")
        _inc_attempts(upload)
        _set_claimed(upload, worker_id)

        db.commit()
        db.refresh(upload)
        return upload

    def process_upload(self, db: Session, upload_id: str, worker_id: Optional[str] = None) -> ProcessResult:
        """
        Run OCR for a single upload_id that is already claimed or is queued.
        Creates/updates one Document per Upload.
        """
        worker_id = worker_id or self._worker_id()

        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if not upload:
            return ProcessResult(processed=False, upload_id=upload_id, message="upload_not_found")

        # ensure state makes sense
        state = get_upload_state(upload)
        if state not in ("queued", "processing"):
            return ProcessResult(processed=False, upload_id=upload_id, state=state, message="not_in_runnable_state")

        # file existence
        if not upload.file_path or not os.path.exists(upload.file_path):
            set_upload_state(upload, "ocr_failed")
            _set_error(upload, "file_missing_on_disk")
            db.commit()
            return ProcessResult(processed=False, upload_id=upload.id, state=get_upload_state(upload), message="file_missing")

        # read bytes
        with open(upload.file_path, "rb") as f:
            file_bytes = f.read()

        hint_type = upload.document_type or None

        # call OCR (still Tesseract right now, via DocumentService)
        ocr_result = self.doc_service.process_document_with_templates(
            file_content=file_bytes,
            hint_type=hint_type,
        )

        if not ocr_result.get("success"):
            # retry until max_attempts, otherwise fail
            err = ocr_result.get("error") or "ocr_failed_unknown"
            if _get_attempts(upload) >= self.max_attempts:
                set_upload_state(upload, "ocr_failed")
            else:
                set_upload_state(upload, "queued")
            _set_error(upload, err)
            db.commit()
            return ProcessResult(processed=False, upload_id=upload.id, state=get_upload_state(upload), message="ocr_failed")

        # 1 Document per Upload: upsert by upload_id
        doc = db.query(Document).filter(Document.upload_id == upload.id).first()
        if not doc:
            doc = Document(
                upload_id=upload.id,
                patient_id=upload.patient_id,
                clinic_id=upload.clinic_id,
                filename=upload.filename,
                original_filename=getattr(upload, "original_filename", upload.filename) or upload.filename,
                file_path=upload.file_path,
                file_size=upload.file_size,
                document_type=ocr_result.get("document_type") or upload.document_type,
                # keep these for compatibility with your current Document model
                ocr_status="completed",
                validation_status="pending",
            )
            db.add(doc)

        # update document OCR fields
        doc.ocr_text = ocr_result.get("ocr_text", "") or ""
        doc.ocr_confidence = int(ocr_result.get("confidence_score") or 0)
        doc.extracted_data = ocr_result.get("structured_data") or {}

        # mark upload done
        set_upload_state(upload, "ocr_done")
        if hasattr(upload, "claimed_at"):
            upload.claimed_at = None

        db.commit()
        db.refresh(upload)
        db.refresh(doc)

        return ProcessResult(
            processed=True,
            upload_id=upload.id,
            document_id=doc.id,
            state=get_upload_state(upload),
            message="ok",
        )
