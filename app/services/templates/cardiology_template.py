# app/services/templates/cardiology_template.py
from .base_template import ConsultationTemplate, TemplateSection, TemplateField, FieldType, AudioExtractability
from .core_sections import (
    get_patient_identification_section,
    get_chief_complaint_section,
    get_vital_signs_section,
    get_diagnosis_section,
    get_treatment_plan_section
)

def get_cardiac_history_section() -> TemplateSection:
    """Cardiology-specific history"""
    return TemplateSection(
        section_id="cardiac_history",
        section_name="Cardiac History / Istoric Cardiac",
        section_description="Detailed cardiac symptoms and history",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="chest_pain_type",
                field_name="Chest Pain Type / Tipul Durerii Toracice",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "typical_angina", "label": "Typical Angina / Angină Tipică"},
                    {"value": "atypical_angina", "label": "Atypical Angina / Angină Atipică"},
                    {"value": "non_cardiac", "label": "Non-Cardiac / Non-Cardiacă"}
                ],
                openehr_archetype="openEHR-EHR-OBSERVATION.chest_pain.v1"
            ),
            TemplateField(
                field_id="chest_pain_description",
                field_name="Chest Pain Description / Descrierea Durerii",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="PQRST assessment: Provocation, Quality, Radiation, Severity, Timing..."
            ),
            TemplateField(
                field_id="dyspnea_grade",
                field_name="Dyspnea (NYHA Class) / Dispnee",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "nyha_1", "label": "NYHA I - No limitation"},
                    {"value": "nyha_2", "label": "NYHA II - Slight limitation"},
                    {"value": "nyha_3", "label": "NYHA III - Marked limitation"},
                    {"value": "nyha_4", "label": "NYHA IV - Severe limitation"}
                ],
                openehr_archetype="openEHR-EHR-OBSERVATION.nyha_classification.v1"
            ),
            TemplateField(
                field_id="palpitations",
                field_name="Palpitations / Palpitații",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Frequency, duration, triggers, associated symptoms..."
            ),
            TemplateField(
                field_id="syncope_presyncope",
                field_name="Syncope/Presyncope / Sincopă",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Episodes of loss of consciousness or near-fainting..."
            ),
            TemplateField(
                field_id="edema_location",
                field_name="Edema Location / Localizarea Edemului",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="e.g., bilateral lower extremities, sacral..."
            )
        ]
    )

def get_cardiovascular_exam_section() -> TemplateSection:
    """Cardiovascular physical examination"""
    return TemplateSection(
        section_id="cardiovascular_exam",
        section_name="Cardiovascular Examination / Examen Cardiovascular",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="jugular_venous_pressure",
                field_name="Jugular Venous Pressure (JVP) / Presiunea Venoasă Jugulară",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="e.g., elevated at 8 cm H2O, normal...",
                openehr_archetype="openEHR-EHR-OBSERVATION.jvp.v1"
            ),
            TemplateField(
                field_id="heart_sounds",
                field_name="Heart Sounds / Zgomote Cardiace",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="S1, S2 normal/abnormal, S3, S4, rhythm regularity...",
                openehr_archetype="openEHR-EHR-OBSERVATION.heart_sounds.v1"
            ),
            TemplateField(
                field_id="murmurs",
                field_name="Murmurs / Sufluri Cardiace",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="Location, timing (systolic/diastolic), grade, radiation...",
                openehr_archetype="openEHR-EHR-OBSERVATION.heart_murmur.v1"
            ),
            TemplateField(
                field_id="peripheral_pulses",
                field_name="Peripheral Pulses / Pulsuri Periferice",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Radial, femoral, dorsalis pedis, posterior tibial - present/diminished/absent"
            ),
            TemplateField(
                field_id="peripheral_edema_grade",
                field_name="Peripheral Edema (Pitting Scale) / Edem Periferic",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "grade_1", "label": "Grade 1+ (2mm depression)"},
                    {"value": "grade_2", "label": "Grade 2+ (4mm depression)"},
                    {"value": "grade_3", "label": "Grade 3+ (6mm depression)"},
                    {"value": "grade_4", "label": "Grade 4+ (8mm depression)"}
                ]
            )
        ]
    )

def get_cardiac_investigations_section() -> TemplateSection:
    """Cardiac test results"""
    return TemplateSection(
        section_id="cardiac_investigations",
        section_name="Cardiac Investigations / Investigații Cardiace",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="ecg_findings",
                field_name="ECG Findings / ECG",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="Rate, rhythm, axis, intervals, ST changes, Q waves, T wave abnormalities...",
                openehr_archetype="openEHR-EHR-OBSERVATION.ecg_result.v1"
            ),
            TemplateField(
                field_id="troponin_level",
                field_name="Troponin Level / Troponina",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="e.g., < 0.04 ng/mL (normal), elevated...",
                units="ng/mL"
            ),
            TemplateField(
                field_id="bnp_level",
                field_name="BNP/NT-proBNP Level",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="e.g., BNP 150 pg/mL or NT-proBNP 300 pg/mL",
                units="pg/mL"
            ),
            TemplateField(
                field_id="lipid_panel",
                field_name="Lipid Panel / Profil Lipidic",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Total cholesterol, LDL, HDL, Triglycerides..."
            ),
            TemplateField(
                field_id="echocardiogram_findings",
                field_name="Echocardiogram Findings / Ecocardiografie",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="LVEF, chamber sizes, valve function, wall motion abnormalities...",
                openehr_archetype="openEHR-EHR-OBSERVATION.echocardiogram.v1"
            )
        ]
    )

def get_cardiac_risk_factors_section() -> TemplateSection:
    """Cardiovascular risk factors"""
    return TemplateSection(
        section_id="cardiac_risk_factors",
        section_name="Cardiovascular Risk Factors / Factori de Risc",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="smoking_status",
                field_name="Smoking Status / Fumat",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                options=[
                    {"value": "never", "label": "Never / Niciodată"},
                    {"value": "former", "label": "Former / Fost fumător"},
                    {"value": "current", "label": "Current / Fumător activ"}
                ]
            ),
            TemplateField(
                field_id="smoking_pack_years",
                field_name="Pack-Years (if applicable)",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                units="pack-years"
            ),
            TemplateField(
                field_id="diabetes_status",
                field_name="Diabetes / Diabet",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "type_1", "label": "Type 1 / Tip 1"},
                    {"value": "type_2", "label": "Type 2 / Tip 2"},
                    {"value": "prediabetes", "label": "Prediabetes"}
                ]
            ),
            TemplateField(
                field_id="hypertension_duration",
                field_name="Hypertension Duration / Durata Hipertensiunii",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="e.g., 5 years, newly diagnosed..."
            ),
            TemplateField(
                field_id="family_history_cardiac",
                field_name="Family History of Cardiac Disease / Istoric Familial",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="First-degree relatives with MI, sudden cardiac death, age at diagnosis..."
            )
        ]
    )

def get_cardiology_template() -> ConsultationTemplate:
    """Complete Cardiology consultation template"""
    return ConsultationTemplate(
        template_id="cardiology_v1",
        specialty="cardiology",
        version="1.0",
        sections=[
            get_patient_identification_section(),
            get_chief_complaint_section(),
            get_cardiac_history_section(),
            get_cardiac_risk_factors_section(),
            get_vital_signs_section(),
            get_cardiovascular_exam_section(),
            get_cardiac_investigations_section(),
            get_diagnosis_section(),
            get_treatment_plan_section()
        ]
    )