# app/services/templates/core_sections.py
from .base_template import TemplateSection, TemplateField, FieldType, AudioExtractability

def get_patient_identification_section() -> TemplateSection:
    """Pre-filled patient demographics - read-only in consultation"""
    return TemplateSection(
        section_id="patient_identification",
        section_name="Patient Identification",
        collapsible=False,
        fields=[
            TemplateField(
                field_id="patient_name",
                field_name="Patient Name",
                field_type=FieldType.TEXT,
                required=True,
                audio_extractable=AudioExtractability.NEVER,
                pre_fill_source="patient_record"
            ),
            TemplateField(
                field_id="patient_cnp",
                field_name="CNP",
                field_type=FieldType.TEXT,
                required=True,
                audio_extractable=AudioExtractability.NEVER,
                pre_fill_source="patient_record"
            ),
            TemplateField(
                field_id="patient_age",
                field_name="Age",
                field_type=FieldType.NUMBER,
                required=True,
                audio_extractable=AudioExtractability.NEVER,
                pre_fill_source="patient_record",
                units="years"
            )
        ]
    )

def get_chief_complaint_section() -> TemplateSection:
    """Main reason for visit"""
    return TemplateSection(
        section_id="chief_complaint",
        section_name="Chief Complaint / Motivul Consultației",
        section_description="Primary reason for patient visit",
        collapsible=False,
        fields=[
            TemplateField(
                field_id="complaint_description",
                field_name="Description",
                field_type=FieldType.TEXTAREA,
                required=True,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="Describe the main complaint...",
                openehr_archetype="openEHR-EHR-OBSERVATION.story.v1",
                openehr_path="/data/events/any_event/data/items[complaint]"
            ),
            TemplateField(
                field_id="symptom_duration",
                field_name="Duration",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="e.g., 3 days, 2 weeks",
                openehr_archetype="openEHR-EHR-OBSERVATION.story.v1",
                openehr_path="/data/events/any_event/data/items[duration]"
            ),
            TemplateField(
                field_id="symptom_onset",
                field_name="Onset",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                options=[
                    {"value": "sudden", "label": "Sudden / Brusc"},
                    {"value": "gradual", "label": "Gradual / Gradat"},
                    {"value": "chronic", "label": "Chronic / Cronic"}
                ]
            )
        ]
    )

def get_vital_signs_section() -> TemplateSection:
    """Vital signs measurements"""
    return TemplateSection(
        section_id="vital_signs",
        section_name="Vital Signs / Semne Vitale",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="blood_pressure_systolic",
                field_name="Blood Pressure (Systolic)",
                field_type=FieldType.NUMBER,
                required=True,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="mmHg",
                validation={"min": 70, "max": 250},
                openehr_archetype="openEHR-EHR-OBSERVATION.blood_pressure.v2",
                openehr_path="/data/events/any_event/data/items[systolic]"
            ),
            TemplateField(
                field_id="blood_pressure_diastolic",
                field_name="Blood Pressure (Diastolic)",
                field_type=FieldType.NUMBER,
                required=True,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="mmHg",
                validation={"min": 40, "max": 150},
                openehr_archetype="openEHR-EHR-OBSERVATION.blood_pressure.v2",
                openehr_path="/data/events/any_event/data/items[diastolic]"
            ),
            TemplateField(
                field_id="heart_rate",
                field_name="Heart Rate / Frecvență Cardiacă",
                field_type=FieldType.NUMBER,
                required=True,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="bpm",
                validation={"min": 30, "max": 220},
                openehr_archetype="openEHR-EHR-OBSERVATION.pulse.v2"
            ),
            TemplateField(
                field_id="temperature",
                field_name="Temperature / Temperatură",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="°C",
                validation={"min": 35.0, "max": 42.0, "step": 0.1},
                openehr_archetype="openEHR-EHR-OBSERVATION.body_temperature.v2"
            ),
            TemplateField(
                field_id="respiratory_rate",
                field_name="Respiratory Rate / Frecvență Respiratorie",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="/min",
                validation={"min": 8, "max": 60}
            ),
            TemplateField(
                field_id="oxygen_saturation",
                field_name="SpO₂",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="%",
                validation={"min": 70, "max": 100}
            )
        ]
    )

def get_diagnosis_section() -> TemplateSection:
    """Diagnosis with ICD-10 codes"""
    return TemplateSection(
        section_id="diagnosis",
        section_name="Diagnosis / Diagnostic",
        collapsible=False,
        fields=[
            TemplateField(
                field_id="diagnoses",
                field_name="Diagnoses (ICD-10)",
                field_type=FieldType.ICD10,  # Special field type
                required=True,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="Describe diagnoses in natural language...",
                openehr_archetype="openEHR-EHR-EVALUATION.problem_diagnosis.v1"
            )
        ]
    )

def get_treatment_plan_section() -> TemplateSection:
    """Treatment and follow-up"""
    return TemplateSection(
        section_id="treatment_plan",
        section_name="Treatment Plan / Plan de Tratament",
        collapsible=False,
        fields=[
            TemplateField(
                field_id="medications",
                field_name="Medications / Medicație",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="List medications, dosages, frequency...",
                openehr_archetype="openEHR-EHR-INSTRUCTION.medication_order.v2"
            ),
            TemplateField(
                field_id="procedures",
                field_name="Procedures / Proceduri",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="Recommended procedures or tests..."
            ),
            TemplateField(
                field_id="follow_up_instructions",
                field_name="Follow-up Instructions",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="When to return, what to monitor..."
            ),
            TemplateField(
                field_id="lifestyle_recommendations",
                field_name="Lifestyle Recommendations",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Diet, exercise, lifestyle changes..."
            )
        ]
    )