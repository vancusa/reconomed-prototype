"""Enhanced OCR processing with Romanian template recognition"""
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pytesseract
from PIL import Image
import io
import numpy as np
from typing import Optional
import logging
audit_logger = logging.getLogger("reconomed.audit")
app_logger = logging.getLogger("reconomed.app")

from app.services.romanian_document_templates import (RomanianDocumentTemplates, DocumentTemplate, RomanianMedicalTerms)
#from app.services.ocr import preprocess_image_aggressive, estimate_text_quality
#from app.services.romanian_id_processor import MultiTemplateIDProcessor, RomanianIDType
#from app.utils.romanian_validation import validate_cnp

from app.services.romanian_document_templates import RomanianDocumentTemplates
#from app.services.medical_terms import RomanianMedicalTerms
#from app.models.enhanced_ocr import EnhancedOCRResult, TemplateMatchResult, DocumentTemplate
from app.utils.romanian_validation import validate_cnp, extract_gender_from_cnp, extract_birth_date_from_cnp
from app.services.ocr import extract_text_confidence

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
        self._current_image = None

    def process_document(self, image_input, hint_document_type: Optional[str] = None) -> 'EnhancedOCRResult':
        """Process document with layout-first approach"""

        print(f"DEBUG process_document 1: entered the function")
        # Normalize hint types
        hint_document_type = self._normalize_hint(hint_document_type)

        # Normalize input
        image = self._normalize_input_to_image(image_input)

        print(f"DEBUG process_document 2: finish normalizations")
        
        # Layout detection
        detected_layout, document_subtype = self._detect_document_layout(image)
        #detected_layout = self._detect_document_layout(image)
        print(f"DEBUG process_document 3: finished detect_layout and is ID {detected_layout} with the type {document_subtype}")

        # If explicit hint overrides layout
        #if hint_document_type == "romanian_id":
        #    detected_layout = "romanian_id"

        if detected_layout == "romanian_id":
            try:
                from app.services.romanian_id_processor import MultiTemplateIDProcessor
                id_processor = MultiTemplateIDProcessor()
                id_results = id_processor.process_id_card(image)
            except Exception as e:
                import traceback
                print(f"TRACE LAYOUT ERROR: {repr(e)}")
                traceback.print_exc()
                raise

            template_match = TemplateMatchResult(
                template_id="ro_identity_card",
                document_type="romanian_id",
                confidence=id_results.get("overall_confidence", 0),
                matched_patterns=["layout_detection"],
                extracted_data=id_results.get("extracted_fields", {})
            )

            structured = id_results.get("extracted_fields", {})
            conf = int(id_results.get("overall_confidence", 0)) if id_results.get("overall_confidence") is not None else 0

            return EnhancedOCRResult(
                raw_text="",
                template_match=template_match,
                structured_data=structured,
                confidence_score=conf,
                processing_metadata={
                    "processing_method": "region_based_extraction",
                    "card_type": id_results.get("card_type", "unknown"),
                    "regions_processed": len(structured)
                }
            )

        # fallback OCR
        return self._process_with_full_ocr(image, hint_document_type)

    # ----------------- Input Normalization ------------------

    def _normalize_hint(self, hint: Optional[str]) -> Optional[str]:
        if not hint:
            return None
        mapping = {
            "carte_identitate": "romanian_id",
            "carte_electronica": "romanian_id",
            "buletin_identitate": "romanian_id",
            "romanian_id": "romanian_id",
            "ro_identity_card": "romanian_id",
        }
        return mapping.get(hint, hint)

    def _normalize_input_to_image(self, image_input) -> Image.Image:
        """Ensure we have a PIL.Image.Image"""
        if isinstance(image_input, bytes):
            try:
                image = Image.open(io.BytesIO(image_input))
                image.load()
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                return image
            except Exception as e:
                print(f"Input bytes could not be opened by PIL: {repr(e)}")
                raise
        elif isinstance(image_input, Image.Image):
            img_copy = image_input.copy()
            if img_copy.mode not in ("RGB", "L"):
                img_copy = img_copy.convert("RGB")
            return img_copy
        else:
            raise TypeError(f"Unsupported input type for OCR: {type(image_input)}")

    # ----------------- Layout Detection ---------------------

    def _detect_document_layout(self, image: Image.Image) -> Tuple[str, Optional[str]]
        """
            Detect the document layout type before OCR. 

            Input:
                image (PIL.Image): Input document image.

            Output:
                Tuple[str, Optional[str]]:
                str --> the actual detected layout
                    values:
                        "romanian_id" - romanian ID
                        "lab_result" - known formats for the big labs: Bioclinica, Synevo, Golea, Regina Maria
                        "unknown"  - for example a hospital discharge note or some other stuff
                Optional[str] --> specific subtype
                        For IDs: "electronic_id" | "standard_id"
                        For labs: "Bioclinica" | "Synevo" | "Golea" | "Regina Maria"
            
            Notes on future versions:
                Replace heuristic _is_card_shaped / _detect_photo_region / _detect_lab_header checks with a CNN or transformer-based document layout classifier.
                This would improve determinism, handle new templates, and adapt to noisy scans.
        """
    app_logger.debug("Entering detect_document_layout")

    try:
        # Get dimensions
        width, height = image.size
        app_logger.debug(f"Image size: width={width}, height={height}")

        # Convert to numpy (could be optimized later)
        img_array = np.array(image)
        app_logger.debug("Converted image to numpy array")

        # --- Step 1: Romanian ID detection ---
        is_card_shaped = self._is_card_shaped(width, height)
        app_logger.debug(f"is_card_shaped={is_card_shaped}")

        has_photo = self._detect_photo_region(img_array)
        lapp_logger.debug(f"has_photo={has_photo}")

        has_id_layout = self._has_structured_text_blocks(img_array)
        app_logger.debug(f"has_id_layout={has_id_layout}")

        if is_card_shaped and has_photo and has_id_layout:
            id_type = self._classify_romanian_id_type(image)
            app_logger.info(f"Detected Romanian ID: {id_type}")
            return "romanian_id", id_type

        # --- Step 2: Lab result detection ---
        has_lab_header = self._detect_lab_header(img_array)
        app_logger.debug(f"has_lab_header={has_lab_header}")

        if has_lab_header:
            lab_type = self._classify_lab_type(image)
            app_logger.info(f"Detected lab result: {lab_type}")
            return "lab_result", lab_type

        # --- Step 3: Fallback ---
        app_logger.info("Document layout unknown")
        return "unknown", None

    except Exception as e:
        # Defensive fallback in case helpers break
        logging.error(f"Layout detection failed: {e}", exc_info=True)
        return "unknown", None





