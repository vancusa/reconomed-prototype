"""Enhanced OCR processing with Romanian template recognition"""
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pytesseract
from PIL import Image
import io

from app.services.romanian_document_templates import (
    RomanianDocumentTemplates, DocumentTemplate, RomanianMedicalTerms
)
from app.services.ocr import preprocess_image_aggressive, estimate_text_quality
from app.services.romanian_id_processor import MultiTemplateIDProcessor, RomanianIDType
from app.utils.romanian_validation import validate_cnp

@dataclass
class TemplateMatchResult:
    template_id: str
    document_type: str
    confidence: float
    matched_patterns: List[str]
    extracted_data: Dict[str, Any]

@dataclass
class EnhancedOCRResult:
    raw_text: str
    template_match: Optional[TemplateMatchResult]
    structured_data: Dict[str, Any]
    confidence_score: int
    processing_metadata: Dict[str, Any]

class RomanianOCRProcessor:
    """Enhanced OCR processor with Romanian document intelligence"""
    
    def __init__(self):
        self.templates = RomanianDocumentTemplates.get_all_templates()
        self.medical_terms = RomanianMedicalTerms()
        
    def process_document(self, image_input, hint_document_type: Optional[str] = None) -> EnhancedOCRResult:
        """Process document with Romanian template recognition"""
        
        # Step 1: Enhanced OCR with Romanian language optimization
        raw_text, ocr_confidence = self._extract_text_romanian_optimized(image_input)
        
        # Step 2: Template matching
        template_match = self._match_document_template(raw_text, hint_document_type)
        
        # Step 3: Structured data extraction
        structured_data = {}
        if template_match:
            structured_data = self._extract_structured_data(raw_text, template_match.template_id)
            # Apply post-processing rules
            structured_data = self._apply_post_processing(structured_data, template_match.template_id)
        
        # Step 4: Medical term enhancement
        if template_match and template_match.document_type in ["lab_result", "prescription"]:
            structured_data = self._enhance_with_medical_terms(structured_data, raw_text)
        
        # Step 5: Calculate final confidence
        final_confidence = self._calculate_final_confidence(
            ocr_confidence, template_match, structured_data
        )
        
        return EnhancedOCRResult(
            raw_text=raw_text,
            template_match=template_match,
            structured_data=structured_data,
            confidence_score=final_confidence,
            processing_metadata={
                "ocr_confidence": ocr_confidence,
                "template_confidence": template_match.confidence if template_match else 0,
                "processing_time": "calculated_in_real_implementation",
                "language_detected": "romanian",
                "medical_terms_found": len(self._find_medical_terms(raw_text))
            }
        )
    
    def _extract_text_romanian_optimized(self, image_input) -> Tuple[str, int]:
        """OCR extraction optimized for Romanian text"""
        try:
            
            print(f"DEBUG OCR: Input type: {type(image_input)}")
            #print(f"DEBUG OCR: Input length: {len(image_input) if isinstance(image_input, bytes) else 'not bytes'}")
            
            # Convert bytes to BytesIO
            if isinstance(image_input, bytes):
                bio = io.BytesIO(image_input)
                #print(f"DEBUG OCR: Created BytesIO, length: {len(image_input)}")
            else:
                bio = image_input
            
            # Reset position
            bio.seek(0)
            
            # Try to open with PIL - this is where it's failing
            try:
                image = Image.open(bio)
                #print(f"DEBUG OCR: PIL opened image: {image.format}, {image.size}, {image.mode}")
            except Exception as pil_error:
                #print(f"DEBUG OCR: PIL failed: {pil_error}")
                # Check if it's actually image data
                bio.seek(0)
                first_bytes = bio.read(10)
                #print(f"DEBUG OCR: First 10 bytes: {first_bytes}")
                raise    

            # Store for ID processor
            self._current_image = image
              
            # Now use the preprocessing functions with the PIL image
            processed_image = preprocess_image_aggressive(image)
            
            # Romanian-specific OCR configuration
            romanian_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
            
            # Try Romanian + English combination for medical documents
            text_ro_en = pytesseract.image_to_string(
                processed_image,
                lang='ron+eng',
                config=romanian_config
            )
            
            # Fallback to English-only if Romanian fails
            if len(text_ro_en.strip()) < 50:
                text_en = pytesseract.image_to_string(
                    processed_image,
                    lang='eng',
                    config=romanian_config
                )
                if len(text_en) > len(text_ro_en):
                    text_ro_en = text_en
            
            # Clean up common OCR errors in Romanian
            cleaned_text = self._clean_romanian_ocr_errors(text_ro_en)
            
            # Estimate confidence
            confidence = estimate_text_quality(cleaned_text)
            
            return cleaned_text, confidence
            
        except Exception as e:
            print(f"DEBUG OCR: Full exception: {e}")
            # Fallback to basic OCR
            return self._basic_fallback_ocr(image_input)
    
    def _clean_romanian_ocr_errors(self, text: str) -> str:
        """Clean common OCR errors in Romanian text"""
        corrections = {
            # Common character misrecognitions
            'ã': 'ă',
            'â': 'â',
            'î': 'î', 
            'ş': 'ș',
            'ţ': 'ț',
            # Common word corrections
            r'\bCNF\b': 'CNP',
            r'\bPACIENT\b': 'PACIENT',
            r'\bRESULTATE\b': 'REZULTATE',
            r'\bLABDRATDR\b': 'LABORATOR',
            r'\bHEMDGLDBINA\b': 'HEMOGLOBINĂ',
            # Fix common spacing issues
            r'(\d)\s+(\d)': r'\1\2',  # Remove spaces in numbers
            r'([A-ZĂÂÎȘȚ])\s+([a-zăâîșț])': r'\1\2',  # Fix broken words
        }
        
        cleaned_text = text
        for pattern, replacement in corrections.items():
            cleaned_text = re.sub(pattern, replacement, cleaned_text, flags=re.IGNORECASE)
        
        return cleaned_text
    
    def _match_document_template(self, text: str, hint_type: Optional[str] = None) -> Optional[TemplateMatchResult]:
        """Match document against Romanian templates"""
        best_match = None
        best_score = 0
        
        # Prioritize hinted template
        templates = self.templates
        if hint_type:
            templates = [t for t in self.templates if t.document_type == hint_type] + \
                       [t for t in self.templates if t.document_type != hint_type]
        
        for template in templates:
            score, matched_patterns = self._calculate_template_score(text, template)
            
            if score > best_score and score >= template.confidence_threshold:
                best_score = score
                best_match = TemplateMatchResult(
                    template_id=template.template_id,
                    document_type=template.document_type,
                    confidence=score,
                    matched_patterns=matched_patterns,
                    extracted_data={}
                )
        
        return best_match
    
    def _calculate_template_score(self, text: str, template: DocumentTemplate) -> Tuple[float, List[str]]:
        """Calculate how well text matches a template"""
        text_upper = text.upper()
        matched_patterns = []
        total_patterns = len(template.identification_patterns)
        
        for pattern in template.identification_patterns:
            if re.search(pattern, text_upper, re.IGNORECASE):
                matched_patterns.append(pattern)
        
        # Base score from pattern matching
        pattern_score = (len(matched_patterns) / total_patterns) * 100
        
        # Boost score for medical documents with medical terms
        if template.document_type in ["lab_result", "prescription"]:
            medical_terms_found = len(self._find_medical_terms(text))
            medical_boost = min(medical_terms_found * 5, 20)  # Max 20 point boost
            pattern_score += medical_boost
        
        return min(pattern_score, 100), matched_patterns
    
    def _find_medical_terms(self, text: str) -> List[str]:
        """Find Romanian medical terms in text"""
        text_lower = text.lower()
        found_terms = []
        
        # Check medical tests
        for romanian_term, english_term in self.medical_terms.MEDICAL_TESTS.items():
            if romanian_term in text_lower:
                found_terms.append(romanian_term)
        
        # Check medications
        for romanian_term, english_term in self.medical_terms.COMMON_MEDICATIONS.items():
            if romanian_term in text_lower:
                found_terms.append(romanian_term)
        
        return found_terms
    
    def _extract_structured_data(self, text: str, template_id: str) -> Dict[str, Any]:
        """Extract structured data using template patterns"""
        template = next(t for t in self.templates if t.template_id == template_id)
        extracted_data = {}
        
        # Use Romanian ID processor for ID cards
        if template_id == "ro_identity_card":
            id_processor = MultiTemplateIDProcessor()
            # Convert bytes back to PIL Image for the processor
            if hasattr(self, '_current_image'):
                id_results = id_processor.process_id_card(self._current_image)
                return id_results["extracted_fields"]

        for field in template.extraction_fields:
            field_value = None
            
            # Try each pattern for this field
            for pattern in field.patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    field_value = match.group(1).strip()
                    break
            
            # Apply field-specific validation if available
            if field_value and field.validation_func:
                if field.validation_func == "validate_cnp":
                    is_valid, error = validate_cnp(field_value)
                    if is_valid:
                        extracted_data[field.field_name] = field_value
                        extracted_data[f"{field.field_name}_valid"] = True
                    else:
                        extracted_data[f"{field.field_name}_error"] = error
                        extracted_data[f"{field.field_name}_valid"] = False
            elif field_value:
                extracted_data[field.field_name] = field_value
        
        # Extract additional data for specific document types
        if template_id == "ro_lab_results":
            extracted_data["test_results"] = self._extract_lab_test_results(text)
        elif template_id == "ro_prescription":
            extracted_data["medications"] = self._extract_medications(text)
        
        return extracted_data
    
    def _extract_lab_test_results(self, text: str) -> List[Dict[str, Any]]:
        """Extract lab test results with values and reference ranges"""
        results = []
        
        # Pattern for test results: "Test Name: Value Unit (Reference: Min-Max)"
        result_pattern = r'([A-ZĂÂÎȘȚ][a-zăâîșț\s]+)[\s:]+([0-9.,]+)\s*([a-zA-Z/μ]+)?\s*(?:\([^)]*(\d+[\.,]?\d*)\s*[-–]\s*(\d+[\.,]?\d*)[^)]*\))?'
        
        matches = re.finditer(result_pattern, text, re.MULTILINE)
        
        for match in matches:
            test_name = match.group(1).strip()
            value = match.group(2).replace(',', '.')
            unit = match.group(3) or ""
            ref_min = match.group(4)
            ref_max = match.group(5)
            
            # Normalize Romanian test names
            normalized_name = self._normalize_test_name(test_name)
            
            result_data = {
                "test_name": test_name,
                "normalized_name": normalized_name,
                "value": value,
                "unit": unit,
                "reference_min": ref_min,
                "reference_max": ref_max,
                "status": self._determine_result_status(value, ref_min, ref_max) if ref_min and ref_max else "unknown"
            }
            
            results.append(result_data)
        
        return results
    
    def _normalize_test_name(self, test_name: str) -> str:
        """Normalize Romanian test name to standard format"""
        test_lower = test_name.lower().strip()
        
        # Map Romanian terms to standardized names
        for romanian_term, english_term in self.medical_terms.MEDICAL_TESTS.items():
            if romanian_term in test_lower:
                return english_term
        
        return test_name.lower().replace(' ', '_')
    
    def _determine_result_status(self, value: str, ref_min: str, ref_max: str) -> str:
        """Determine if test result is normal, low, or high"""
        try:
            val = float(value.replace(',', '.'))
            min_val = float(ref_min.replace(',', '.'))
            max_val = float(ref_max.replace(',', '.'))
            
            if val < min_val:
                return "low"
            elif val > max_val:
                return "high"
            else:
                return "normal"
        except ValueError:
            return "unknown"
    
    def _extract_medications(self, text: str) -> List[Dict[str, Any]]:
        """Extract medication information from prescription"""
        medications = []
        
        # Pattern for medications with dosage
        med_pattern = r'([A-ZĂÂÎȘȚ][a-zăâîșț]+)\s*(\d+\s*mg|mg)?\s*(?:(\d+)\s*(?:tablete|capsule|comprimate))?'
        
        matches = re.finditer(med_pattern, text, re.MULTILINE)
        
        for match in matches:
            medication_name = match.group(1).strip()
            dosage = match.group(2) or ""
            quantity = match.group(3) or ""
            
            # Check if it's a known medication
            normalized_name = None
            for romanian_med, english_med in self.medical_terms.COMMON_MEDICATIONS.items():
                if romanian_med.lower() in medication_name.lower():
                    normalized_name = english_med
                    break
            
            med_data = {
                "medication_name": medication_name,
                "normalized_name": normalized_name,
                "dosage": dosage,
                "quantity": quantity,
                "recognized": normalized_name is not None
            }
            
            medications.append(med_data)
        
        return medications
    
    def _apply_post_processing(self, data: Dict[str, Any], template_id: str) -> Dict[str, Any]:
        """Apply template-specific post-processing rules"""
        template = next(t for t in self.templates if t.template_id == template_id)
        
        if not template.post_processing_rules:
            return data
        
        processed_data = data.copy()
        
        # Apply normalization rules
        if template.post_processing_rules.get("normalize_names"):
            for field in ["nume", "prenume", "nume_pacient"]:
                if field in processed_data:
                    processed_data[field] = self._normalize_romanian_name(processed_data[field])
        
        # Validate CNP consistency with birth date
        if template.post_processing_rules.get("validate_cnp_date_consistency"):
            if "cnp" in processed_data and "data_nasterii" in processed_data:
                consistency_check = self._validate_cnp_date_consistency(
                    processed_data["cnp"], processed_data["data_nasterii"]
                )
                processed_data["cnp_date_consistent"] = consistency_check
        
        # Extract gender from CNP
        if template.post_processing_rules.get("extract_gender_from_cnp"):
            if "cnp" in processed_data:
                from app.utils.romanian_validation import extract_gender_from_cnp
                gender = extract_gender_from_cnp(processed_data["cnp"])
                if gender:
                    processed_data["gender"] = gender
        
        return processed_data
    
    def _normalize_romanian_name(self, name: str) -> str:
        """Normalize Romanian names"""
        if not name:
            return ""
        
        # Title case with Romanian character handling
        words = name.strip().split()
        normalized_words = []
        
        for word in words:
            if len(word) > 0:
                normalized_word = word[0].upper() + word[1:].lower()
                normalized_words.append(normalized_word)
        
        return " ".join(normalized_words)
    
    def _validate_cnp_date_consistency(self, cnp: str, birth_date: str) -> bool:
        """Validate that CNP and birth date are consistent"""
        try:
            from app.utils.romanian_validation import extract_birth_date_from_cnp
            cnp_date = extract_birth_date_from_cnp(cnp)
            
            if not cnp_date:
                return False
            
            # Normalize birth date format
            normalized_birth_date = self._normalize_date(birth_date)
            
            return cnp_date == normalized_birth_date
        except Exception:
            return False
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to YYYY-MM-DD format"""
        if not date_str:
            return ""
        
        # Handle different date formats
        date_patterns = [
            r'(\d{2})[\.\-/](\d{2})[\.\-/](\d{4})',  # DD.MM.YYYY
            r'(\d{4})[\.\-/](\d{2})[\.\-/](\d{2})',  # YYYY.MM.DD
        ]
        
        for pattern in date_patterns:
            match = re.match(pattern, date_str.strip())
            if match:
                if len(match.group(1)) == 4:  # YYYY format first
                    return f"{match.group(1)}-{match.group(2):0>2}-{match.group(3):0>2}"
                else:  # DD format first
                    return f"{match.group(3)}-{match.group(2):0>2}-{match.group(1):0>2}"
        
        return date_str
    
    def _enhance_with_medical_terms(self, data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """Enhance data with medical term recognition"""
        enhanced_data = data.copy()
        
        # Find and classify medical terms
        found_medical_terms = self._find_medical_terms(raw_text)
        enhanced_data["recognized_medical_terms"] = found_medical_terms
        
        # Add medical context flags
        enhanced_data["contains_lab_tests"] = any(
            term in self.medical_terms.MEDICAL_TESTS for term in found_medical_terms
        )
        enhanced_data["contains_medications"] = any(
            term in self.medical_terms.COMMON_MEDICATIONS for term in found_medical_terms
        )
        
        return enhanced_data
    
    def _calculate_final_confidence(
        self, 
        ocr_confidence: int, 
        template_match: Optional[TemplateMatchResult], 
        structured_data: Dict[str, Any]
    ) -> int:
        """Calculate final confidence score"""
        base_confidence = ocr_confidence
        
        # Template matching bonus
        if template_match:
            template_bonus = min(template_match.confidence * 0.3, 20)
            base_confidence += template_bonus
        
        # Structured data extraction bonus
        if structured_data:
            extraction_bonus = min(len(structured_data) * 2, 15)
            base_confidence += extraction_bonus
        
        # Medical term recognition bonus
        if structured_data.get("recognized_medical_terms"):
            medical_bonus = min(len(structured_data["recognized_medical_terms"]) * 3, 10)
            base_confidence += medical_bonus
        
        return min(int(base_confidence), 100)
    
    def _basic_fallback_ocr(self, image_input) -> Tuple[str, int]:
        """Fallback OCR processing"""
        try:
            from app.services.ocr import extract_text_from_image
            text = extract_text_from_image(image_input)
            confidence = estimate_text_quality(text)
            return text, confidence
        except Exception as e:
            return f"OCR processing failed: {str(e)}", 0