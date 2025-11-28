# app/services/llm_extraction_service.py
import importlib
import importlib.util
import json
from typing import Dict, Any, List

class LLMExtractionService:
    """Service for extracting structured data from transcripts using LLM"""

    def __init__(self, api_key: str):
        if importlib.util.find_spec("openai") is None:
            raise ModuleNotFoundError("openai")

        self._client = importlib.import_module("openai")
        self._client.api_key = api_key
    
    async def extract_fields_from_transcript(
        self,
        transcript: str,
        template: Dict[str, Any],
        existing_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Extract structured fields from consultation transcript"""
        prompt = self._build_extraction_prompt(transcript, template, existing_data)
        
        try:
            response = self._client.ChatCompletion.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            extracted_data = json.loads(response.choices[0].message.content)
            return extracted_data
            
        except Exception as e:
            raise Exception(f"LLM extraction failed: {str(e)}")
    
    async def extract_icd10_codes(
        self,
        diagnosis_text: str
    ) -> List[Dict[str, str]]:
        """Extract ICD-10 codes from diagnosis - SIMPLE VERSION for V1"""
        prompt = f"""
You are a medical coding assistant for Romanian healthcare.

Romanian Diagnosis Text:
{diagnosis_text}

Extract ICD-10 codes. Respond with JSON array:
{{
  "diagnoses": [
    {{
      "diagnosis_romanian": "Tuberculoza pulmonară",
      "icd10_code": "A16.1",
      "icd10_description": "Tubercoloza pulmonara, fara investigatii bacteriologice sau histologice",
      "confidence": "high",
      "notes": ""
    }}
  ]
}}

Rules:
1. Use most specific code available
2. If code requires additional codes (marked with †), mention in notes field
3. Keep it simple - doctor will validate
4. Romanian medical terminology

IMPORTANT: Do NOT validate cross-references or exclusion rules. Just suggest codes.
"""
        
        try:
            response = self._client.ChatCompletion.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical coding assistant. Suggest ICD-10 codes but do not enforce validation rules. The doctor will validate."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("diagnoses", [])
            
        except Exception as e:
            raise Exception(f"ICD-10 extraction failed: {str(e)}")
    
    def _get_system_prompt(self) -> str:
        """System prompt for field extraction"""
        return """You are a medical assistant helping Romanian doctors digitize consultation notes.

Your task is to extract structured medical information from Romanian consultation transcripts.

Rules:
1. Extract ONLY information explicitly mentioned in the transcript
2. Use exact medical terminology from the transcript
3. For fields not mentioned, return null
4. Preserve Romanian medical terms
5. Extract measurements with correct units
6. Be conservative - if uncertain, return null with low confidence

Respond with valid JSON matching the template structure provided."""
    
    def _build_extraction_prompt(
        self,
        transcript: str,
        template: Dict[str, Any],
        existing_data: Dict[str, Any] = None
    ) -> str:
        """Build extraction prompt from template and transcript"""
        
        extractable_fields = []
        for section in template["sections"]:
            section_id = section["section_id"]
            for field in section["fields"]:
                if field["audio_extractable"] in ["always", "conditional"]:
                    extractable_fields.append({
                        "section_id": section_id,
                        "field_id": field["field_id"],
                        "field_name": field["field_name"],
                        "field_type": field["field_type"],
                        "priority": field["audio_extractable"]
                    })
        
        prompt = f"""
Extract structured medical information from this Romanian consultation transcript.

CONSULTATION TRANSCRIPT:
{transcript}

TEMPLATE STRUCTURE:
Extract data for these fields:
{json.dumps(extractable_fields, indent=2, ensure_ascii=False)}

"""
        
        if existing_data:
            prompt += f"""
EXISTING DATA (do not overwrite unless transcript has newer information):
{json.dumps(existing_data, indent=2, ensure_ascii=False)}

"""
        
        prompt += """
OUTPUT FORMAT:
Return JSON with this structure:
{
  "section_id": {
    "field_id": "extracted_value",
    "field_id_confidence": "high/medium/low"
  }
}

Example:
{
  "chief_complaint": {
    "complaint_description": "Durere toracică de 3 zile",
    "complaint_description_confidence": "high",
    "symptom_duration": "3 zile",
    "symptom_duration_confidence": "high"
  },
  "vital_signs": {
    "blood_pressure_systolic": 140,
    "blood_pressure_systolic_confidence": "high",
    "blood_pressure_diastolic": 90,
    "blood_pressure_diastolic_confidence": "high"
  }
}

Extract all mentioned fields. Return null for unmentioned fields.
"""
        return prompt