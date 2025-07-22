"""Document processing service for type detection and data extraction"""

def detect_document_type(text):
    """Detect document type based on OCR text (supports Romanian and English)"""
    text_lower = text.lower()
    
    # Romanian terms for document types
    romanian_terms = {
        "lab_result": ["laborator", "analize", "sânge", "hemoglobină", "glicemie", "colesterol", "rezultate"],
        "xray": ["raze-x", "radiografie", "torace", "plămân", "fractură", "oase"],
        "ct_scan": ["tomografie", "computer", "contrast", "ct"],
        "mri": ["rezonanță", "magnetică", "creier", "coloană", "articulație"],
        "ultrasound": ["ecografie", "doppler", "fetal", "abdomen"],
        "mammography": ["mamografie", "sân"],
        "endoscopy": ["endoscopie", "colonoscopie", "gastroscopie", "biopsie"],
        "ecg": ["electrocardiogramă", "cardiac", "inimă", "ritm"],
        "discharge_note": ["externare", "rezumat", "spital", "internare"],
        "prescription": ["rețetă", "medicament", "doză", "farmacie", "tratament"],
        "consultation": ["consultație", "vizită", "examinare", "diagnostic"],
        "surgical_report": ["chirurgie", "operație", "procedură", "chirurgical"],
        "pathology_report": ["patologie", "histologie", "țesut", "probă"]
    }
    
    # English terms
    english_terms = {
        "lab_result": ["lab", "blood", "test results", "hemoglobin", "glucose", "cholesterol"],
        "xray": ["x-ray", "xray", "radiography", "chest", "lung", "fracture"],
        "ct_scan": ["ct", "computed tomography", "scan", "contrast"],
        "mri": ["mri", "magnetic resonance", "brain", "spine", "joint"],
        "ultrasound": ["ultrasound", "ultrasonography", "echo", "doppler", "fetal"],
        "mammography": ["mammography", "mammogram", "breast"],
        "endoscopy": ["endoscopy", "colonoscopy", "gastroscopy", "biopsy"],
        "ecg": ["ecg", "electrocardiogram", "ekg", "cardiac", "heart rate"],
        "discharge_note": ["discharge", "summary", "hospital", "admission"],
        "prescription": ["prescription", "medication", "dosage", "pharmacy"],
        "consultation": ["consultation", "visit", "examination", "diagnosis"],
        "surgical_report": ["surgery", "operation", "procedure", "surgical"],
        "pathology_report": ["pathology", "histology", "tissue", "specimen"]
    }
    
    # Check both Romanian and English terms
    for doc_type in romanian_terms:
        if any(term in text_lower for term in romanian_terms[doc_type]):
            return doc_type
        if any(term in text_lower for term in english_terms.get(doc_type, [])):
            return doc_type
    
    return "general"

def extract_structured_data(text, doc_type):
    """Extract structured data based on document type (Romanian + English support)"""
    # Mock structured data extraction - we'll enhance this with LLM later
    
    if doc_type == "lab_result":
        # Support both Romanian and English lab results
        if "pacient" in text.lower() or "romanian" in text.lower():
            return {
                "patient_name": "Ion Popescu",
                "test_date": "15.01.2024",
                "lab_id": "LAB001",
                "results": {
                    "hemoglobina": "14,2 g/dL",
                    "leucocite": "7.500 /μL",
                    "trombocite": "250.000 /μL",
                    "glicemia": "95 mg/dL"
                },
                "language": "ro"
            }
        else:
            return {
                "patient_name": "John Doe",
                "test_date": "2024-01-15",
                "lab_id": "LAB001",
                "results": {
                    "hemoglobin": "14.2 g/dL",
                    "wbc": "7,500 /μL",
                    "platelets": "250,000 /μL"
                },
                "language": "en"
            }
    
    elif doc_type in ["xray", "ct_scan", "mri", "ultrasound", "mammography"]:
        return {
            "imaging_type": doc_type,
            "patient_name": "Extracted from OCR",
            "study_date": "2024-01-15",
            "findings": "Normal study" if "normal" in text.lower() else "Findings noted",
            "radiologist": "Dr. Radiolog"
        }
    
    elif doc_type == "prescription":
        return {
            "patient_name": "Extracted from OCR",
            "medications": ["Medication 1", "Medication 2"],
            "prescribing_doctor": "Dr. Doctor",
            "date": "2024-01-15"
        }
    
    elif doc_type == "consultation":
        return {
            "patient_name": "Extracted from OCR",
            "consultation_date": "2024-01-15",
            "chief_complaint": "Patient symptoms",
            "diagnosis": "Clinical diagnosis",
            "doctor": "Dr. Doctor"
        }
    
    return {"type": doc_type, "status": "processed", "language": "auto-detected"}