# app/services/templates/respiratory_template.py
from .base_template import ConsultationTemplate, TemplateSection, TemplateField, FieldType, AudioExtractability
from .core_sections import (
    get_patient_identification_section,
    get_chief_complaint_section,
    get_vital_signs_section,
    get_diagnosis_section,
    get_treatment_plan_section
)

def get_respiratory_history_section() -> TemplateSection:
    """Respiratory-specific history"""
    return TemplateSection(
        section_id="respiratory_history",
        section_name="Respiratory History / Istoric Respirator",
        section_description="Detailed respiratory symptoms and history",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="cough_type",
                field_name="Cough Type / Tipul Tusei",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "dry", "label": "Dry / Uscată"},
                    {"value": "productive", "label": "Productive / Productivă"},
                    {"value": "paroxysmal", "label": "Paroxysmal / Paroxistică"}
                ],
                openehr_archetype="openEHR-EHR-OBSERVATION.cough.v1"
            ),
            TemplateField(
                field_id="cough_duration",
                field_name="Cough Duration / Durata Tusei",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="e.g., 2 weeks, 3 months, chronic..."
            ),
            TemplateField(
                field_id="sputum_characteristics",
                field_name="Sputum Characteristics / Caracteristicile Sputei",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Color (clear, yellow, green, bloody), consistency, volume...",
                openehr_archetype="openEHR-EHR-OBSERVATION.sputum.v1"
            ),
            TemplateField(
                field_id="dyspnea_severity",
                field_name="Dyspnea Severity / Severitatea Dispneei",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "on_exertion", "label": "On Exertion / La Efort"},
                    {"value": "at_rest", "label": "At Rest / În Repaus"},
                    {"value": "orthopnea", "label": "Orthopnea / Ortopnee"},
                    {"value": "paroxysmal_nocturnal", "label": "Paroxysmal Nocturnal / Dispnee Paroxistică Nocturnă"}
                ],
                openehr_archetype="openEHR-EHR-OBSERVATION.dyspnea.v1"
            ),
            TemplateField(
                field_id="wheezing",
                field_name="Wheezing / Wheezing",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Present/absent, timing, triggers..."
            ),
            TemplateField(
                field_id="hemoptysis",
                field_name="Hemoptysis / Hemoptizie",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Amount, frequency, color..."
            )
        ]
    )

def get_smoking_history_section() -> TemplateSection:
    """Detailed smoking history"""
    return TemplateSection(
        section_id="smoking_history",
        section_name="Smoking History / Istoric de Fumat",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="smoking_status",
                field_name="Smoking Status / Statut Fumat",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                options=[
                    {"value": "never", "label": "Never Smoked / Niciodată"},
                    {"value": "former", "label": "Former Smoker / Fost Fumător"},
                    {"value": "current", "label": "Current Smoker / Fumător Activ"}
                ]
            ),
            TemplateField(
                field_id="cigarettes_per_day",
                field_name="Cigarettes Per Day / Țigări pe Zi",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                units="cigarettes/day"
            ),
            TemplateField(
                field_id="smoking_years",
                field_name="Years Smoked / Ani de Fumat",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                units="years"
            ),
            TemplateField(
                field_id="pack_years",
                field_name="Pack-Years (Calculated) / Pack-Years",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="(Cigarettes per day / 20) × Years smoked",
                units="pack-years"
            ),
            TemplateField(
                field_id="quit_date",
                field_name="Quit Date (if former smoker) / Data Renunțării",
                field_type=FieldType.DATE,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult"
            )
        ]
    )

