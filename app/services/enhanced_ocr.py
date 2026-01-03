"""Enhanced OCR processing with Romanian template recognition"""
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pytesseract
from PIL import Image
import io
import numpy as np
import logging
import cv2

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
        
        w, h = image.size
        if w < 600 or h < 600:
            app_logger.info(f"Image too small ({w}x{h}); skipping layout detection and using full OCR.")
            return self._process_with_full_ocr(image, hint_document_type)

        # Layout detection
        detected_layout, document_subtype = self._detect_document_layout(image)
        app_logger.debug(f"Detected layout: {detected_layout}, subtype: {document_subtype}")

        # Route processing based on detected layout
        if detected_layout == "romanian_id":
            # v1: ID OCR disabled unless explicitly requested
            id_hints = {"romanian_id", "id_card", "carte_identitate", "ci", "eci"}
            if hint_document_type not in id_hints:
                app_logger.info("ID layout detected, but ID OCR disabled for v1. Falling back to full OCR.")
                return self._process_with_full_ocr(image, hint_document_type)

            return self._process_romanian_id(image, document_subtype)

        # Otherwise: normal medical docs
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

    def _reconstruct_text_by_lines(self, ocr_data: dict) -> str:
            words = []
            n = len(ocr_data.get("text", []))
            for i in range(n):
                txt = (ocr_data["text"][i] or "").strip()
                conf = ocr_data["conf"][i]
                if not txt:
                    continue
                try:
                    if float(conf) < 0:  # tesseract uses -1 for non-words
                        continue
                except Exception:
                    pass
                words.append({
                    "block": ocr_data["block_num"][i],
                    "par": ocr_data["par_num"][i],
                    "line": ocr_data["line_num"][i],
                    "left": ocr_data["left"][i],
                    "text": txt
                })

            # group words by line, then sort by x-position
            from collections import defaultdict
            lines = defaultdict(list)
            for w in words:
                key = (w["block"], w["par"], w["line"])
                lines[key].append(w)

            out_lines = []
            for key in sorted(lines.keys()):
                line_words = sorted(lines[key], key=lambda x: x["left"])
                out_lines.append(" ".join(w["text"] for w in line_words))

            return "\n".join(out_lines)

    def _preprocess_for_document(self, pil_img: Image.Image) -> Image.Image:
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # denoise
        gray = cv2.fastNlMeansDenoising(gray, h=12)

        # adaptive threshold (very good for photos)
        thr = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 11
        )

        return Image.fromarray(thr)

    def _preprocess_grayscale_clahe(self, pil_img: Image.Image) -> Image.Image:
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # local contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # mild denoise
        gray = cv2.fastNlMeansDenoising(gray, h=10)

        return Image.fromarray(gray)

    def _repair_spacing(self, text: str) -> str:
        # add space after punctuation if missing
        text = re.sub(r"([,;:\.\!\?])(?=\S)", r"\1 ", text)

        # fix common glued patterns around Romanian diacritics / words
        # split CamelCase-ish OCR glue: "...multipleLeziune..." -> "...multiple Leziune..."
        text = re.sub(r"([a-zăâîșț])([A-ZĂÂÎȘȚ])", r"\1 \2", text)

        # add spaces between letters and numbers: "CO2a" -> "CO2 a"
        text = re.sub(r"([A-Za-zăâîșțĂÂÎȘȚ])(\d)", r"\1 \2", text)
        text = re.sub(r"(\d)([A-Za-zăâîșțĂÂÎȘȚ])", r"\1 \2", text)

        # collapse repeated spaces
        text = re.sub(r"[ \t]{2,}", " ", text)

        # clean weird OCR separators
        text = re.sub(r"[|]{2,}", " ", text)
        text = re.sub(r"^\s*[|/]+\s*$", "", text, flags=re.MULTILINE)

        # split common Romanian glued patterns (very high ROI)
        text = re.sub(r"\b(S-a)([a-zăâîșț])", r"\1 \2", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(Se)(va|a)\b", r"\1 \2", text, flags=re.IGNORECASE)  # "Seva" -> "Se va" (common OCR)
        text = re.sub(r"(Evitarea|Igienizare|Reevaluare|Leziune|Diagnosticul|Tratament|Recomandări)(?=[A-Za-zăâîșț])",
                    r"\1 ", text)

        # remove line-noise characters that survive thresholding
        text = re.sub(r"[|]{1,}", " ", text)
        text = re.sub(r"[_]{1,}", " ", text)
        text = re.sub(r"\s*/\s*", " ", text)

        # collapse whitespace
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _extract_text_romanian_optimized(self, image: Image.Image) -> Tuple[str, int]:
        """
        Extract text optimized for Romanian medical documents using
        multiple OCR configurations and select the best result.
        """
        try:
            app_logger.debug("Starting Romanian OCR (multi-config)")

            # Store original image (used elsewhere in pipeline)
            self._current_image = image.copy()

            # Preprocessing options for the image
            variants = [
                ("thr", self._preprocess_for_document(image)),
                ("clahe", self._preprocess_grayscale_clahe(image)),
            ]

            # OCR configurations to try
            ocr_configs = [
                r"--oem 3 --psm 3 -c preserve_interword_spaces=1",   # fully automatic page segmentation
                r"--oem 3 --psm 4 -c preserve_interword_spaces=1",   # block / semi-structured
                r"--oem 3 --psm 6 -c preserve_interword_spaces=1",   # uniform text
                r"--oem 3 --psm 11 -c preserve_interword_spaces=1",  # sparse text
            ]

            best_text = ""
            best_confidence = 0
            best_score = float("-inf")

            for variant_tag, variant_img in variants:
                # Use variant_img for OCR in this iteration
                for config in ocr_configs:
                    
                    app_logger.debug(f"Running OCR with config: {config}")

                    ocr_data = pytesseract.image_to_data(
                        variant_img,
                        lang="ron+eng",
                        config=config,
                        output_type=pytesseract.Output.DICT
                    )

                    # Reconstruct text by lines (replaces image_to_string)
                    raw_text = self._reconstruct_text_by_lines(ocr_data)
                    cleaned_text = self._clean_romanian_ocr_errors(raw_text)
                    cleaned_text = self._repair_spacing(cleaned_text)

                    # Confidence
                    confidences = [
                        int(c) for c in ocr_data.get("conf", []) if c != "-1"
                    ]
                    avg_conf = int(sum(confidences) / len(confidences)) if confidences else 0

                    # Simple quality heuristics
                    char_count = len(cleaned_text)
                    word_count = len(cleaned_text.split())
                    garbage_ratio = (
                        sum(1 for w in cleaned_text.split() if len(w) <= 1) / word_count
                        if word_count > 0
                        else 1.0
                    )

                    tokens = cleaned_text.split()
                    long_tokens = sum(1 for t in tokens if len(t) >= 20)
                    long_token_ratio = long_tokens / len(tokens) if tokens else 1.0

                    # Composite score (tunable, but works well in practice)
                    score = (
                        avg_conf
                        + 0.3 * word_count
                        - 20 * garbage_ratio
                        - 25 * long_token_ratio
                    )

                    app_logger.debug(
                        f"OCR result: chars={char_count}, words={word_count}, "
                        f"conf={avg_conf}, garbage_ratio={garbage_ratio:.2f}, score={score:.1f}"
                    )

                    if score > best_score and char_count > 0:
                        best_score = score
                        best_text = cleaned_text
                        best_confidence = avg_conf

            app_logger.debug(
                f"Selected OCR output with {len(best_text)} chars "
                f"and {best_confidence}% confidence"
            )

            return best_text, best_confidence

        except Exception as e:
            app_logger.error(f"Romanian OCR failed: {e}", exc_info=True)
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