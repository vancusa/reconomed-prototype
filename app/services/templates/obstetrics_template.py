# app/services/templates/obstetrics_template.py
from .base_template import ConsultationTemplate, TemplateSection, TemplateField, FieldType, AudioExtractability
from .core_sections import (
    get_patient_identification_section,
    get_chief_complaint_section,
    get_vital_signs_section,
    get_diagnosis_section,
    get_treatment_plan_section
)

def get_current_pregnancy_section() -> TemplateSection:
    """Current pregnancy details"""
    return TemplateSection(
        section_id="current_pregnancy",
        section_name="Current Pregnancy / Sarcina Actuală",
        section_description="Gestational age and pregnancy tracking",
        collapsible=False,
        fields=[
            TemplateField(
                field_id="lmp",
                field_name="Last Menstrual Period (LMP) / Ultima Menstruație",
                field_type=FieldType.DATE,
                required=True,
                audio_extractable=AudioExtractability.ALWAYS,
                pre_fill_source="previous_consult",
                openehr_archetype="openEHR-EHR-OBSERVATION.pregnancy_status.v1"
            ),
            TemplateField(
                field_id="edd",
                field_name="Estimated Due Date (EDD) / Data Estimată a Nașterii",
                field_type=FieldType.DATE,
                required=True,
                audio_extractable=AudioExtractability.ALWAYS,
                pre_fill_source="previous_consult",
                placeholder="Calculated from LMP or ultrasound"
            ),
            TemplateField(
                field_id="gestational_age_weeks",
                field_name="Gestational Age (Weeks) / Vârsta Gestațională",
                field_type=FieldType.NUMBER,
                required=True,
                audio_extractable=AudioExtractability.ALWAYS,
                units="weeks",
                validation={"min": 0, "max": 44}
            ),
            TemplateField(
                field_id="gestational_age_days",
                field_name="Gestational Age (Days) / Zile",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="days",
                validation={"min": 0, "max": 6}
            ),
            TemplateField(
                field_id="pregnancy_number",
                field_name="Pregnancy Number This Visit / Numărul Sarcinii",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="e.g., First pregnancy, Second pregnancy..."
            )
        ]
    )

def get_antenatal_symptoms_section() -> TemplateSection:
    """Symptoms in current pregnancy"""
    return TemplateSection(
        section_id="antenatal_symptoms",
        section_name="Pregnancy Symptoms / Simptome în Sarcină",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="nausea_vomiting",
                field_name="Nausea/Vomiting / Greață/Vărsături",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "none", "label": "None / Absent"},
                    {"value": "mild", "label": "Mild / Ușoară"},
                    {"value": "moderate", "label": "Moderate / Moderată"},
                    {"value": "severe", "label": "Severe (Hyperemesis) / Severă"}
                ]
            ),
            TemplateField(
                field_id="fetal_movements",
                field_name="Fetal Movements / Mișcări Fetale",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.ALWAYS,
                options=[
                    {"value": "not_yet_felt", "label": "Not Yet Felt / Încă Nu"},
                    {"value": "normal", "label": "Normal / Normale"},
                    {"value": "reduced", "label": "Reduced / Reduse"},
                    {"value": "absent", "label": "Absent / Absente"}
                ],
                openehr_archetype="openEHR-EHR-OBSERVATION.fetal_movement.v1"
            ),
            TemplateField(
                field_id="contractions",
                field_name="Contractions / Contracții",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Frequency, duration, regularity, painful..."
            ),
            TemplateField(
                field_id="vaginal_bleeding",
                field_name="Vaginal Bleeding / Sângerare Vaginală",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Amount, color, timing..."
            ),
            TemplateField(
                field_id="fluid_leakage",
                field_name="Fluid Leakage / Scurgere de Lichid",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Suspected rupture of membranes..."
            ),
            TemplateField(
                field_id="headache",
                field_name="Headache / Cefalee",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Severity, frequency, visual changes..."
            ),
            TemplateField(
                field_id="edema_swelling",
                field_name="Edema/Swelling / Edem/Umflare",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Location (face, hands, feet), severity..."
            )
        ]
    )

