"""Romanian-specific document templates for OCR processing"""
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class DocumentField:
    field_name: str
    patterns: List[str]
    validation_func: Optional[str] = None
    required: bool = False
    data_type: str = "string"

@dataclass
class DocumentTemplate:
    template_id: str
    document_type: str
    language: str
    confidence_threshold: int
    identification_patterns: List[str]
    extraction_fields: List[DocumentField]
    post_processing_rules: Optional[Dict] = None

class RomanianDocumentTemplates:
    """Template definitions for common Romanian medical documents"""
    
    @staticmethod
    def get_romanian_id_template() -> DocumentTemplate:
        """Romanian ID card (Carte de identitate) template"""
        return DocumentTemplate(
            template_id="ro_identity_card",
            document_type="romanian_id",
            language="romanian",
            confidence_threshold=70,
            identification_patterns=[
                r"ROMANIA|ROMÂNIA|ROUMANIE",
                r"CARTE DE IDENTITATE||D'IDENTITE",
                r"IDENTITY CARD",
                r"CNP[\s:]*\d{13}",
                r"SERIA|SERIA\s+[A-Z]{2}"
            ],
            extraction_fields=[
                DocumentField("nume", [r"NUME[:\s]+([A-ZĂÂÎȘȚ\s]+)"], required=True),
                DocumentField("prenume", [r"PRENUME[:\s]+([A-ZĂÂÎȘȚ\s]+)"], required=True),
                DocumentField("cnp", [r"CNP[\s:]*(\d{13})"], "validate_cnp", required=True),
                DocumentField("data_nasterii", [
                    r"(\d{2}[\.\-/]\d{2}[\.\-/]\d{4})",
                    r"DATA NAȘTERII[:\s]+(\d{2}[\.\-/]\d{2}[\.\-/]\d{4})"
                ], required=True),
                DocumentField("seria", [r"SERIA\s+([A-Z]{2})"], required=False),
                DocumentField("numar", [r"NR[\.\s]*(\d+)"], required=False),
                DocumentField("eliberata_de", [
                    r"ELIBERATĂ DE[:\s]+([A-ZĂÂÎȘȚ\s,]+)",
                    r"ISSUED BY[:\s]+([A-ZĂÂÎȘȚ\s,]+)"
                ], required=False)
            ],
            post_processing_rules={
                "normalize_names": True,
                "validate_cnp_date_consistency": True,
                "extract_gender_from_cnp": True
            }
        )
    
    @staticmethod
    def get_lab_result_template() -> DocumentTemplate:
        """Romanian laboratory results template"""
        return DocumentTemplate(
            template_id="ro_lab_results",
            document_type="lab_result",
            language="romanian",
            confidence_threshold=65,
            identification_patterns=[
                r"LABORATOR|ANALIZE|REZULTATE",
                r"PACIENT|PATIENT",
                r"HEMOGLOBINĂ|GLICEMIE|COLESTEROL",
                r"NORMAL|PATOLOGIC|REFERINȚĂ",
                r"mg/dL|g/dL|μL|mmol/L"
            ],
            extraction_fields=[
                DocumentField("nume_pacient", [
                    r"PACIENT[:\s]+([A-ZĂÂÎȘȚ\s]+)",
                    r"PATIENT[:\s]+([A-ZĂÂÎȘȚ\s]+)",
                    r"NUME[:\s]+([A-ZĂÂÎȘȚ\s]+)"
                ], required=True),
                DocumentField("data_prelevare", [
                    r"DATA PRELEVĂRII?[:\s]*(\d{2}[\.\-/]\d{2}[\.\-/]\d{4})",
                    r"DATA ANALIZEI[:\s]*(\d{2}[\.\-/]\d{2}[\.\-/]\d{4})",
                    r"(\d{2}[\.\-/]\d{2}[\.\-/]\d{4})"
                ], required=True),
                DocumentField("laborator", [
                    r"LABORATOR[:\s]+([A-ZĂÂÎȘȚ\s\.,]+)",
                    r"LAB[:\s]+([A-ZĂÂÎȘȚ\s\.,]+)"
                ], required=False),
                DocumentField("medic", [
                    r"DR[\.\s]+([A-ZĂÂÎȘȚ\s]+)",
                    r"MEDIC[:\s]+([A-ZĂÂÎȘȚ\s]+)"
                ], required=False)
            ],
            post_processing_rules={
                "extract_test_results": True,
                "identify_abnormal_values": True,
                "map_romanian_medical_terms": True
            }
        )
    
    @staticmethod
    def get_prescription_template() -> DocumentTemplate:
        """Romanian prescription template"""
        return DocumentTemplate(
            template_id="ro_prescription",
            document_type="prescription",
            language="romanian",
            confidence_threshold=60,
            identification_patterns=[
                r"REȚETĂ|PRESCRIPȚIE",
                r"MEDICAMENT|TRATAMENT",
                r"DOZA|ADMINISTRARE",
                r"DR\.|MEDIC",
                r"PARACETAMOL|ASPIRIN|IBUPROFEN"
            ],
            extraction_fields=[
                DocumentField("nume_pacient", [
                    r"PENTRU[:\s]+([A-ZĂÂÎȘȚ\s]+)",
                    r"PACIENT[:\s]+([A-ZĂÂÎȘȚ\s]+)"
                ], required=True),
                DocumentField("data_prescriere", [
                    r"DATA[:\s]*(\d{2}[\.\-/]\d{2}[\.\-/]\d{4})"
                ], required=True),
                DocumentField("medic_prescriptor", [
                    r"DR[\.\s]+([A-ZĂÂÎȘȚ\s]+)",
                    r"MEDIC[:\s]+([A-ZĂÂÎȘȚ\s]+)"
                ], required=True)
            ],
            post_processing_rules={
                "extract_medications": True,
                "parse_dosage_instructions": True,
                "identify_controlled_substances": True
            }
        )

    @staticmethod
    def get_all_templates() -> List[DocumentTemplate]:
        """Get all available Romanian document templates"""
        return [
            RomanianDocumentTemplates.get_romanian_id_template(),
            RomanianDocumentTemplates.get_lab_result_template(),
            RomanianDocumentTemplates.get_prescription_template()
        ]

