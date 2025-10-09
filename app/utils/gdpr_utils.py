"""GDPR compliance utilities"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

class ConsentType(Enum):
    TREATMENT = "treatment"
    DATA_PROCESSING = "data_processing"
    RESEARCH = "research"
    MARKETING = "marketing"
    CROSS_CLINIC = "cross_clinic"

class LegalBasis(Enum):
    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_TASK = "public_task"
    LEGITIMATE_INTERESTS = "legitimate_interests"

def create_gdpr_consent_record(
    consent_type: ConsentType,
    legal_basis: LegalBasis = LegalBasis.CONSENT,
    granted: bool = True,
    expiry_months: Optional[int] = None,
    metadata: Optional[Dict] = None
) -> Dict[str, Any]:
    """Create a GDPR-compliant consent record"""
    now = datetime.utcnow()
    
    consent_record = {
        "consent_type": consent_type.value,
        "legal_basis": legal_basis.value,
        "granted": granted,
        "granted_at": now.isoformat(),
        "withdrawn": False,
        "withdrawn_at": None,
        "metadata": metadata or {}
    }
    
    # Add expiry if specified
    if expiry_months:
        expiry_date = now + timedelta(days=30 * expiry_months)
        consent_record["expires_at"] = expiry_date.isoformat()
    else:
        consent_record["expires_at"] = None
    
    return consent_record

def get_default_romanian_consents() -> Dict[str, Any]:
    """Get default GDPR consents for Romanian patients"""
    return {
        "treatment": create_gdpr_consent_record(
            ConsentType.TREATMENT,
            LegalBasis.CONSENT,
            granted=True,
            expiry_months=12,  # Annual renewal
            metadata={
                "purpose": "Medical treatment and care",
                "purpose_ro": "Îngrijire și tratament medical",
                "required": True
            }
        ),
        "data_processing": create_gdpr_consent_record(
            ConsentType.DATA_PROCESSING,
            LegalBasis.CONSENT,
            granted=True,
            expiry_months=24,  # 2-year renewal
            metadata={
                "purpose": "Personal data processing for healthcare",
                "purpose_ro": "Prelucrarea datelor personale pentru îngrijirea sănătății",
                "required": True
            }
        ),
        "research": create_gdpr_consent_record(
            ConsentType.RESEARCH,
            LegalBasis.CONSENT,
            granted=False,  # Optional by default
            expiry_months=36,  # 3-year projects
            metadata={
                "purpose": "Anonymous medical research participation",
                "purpose_ro": "Participare anonimă la cercetare medicală",
                "required": False
            }
        ),
        "marketing": create_gdpr_consent_record(
            ConsentType.MARKETING,
            LegalBasis.CONSENT,
            granted=False,  # Optional by default
            expiry_months=12,
            metadata={
                "purpose": "Healthcare-related communications",
                "purpose_ro": "Comunicări legate de sănătate",
                "required": False
            }
        )
    }

def is_consent_valid(consent_record: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Check if a consent record is currently valid"""
    if not consent_record.get("granted", False):
        return False, "Consent not granted"
    
    if consent_record.get("withdrawn", False):
        return False, "Consent has been withdrawn"
    
    expires_at = consent_record.get("expires_at")
    if expires_at:
        try:
            expiry_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if datetime.utcnow() > expiry_date:
                return False, "Consent has expired"
        except ValueError:
            return False, "Invalid expiry date format"
    
    return True, None

def withdraw_consent(
    consent_record: Dict[str, Any],
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """Withdraw a consent record"""
    consent_record["granted"] = False 
    consent_record["withdrawn"] = True
    consent_record["granted_at"] = None 
    consent_record["withdrawn_at"] = datetime.utcnow().isoformat()
    if reason:
        consent_record["withdrawal_reason"] = reason
    
    return consent_record

def check_required_consents(gdpr_consents: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Check if all required consents are valid"""
    required_consent_types = ["treatment", "data_processing"]
    missing_consents = []
    
    for consent_type in required_consent_types:
        consent_record = gdpr_consents.get(consent_type)
        if not consent_record:
            missing_consents.append(consent_type)
            continue
        
        is_valid, reason = is_consent_valid(consent_record)
        if not is_valid:
            missing_consents.append(f"{consent_type} ({reason})")
    
    return len(missing_consents) == 0, missing_consents