"""Enhanced OCR processing with Romanian template recognition"""
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pytesseract
from PIL import Image
import io
import numpy as np
import logging

# Loggers
audit_logger = logging.getLogger("reconomed.audit")
app_logger = logging.getLogger("reconomed.app")

from app.services.romanian_document_templates import RomanianDocumentTemplates, RomanianMedicalTerms
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
        app_logger.debug("Starting document processing")
        
        # Normalize hint types
        hint_document_type = self._normalize_hint(hint_document_type)
        
        # Normalize input to PIL Image
        image = self._normalize_input_to_image(image_input)
        app_logger.debug("Input normalized to PIL Image")
        
        # Layout detection
        detected_layout, document_subtype = self._detect_document_layout(image)
        app_logger.debug(f"Detected layout: {detected_layout}, subtype: {document_subtype}")

        # Route processing based on detected layout
        if detected_layout == "romanian_id":
            return self._process_romanian_id(image, document_subtype)
        else:
            # Fall back to full OCR for other documents
            return self._process_with_full_ocr(image, hint_document_type)

    def _normalize_hint(self, hint: Optional[str]) -> Optional[str]:
        """Normalize document type hints"""
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
        """Convert input to PIL Image"""
        if isinstance(image_input, bytes):
            try:
                image = Image.open(io.BytesIO(image_input))
                image.load()
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                return image
            except Exception as e:
                app_logger.error(f"Failed to open image from bytes: {e}")
                raise
        elif isinstance(image_input, Image.Image):
            img_copy = image_input.copy()
            if img_copy.mode not in ("RGB", "L"):
                img_copy = img_copy.convert("RGB")
            return img_copy
        else:
            raise TypeError(f"Unsupported input type: {type(image_input)}")

    def _detect_document_layout(self, image: Image.Image) -> Tuple[str, Optional[str]]:
        """
        Detect document layout type before OCR processing.
        
        Returns:
            Tuple[str, Optional[str]]: (layout_type, subtype)
            - layout_type: "romanian_id" | "lab_result" | "unknown" 
            - subtype: For IDs: "eci_electronic" | "ci_standard"
        """
        app_logger.debug("Starting layout detection")
        
        try:
            width, height = image.size
            app_logger.debug(f"Image dimensions: {width}x{height}")
            
            # Convert to numpy array
            img_array = np.array(image)
            
            # Step 1: Romanian ID detection
            is_card_shaped = self._is_card_shaped(width, height)
            has_photo = self._detect_photo_region(img_array)
            has_id_layout = self._has_structured_text_blocks(img_array)
            
            app_logger.debug(f"Card detection: shaped={is_card_shaped}, photo={has_photo}, layout={has_id_layout}")
            
            if is_card_shaped and has_photo and has_id_layout:
                id_type = self._classify_romanian_id_type(image)
                app_logger.info(f"Detected Romanian ID: {id_type}")
                return "romanian_id", id_type
            
            # Step 2: Lab result detection
            has_lab_header = self._detect_lab_header(img_array)
            if has_lab_header:
                lab_type = self._classify_lab_type(image)
                app_logger.info(f"Detected lab result: {lab_type}")
                return "lab_result", lab_type
            
            # Step 3: Fallback
            app_logger.info("Unknown document layout")
            return "unknown", None
            
        except Exception as e:
            app_logger.error(f"Layout detection failed: {e}", exc_info=True)
            return "unknown", None

    def _is_card_shaped(self, width: int, height: int) -> bool:
        """Check if image has ID card proportions"""
        aspect_ratio = width / height
        return 1.3 < aspect_ratio < 1.9

    def _detect_photo_region(self, img_array) -> bool:
        """Detect photo region (dark rectangular area on left side)"""
        height, width = img_array.shape[:2]
        left_region = img_array[:, :int(width * 0.3)]
        
        # Convert to grayscale if needed
        if len(left_region.shape) == 3:
            left_gray = np.mean(left_region, axis=2)
        else:
            left_gray = left_region
        
        # Check for photo characteristics
        dark_pixel_ratio = np.sum(left_gray < 120) / left_gray.size
        
        # Edge detection for rectangular boundaries
        edges = np.gradient(left_gray)
        edge_magnitude = np.sqrt(edges[0]**2 + edges[1]**2)
        strong_edges = np.sum(edge_magnitude > 30) / edge_magnitude.size
        
        return dark_pixel_ratio > 0.10 or strong_edges > 0.01

    def _has_structured_text_blocks(self, img_array) -> bool:
        """Detect structured text layout"""
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2)
        else:
            gray = img_array
        
        edges = np.gradient(gray)
        edge_magnitude = np.sqrt(edges[0]**2 + edges[1]**2)
        horizontal_lines = np.sum(edge_magnitude > 20, axis=1)
        text_rows = np.sum(horizontal_lines > gray.shape[1] * 0.1)
        
        return text_rows > 3

    def _classify_romanian_id_type(self, image: Image.Image) -> str:
        """Classify specific Romanian ID type using photo area ratio"""
        photo_bounds = self._get_precise_photo_boundaries(image)
        
        if not photo_bounds:
            return "unknown"
        
        # Calculate photo-to-card area ratio
        card_area = image.size[0] * image.size[1]
        photo_area = photo_bounds['width'] * photo_bounds['height']
        area_ratio = photo_area / card_area
        
        app_logger.debug(f"Photo area ratio: {area_ratio:.3f}")
        
        # ECI=28%, CI=19%, threshold at 23.5%
        if area_ratio > 0.235:
            return "eci_electronic"
        elif area_ratio > 0.15:
            return "ci_standard"
        else:
            return "unknown"

    def _get_precise_photo_boundaries(self, image: Image.Image) -> Optional[Dict]:
        """Find precise photo boundaries"""
        gray = image.convert('L')
        img_array = np.array(gray)
        height, width = img_array.shape
        
        # Focus on left side where photo should be
        left_region = img_array[:, :int(width * 0.6)]
        
        # Find dark regions
        dark_threshold = np.mean(left_region) - np.std(left_region)
        dark_mask = left_region < dark_threshold
        
        # Find bounding box
        rows = np.any(dark_mask, axis=1)
        cols = np.any(dark_mask, axis=0)
        
        if not np.any(rows) or not np.any(cols):
            return None
        
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]
        
        return {
            'width': x_max - x_min,
            'height': y_max - y_min
        }

    def _detect_lab_header(self, img_array: np.ndarray) -> bool:
        """Detect laboratory headers - placeholder for future implementation"""
        # TODO: Implement lab header detection
        return False

    def _classify_lab_type(self, image: Image.Image) -> str:
        """Classify lab result type - placeholder for future implementation"""
        # TODO: Implement lab type classification
        return "unknown"

    def _process_romanian_id(self, image: Image.Image, id_type: str) -> 'EnhancedOCRResult':
        """Process Romanian ID using specialized processor"""
        try:
            app_logger.debug("Processing Romanian ID with specialized processor")
            from app.services.romanian_id_processor import MultiTemplateIDProcessor
            
            id_processor = MultiTemplateIDProcessor()
            id_results = id_processor.process_id_card(image)
            
            template_match = TemplateMatchResult(
                template_id="ro_identity_card",
                document_type="romanian_id",
                confidence=id_results.get("overall_confidence", 0),
                matched_patterns=["layout_detection"],
                extracted_data=id_results.get("extracted_fields", {})
            )
            
            return EnhancedOCRResult(
                raw_text="",
                template_match=template_match,
                structured_data=id_results.get("extracted_fields", {}),
                confidence_score=int(id_results.get("overall_confidence", 0)),
                processing_metadata={
                    "processing_method": "region_based_extraction",
                    "card_type": id_type,
                    "regions_processed": len(id_results.get("extracted_fields", {}))
                }
            )
            
        except Exception as e:
            app_logger.error(f"Romanian ID processing failed: {e}", exc_info=True)
            # Fall back to full OCR
            return self._process_with_full_ocr(image, "romanian_id")

    def _process_with_full_ocr(self, image: Image.Image, hint_document_type: Optional[str] = None) -> 'EnhancedOCRResult':
        """Process document using full OCR"""
        try:
            app_logger.debug("Processing with full OCR")
            
            # Extract text
            raw_text, confidence = self._extract_text_romanian_optimized(image)
            
            # Match template
            template_match = self._match_document_template(raw_text, hint_document_type)
            
            # Extract structured data
            structured_data = {}
            if template_match and template_match.document_type != "unknown":
                structured_data = self._extract_structured_data(raw_text, template_match.template_id)
                structured_data = self._apply_post_processing(structured_data, template_match.template_id)
                structured_data = self._enhance_with_medical_terms(structured_data, raw_text)
            
            final_confidence = self._calculate_final_confidence(confidence, template_match, structured_data)
            
            return EnhancedOCRResult(
                raw_text=raw_text,
                template_match=template_match,
                structured_data=structured_data,
                confidence_score=int(final_confidence),
                processing_metadata={"method": "full_ocr"}
            )
            
        except Exception as e:
            app_logger.error(f"Full OCR processing failed: {e}", exc_info=True)
            return self._create_fallback_result(image)

    def _extract_text_romanian_optimized(self, image: Image.Image) -> Tuple[str, int]:
        """Extract text optimized for Romanian"""
        try:
            app_logger.debug("Starting Romanian OCR")
            
            # Store current image
            self._current_image = image.copy()
            
            # Romanian OCR configuration
            romanian_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
            
            # Extract text
            text_ro_en = pytesseract.image_to_string(
                image, 
                lang='ron+eng', 
                config=romanian_config
            )
            
            # Get confidence
            ocr_data = pytesseract.image_to_data(
                image,
                lang='ron+eng', 
                config=romanian_config,
                output_type=pytesseract.Output.DICT
            )
            
            confidences = [int(c) for c in ocr_data["conf"] if c != "-1"]
            avg_confidence = int(sum(confidences) / len(confidences)) if confidences else 0
            
            # Clean text
            cleaned_text = self._clean_romanian_ocr_errors(text_ro_en)
            
            app_logger.debug(f"OCR extracted {len(cleaned_text)} chars with {avg_confidence}% confidence")
            return cleaned_text, avg_confidence
            
        except Exception as e:
            app_logger.error(f"Romanian OCR failed: {e}")
            return self._basic_fallback_ocr(image)

    def _clean_romanian_ocr_errors(self, text: str) -> str:
        """Clean common Romanian OCR errors"""
        corrections = {
            'Ã£': 'ă', 'Ã¢': 'â', 'Ã®': 'î', 'ÅŸ': 'ș', 'Å£': 'ț',
            r'\bCNF\b': 'CNP', r'\bPACIENT\b': 'PACIENT',
            r'(\d)\s+(\d)': r'\1\2',  # Remove spaces in numbers
            r'([A-ZĂÂÎȘȚ])\s+([a-zăâîșț])': r'\1\2',  # Fix broken words
        }
        
        cleaned = text
        for pattern, replacement in corrections.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        
        return cleaned

    def _match_document_template(self, text: str, hint_type: Optional[str] = None) -> Optional['TemplateMatchResult']:
        """Match document against templates"""
        best_match, best_score = None, 0
        
        templates = self.templates
        if hint_type:
            # Prioritize hinted template
            templates = [t for t in templates if t.document_type == hint_type] + \
                       [t for t in templates if t.document_type != hint_type]
        
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

    def _calculate_template_score(self, text: str, template) -> Tuple[float, List[str]]:
        """Calculate template matching score"""
        text_upper = text.upper()
        matched_patterns = []
        
        for pattern in template.identification_patterns:
            if re.search(pattern, text_upper, re.IGNORECASE):
                matched_patterns.append(pattern)
        
        pattern_score = (len(matched_patterns) / len(template.identification_patterns)) * 100
        
        # Medical document bonus
        if template.document_type in ["lab_result", "prescription"]:
            medical_terms_found = len(self._find_medical_terms(text))
            pattern_score += min(medical_terms_found * 5, 20)
        
        return min(pattern_score, 100), matched_patterns

    def _find_medical_terms(self, text: str) -> List[str]:
        """Find Romanian medical terms in text"""
        text_lower = text.lower()
        found_terms = []
        
        for ro_term in self.medical_terms.MEDICAL_TESTS.keys():
            if ro_term in text_lower:
                found_terms.append(ro_term)
                
        for ro_term in self.medical_terms.COMMON_MEDICATIONS.keys():
            if ro_term in text_lower:
                found_terms.append(ro_term)
        
        return found_terms

    def _extract_structured_data(self, text: str, template_id: str) -> Dict[str, Any]:
        """Extract structured data using template"""
        template = next(t for t in self.templates if t.template_id == template_id)
        extracted = {}
        
        for field in template.extraction_fields:
            value = None
            for pattern in field.patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
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
        
        return extracted

    def _apply_post_processing(self, data: Dict[str, Any], template_id: str) -> Dict[str, Any]:
        """Apply template-specific post-processing"""
        return data  # Simplified for now

    def _enhance_with_medical_terms(self, data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """Enhance data with medical term recognition"""
        enhanced = data.copy()
        terms = self._find_medical_terms(raw_text)
        enhanced["recognized_medical_terms"] = terms
        return enhanced

    def _calculate_final_confidence(self, ocr_confidence: int, template_match: Optional['TemplateMatchResult'], structured_data: Dict[str, Any]) -> int:
        """Calculate final confidence score"""
        base = ocr_confidence
        
        if template_match:
            base += min(template_match.confidence * 0.3, 20)
        if structured_data:
            base += min(len(structured_data) * 2, 15)
            
        return min(int(base), 100)

    def _basic_fallback_ocr(self, image: Image.Image) -> Tuple[str, int]:
        """Basic fallback OCR"""
        try:
            result = extract_text_confidence(image)
            return result['full_text'], result['average_confidence']
        except Exception as e:
            app_logger.error(f"Fallback OCR failed: {e}")
            return f"OCR processing failed: {str(e)}", 0

    def _create_fallback_result(self, image: Image.Image) -> 'EnhancedOCRResult':
        """Create fallback result for failed processing"""
        text, conf = self._basic_fallback_ocr(image)
        return EnhancedOCRResult(
            raw_text=text,
            template_match=None,
            structured_data={},
            confidence_score=conf,
            processing_metadata={"method": "fallback"}
        )