def get_respiratory_exam_section() -> TemplateSection:
    """Respiratory physical examination"""
    return TemplateSection(
        section_id="respiratory_exam",
        section_name="Respiratory Examination / Examen Respirator",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="inspection",
                field_name="Inspection / Inspecție",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Chest shape (barrel chest, kyphosis), breathing pattern, use of accessory muscles, cyanosis..."
            ),
            TemplateField(
                field_id="palpation_percussion",
                field_name="Palpation & Percussion / Palpare și Percuție",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Tactile fremitus, chest expansion, percussion note..."
            ),
            TemplateField(
                field_id="auscultation",
                field_name="Auscultation / Auscultație",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                placeholder="Breath sounds (normal vesicular, bronchial, diminished), adventitious sounds...",
                openehr_archetype="openEHR-EHR-OBSERVATION.lung_auscultation.v1"
            ),
            TemplateField(
                field_id="adventitious_sounds",
                field_name="Adventitious Sounds / Zgomote Adventive",
                field_type=FieldType.MULTISELECT,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "crackles", "label": "Crackles/Rales / Raluri Crepitante"},
                    {"value": "wheezes", "label": "Wheezes / Sibilanțe"},
                    {"value": "rhonchi", "label": "Rhonchi / Ronhusuri"},
                    {"value": "stridor", "label": "Stridor"},
                    {"value": "pleural_rub", "label": "Pleural Rub / Frecare Pleurală"}
                ]
            ),
            TemplateField(
                field_id="oxygen_saturation_room_air",
                field_name="SpO₂ on Room Air / SpO₂ pe Aer",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="%",
                validation={"min": 70, "max": 100}
            )
        ]
    )

def get_pulmonary_function_tests_section() -> TemplateSection:
    """Pulmonary function test results"""
    return TemplateSection(
        section_id="pulmonary_function_tests",
        section_name="Pulmonary Function Tests (PFTs) / Teste Funcționale Respiratorii",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="fev1_value",
                field_name="FEV1 (Forced Expiratory Volume in 1 second)",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="L",
                openehr_archetype="openEHR-EHR-OBSERVATION.spirometry.v1"
            ),
            TemplateField(
                field_id="fev1_percent_predicted",
                field_name="FEV1 % Predicted / FEV1 % Prezis",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="%"
            ),
            TemplateField(
                field_id="fvc_value",
                field_name="FVC (Forced Vital Capacity)",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="L"
            ),
            TemplateField(
                field_id="fvc_percent_predicted",
                field_name="FVC % Predicted / FVC % Prezis",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="%"
            ),
            TemplateField(
                field_id="fev1_fvc_ratio",
                field_name="FEV1/FVC Ratio",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Normal: > 0.70",
                validation={"min": 0, "max": 1, "step": 0.01}
            ),
            TemplateField(
                field_id="dlco",
                field_name="DLCO (Diffusing Capacity)",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Value and % predicted"
            )
        ]
    )

def get_oxygen_therapy_section() -> TemplateSection:
    """Oxygen and respiratory support"""
    return TemplateSection(
        section_id="oxygen_therapy",
        section_name="Oxygen Therapy / Oxigenoterapie",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="oxygen_requirement",
                field_name="Oxygen Requirement / Necesită Oxigen",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "none", "label": "None / Nu"},
                    {"value": "prn", "label": "PRN (As Needed) / La Nevoie"},
                    {"value": "continuous", "label": "Continuous / Continuu"}
                ]
            ),
            TemplateField(
                field_id="oxygen_delivery_method",
                field_name="Delivery Method / Metodă de Administrare",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "nasal_cannula", "label": "Nasal Cannula / Canulă Nazală"},
                    {"value": "simple_mask", "label": "Simple Face Mask / Mască Simplă"},
                    {"value": "venturi_mask", "label": "Venturi Mask / Mască Venturi"},
                    {"value": "non_rebreather", "label": "Non-Rebreather Mask / Mască Non-Rebreather"},
                    {"value": "cpap", "label": "CPAP"},
                    {"value": "bipap", "label": "BiPAP"}
                ]
            ),
            TemplateField(
                field_id="oxygen_flow_rate",
                field_name="Flow Rate / Debit",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="e.g., 2 L/min, 4 L/min",
                units="L/min"
            )
        ]
    )

def get_respiratory_template() -> ConsultationTemplate:
    """Complete Respiratory Medicine consultation template"""
    return ConsultationTemplate(
        template_id="respiratory_v1",
        specialty="respiratory",
        version="1.0",
        sections=[
            get_patient_identification_section(),
            get_chief_complaint_section(),
            get_respiratory_history_section(),
            get_smoking_history_section(),
            get_vital_signs_section(),
            get_respiratory_exam_section(),
            get_pulmonary_function_tests_section(),
            get_oxygen_therapy_section(),
            get_diagnosis_section(),
            get_treatment_plan_section()
        ]
    )