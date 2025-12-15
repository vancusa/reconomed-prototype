# app/services/gdpr_logging.py

from typing import Optional, Dict, Any
from fastapi import Request
from sqlalchemy.orm import Session
from app.models import GDPRAuditLog

def log_gdpr_event(
    db: Session,
    *,
    clinic_id: str,
    action: str,
    user_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    legal_basis: str = "art9_2_h_medical_diagnosis",
    data_category: str = "health_data_document",
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> None:
    """
    Insert a GDPR audit log entry.
    `details` should contain only IDs and metadata, no full OCR text or diagnoses.
    """
    ip_address = None
    user_agent = None

    if request is not None:
        client_host = request.client.host if request.client else None
        ip_address = client_host
        user_agent = request.headers.get("User-Agent")

    log_entry = GDPRAuditLog(
        clinic_id=clinic_id,
        user_id=user_id,
        patient_id=patient_id,
        action=action,
        legal_basis=legal_basis,
        data_category=data_category,
        details=details or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(log_entry)
    db.commit()