def get_antenatal_examination_section() -> TemplateSection:
    """Prenatal physical examination"""
    return TemplateSection(
        section_id="antenatal_examination",
        section_name="Antenatal Examination / Examen Prenatal",
        collapsible=False,
        fields=[
            TemplateField(
                field_id="maternal_weight",
                field_name="Maternal Weight / Greutatea Maternă",
                field_type=FieldType.NUMBER,
                required=True,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="kg",
                openehr_archetype="openEHR-EHR-OBSERVATION.body_weight.v2"
            ),
            TemplateField(
                field_id="weight_gain_total",
                field_name="Total Weight Gain / Creștere Totală în Greutate",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.NEVER,
                placeholder="Calculated from pre-pregnancy weight",
                units="kg"
            ),
            TemplateField(
                field_id="fundal_height",
                field_name="Fundal Height / Înălțimea Fundului Uterin",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="cm",
                validation={"min": 0, "max": 50},
                openehr_archetype="openEHR-EHR-OBSERVATION.fundal_height.v1"
            ),
            TemplateField(
                field_id="fetal_heart_rate",
                field_name="Fetal Heart Rate (FHR) / Frecvența Cardiacă Fetală",
                field_type=FieldType.NUMBER,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                units="bpm",
                validation={"min": 100, "max": 180},
                openehr_archetype="openEHR-EHR-OBSERVATION.fetal_heart_rate.v1"
            ),
            TemplateField(
                field_id="fetal_presentation",
                field_name="Fetal Presentation / Prezentația Fetală",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "not_determined", "label": "Not Yet Determined / Încă Nedeterminată"},
                    {"value": "cephalic", "label": "Cephalic (Head Down) / Cefalică"},
                    {"value": "breech", "label": "Breech / Pelviană"},
                    {"value": "transverse", "label": "Transverse / Transversală"}
                ]
            ),
            TemplateField(
                field_id="cervical_exam",
                field_name="Cervical Examination / Examen Cervical",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Dilation, effacement, station, consistency (if performed)..."
            ),
            TemplateField(
                field_id="urine_dipstick",
                field_name="Urine Dipstick / Analiză Urină",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Protein, glucose, ketones, blood..."
            )
        ]
    )

def get_pregnancy_risk_assessment_section() -> TemplateSection:
    """Risk screening and complications"""
    return TemplateSection(
        section_id="pregnancy_risk_assessment",
        section_name="Risk Assessment / Evaluarea Riscului",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="gestational_diabetes_screening",
                field_name="Gestational Diabetes Screening / Screening Diabet Gestațional",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="OGTT results, glucose levels..."
            ),
            TemplateField(
                field_id="preeclampsia_risk",
                field_name="Preeclampsia Risk Factors / Factori de Risc Preeclampsie",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Elevated BP, proteinuria, symptoms..."
            ),
            TemplateField(
                field_id="preterm_labor_risk",
                field_name="Preterm Labor Risk / Risc Naștere Prematură",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Cervical length, previous preterm birth, symptoms..."
            ),
            TemplateField(
                field_id="rh_status",
                field_name="Rh Blood Type Status / Statut Rh",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                pre_fill_source="previous_consult",
                placeholder="Rh positive/negative, antibody screen, RhoGAM given..."
            ),
            TemplateField(
                field_id="group_b_strep_status",
                field_name="Group B Streptococcus Status / Streptococ Grup B",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "not_tested", "label": "Not Yet Tested / Încă Netestat"},
                    {"value": "positive", "label": "Positive / Pozitiv"},
                    {"value": "negative", "label": "Negative / Negativ"}
                ]
            )
        ]
    )

def get_prenatal_labs_imaging_section() -> TemplateSection:
    """Laboratory and imaging results"""
    return TemplateSection(
        section_id="prenatal_labs_imaging",
        section_name="Labs & Imaging / Analize și Imagistică",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="hemoglobin_hematocrit",
                field_name="Hemoglobin/Hematocrit / Hemoglobină/Hematocrit",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="e.g., Hgb 12.5 g/dL, Hct 37%"
            ),
            TemplateField(
                field_id="ultrasound_findings",
                field_name="Ultrasound Findings / Rezultate Ecografie",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Biometric measurements (BPD, HC, AC, FL), AFI, placental location, anatomy scan...",
                openehr_archetype="openEHR-EHR-OBSERVATION.ultrasound_obstetric.v1"
            ),
            TemplateField(
                field_id="fetal_biometry",
                field_name="Fetal Biometry / Biometrie Fetală",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="BPD, HC, AC, FL measurements and percentiles..."
				),
            TemplateField(
                field_id="amniotic_fluid_index",
                field_name="Amniotic Fluid Index (AFI) / Indicele Lichidului Amniotic",
                field_type=FieldType.TEXT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="e.g., AFI 12 cm (normal 5-25 cm)"
            ),
            TemplateField(
                field_id="placental_location",
                field_name="Placental Location / Localizarea Placentei",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "anterior", "label": "Anterior"},
                    {"value": "posterior", "label": "Posterior"},
                    {"value": "fundal", "label": "Fundal"},
                    {"value": "low_lying", "label": "Low-Lying / Jos Poziționată"},
                    {"value": "previa", "label": "Placenta Previa"}
                ]
            )
        ]
    )

