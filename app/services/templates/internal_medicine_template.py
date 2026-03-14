# app/services/templates/internal_medicine_template.py
from .base_template import ConsultationTemplate, TemplateSection, TemplateField, FieldType, AudioExtractability
from .core_sections import (
    get_patient_identification_section,
    get_chief_complaint_section,
    get_vital_signs_section,
    get_diagnosis_section,
    get_treatment_plan_section
)

def get_history_present_illness_section() -> TemplateSection:
    """Detailed history of present illness"""
    return TemplateSection(
        section_id="history_present_illness",
        section_name="History of Present Illness / Istoricul Bolii Actuale",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="illness_narrative",
                field_name="Detailed History",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="Detailed chronological account of symptoms...",
                openehr_archetype="openEHR-EHR-SECTION.history_of_present_illness.v1"
            ),
            TemplateField(
                field_id="aggravating_factors",
                field_name="Aggravating Factors",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="What makes it worse?"
            ),
            TemplateField(
                field_id="relieving_factors",
                field_name="Relieving Factors",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="What makes it better?"
            )
        ]
    )

def get_review_of_systems_section() -> TemplateSection:
    """Systematic review - Internal Medicine specific"""
    return TemplateSection(
        section_id="review_of_systems",
        section_name="Review of Systems / Revizia Sistemelor",
        section_description="Systematic review of body systems",
        collapsible=True,
        fields=[
            # Constitutional
            TemplateField(
                field_id="constitutional_symptoms",
                field_name="Constitutional (Fever, Weight Loss, Fatigue)",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Fever, chills, night sweats, weight changes..."
            ),
            # Cardiovascular
            TemplateField(
                field_id="cardiovascular_symptoms",
                field_name="Cardiovascular",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Chest pain, palpitations, edema...",
                pre_fill_source="previous_consult"  # If cardiology history exists
            ),
            # Respiratory
            TemplateField(
                field_id="respiratory_symptoms",
                field_name="Respiratory",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Cough, dyspnea, wheezing...",
                pre_fill_source="previous_consult"
            ),
            # Gastrointestinal
            TemplateField(
                field_id="gastrointestinal_symptoms",
                field_name="Gastrointestinal",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Nausea, vomiting, diarrhea, constipation..."
            ),
            # Genitourinary
            TemplateField(
                field_id="genitourinary_symptoms",
                field_name="Genitourinary",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Urinary frequency, dysuria, hematuria..."
            ),
            # Musculoskeletal
            TemplateField(
                field_id="musculoskeletal_symptoms",
                field_name="Musculoskeletal",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Joint pain, swelling, stiffness..."
            ),
            # Neurological
            TemplateField(
                field_id="neurological_symptoms",
                field_name="Neurological",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Headache, dizziness, weakness, numbness..."
            ),
            # Endocrine
            TemplateField(
                field_id="endocrine_symptoms",
                field_name="Endocrine",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Polyuria, polydipsia, heat/cold intolerance..."
            )
        ]
    )

def get_past_medical_history_section() -> TemplateSection:
    """Past medical history - pre-filled from previous consultations"""
    return TemplateSection(
        section_id="past_medical_history",
        section_name="Past Medical History / Antecedente Personale",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="chronic_conditions",
                field_name="Chronic Conditions",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Diabetes, hypertension, asthma..."
            ),
            TemplateField(
                field_id="surgical_history",
                field_name="Surgical History",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Previous surgeries and dates..."
            ),
            TemplateField(
                field_id="current_medications",
                field_name="Current Medications",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Ongoing medication list..."
            ),
            TemplateField(
                field_id="allergies",
                field_name="Allergies",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Drug allergies, food allergies..."
            )
        ]
    )

def get_physical_examination_section() -> TemplateSection:
    """Physical examination findings"""
    return TemplateSection(
        section_id="physical_examination",
        section_name="Physical Examination / Examen Fizic",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="general_appearance",
                field_name="General Appearance",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Well-appearing, in distress, etc."
            ),
            TemplateField(
                field_id="heent_findings",
                field_name="HEENT (Head, Eyes, Ears, Nose, Throat)",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL
            ),
            TemplateField(
                field_id="cardiovascular_exam",
                field_name="Cardiovascular Exam",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Heart sounds, murmurs, peripheral pulses..."
            ),
            TemplateField(
                field_id="respiratory_exam",
                field_name="Respiratory Exam",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Breath sounds, adventitious sounds..."
            ),
            TemplateField(
                field_id="abdominal_exam",
                field_name="Abdominal Exam",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Tenderness, organomegaly, bowel sounds..."
            ),
            TemplateField(
                field_id="neurological_exam",
                field_name="Neurological Exam",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Mental status, cranial nerves, motor/sensory..."
            )
        ]
    )

def get_internal_medicine_template() -> ConsultationTemplate:
    """Complete Internal Medicine consultation template"""
    return ConsultationTemplate(
        template_id="internal_medicine_v1",
        specialty="internal_medicine",
        version="1.0",
        sections=[
            get_patient_identification_section(),
            get_chief_complaint_section(),
            get_history_present_illness_section(),
            get_past_medical_history_section(),
            get_review_of_systems_section(),
            get_vital_signs_section(),
            get_physical_examination_section(),
            get_diagnosis_section(),
            get_treatment_plan_section()
        ]
    )