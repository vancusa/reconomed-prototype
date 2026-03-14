# app/services/templates/gynecology_template.py
from .base_template import ConsultationTemplate, TemplateSection, TemplateField, FieldType, AudioExtractability
from .core_sections import (
    get_patient_identification_section,
    get_chief_complaint_section,
    get_vital_signs_section,
    get_diagnosis_section,
    get_treatment_plan_section
)

def get_menstrual_history_section() -> TemplateSection:
    """Menstrual history"""
    return TemplateSection(
        section_id="menstrual_history",
        section_name="Menstrual History / Istoric Menstrual",
        section_description="Detailed menstrual cycle information",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="lmp",
                field_name="Last Menstrual Period (LMP) / Ultima Menstruație",
                field_type=FieldType.DATE,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                pre_fill_source="previous_consult",
                openehr_archetype="openEHR-EHR-OBSERVATION.menstrual_cycle.v1"
            ),
            TemplateField(
                field_id="menarche_age",
                field_name="Age at Menarche / Vârsta Menarhei",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                units="years",
                validation={"min": 8, "max": 18}
            ),
            TemplateField(
                field_id="cycle_length",
                field_name="Cycle Length / Durata Ciclului",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Average number of days between periods",
                units="days",
                validation={"min": 21, "max": 45}
            ),
            TemplateField(
                field_id="cycle_regularity",
                field_name="Cycle Regularity / Regularitate",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                options=[
                    {"value": "regular", "label": "Regular / Regulat"},
                    {"value": "irregular", "label": "Irregular / Neregulat"},
                    {"value": "variable", "label": "Variable / Variabil"}
                ]
            ),
            TemplateField(
                field_id="menstrual_flow",
                field_name="Menstrual Flow / Fluxul Menstrual",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "light", "label": "Light / Scăzut"},
                    {"value": "moderate", "label": "Moderate / Moderat"},
                    {"value": "heavy", "label": "Heavy / Abundent"},
                    {"value": "very_heavy", "label": "Very Heavy / Foarte Abundent"}
                ]
            ),
            TemplateField(
                field_id="dysmenorrhea",
                field_name="Dysmenorrhea / Dismenoree",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "mild", "label": "Mild / Ușoară"},
                    {"value": "moderate", "label": "Moderate / Moderată"},
                    {"value": "severe", "label": "Severe / Severă"}
                ]
            ),
            TemplateField(
                field_id="menopause_status",
                field_name="Menopause Status / Statut Menopauzal",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                options=[
                    {"value": "premenopausal", "label": "Premenopausal / Premenopauzală"},
                    {"value": "perimenopausal", "label": "Perimenopausal / Perimenopauzală"},
                    {"value": "postmenopausal", "label": "Postmenopausal / Postmenopauzală"}
                ]
            ),
            TemplateField(
                field_id="menopause_age",
                field_name="Age at Menopause / Vârsta Menopauzei",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                units="years"
            )
        ]
    )

def get_obstetric_history_section() -> TemplateSection:
    """Obstetric and pregnancy history"""
    return TemplateSection(
        section_id="obstetric_history",
        section_name="Obstetric History / Istoric Obstetric",
        section_description="Pregnancy and delivery history (GTPAL)",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="gravida",
                field_name="Gravida (Total Pregnancies) / Gravida",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                pre_fill_source="previous_consult",
                validation={"min": 0, "max": 20},
                openehr_archetype="openEHR-EHR-OBSERVATION.obstetric_summary.v1"
            ),
            TemplateField(
                field_id="para_term",
                field_name="Para - Term Births / Nașteri la Termen",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                validation={"min": 0, "max": 20}
            ),
            TemplateField(
                field_id="para_preterm",
                field_name="Para - Preterm Births / Nașteri Premature",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                validation={"min": 0, "max": 20}
            ),
            TemplateField(
                field_id="abortions",
                field_name="Abortions (Spontaneous + Induced) / Avorturi",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                validation={"min": 0, "max": 20}
            ),
            TemplateField(
                field_id="living_children",
                field_name="Living Children / Copii în Viață",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                validation={"min": 0, "max": 20}
            ),
            TemplateField(
                field_id="delivery_details",
                field_name="Previous Delivery Details / Detalii Nașteri Anterioare",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Vaginal/C-section, complications, birth weights, dates..."
            ),
            TemplateField(
                field_id="pregnancy_complications",
                field_name="Past Pregnancy Complications / Complicații Sarcini Anterioare",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Gestational diabetes, preeclampsia, preterm labor, etc."
            )
        ]
    )