def get_prenatal_education_counseling_section() -> TemplateSection:
    """Patient education and counseling"""
    return TemplateSection(
        section_id="prenatal_education_counseling",
        section_name="Education & Counseling / Educație și Consiliere",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="nutrition_counseling",
                field_name="Nutrition Counseling / Consiliere Nutrițională",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Diet recommendations, prenatal vitamins, food safety..."
            ),
            TemplateField(
                field_id="warning_signs_discussed",
                field_name="Warning Signs Discussed / Semne de Alarmă Discutate",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Preeclampsia symptoms, preterm labor, decreased fetal movement, bleeding..."
            ),
            TemplateField(
                field_id="labor_signs_discussed",
                field_name="Labor Signs Discussed / Semne de Travaliu Discutate",
                field_type=FieldType.CHECKBOX,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Regular contractions, rupture of membranes, bloody show..."
            ),
            TemplateField(
                field_id="birth_plan_discussed",
                field_name="Birth Plan Discussed / Plan de Naștere Discutat",
                field_type=FieldType.TEXTAREA,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                placeholder="Patient preferences for labor, pain management, delivery..."
            )
        ]
    )

def get_vaccinations_prophylaxis_section() -> TemplateSection:
    """Vaccinations and prophylaxis during pregnancy"""
    return TemplateSection(
        section_id="vaccinations_prophylaxis",
        section_name="Vaccinations & Prophylaxis / Vaccinări și Profilaxie",
        collapsible=True,
        fields=[
            TemplateField(
                field_id="tdap_vaccine_status",
                field_name="Tdap Vaccine / Vaccin Tdap",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "not_given", "label": "Not Yet Given / Încă Nu"},
                    {"value": "given_this_pregnancy", "label": "Given This Pregnancy / Administrat în Această Sarcină"},
                    {"value": "declined", "label": "Declined / Refuzat"}
                ]
            ),
            TemplateField(
                field_id="tdap_vaccine_date",
                field_name="Tdap Vaccine Date / Data Administrării",
                field_type=FieldType.DATE,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL
            ),
            TemplateField(
                field_id="flu_vaccine_status",
                field_name="Influenza Vaccine / Vaccin Gripal",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "not_given", "label": "Not Yet Given / Încă Nu"},
                    {"value": "given_this_season", "label": "Given This Season / Administrat Sezonul Acesta"},
                    {"value": "declined", "label": "Declined / Refuzat"}
                ]
            ),
            TemplateField(
                field_id="rhogam_administered",
                field_name="RhoGAM Administered / RhoGAM Administrat",
                field_type=FieldType.SELECT,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL,
                options=[
                    {"value": "not_applicable", "label": "Not Applicable (Rh+) / Nu Se Aplică"},
                    {"value": "28_weeks", "label": "Given at 28 Weeks / Administrat la 28 Săptămâni"},
                    {"value": "postpartum_only", "label": "Planned Postpartum / Planificat Postpartum"}
                ]
            ),
            TemplateField(
                field_id="rhogam_date",
                field_name="RhoGAM Date / Data Administrării",
                field_type=FieldType.DATE,
                required=False,
                audio_extractable=AudioExtractability.CONDITIONAL
            )
        ]
    )

def get_obstetrics_template() -> ConsultationTemplate:
    """Complete Obstetrics (Prenatal) consultation template"""
    return ConsultationTemplate(
        template_id="obstetrics_v1",
        specialty="obstetrics",
        version="1.0",
        sections=[
            get_patient_identification_section(),
            get_current_pregnancy_section(),
            get_antenatal_symptoms_section(),
            get_vital_signs_section(),
            get_antenatal_examination_section(),
            get_pregnancy_risk_assessment_section(),
            get_prenatal_labs_imaging_section(),
            get_vaccinations_prophylaxis_section(),
            get_prenatal_education_counseling_section(),
            get_diagnosis_section(),
            get_treatment_plan_section()
        ]
    )