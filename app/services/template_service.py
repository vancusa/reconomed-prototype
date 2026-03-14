# app/services/template_service.py
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.models import Consultation, Patient
from .templates.internal_medicine_template import get_internal_medicine_template
from .templates.cardiology_template import get_cardiology_template
from .templates.respiratory_template import get_respiratory_template
from .templates.gynecology_template import get_gynecology_template
from .templates.obstetrics_template import get_obstetrics_template

class TemplateService:
    """Service for managing consultation templates"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_template(self, specialty: str) -> Dict[str, Any]:
        """Get template definition for specialty"""
        template_map = {
            "internal_medicine": get_internal_medicine_template,
            "cardiology": get_cardiology_template,
            "respiratory": get_respiratory_template,
            "gynecology": get_gynecology_template,
            "obstetrics": get_obstetrics_template,  # For prenatal care
        }
        
        if specialty not in template_map:
            raise ValueError(f"Unknown specialty: {specialty}")
        
        template = template_map[specialty]()
        return template.to_dict()
    
    def pre_fill_template(
        self, 
        patient_id: str, 
        specialty: str,
        selected_documents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Pre-fill template with patient data and previous consultation history.
        
        Args:
            patient_id: Patient UUID
            specialty: Consultation specialty
            selected_documents: List of document IDs doctor selected to include
        
        Returns:
            Pre-filled structured_data dict
        """
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            return {}
        
        # Get template structure
        template = self.get_template(specialty)
        pre_filled_data = {}
        
        # 1. Pre-fill patient identification (always)
        pre_filled_data["patient_identification"] = {
            "patient_name": f"{patient.given_name} {patient.family_name}",
            "patient_cnp": patient.cnp,
            "patient_age": self._calculate_age(patient.birth_date)
        }
        
        # 2. Get most recent completed consultation
        previous_consult = self.db.query(Consultation).filter(
            Consultation.patient_id == patient_id,
            Consultation.status.in_(["completed", "discharged"]),
            Consultation.is_signed == True
        ).order_by(
            Consultation.consultation_date.desc()
        ).first()
        
        if previous_consult and previous_consult.structured_data:
            # Pre-fill fields marked with pre_fill_source="previous_consult"
            pre_filled_data.update(
                self._extract_prefillable_fields(
                    template, 
                    previous_consult.structured_data
                )
            )
        
        # 3. Include selected document data (doctor's choice)
        if selected_documents:
            from app.models import Document
            documents = self.db.query(Document).filter(
                Document.id.in_(selected_documents),
                Document.patient_id == patient_id,
                Document.validation_status == "validated"
            ).all()
            
            pre_filled_data["selected_documents"] = [
                {
                    "document_id": doc.id,
                    "document_type": doc.document_type,
                    "extracted_data": doc.extracted_data
                }
                for doc in documents
            ]
        
        return pre_filled_data
    
    def _extract_prefillable_fields(
        self, 
        template: Dict[str, Any], 
        previous_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract fields from previous consultation that have pre_fill_source.
        Only copy data for fields explicitly marked for pre-filling.
        """
        prefilled = {}
        
        for section in template["sections"]:
            section_id = section["section_id"]
            section_data = {}
            
            for field in section["fields"]:
                if field.get("pre_fill_source") == "previous_consult":
                    field_id = field["field_id"]
                    # Copy from previous consultation if exists
                    if section_id in previous_data:
                        if field_id in previous_data[section_id]:
                            section_data[field_id] = previous_data[section_id][field_id]
            
            if section_data:
                prefilled[section_id] = section_data
        
        return prefilled
    
    def _calculate_age(self, birth_date: Optional[str]) -> Optional[int]:
        """Calculate age from birth date string"""
        if not birth_date:
            return None
        from datetime import datetime
        try:
            birth = datetime.strptime(birth_date, "%Y-%m-%d")
            today = datetime.today()
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            return age
        except:
            return None