"""

        width, height = image.size
        aspect_ratio = width / height
        img_array = np.array(image)

        photo_detected = self._detect_photo_region(img_array)
        is_card_shaped = 1.3 < aspect_ratio < 1.8
        has_structured_layout = self._detect_structured_text_blocks(img_array)
        has_official_colors = self._detect_official_document_colors(image)

        if photo_detected and is_card_shaped and has_structured_layout:
            return "romanian_id"
        elif has_official_colors and has_structured_layout:
            return "official_document"
        else:
            return "unknown_document"
"""

    def _detect_photo_region(self, img_array) -> bool:
        height, width = img_array.shape[:2]
        left_region = img_array[:, :int(width * 0.3)]
        if len(left_region.shape) == 3:
            left_gray = np.mean(left_region, axis=2)
        else:
            left_gray = left_region
        dark_pixel_ratio = np.sum(left_gray < 120) / left_gray.size
        edges = np.gradient(left_gray)
        edge_magnitude = np.sqrt(edges[0]**2 + edges[1]**2)
        strong_edges = np.sum(edge_magnitude > 30) / edge_magnitude.size
        return dark_pixel_ratio > 0.15 and strong_edges > 0.05

    def _detect_structured_text_blocks(self, img_array) -> bool:
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2)
        else:
            gray = img_array
        edges = np.gradient(gray)
        edge_magnitude = np.sqrt(edges[0]**2 + edges[1]**2)
        horizontal_lines = np.sum(edge_magnitude > 20, axis=1)
        text_rows = np.sum(horizontal_lines > gray.shape[1] * 0.1)
        return text_rows > 3

    def _detect_official_document_colors(self, image: Image.Image) -> bool:
        width, height = image.size
        top_region = image.crop((0, 0, width, int(height * 0.2)))
        top_array = np.array(top_region)
        if len(top_array.shape) == 3:
            blue_pixels = np.sum((top_array[:,:,2] > 100) & (top_array[:,:,0] < 100))
            red_pixels = np.sum((top_array[:,:,0] > 150) & (top_array[:,:,1] < 100))
            total_pixels = top_array.shape[0] * top_array.shape[1]
            official_color_ratio = (blue_pixels + red_pixels) / total_pixels
            return official_color_ratio > 0.05
        return False

    # ----------------- OCR Core -----------------------------

    def _extract_text_romanian_optimized(self, image_input) -> Tuple[str, int]:
        try:
            print(f"DEBUG OCR RO 1: Starting Romanian OCR")
            if isinstance(image_input, bytes):
                bio = io.BytesIO(image_input)
                print(f"DEBUG OCR RO 2.1: Created BytesIO")
                bio.seek(0)
                print(f"DEBUG OCR RO 2.1: Done seek")
                image = Image.open(bio)
                image.load()
                print(f"DEBUG OCR RO 2.1: Done open")
            elif isinstance(image_input, Image.Image):
                image = image_input
                print(f"DEBUG OCR RO 2.2: Using PIL Image directly")
            else:
                raise TypeError("Unsupported type for _extract_text_romanian_optimized")

            self._current_image = image.copy()
            processed_image = image
            print (f"DEBUG OCR RO 2.3: done copying the image to processed_image")

            romanian_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
            text_ro_en = pytesseract.image_to_string(processed_image, lang='ron+eng', config=romanian_config)
            print(f"DEBUG OCR RO 2.4: Pytesseract completed, got {len(text_ro_en)} chars")

            if len(text_ro_en.strip()) < 20:              #IS THIS THRESHOLD OK TO BE HARDCODED????????????
                print (f"DEBUG OCR RO 2.5: Less then 20, try english")
                text_en = pytesseract.image_to_string(processed_image, lang='eng', config=romanian_config)
                if len(text_en) > len(text_ro_en):
                    text_ro_en = text_en

            cleaned_text = self._clean_romanian_ocr_errors(text_ro_en)
            confidence = estimate_text_quality(cleaned_text) if 'estimate_text_quality' in globals() else min(100, max(0, int(len(cleaned_text.strip())/2)))
            print(f"DEBUG OCR RO 2.6: {cleaned_text}")
            print(f"DEBUG OCR RO 2.7: Confidence: {confidence}")

            return cleaned_text, int(confidence)

        except Exception as e:
            print(f"DEBUG OCR 1: Full exception in optimized extractor: {repr(e)}")
            import traceback
            traceback.print_exc()
            return self._basic_fallback_ocr(image_input)

    def _clean_romanian_ocr_errors(self, text: str) -> str:
        corrections = {
            'ã': 'ă', 'â': 'â', 'î': 'î', 'ş': 'ș', 'ţ': 'ț',
            r'\bCNF\b': 'CNP', r'\bPACIENT\b': 'PACIENT', r'\bRESULTATE\b': 'REZULTATE',
            r'\bLABDRATDR\b': 'LABORATOR', r'\bHEMDGLDBINA\b': 'HEMOGLOBINĂ',
            r'(\d)\s+(\d)': r'\1\2',
            r'([A-ZĂÂÎȘȚ])\s+([a-zăâîșț])': r'\1\2',
        }
        cleaned = text
        for pat, rep in corrections.items():
            cleaned = re.sub(pat, rep, cleaned, flags=re.IGNORECASE)
        return cleaned

    # ----------------- Template Matching -------------------

    def _match_document_template(self, text: str, hint_type: Optional[str] = None) -> Optional['TemplateMatchResult']:
        best_match, best_score = None, 0
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

    def _calculate_template_score(self, text: str, template: 'DocumentTemplate') -> Tuple[float, List[str]]:
        text_upper = text.upper()
        matched = []
        for pattern in template.identification_patterns:
            if re.search(pattern, text_upper, re.IGNORECASE):
                matched.append(pattern)
        pattern_score = (len(matched) / len(template.identification_patterns)) * 100
        if template.document_type in ["lab_result", "prescription"]:
            medical_terms_found = len(self._find_medical_terms(text))
            pattern_score += min(medical_terms_found * 5, 20)
        return min(pattern_score, 100), matched

    def _find_medical_terms(self, text: str) -> List[str]:
        text_lower = text.lower()
        found = []
        for ro, en in self.medical_terms.MEDICAL_TESTS.items():
            if ro in text_lower:
                found.append(ro)
        for ro, en in self.medical_terms.COMMON_MEDICATIONS.items():
            if ro in text_lower:
                found.append(ro)
        return found

    # ----------------- Structured Extraction ---------------

    def _extract_structured_data(self, text: str, template_id: str) -> Dict[str, Any]:
        template = next(t for t in self.templates if t.template_id == template_id)
        extracted = {}

        if template_id == "ro_identity_card" and self._current_image is not None:
            from app.services.romanian_id_processor import MultiTemplateIDProcessor
            id_results = MultiTemplateIDProcessor().process_id_card(self._current_image)
            return id_results["extracted_fields"]

        for field in template.extraction_fields:
            value = None
            for pat in field.patterns:
                match = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    break
            if value and field.validation_func == "validate_cnp":
                is_valid, error = validate_cnp(value)
                if is_valid:
                    extracted[field.field_name] = value
                    extracted[f"{field.field_name}_valid"] = True
                else:
                    extracted[f"{field.field_name}_error"] = error
                    extracted[f"{field.field_name}_valid"] = False
            elif value:
                extracted[field.field_name] = value

        if template_id == "ro_lab_results":
            extracted["test_results"] = self._extract_lab_test_results(text)
        elif template_id == "ro_prescription":
            extracted["medications"] = self._extract_medications(text)
        return extracted

    def _extract_lab_test_results(self, text: str) -> List[Dict[str, Any]]:
        results = []
        pat = r'([A-ZĂÂÎȘȚ][a-zăâîșț\s]+)[\s:]+([0-9.,]+)\s*([a-zA-Z/μ]+)?\s*(?:\([^)]*(\d+[\.,]?\d*)\s*[-–]\s*(\d+[\.,]?\d*)[^)]*\))?'
        for m in re.finditer(pat, text, re.MULTILINE):
            test_name, value, unit, ref_min, ref_max = m.group(1).strip(), m.group(2).replace(',', '.'), m.group(3) or "", m.group(4), m.group(5)
            normalized = self._normalize_test_name(test_name)
            results.append({
                "test_name": test_name,
                "normalized_name": normalized,
                "value": value,
                "unit": unit,
                "reference_min": ref_min,
                "reference_max": ref_max,
                "status": self._determine_result_status(value, ref_min, ref_max) if ref_min and ref_max else "unknown"
            })
        return results

    def _normalize_test_name(self, test_name: str) -> str:
        tl = test_name.lower().strip()
        for ro, en in self.medical_terms.MEDICAL_TESTS.items():
            if ro in tl:
                return en
        return tl.replace(' ', '_')

    def _determine_result_status(self, value: str, ref_min: str, ref_max: str) -> str:
        try:
            val, mn, mx = float(value.replace(',', '.')), float(ref_min.replace(',', '.')), float(ref_max.replace(',', '.'))
            if val < mn: return "low"
            elif val > mx: return "high"
            else: return "normal"
        except ValueError:
            return "unknown"

    def _extract_medications(self, text: str) -> List[Dict[str, Any]]:
        meds = []
        pat = r'([A-ZĂÂÎȘȚ][a-zăâîșț]+)\s*(\d+\s*mg|mg)?\s*(?:(\d+)\s*(?:tablete|capsule|comprimate))?'
        for m in re.finditer(pat, text, re.MULTILINE):
            name, dosage, qty = m.group(1).strip(), m.group(2) or "", m.group(3) or ""
            normalized = None
            for ro, en in self.medical_terms.COMMON_MEDICATIONS.items():
                if ro.lower() in name.lower():
                    normalized = en
                    break
            meds.append({"medication_name": name, "normalized_name": normalized, "dosage": dosage, "quantity": qty, "recognized": normalized is not None})
        return meds

    # ----------------- Post Processing ---------------------

    def _apply_post_processing(self, data: Dict[str, Any], template_id: str) -> Dict[str, Any]:
        template = next(t for t in self.templates if t.template_id == template_id)
        if not template.post_processing_rules:
            return data
        processed = data.copy()
        if template.post_processing_rules.get("normalize_names"):
            for f in ["nume", "prenume", "nume_pacient"]:
                if f in processed:
                    processed[f] = self._normalize_romanian_name(processed[f])
        if template.post_processing_rules.get("validate_cnp_date_consistency"):
            if "cnp" in processed and "data_nasterii" in processed:
                processed["cnp_date_consistent"] = self._validate_cnp_date_consistency(processed["cnp"], processed["data_nasterii"])
        if template.post_processing_rules.get("extract_gender_from_cnp"):
            if "cnp" in processed:
                gender = extract_gender_from_cnp(processed["cnp"])
                if gender:
                    processed["gender"] = gender
        return processed

    def _normalize_romanian_name(self, name: str) -> str:
        if not name: return ""
        return " ".join(w[0].upper() + w[1:].lower() for w in name.strip().split() if w)

    def _validate_cnp_date_consistency(self, cnp: str, birth_date: str) -> bool:
        try:
            cnp_date = extract_birth_date_from_cnp(cnp)
            if not cnp_date: return False
            return cnp_date == self._normalize_date(birth_date)
        except Exception:
            return False

    def _normalize_date(self, date_str: str) -> str:
        if not date_str: return ""
        patterns = [r'(\d{2})[\.\-/](\d{2})[\.\-/](\d{4})', r'(\d{4})[\.\-/](\d{2})[\.\-/](\d{2})']
        for pat in patterns:
            m = re.match(pat, date_str.strip())
            if m:
                if len(m.group(1)) == 4:
                    return f"{m.group(1)}-{m.group(2):0>2}-{m.group(3):0>2}"
                else:
                    return f"{m.group(3)}-{m.group(2):0>2}-{m.group(1):0>2}"
        return date_str

    def _enhance_with_medical_terms(self, data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        enhanced = data.copy()
        terms = self._find_medical_terms(raw_text)
        enhanced["recognized_medical_terms"] = terms
        enhanced["contains_lab_tests"] = any(t in self.medical_terms.MEDICAL_TESTS for t in terms)
        enhanced["contains_medications"] = any(t in self.medical_terms.COMMON_MEDICATIONS for t in terms)
        return enhanced

    # ----------------- Confidence + Fallback ----------------

    def _calculate_final_confidence(self, ocr_confidence: int, template_match: Optional['TemplateMatchResult'], structured_data: Dict[str, Any]) -> int:
        base = ocr_confidence
        if template_match:
            base += min(template_match.confidence * 0.3, 20)
        if structured_data:
            base += min(len(structured_data) * 2, 15)
        if structured_data.get("recognized_medical_terms"):
            base += min(len(structured_data["recognized_medical_terms"]) * 3, 10)
        return min(int(base), 100)

    def _basic_fallback_ocr(self, image_input) -> Tuple[str, int]:
        try:
            result = extract_text_confidence(image_input)
            return result['full_text'], result['average_confidence']
        except Exception as e:
            print(f"Fallback OCR also failed: {repr(e)}")
            return f"OCR processing failed: {str(e)}", 0

    def _process_with_full_ocr(self, image: Image.Image, hint_document_type: Optional[str] = None) -> 'EnhancedOCRResult':
        try:
            raw_text, confidence = self._extract_text_romanian_optimized(image)
            template_match = self._match_document_template(raw_text, hint_document_type)
            structured = {}
            if template_match and template_match.document_type != "unknown_document":
                structured = self._extract_structured_data(raw_text, template_match.template_id)
                structured = self._apply_post_processing(structured, template_match.template_id)
                structured = self._enhance_with_medical_terms(structured, raw_text)
            final_conf = self._calculate_final_confidence(confidence, template_match, structured)
            return EnhancedOCRResult(
                raw_text=raw_text,
                template_match=template_match,
                structured_data=structured,
                confidence_score=int(final_conf),
                processing_metadata={"method": "full_ocr_fallback"}
            )
        except Exception as e:
            print(f"_process_with_full_ocr error: {repr(e)}")
            import traceback
            traceback.print_exc()
            text, conf = self._basic_fallback_ocr(image)
            return EnhancedOCRResult(
                raw_text=text,
                template_match=None,
                structured_data={},
                confidence_score=int(conf),
                processing_metadata={"method": "basic_fallback"}
            )

    """Enhanced OCR processor with Romanian document intelligence"""
    
    def __init__(self):
        self.templates = RomanianDocumentTemplates.get_all_templates()
        self.medical_terms = RomanianMedicalTerms()
    
    def process_document(self, image_input, hint_document_type: Optional[str] = None) -> EnhancedOCRResult:
        """Process document with layout-first approach"""
        print(f"DEBUG PD1: we are inside services - enchanced_ocr - class RomanianOCRProcessor - function process_document")
        # Convert bytes to PIL Image once
        if isinstance(image_input, bytes):
            image = Image.open(io.BytesIO(image_input))
            print(f"DEBUG PD2: check if image is bytes")
        else:
            image = image_input
            print(f"DEBUG PD2: check if image is image")
        
        print(f"DEBUG PD2-1: starting layout based detection")
        # Step 1: Layout-based detection (no OCR yet)
        detected_layout = self._detect_document_layout(image)
        print(f"DEBUG PD2-2: Finished layout {detected_layout}")
        # Step 2: Route based on layout

        if detected_layout == "romanian_id":
            print(f"DEBUG PD3 TRACE LAYOUT: About to import Romanian processor")
            try:
                from app.services.romanian_id_processor import MultiTemplateIDProcessor
                print(f"DEBUG PD4 TRACE LAYOUT: Import successful")
                id_processor = MultiTemplateIDProcessor()
                print(f"DEBUG PD5 TRACE LAYOUT: Processor created")
                id_results = id_processor.process_id_card(image)
                print(f"DEBUG PD6 TRACE LAYOUT: Processing completed")
            except Exception as e:
                print(f"DEBUG PD7 TRACE LAYOUT ERROR: {e}")
                raise
            # Use region-based processor directly
            #from app.services.romanian_id_processor import MultiTemplateIDProcessor
            #id_processor = MultiTemplateIDProcessor()
            #id_results = id_processor.process_id_card(image)
            
            return EnhancedOCRResult(
                raw_text="",  # No full OCR needed
                template_match=TemplateMatchResult(
                    template_id="ro_identity_card",
                    document_type="romanian_id", 
                    confidence=id_results["overall_confidence"],
                    matched_patterns=["layout_detection"],
                    extracted_data=id_results["extracted_fields"]
                ),
                structured_data=id_results["extracted_fields"],
                confidence_score=int(id_results["overall_confidence"]),
                processing_metadata={
                    "processing_method": "region_based_extraction",
                    "card_type": id_results.get("card_type", "unknown"),
                    "regions_processed": len(id_results["extracted_fields"])
                }
            )
        else:
            # Fall back to existing full-text OCR for other documents
            return self._process_with_full_ocr(image, hint_document_type)

    def _detect_document_layout(self, image: Image.Image) -> str:
        """Detect document type by layout features, not OCR"""
        print(f"DEBUG DDL1: hello! we are inside the detect_document_layout function")
        width, height = image.size
        aspect_ratio = width / height
        print(f"DEBUG DDL2: Computed width {width} and height {height}")

        # Convert to array for analysis
        img_array = np.array(image)
        print(f"DEBUG DDL3: converted the image to array")

        # Romanian ID detection by layout features:
        
        # 1. Photo detection (dark rectangular region on left)
        photo_detected = self._detect_photo_region(img_array)
        print(f"DEBUG DDL4: photo detection {photo_detected}")

        # 2. Card-like aspect ratio
        is_card_shaped = 1.3 < aspect_ratio < 1.8
        print(f"DEBUG DDL5: is card shaped {is_card_shaped}")
        
        # 3. Structured layout (text blocks vs scattered text)
        has_structured_layout = self._detect_structured_text_blocks(img_array)
        print(f"DEBUG DDL6: has layout {has_structured_layout}")

        # 4. Color pattern analysis (flags, headers)
        has_official_colors = self._detect_official_document_colors(image)
        print(f"DEBUG DDL7: photo detection {has_official_colors}")

        # Decision logic
        if photo_detected and is_card_shaped and has_structured_layout:
            return "romanian_id"
        elif has_official_colors and has_structured_layout:
            return "official_document" 
        else:
            return "unknown_document"

    def _detect_photo_region(self, img_array) -> bool:
        """Detect photo region (dark rectangular area on left side)"""
        print(f"DEBUG DPR1: Hello! we are inside detect photo region")
        height, width = img_array.shape[:2]
        print(f"DEBUG DPR2: The height and width are {height} and {width}")
        # Check left 30% of image for photo-like region
        left_region = img_array[:, :int(width * 0.3)]
        
        # Convert to grayscale if color
        if len(left_region.shape) == 3:
            left_gray = np.mean(left_region, axis=2)
            print(f"DEBUG DPR3: converting to grayscale")
        else:
            left_gray = left_region
            print(f"DEBUG DPR4: no conversion needed")
        
        # Photos have: dark regions (hair, clothing) + rectangular boundaries
        dark_pixel_ratio = np.sum(left_gray < 120) / left_gray.size
        print(f"DEBUG DPR5: Dark pixel ration: {dark_pixel_ratio} (need > 0.15)")
        # Edge detection for rectangular boundaries
        edges = np.gradient(left_gray)
        print(f"DEBUG DPR6: Edges {edges}")
        edge_magnitude = np.sqrt(edges[0]**2 + edges[1]**2)
        print(f"DEBUG DPR7: Edge magnitude {edge_magnitude}")
        strong_edges = np.sum(edge_magnitude > 30) / edge_magnitude.size
        print(f"DEBUG DPR8: Strong edge {strong_edges}")
        result = (dark_pixel_ratio > 0.10) or (strong_edges > 0.01)
        print(f"DEBUG DPR10: Final result: {result}")

        # Photo criteria: significant dark area + rectangular edges
        return result

    def _detect_structured_text_blocks(self, img_array) -> bool:
        """Detect if image has structured text blocks (vs random text)"""
        # Use edge detection to find text regions
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2)
        else:
            gray = img_array
        
        edges = np.gradient(gray)
        edge_magnitude = np.sqrt(edges[0]**2 + edges[1]**2)
        
        # Text blocks have horizontal alignment patterns
        horizontal_lines = np.sum(edge_magnitude > 20, axis=1)
        text_rows = np.sum(horizontal_lines > gray.shape[1] * 0.1)
        
        # Structured documents have multiple aligned text rows
        return text_rows > 3

    def _detect_official_document_colors(self, image: Image.Image) -> bool:
        """Detect official document colors (flags, coats of arms)"""
        # Sample top and right regions for official colors
        width, height = image.size
        
        # Top region (flags)
        top_region = image.crop((0, 0, width, int(height * 0.2)))
        top_array = np.array(top_region)
        
        if len(top_array.shape) == 3:
            # Check for blue/yellow (EU flag) or red/yellow/blue (Romanian flag)
            blue_pixels = np.sum((top_array[:,:,2] > 100) & (top_array[:,:,0] < 100))
            red_pixels = np.sum((top_array[:,:,0] > 150) & (top_array[:,:,1] < 100))
            
            total_pixels = top_array.shape[0] * top_array.shape[1]
            official_color_ratio = (blue_pixels + red_pixels) / total_pixels
            
            return official_color_ratio > 0.05
        
        return False
    
    def _extract_text_romanian_optimized(self, image_input) -> Tuple[str, int]:
        """OCR extraction optimized for Romanian text"""
        try:
            print(f"DEBUG OCR A: Input type: {type(image_input)}")
            
            if isinstance(image_input, Image.Image):
                image = image_input.copy()
                print("DEBUG OCR B: Using PIL Image directly")
            elif isinstance(image_input, bytes):
                image = Image.open(io.BytesIO(image_input))
                print("DEBUG OCR B: Converted bytes to PIL Image")
            else:
                raise ValueError(f"Unexpected input type: {type(image_input)}")
            
            # Ensure fully loaded and in good mode
            image.load()
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            self._current_image = image.copy()
            
            print("DEBUG OCR C: About to call pytesseract")
            
            romanian_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
            text_ro_en = pytesseract.image_to_string(
                image,
                lang='ron+eng',
                config=romanian_config
            )
            
            # --- Confidence calculation via image_to_data ---
            ocr_data = pytesseract.image_to_data(
                image,
                lang='ron+eng',
                config=romanian_config,
                output_type=pytesseract.Output.DICT
            )

            confs = [int(c) for c in ocr_data["conf"] if c != "-1"]
            avg_conf = int(sum(confs) / len(confs)) if confs else 0

            print(f"DEBUG OCR D: Extracted {len(text_ro_en)} characters, avg conf={avg_conf}")
            return text_ro_en, avg_conf

            #return text_ro_en, 80  # placeholder confidence
            
        except Exception as e:
            print(f"DEBUG OCR ERROR: {e}")
            return f"OCR failed: {str(e)}", 0
    
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
            # Use working OCR instead of mock data
            from app.services.ocr import extract_text_confidence
            result = extract_text_confidence(image_input)
            return result['full_text'], result['average_confidence']
        except Exception as e:
            print(f"Fallback OCR also failed: {e}")
            return f"OCR processing failed: {str(e)}", 0

    def _process_with_full_ocr(self, image: Image.Image, hint_document_type: Optional[str] = None) -> 'EnhancedOCRResult':
        """Fallback to full OCR processing for non-ID documents"""
        try:
            # Extract text using existing method
            raw_text, confidence = self._extract_text_romanian_optimized(image)
            
            # Use existing template matching
            template_match = self._match_document_template(raw_text, hint_document_type)
            
            # Extract structured data if template found
            if template_match and template_match.document_type != "unknown_document":
                structured_data = self._extract_structured_data(raw_text, template_match.template_id)
            else:
                structured_data = {}
            
            return EnhancedOCRResult(
                raw_text=raw_text,
                template_match=template_match,
                structured_data=structured_data,
                confidence_score=confidence,
                processing_metadata={"method": "full_ocr_fallback"}
            )
        except Exception as e:
            return self._basic_fallback_ocr(image)