class RomanianMedicalTerms:
    """Romanian medical terminology for OCR enhancement"""
    
    MEDICAL_TESTS = {
        "hemoglobină": "hemoglobin",
        "hematocrit": "hematocrit", 
        "leucocite": "white_blood_cells",
        "eritrocite": "red_blood_cells",
        "trombocite": "platelets",
        "glicemie": "blood_glucose",
        "colesterol": "cholesterol",
        "trigliceride": "triglycerides",
        "creatinină": "creatinine",
        "uree": "urea",
        "bilirubină": "bilirubin",
        "transaminaze": "transaminases",
        "proteina c reactivă": "c_reactive_protein",
        "viteza sedimentării": "erythrocyte_sedimentation_rate"
    }
    
    UNITS = {
        "mg/dL": "milligrams per deciliter",
        "g/dL": "grams per deciliter", 
        "μL": "microliters",
        "mmol/L": "millimoles per liter",
        "U/L": "units per liter",
        "ng/mL": "nanograms per milliliter",
        "μg/mL": "micrograms per milliliter"
    }
    
    REFERENCE_TERMS = {
        "normal": "normal",
        "patologic": "abnormal",
        "scăzut": "low",
        "crescut": "high", 
        "în limite normale": "within_normal_limits",
        "peste limita normală": "above_normal",
        "sub limita normală": "below_normal"
    }
    
    COMMON_MEDICATIONS = {
        "paracetamol": "acetaminophen",
        "ibuprofen": "ibuprofen",
        "aspirin": "aspirin",
        "amoxicilină": "amoxicillin",
        "diclofenac": "diclofenac",
        "metamizol": "metamizole",
        "omeprazol": "omeprazole",
        "enalapril": "enalapril"
    }