def get_gynecologic_history_section() -> TemplateSection:
    """Gynecologic symptoms and conditions"""
    return TemplateSection(
        section_id="gynecologic_history",
        section_name="Gynecologic History / Istoric Ginecologic",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="vaginal_discharge",
                field_name="Vaginal Discharge / Scurgeri Vaginale",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Color, odor, consistency, associated symptoms..."
            ),
            TemplateField(
                field_id="vaginal_bleeding_abnormal",
                field_name="Abnormal Vaginal Bleeding / Sângerare Vaginală Anormală",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Intermenstrual bleeding, postcoital bleeding, postmenopausal bleeding..."
            ),
            TemplateField(
                field_id="pelvic_pain",
                field_name="Pelvic Pain / Durere Pelviană",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Location, character, timing, severity, aggravating/relieving factors..."
            ),
            TemplateField(
                field_id="dyspareunia",
                field_name="Dyspareunia (Painful Intercourse) / Dispareunie",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "superficial", "label": "Superficial / Superficială"},
                    {"value": "deep", "label": "Deep / Profundă"}
                ]
            ),
            TemplateField(
                field_id="urinary_symptoms",
                field_name="Urinary Symptoms / Simptome Urinare",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Urgency, frequency, dysuria, incontinence..."
            )
        ]
    )

def get_contraception_sexual_health_section() -> TemplateSection:
    """Contraception and sexual health"""
    return TemplateSection(
        section_id="contraception_sexual_health",
        section_name="Contraception & Sexual Health / Contracepție și Sănătate Sexuală",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="contraception_current",
                field_name="Current Contraception Method / Metodă Contraceptivă Actuală",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                options=[
                    {"value": "none", "label": "None / Niciunul"},
                    {"value": "oral_contraceptives", "label": "Oral Contraceptives / Contraceptive Orale"},
                    {"value": "iud_copper", "label": "IUD (Copper) / DIU (Cupru)"},
                    {"value": "iud_hormonal", "label": "IUD (Hormonal) / DIU (Hormonal)"},
                    {"value": "implant", "label": "Implant / Implant"},
                    {"value": "injection", "label": "Injection / Injecție"},
                    {"value": "condoms", "label": "Condoms / Prezervative"},
                    {"value": "natural_methods", "label": "Natural Methods / Metode Naturale"},
                    {"value": "sterilization", "label": "Sterilization / Sterilizare"}
                ],
                openehr_archetype="openEHR-EHR-CLUSTER.contraception.v1"
            ),
            TemplateField(
                field_id="contraception_start_date",
                field_name="Start Date / Data Începerii",
                field_type=FieldType.DATE,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult"
            ),
            TemplateField(
                field_id="contraception_complications",
                field_name="Complications/Side Effects / Complicații",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Any issues with current method..."
            ),
            TemplateField(
                field_id="sexually_active",
                field_name="Sexually Active / Activă Sexual",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "yes", "label": "Yes / Da"},
                    {"value": "no", "label": "No / Nu"}
                ]
            ),
            TemplateField(
                field_id="sti_history",
                field_name="STI History / Istoric Infecții Transmise Sexual",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Previous STIs, treatment, partner notification..."
            )
        ]
    )

