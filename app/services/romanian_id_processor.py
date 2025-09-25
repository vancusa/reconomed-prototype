"""Multi-template Romanian ID processor based on actual marked regions"""
from typing import Dict, Optional, Tuple
from enum import Enum
import pytesseract
from PIL import Image, ImageEnhance
import numpy as np

class RomanianIDType(Enum):
    ECI_ELECTRONIC = "carte_electronica"  # Image 1 (newest)
    CI_STANDARD = "carte_identitate"      # Image 2 (current standard)
    BI_OLD = "buletin_identitate"         # Image 3 (old bulletin) - to be developed in further versions, if needed.
    UNKNOWN = "unknown"

class MultiTemplateIDProcessor:
    """Process different Romanian ID card types with precise region coordinates"""
    
    def __init__(self):
        self.templates = {
            RomanianIDType.CI_STANDARD: {
                "alignment_reference": "romania_text_top",  # "ROMANIA" at top
                "regions": {
                    "nume": {
                        "x_start": 0.305, "x_end": 0.935, "y_start": 0.365, "y_end": 0.415,
                        "ocr_config": "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĂÎÂȘȚăîâșț"

                    },
                    "prenume": {
                        "x_start": 0.305, "x_end": 0.935, "y_start": 0.463, "y_end": 0.513,
                        "ocr_config": "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĂÎÂȘȚăîâșț"
                    },
                    "cnp": {
                        "x_start": 0.305, "x_end": 0.570, "y_start": 0.267, "y_end": 0.307,
                        "ocr_config": "--psm 8 -c tessedit_char_whitelist=0123456789"
                    },
                    "address": {
                        "x_start": 0.305, "x_end": 0.935, "y_start": 0.755, "y_end": 0.855,
                        "ocr_config": "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĂÎÂȘȚăîâșț0123456789 .,-/"
                    }
                },
                "photo_region": {"x_start": 0.035, "x_end": 0.280, "y_start": 0.155, "y_end": 0.800}
            },
            
            RomanianIDType.ECI_ELECTRONIC: {
                "alignment_reference": "romania_coat_of_arms",  # Right side coat of arms
                "regions": {
                    "nume": {
                        "x_start": 0.538, "x_end": 0.938, "y_start": 0.190, "y_end": 0.240,
                        "ocr_config": "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĂÎÂȘȚăîâșț"
                    },
                    "prenume": {
                        "x_start": 0.538, "x_end": 0.938, "y_start": 0.252, "y_end": 0.340,
                        "ocr_config": "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĂÎÂȘȚăîâșț"
                    },
                    "cnp": {
                        "x_start": 0.538, "x_end": 0.845, "y_start": 0.488, "y_end": 0.538,
                        "ocr_config": "--psm 8 -c tessedit_char_whitelist=0123456789"
                    }
                    # No address field in electronic CI
                },
                "photo_region": {"x_start": 0.048, "x_end": 0.485, "y_start": 0.155, "y_end": 0.590}
            },
            
            RomanianIDType.BI_OLD: {
                "alignment_reference": "series_number_top",  # Series numbers at top
                "regions": {
                    "nume": {
                        "x_start": 0.251, "x_end": 0.600, "y_start": 0.360, "y_end": 0.420,
                        "ocr_config": "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĂÎÂȘȚăîâșț"
                    },
                    "prenume": {
                        "x_start": 0.251, "x_end": 0.600, "y_start": 0.440, "y_end": 0.500,
                        "ocr_config": "--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĂÎÂȘȚăîâșț"
                    },
                    "address": {
                        "x_start": 0.620, "x_end": 0.950, "y_start": 0.360, "y_end": 0.500,
                        "ocr_config": "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĂÎÂȘȚăîâșț0123456789 .,-/"
                    }
                    # CNP not visible in old BI format
                },
                "photo_region": {"x_start": 0.025, "x_end": 0.225, "y_start": 0.225, "y_end": 0.665}
            }
        }
    
    def detect_id_type_by_layout(self, image: Image.Image) -> RomanianIDType:
        """Detect ID type using layout analysis instead of OCR"""
        width, height = image.size
        
        # Convert to grayscale for analysis
        gray = image.convert('L')
        img_array = np.array(gray)
        
        # Key layout differences to detect:
        
        # 1. Photo position analysis
        photo_left = self._detect_photo_position(img_array)
        
        # 2. Card orientation (landscape vs portrait-ish)
        aspect_ratio = width / height
        
        # 3. Color regions in top area (flags, headers)
        top_region = image.crop((0, 0, width, int(height * 0.25)))
        has_eu_flag = self._detect_blue_yellow_regions(top_region)
        
        # 4. Overall layout pattern
        text_density_right = self._analyze_text_density(img_array, "right")
        text_density_bottom = self._analyze_text_density(img_array, "bottom")
        
        # Decision logic based on layout patterns:
        
        # ECI Electronic: EU flag + horizontal layout + photo left
        if has_eu_flag and aspect_ratio > 1.4 and photo_left:
            return RomanianIDType.ECI_ELECTRONIC
        
        # Standard CI: Coat of arms + photo left + high right text density  
        elif photo_left and text_density_right > 0.6 and aspect_ratio > 1.3:
            return RomanianIDType.CI_STANDARD
            
        # Old BI: Photo left + vertical-ish + low right text density
        elif photo_left and aspect_ratio < 1.6 and text_density_right < 0.4:
            return RomanianIDType.BI_OLD
        
        return RomanianIDType.UNKNOWN

    def _detect_photo_position(self, img_array) -> bool:
        """Detect if photo is on left side by finding dark rectangular region"""
        height, width = img_array.shape
        left_region = img_array[:, :int(width * 0.3)]
        
        # Photos have consistent dark regions (hair, clothing)
        dark_pixels = np.sum(left_region < 100)
        total_pixels = left_region.size
        
        return (dark_pixels / total_pixels) > 0.15

    def _detect_blue_yellow_regions(self, top_region) -> bool:
        """Detect EU flag colors in top region"""
        img_array = np.array(top_region)
        
        # Simple blue detection (EU flag blue)
        blue_mask = (img_array[:,:,2] > img_array[:,:,0]) & (img_array[:,:,2] > img_array[:,:,1])
        blue_ratio = np.sum(blue_mask) / blue_mask.size
        
        return blue_ratio > 0.1

    def _analyze_text_density(self, img_array, region: str) -> float:
        """Analyze text density in specific regions"""
        height, width = img_array.shape
        
        if region == "right":
            analysis_region = img_array[:, int(width * 0.5):]
        elif region == "bottom":
            analysis_region = img_array[int(height * 0.7):, :]
        
        # Text areas have high contrast (edge detection)
        edges = np.gradient(analysis_region.astype(float))
        edge_magnitude = np.sqrt(edges[0]**2 + edges[1]**2)
        
        return np.mean(edge_magnitude > 50)
    
    def process_id_card(self, image: Image.Image) -> Dict:
        """Process Romanian ID card with automatic type detection"""
        # Detect card type
        card_type = self.detect_id_type_by_layout(image)
        
        if card_type == RomanianIDType.UNKNOWN:
            return self._try_all_templates(image)
        
        # Process with detected template
        template = self.templates[card_type]
        results = self._extract_from_template(image, template, card_type)
        
        return results
    
    def _extract_from_template(self, image: Image.Image, template: Dict, card_type: RomanianIDType) -> Dict:
        """Extract data using specific template"""
        results = {
            "card_type": card_type.value,
            "extraction_method": "multi_template_region",
            "extracted_fields": {},
            "confidence_scores": {},
            "validation_results": {}
        }
        
        width, height = image.size
        print(f"DEBUG EFT1: Hello! we are inside extract from template function and the image is {width} x {height}")
        print(f"DEBUG EFT2: The card type we got is {card_type}")

        for field_name, region in template["regions"].items():
            try:
                # Calculate pixel coordinates
                x1 = int(region["x_start"] * width)
                x2 = int(region["x_end"] * width)
                y1 = int(region["y_start"] * height)
                y2 = int(region["y_end"] * height)
                
                # Extract and enhance region
                region_img = image.crop((x1, y1, x2, y2))
                enhanced_region = self._enhance_region_for_ocr(region_img, field_name)
       
                print(f"DEBUG EFT3: About to process field '{field_name}'")
                print(f"DEBUG EFT4: Enhanced region size: {enhanced_region.size}")
                print(f"DEBUG EFT5: Enhanced region mode: {enhanced_region.mode}")        
       
                # OCR extraction
                field_text = pytesseract.image_to_string(
                    enhanced_region,
                    lang='ron',
                    config=region["ocr_config"]
                ).strip()
                
                # Get confidence scores
                field_data = pytesseract.image_to_data(
                    enhanced_region,
                    lang='ron',
                    config=region["ocr_config"],
                    output_type=pytesseract.Output.DICT
                )
                
                confidences = [int(conf) for conf in field_data['conf'] if int(conf) > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                
                # Store results
                results["extracted_fields"][field_name] = field_text
                results["confidence_scores"][field_name] = avg_confidence
                
                # Validate field
                results["validation_results"][field_name] = self._validate_field(
                    field_name, field_text, card_type
                )
                
            except Exception as e:
                print(f"Extraction failed for {field_name}: {e}")
                results["extracted_fields"][field_name] = ""
                results["confidence_scores"][field_name] = 0
                results["validation_results"][field_name] = {"valid": False, "error": str(e)}
        
        # Calculate overall confidence
        confidences = list(results["confidence_scores"].values())
        results["overall_confidence"] = sum(confidences) / len(confidences) if confidences else 0
        
        return results
    
    def _enhance_region_for_ocr(self, region_img: Image.Image, field_type: str) -> Image.Image:
        """Field-specific enhancement for better OCR"""
        # Convert to grayscale
        print(f"DEBUG ERFOCR 1: We are inside the Enhance region for OCR function")
        width, height = region_img.size    
        # Debug the incoming region size
        print(f"DEBUG ERFOCR 2: Field '{field_type}' incoming size: {width}x{height}")
        
        # Ensure minimum size before processing
        if width < 50 or height < 20:
            print(f"DEBUG ERFOCR 3: Region too small ({width}x{height}), skipping OCR")
            # Return a blank image or raise an exception
            raise ValueError(f"Region too small for OCR: {width}x{height}")
        
        gray = region_img.convert('L')
        print(f"DEBUG ERFOCR 4: Gray done")

        # Field-specific enhancements
        #if field_type == "cnp":
            # High contrast for numbers
        #    from PIL import ImageEnhance
        #    enhancer = ImageEnhance.Contrast(gray)
        #    enhanced = enhancer.enhance(2.5)
        #elif field_type in ["nume", "prenume"]:
            # Balanced enhancement for names
        #    from PIL import ImageEnhance
        #    enhancer = ImageEnhance.Contrast(gray)
        #    enhanced = enhancer.enhance(1.8)
        #elif field_type == "address":
            # Moderate enhancement for mixed text
        #    from PIL import ImageEnhance  
        #    enhancer = ImageEnhance.Contrast(gray)
        #    enhanced = enhancer.enhance(1.5)
        #else:
        #    enhanced = gray
        
        # Simple contrast enhancement
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        print(f"DEBUG ERFOCR 5: Enhanced done")

        #Scale up for better OCR (3x)
        scale_factor = max(3, 100 // min(width, height))  # Ensure at least 100px minimum dimension
        scaled = enhanced.resize((width * scale_factor, height * scale_factor), Image.Resampling.LANCZOS)
        print(f"DEBUG ERFOCR 6: Final size: {scaled.size}")

        return scaled
    
    def _validate_field(self, field_name: str, field_value: str, card_type: RomanianIDType) -> Dict:
        """Validate extracted field with card-type awareness"""
        if field_name == "cnp" and card_type != RomanianIDType.BI_OLD:
            # CNP validation for modern cards
            from app.utils.romanian_validation import validate_cnp
            is_valid, error = validate_cnp(field_value)
            return {"valid": is_valid, "error": error, "normalized": field_value}
        
        elif field_name in ["nume", "prenume"]:
            # Name validation
            if len(field_value) < 2:
                return {"valid": False, "error": "Name too short"}
            # Allow Romanian characters and hyphens
            import re
            if not re.match(r'^[a-zA-ZăîâșțĂÎÂȘȚ\s\-]+$', field_value):
                return {"valid": False, "error": "Name contains invalid characters"}
            return {"valid": True, "normalized": field_value.title()}
        
        elif field_name == "address":
            # Address validation
            if len(field_value) < 5:
                return {"valid": False, "error": "Address too short"}
            return {"valid": True, "normalized": field_value}
        
        return {"valid": True, "normalized": field_value}
    
    def _try_all_templates(self, image: Image.Image) -> Dict:
        """Try all templates and return best results"""
        best_results = None
        best_confidence = 0
        
        for card_type, template in self.templates.items():
            try:
                results = self._extract_from_template(image, template, card_type)
                avg_confidence = results.get("overall_confidence", 0)
                
                if avg_confidence > best_confidence:
                    best_confidence = avg_confidence
                    best_results = results
                    best_results["card_type"] = f"{card_type.value}_auto_detected"
                    
            except Exception:
                continue
        
        return best_results or {
            "card_type": "unknown", 
            "error": "No template produced reliable results",
            "extracted_fields": {},
            "overall_confidence": 0
        }