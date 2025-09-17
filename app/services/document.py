"""Enhanced document service with Romanian template processing"""
from typing import Dict, Any, Optional, List
import json
import logging
from datetime import datetime

from app.services.enhanced_ocr import RomanianOCRProcessor, EnhancedOCRResult
from app.services.romanian_document_templates import RomanianDocumentTemplates

logger = logging.getLogger(__name__)

class EnhancedDocumentService:
    """Enhanced document processing with Romanian intelligence"""
    
    def __init__(self):
        self.ocr_processor = RomanianOCRProcessor()
        self.templates = RomanianDocumentTemplates.get_all_templates()
    
    def detect_document_type(self, ocr_text: str) -> str:
        """Detect document type from OCR text"""
        text_upper = ocr_text.upper()
        
        # Romanian ID card detection
        if any(pattern in text_upper for pattern in ["ROMANIA", "CARTE DE IDENTITATE", "CNP"]):
            return "romanian_id"
        
        # Lab results detection
        elif any(pattern in text_upper for pattern in ["LABORATOR", "ANALIZE", "HEMOGLOBINĂ", "REZULTATE"]):
            return "lab_result"
        
        # Prescription detection
        elif any(pattern in text_upper for pattern in ["REȚETĂ", "PRESCRIPȚIE", "MEDICAMENT"]):
            return "prescription"
        
        # Medical imaging detection
        elif any(pattern in text_upper for pattern in ["RADIOGRAFIE", "ECOGRAFIE", "RMN", "CT"]):
            return "medical_imaging"
        
        # Discharge summary detection
        elif any(pattern in text_upper for pattern in ["FOAIA DE EXTERNARE", "SCRISOARE MEDICALĂ"]):
            return "discharge_summary"
        
        return "unknown_document"
    
    def process_document_with_templates(self, file_content: bytes, hint_type: Optional[str] = None) -> Dict[str, Any]:
        """Process document using Romanian templates"""
        try:
            # Use enhanced OCR processor
            ocr_result = self.ocr_processor.process_document(file_content, hint_type)
            
            # Build comprehensive response
            result = {
                "success": True,
                "ocr_text": ocr_result.raw_text,
                "document_type": ocr_result.template_match.document_type if ocr_result.template_match else "unknown_document",
                "confidence_score": ocr_result.confidence_score,
                "structured_data": ocr_result.structured_data,
                "processing_metadata": ocr_result.processing_metadata,
                "template_match": {
                    "matched": ocr_result.template_match is not None,
                    "template_id": ocr_result.template_match.template_id if ocr_result.template_match else None,
                    "matched_patterns": ocr_result.template_match.matched_patterns if ocr_result.template_match else [],
                    "confidence": ocr_result.template_match.confidence if ocr_result.template_match else 0
                }
            }
            
            # Add validation results for Romanian ID
            if ocr_result.template_match and ocr_result.template_match.document_type == "romanian_id":
                result["validation_results"] = self._validate_romanian_id_extraction(ocr_result.structured_data)
            
            # Add medical analysis for lab results
            elif ocr_result.template_match and ocr_result.template_match.document_type == "lab_result":
                result["medical_analysis"] = self._analyze_lab_results(ocr_result.structured_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Enhanced document processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "ocr_text": "",
                "document_type": "processing_error",
                "confidence_score": 0,
                "structured_data": {},
                "fallback_used": True
            }
    
    def _validate_romanian_id_extraction(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Romanian ID card extraction"""
        validation_results = {
            "cnp_valid": structured_data.get("cnp_valid", False),
            "names_extracted": bool(structured_data.get("nume") and structured_data.get("prenume")),
            "date_consistent": structured_data.get("cnp_date_consistent", False),
            "required_fields_present": True,
            "warnings": [],
            "suggestions": []
        }
        
        # Check required fields
        required_fields = ["nume", "prenume", "cnp"]
        missing_fields = [field for field in required_fields if not structured_data.get(field)]
        
        if missing_fields:
            validation_results["required_fields_present"] = False
            validation_results["warnings"].append(f"Missing required fields: {', '.join(missing_fields)}")
            validation_results["suggestions"].append("Manual verification recommended for missing fields")
        
        # CNP validation warnings
        if not structured_data.get("cnp_valid", True):
            validation_results["warnings"].append("CNP validation failed")
            validation_results["suggestions"].append("Verify CNP manually - OCR may have misread digits")
        
        # Date consistency warnings
        if not structured_data.get("cnp_date_consistent", True):
            validation_results["warnings"].append("CNP and birth date are inconsistent")
            validation_results["suggestions"].append("Check birth date against CNP-derived date")
        
        return validation_results
    
    def _analyze_lab_results(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze lab results for medical insights"""
        analysis = {
            "test_count": 0,
            "abnormal_results": [],
            "normal_results": [],
            "unknown_results": [],
            "critical_flags": [],
            "recommendations": []
        }
        
        test_results = structured_data.get("test_results", [])
        analysis["test_count"] = len(test_results)
        
        for test in test_results:
            test_status = test.get("status", "unknown")
            test_name = test.get("test_name", "Unknown Test")
            
            if test_status == "normal":
                analysis["normal_results"].append(test_name)
            elif test_status in ["high", "low"]:
                analysis["abnormal_results"].append({
                    "test": test_name,
                    "status": test_status,
                    "value": test.get("value", ""),
                    "unit": test.get("unit", "")
                })
                
                # Flag critical values (simplified logic)
                if self._is_critical_value(test):
                    analysis["critical_flags"].append(test_name)
            else:
                analysis["unknown_results"].append(test_name)
        
        # Generate recommendations
        if analysis["abnormal_results"]:
            analysis["recommendations"].append("Review abnormal results with patient's medical history")
        
        if analysis["critical_flags"]:
            analysis["recommendations"].append("URGENT: Critical values detected - immediate medical review required")
        
        if analysis["unknown_results"]:
            analysis["recommendations"].append("Manual verification needed for tests with unclear results")
        
        return analysis
    
    def _is_critical_value(self, test_result: Dict[str, Any]) -> bool:
        """Determine if a test result represents a critical value"""
        test_name = test_result.get("normalized_name", "").lower()
        value_str = test_result.get("value", "")
        
        try:
            value = float(value_str.replace(',', '.'))
        except (ValueError, AttributeError):
            return False
        
        # Simplified critical value thresholds (would be more comprehensive in production)
        critical_thresholds = {
            "hemoglobin": {"low": 7.0, "high": 20.0},
            "white_blood_cells": {"low": 2.0, "high": 20.0},
            "blood_glucose": {"low": 50, "high": 400},
            "creatinine": {"low": 0.5, "high": 3.0}
        }
        
        if test_name in critical_thresholds:
            thresholds = critical_thresholds[test_name]
            return value < thresholds["low"] or value > thresholds["high"]
        
        return False

# Backward compatibility functions
def detect_document_type(ocr_text: str) -> str:
    """Legacy function for backward compatibility"""
    service = EnhancedDocumentService()
    return service.detect_document_type(ocr_text)

def extract_structured_data(ocr_text: str, document_type: str) -> Dict[str, Any]:
    """Legacy function - now replaced by template processing"""
    # For backward compatibility, return basic extraction
    return {
        "legacy_extraction": True,
        "text_preview": ocr_text[:200] + "..." if len(ocr_text) > 200 else ocr_text,
        "detected_type": document_type,
        "upgrade_note": "Use enhanced template processing for better results"
    }