def get_gynecologic_exam_section() -> TemplateSection:
    """Gynecologic physical examination"""
    return TemplateSection(
        section_id="gynecologic_exam",
        section_name="Gynecologic Examination / Examen Ginecologic",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="external_genitalia",
                field_name="External Genitalia / Organele Genitale Externe",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Normal appearance, lesions, masses, etc."
            ),
            TemplateField(
                field_id="speculum_exam_cervix",
                field_name="Speculum Exam - Cervix / Examen cu Specul - Col Uterin",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Appearance, discharge, lesions, ectropion...",
                openehr_archetype="openEHR-EHR-OBSERVATION.exam_cervix.v1"
            ),
            TemplateField(
                field_id="speculum_exam_discharge",
                field_name="Vaginal Discharge Characteristics / Caracteristicile Scurgerilor",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Color, consistency, odor..."
            ),
            TemplateField(
                field_id="bimanual_exam_uterus",
                field_name="Bimanual Exam - Uterus / Examen Bimanual - Uter",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Size, position (anteverted/retroverted), mobility, tenderness, masses...",
                openehr_archetype="openEHR-EHR-OBSERVATION.exam_uterus.v1"
            ),
            TemplateField(
                field_id="bimanual_exam_adnexa",
                field_name="Bimanual Exam - Adnexa / Examen Bimanual - Anexe",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Ovaries (palpable/non-palpable, size, tenderness), masses, tenderness..."
            ),
            TemplateField(
                field_id="rectovaginal_exam",
                field_name="Rectovaginal Exam / Examen Rectovaginal",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Performed if indicated, findings..."
            )
        ]
    )

def get_breast_exam_section() -> TemplateSection:
    """Breast examination"""
    return TemplateSection(
        section_id="breast_exam",
        section_name="Breast Examination / Examinarea Sânilor",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="breast_inspection",
                field_name="Inspection / Inspecție",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Symmetry, skin changes, nipple abnormalities..."
            ),
            TemplateField(
                field_id="breast_palpation",
                field_name="Palpation / Palpare",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Masses, tenderness, location, characteristics...",
                openehr_archetype="openEHR-EHR-OBSERVATION.exam_breast.v1"
            ),
            TemplateField(
                field_id="nipple_discharge",
                field_name="Nipple Discharge / Scurgere Mamelonară",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Present/absent, color, bilateral/unilateral..."
            ),
            TemplateField(
                field_id="axillary_lymph_nodes",
                field_name="Axillary Lymph Nodes / Ganglioni Limfatici Axilari",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Palpable/non-palpable, size, tenderness..."
            )
        ]
    )

def get_screening_section() -> TemplateSection:
    """Cancer screening and preventive care"""
    return TemplateSection(
        section_id="gynecologic_screening",
        section_name="Screening & Prevention / Screening și Prevenție",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="last_pap_smear_date",
                field_name="Last Pap Smear Date / Ultima Analiză Babeș-Papanicolau",
                field_type=FieldType.DATE,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult"
            ),
            TemplateField(
                field_id="last_pap_smear_result",
                field_name="Last Pap Smear Result / Rezultat",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Normal, ASCUS, LSIL, HSIL, etc."
            ),
            TemplateField(
                field_id="hpv_testing",
                field_name="HPV Testing / Test HPV",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Date and result"
            ),
            TemplateField(
                field_id="last_mammogram_date",
                field_name="Last Mammogram Date / Ultima Mamografie",
                field_type=FieldType.DATE,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult"
            ),
            TemplateField(
                field_id="last_mammogram_result",
                field_name="Last Mammogram Result / Rezultat Mamografie",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="BI-RADS category, findings..."
            )
        ]
    )

def get_gynecology_template() -> ConsultationTemplate:
    """Complete Gynecology consultation template"""
    return ConsultationTemplate(
        template_id="gynecology_v1",
        specialty="gynecology",
        version="1.0",
        sections=[
            get_patient_identification_section(),
            get_chief_complaint_section(),
            get_menstrual_history_section(),
            get_obstetric_history_section(),
            get_gynecologic_history_section(),
            get_contraception_sexual_health_section(),
            get_vital_signs_section(),
            get_gynecologic_exam_section(),
            get_breast_exam_section(),
            get_screening_section(),
            get_diagnosis_section(),
            get_treatment_plan_section()
        ]
    )