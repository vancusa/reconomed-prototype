# app/services/templates/base_template.py
from typing import Dict, List, Any, Optional
from enum import Enum

class FieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SELECT = "select"
    MULTISELECT = "multiselect"
    DATE = "date"
    CHECKBOX = "checkbox"
    VITAL_SIGNS = "vital_signs"  # Composite field
    ICD10 = "icd10"  # Special handling

class AudioExtractability(str, Enum):
    ALWAYS = "always"  # LLM should always extract if present
    CONDITIONAL = "conditional"  # Extract if mentioned
    NEVER = "never"  # Manual entry only

class TemplateField:
    def __init__(
        self,
        field_id: str,
        field_name: str,
        field_type: FieldType,
        required: bool = False,
        audio_extractable: AudioExtractability = AudioExtractability.CONDITIONAL,
        pre_fill_source: Optional[str] = None,  # "previous_consult" or None
        placeholder: str = "",
        validation: Optional[Dict] = None,
        options: Optional[List[Dict]] = None,  # For select/multiselect
        units: Optional[str] = None,  # For number fields
        openehr_archetype: Optional[str] = None,  # Future migration
        openehr_path: Optional[str] = None
    ):
        self.field_id = field_id
        self.field_name = field_name
        self.field_type = field_type
        self.required = required
        self.audio_extractable = audio_extractable
        self.pre_fill_source = pre_fill_source
        self.placeholder = placeholder
        self.validation = validation or {}
        self.options = options or []
        self.units = units
        self.openehr_archetype = openehr_archetype
        self.openehr_path = openehr_path
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "field_name": self.field_name,
            "field_type": self.field_type.value,
            "required": self.required,
            "audio_extractable": self.audio_extractable.value,
            "pre_fill_source": self.pre_fill_source,
            "placeholder": self.placeholder,
            "validation": self.validation,
            "options": self.options,
            "units": self.units,
            "openehr_archetype": self.openehr_archetype,
            "openehr_path": self.openehr_path
        }

class TemplateSection:
    def __init__(
        self,
        section_id: str,
        section_name: str,
        section_description: str = "",
        collapsible: bool = False,
        fields: List[TemplateField] = None
    ):
        self.section_id = section_id
        self.section_name = section_name
        self.section_description = section_description
        self.collapsible = collapsible
        self.fields = fields or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_name": self.section_name,
            "section_description": self.section_description,
            "collapsible": self.collapsible,
            "fields": [f.to_dict() for f in self.fields]
        }

class ConsultationTemplate:
    def __init__(
        self,
        template_id: str,
        specialty: str,
        version: str,
        sections: List[TemplateSection]
    ):
        self.template_id = template_id
        self.specialty = specialty
        self.version = version
        self.sections = sections
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "specialty": self.specialty,
            "version": self.version,
            "template_format": "pragmatic_json_v1",
            "openehr_compatible": True,
            "sections": [s.to_dict() for s in self.sections]
        }