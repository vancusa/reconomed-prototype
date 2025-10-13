// static/js/consultations.js - Complete Phase 4A Implementation

import { showToast, showLoading, hideLoading } from './ui.js';

export class ConsultationManager {
    constructor() {
        this.currentConsultationId = null;
        this.currentPatientId = null;
        this.autoSaveInterval = null;
        this.hasUnsavedChanges = false;
        this.specialtyTemplates = this.initializeTemplates();
    }

    // ----------------------------
    // Specialty Templates (Simplified for MVP)
    // ----------------------------
    initializeTemplates() {
        return {
            internal_medicine: {
                name: "Internal Medicine",
                fields: [
                    { id: "chief_complaint", label: "Chief Complaint", type: "textarea" },
                    { id: "history_present_illness", label: "History of Present Illness", type: "textarea" },
                    { id: "review_systems", label: "Review of Systems", type: "textarea" },
                    { id: "physical_exam", label: "Physical Examination", type: "textarea" },
                    { id: "assessment", label: "Assessment", type: "textarea" },
                    { id: "plan", label: "Plan", type: "textarea" }
                ]
            },
            cardiology: {
                name: "Cardiology",
                fields: [
                    { id: "chief_complaint", label: "Chief Complaint", type: "textarea" },
                    { id: "cardiac_history", label: "Cardiac History", type: "textarea" },
                    { id: "blood_pressure", label: "Blood Pressure", type: "text", placeholder: "120/80 mmHg" },
                    { id: "heart_rate", label: "Heart Rate", type: "text", placeholder: "72 bpm" },
                    { id: "ecg_findings", label: "ECG Findings", type: "textarea" },
                    { id: "cardiac_exam", label: "Cardiac Examination", type: "textarea" },
                    { id: "assessment", label: "Assessment", type: "textarea" },
                    { id: "plan", label: "Treatment Plan", type: "textarea" }
                ]
            },
            respiratory: {
                name: "Respiratory Medicine",
                fields: [
                    { id: "chief_complaint", label: "Chief Complaint", type: "textarea" },
                    { id: "respiratory_history", label: "Respiratory History", type: "textarea" },
                    { id: "spo2", label: "SpO2", type: "text", placeholder: "98%" },
                    { id: "respiratory_rate", label: "Respiratory Rate", type: "text", placeholder: "16/min" },
                    { id: "lung_sounds", label: "Lung Sounds", type: "textarea" },
                    { id: "spirometry", label: "Spirometry Results", type: "textarea" },
                    { id: "assessment", label: "Assessment", type: "textarea" },
                    { id: "plan", label: "Treatment Plan", type: "textarea" }
                ]
            },
            gynecology: {
                name: "Gynecology",
                fields: [
                    { id: "chief_complaint", label: "Chief Complaint", type: "textarea" },
                    { id: "menstrual_history", label: "Menstrual History", type: "textarea" },
                    { id: "pregnancy_history", label: "Pregnancy History", type: "textarea" },
                    { id: "gynecological_exam", label: "Gynecological Examination", type: "textarea" },
                    { id: "assessment", label: "Assessment", type: "textarea" },
                    { id: "plan", label: "Treatment Plan", type: "textarea" }
                ]
            }
        };
    }

    // ----------------------------
    // Step 1: Start Consultation from Patient Card
    // ----------------------------
    async startFromPatient(patientId) {
        try {
            // Get doctor's specialties to show selector
            const response = await fetch('/api/auth/me');
            const doctor = await response.json();
            
            if (!doctor.specialties || doctor.specialties.length === 0) {
                showToast('No specialties configured for doctor', 'error');
                return;
            }

            // If doctor has only one specialty, skip selection
            if (doctor.specialties.length === 1) {
                await this.createConsultation(patientId, doctor.specialties[0]);
            } else {
                // Show specialty selector modal
                this.showSpecialtySelector(patientId, doctor.specialties);
            }
        } catch (error) {
            console.error('Error starting consultation:', error);
            showToast('Failed to start consultation', 'error');
        }
    }

    showSpecialtySelector(patientId, specialties) {
        const modalHTML = `
            <div class="modal" id="specialty-selector-modal" style="display: block;">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>Select Consultation Specialty</h2>
                    </div>
                    <div class="modal-body">
                        <div class="specialty-options">
                            ${specialties.map(specialty => `
                                <button class="specialty-option-btn" data-specialty="${specialty}">
                                    <i class="fas fa-stethoscope"></i>
                                    ${this.specialtyTemplates[specialty]?.name || specialty}
                                </button>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Add click handlers
        document.querySelectorAll('.specialty-option-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const specialty = btn.dataset.specialty;
                document.getElementById('specialty-selector-modal').remove();
                await this.createConsultation(patientId, specialty);
            });
        });
    }

    // ----------------------------
    // Step 2: Create Consultation and Show Recording Interface
    // ----------------------------
    async createConsultation(patientId, specialty) {
        try {
            showLoading();

            const response = await fetch('/api/consultations/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    patient_id: patientId,
                    specialty: specialty
                })
            });

            if (!response.ok) throw new Error('Failed to start consultation');

            const consultation = await response.json();
            this.currentConsultationId = consultation.id;
            this.currentPatientId = patientId;

            // Navigate to consultations section and show recording interface
            window.app.goToSection('consultations');
            await this.showConsultationRecorder(consultation);

            // Start auto-save
            this.startAutoSave();

            hideLoading();
            showToast('Consultation started', 'success');

        } catch (error) {
            hideLoading();
            console.error('Error creating consultation:', error);
            showToast('Failed to create consultation', 'error');
        }
    }

    // ----------------------------
    // Step 2: Consultation Recording Interface (Split View)
    // ----------------------------
    async showConsultationRecorder(consultation) {
        try {
            // Get patient history for left panel
            const historyResponse = await fetch(
                `/api/consultations/${consultation.id}/patient-history`
            );
            const history = await historyResponse.json();

            // Build split-view interface
            const consultationTab = document.getElementById('new-consultation-tab');
            consultationTab.innerHTML = `
                <div class="consultation-recorder-container">
                    <!-- Left Panel: Patient History -->
                    <div class="consultation-left-panel">
                        <div class="patient-info-banner">
                            <h3>${history.patient.given_name} ${history.patient.family_name}</h3>
                            <span>CNP: ${history.patient.cnp || 'N/A'}</span>
                            <span>DOB: ${history.patient.birth_date || 'N/A'}</span>
                        </div>

                        <div class="patient-history-tabs">
                            <button class="history-tab-btn active" data-tab="consultations">
                                Previous Consultations (${history.consultations.length})
                            </button>
                            <button class="history-tab-btn" data-tab="documents">
                                Documents (${history.documents.length})
                            </button>
                        </div>

                        <div id="consultations-history-content" class="history-content active">
                            ${this.renderPreviousConsultations(history.consultations)}
                        </div>

                        <div id="documents-history-content" class="history-content">
                            ${this.renderDocumentsHistory(history.documents)}
                        </div>
                    </div>

                    <!-- Right Panel: Consultation Form -->
                    <div class="consultation-right-panel">
                        <div class="consultation-header">
                            <div class="specialty-selector-container">
                                <label>Specialty:</label>
                                <select id="consultation-specialty" class="specialty-selector">
                                    ${Object.keys(this.specialtyTemplates).map(key => `
                                        <option value="${key}" ${key === consultation.specialty ? 'selected' : ''}>
                                            ${this.specialtyTemplates[key].name}
                                        </option>
                                    `).join('')}
                                </select>
                            </div>

                            <div class="auto-save-indicator">
                                <i class="fas fa-circle" id="save-status-icon"></i>
                                <span id="save-status-text">Draft</span>
                            </div>
                        </div>

                        <!-- Audio Recording Controls -->
                        <div class="audio-recording-section">
                            <button class="btn-primary" id="start-audio-btn">
                                <i class="fas fa-microphone"></i> Start Recording
                            </button>
                            <button class="btn-danger" id="stop-audio-btn" style="display: none;">
                                <i class="fas fa-stop"></i> Stop Recording
                            </button>
                            <div id="audio-waveform" style="display: none;"></div>
                            <span id="recording-duration">00:00</span>
                        </div>

                        <!-- Dynamic Form Fields -->
                        <form id="consultation-form" class="consultation-form">
                            ${this.renderConsultationForm(consultation.specialty, consultation.structured_data)}
                        </form>

                        <!-- Action Buttons -->
                        <div class="consultation-actions">
                            <button class="btn-secondary" onclick="consultationManager.saveAsDraft()">
                                <i class="fas fa-save"></i> Save Draft
                            </button>
                            <button class="btn-primary" onclick="consultationManager.markInProgress()">
                                <i class="fas fa-play"></i> Mark In Progress
                            </button>
                            <button class="btn-success" onclick="consultationManager.completeConsultation()">
                                <i class="fas fa-check"></i> Complete Consultation
                            </button>
                            <button class="btn-danger" onclick="consultationManager.cancelConsultation()">
                                <i class="fas fa-times"></i> Cancel
                            </button>
                        </div>
                    </div>
                </div>
            `;

            // Setup event listeners
            this.setupConsultationRecorderListeners();

        } catch (error) {
            console.error('Error showing consultation recorder:', error);
            showToast('Failed to load consultation interface', 'error');
        }
    }

    renderConsultationForm(specialty, structuredData = {}) {
        const template = this.specialtyTemplates[specialty];
        if (!template) return '<p>Template not found</p>';

        return template.fields.map(field => {
            const value = structuredData[field.id] || '';
            
            if (field.type === 'textarea') {
                return `
                    <div class="form-group">
                        <label for="${field.id}">${field.label}</label>
                        <textarea 
                            id="${field.id}" 
                            name="${field.id}" 
                            rows="4"
                            placeholder="${field.placeholder || ''}"
                            class="form-control"
                        >${value}</textarea>
                    </div>
                `;
            } else {
                return `
                    <div class="form-group">
                        <label for="${field.id}">${field.label}</label>
                        <input 
                            type="${field.type}" 
                            id="${field.id}" 
                            name="${field.id}" 
                            value="${value}"
                            placeholder="${field.placeholder || ''}"
                            class="form-control"
                        />
                    </div>
                `;
            }
        }).join('');
    }

    renderPreviousConsultations(consultations) {
        if (consultations.length === 0) {
            return '<p class="empty-message">No previous consultations</p>';
        }

        return consultations.map(c => `
            <div class="history-item consultation-item" data-consultation-id="${c.id}">
                <div class="history-item-header">
                    <strong>${this.specialtyTemplates[c.specialty]?.name || c.specialty}</strong>
                    <span class="history-item-date">${new Date(c.consultation_date).toLocaleDateString()}</span>
                </div>
                <div class="history-item-preview">
                    ${c.structured_data?.chief_complaint || c.structured_data?.assessment || 'No details'}
                </div>
                ${c.is_signed ? '<span class="badge badge-success">Signed</span>' : ''}
            </div>
        `).join('');
    }

    renderDocumentsHistory(documents) {
        if (documents.length === 0) {
            return '<p class="empty-message">No documents</p>';
        }

        return documents.map(d => `
            <div class="history-item document-item" data-document-id="${d.id}">
                <div class="history-item-header">
                    <i class="fas fa-file-medical"></i>
                    <strong>${d.filename}</strong>
                    <span class="history-item-date">${new Date(d.created_at).toLocaleDateString()}</span>
                </div>
                <div class="document-type-badge">${d.document_type || 'Unknown'}</div>
            </div>
        `).join('');
    }

    setupConsultationRecorderListeners() {
        // Specialty change listener
        const specialtySelect = document.getElementById('consultation-specialty');
        if (specialtySelect) {
            specialtySelect.addEventListener('change', async (e) => {
                await this.changeSpecialty(e.target.value);
            });
        }

        // Form change listeners for unsaved changes tracking
        const form = document.getElementById('consultation-form');
        if (form) {
            form.addEventListener('input', () => {
                this.hasUnsavedChanges = true;
                this.updateSaveIndicator('unsaved');
            });
        }

        // History tab switching
        document.querySelectorAll('.history-tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.history-tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.history-content').forEach(c => c.classList.remove('active'));
                
                btn.classList.add('active');
                const tabName = btn.dataset.tab;
                document.getElementById(`${tabName}-history-content`).classList.add('active');
            });
        });

        // Audio recording (placeholder for Phase 4B)
        document.getElementById('start-audio-btn')?.addEventListener('click', () => {
            showToast('Audio recording coming in Phase 4B', 'info');
        });
    }

    // ----------------------------
    // Auto-Save Every 60 Seconds
    // ----------------------------
    startAutoSave() {
        this.stopAutoSave(); // Clear any existing interval
        
        this.autoSaveInterval = setInterval(async () => {
            if (this.hasUnsavedChanges) {
                await this.performAutoSave();
            }
        }, 60000); // 60 seconds
    }

    stopAutoSave() {
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
            this.autoSaveInterval = null;
        }
    }

    async performAutoSave() {
        try {
            this.updateSaveIndicator('saving');

            const formData = this.collectFormData();

            const response = await fetch(
                `/api/consultations/${this.currentConsultationId}/auto-save`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        structured_data: formData
                    })
                }
            );

            if (!response.ok) throw new Error('Auto-save failed');

            this.hasUnsavedChanges = false;
            this.updateSaveIndicator('saved');

        } catch (error) {
            console.error('Auto-save error:', error);
            this.updateSaveIndicator('error');
        }
    }

    collectFormData() {
        const form = document.getElementById('consultation-form');
        if (!form) return {};

        const formData = {};
        const inputs = form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            if (input.name) {
                formData[input.name] = input.value;
            }
        });

        return formData;
    }

    updateSaveIndicator(status) {
        const icon = document.getElementById('save-status-icon');
        const text = document.getElementById('save-status-text');
        
        if (!icon || !text) return;

        const states = {
            unsaved: { icon: 'fa-circle text-warning', text: 'Unsaved changes' },
            saving: { icon: 'fa-spinner fa-spin text-info', text: 'Saving...' },
            saved: { icon: 'fa-check-circle text-success', text: 'Saved' },
            error: { icon: 'fa-exclamation-circle text-danger', text: 'Save failed' }
        };

        const state = states[status] || states.unsaved;
        icon.className = `fas ${state.icon}`;
        text.textContent = state.text;
    }

    // ----------------------------
    // Specialty Change
    // ----------------------------
    async changeSpecialty(newSpecialty) {
        try {
            const response = await fetch(
                `/api/consultations/${this.currentConsultationId}/specialty?specialty=${newSpecialty}`,
                { method: 'PUT' }
            );

            if (!response.ok) throw new Error('Failed to change specialty');

            // Reload form with new template
            const consultation = await response.json();
            const form = document.getElementById('consultation-form');
            form.innerHTML = this.renderConsultationForm(newSpecialty, consultation.structured_data);

            showToast(`Specialty changed to ${this.specialtyTemplates[newSpecialty].name}`, 'success');

        } catch (error) {
            console.error('Error changing specialty:', error);
            showToast('Failed to change specialty', 'error');
        }
    }

    // ----------------------------
    // Action Buttons
    // ----------------------------
    async saveAsDraft() {
        await this.performAutoSave();
        showToast('Consultation saved as draft', 'success');
    }

    async markInProgress() {
        try {
            await this.performAutoSave();

            const response = await fetch(
                `/api/consultations/${this.currentConsultationId}/status?status=in_progress`,
                { method: 'PUT' }
            );

            if (!response.ok) throw new Error('Failed to update status');

            showToast('Consultation marked as in progress', 'success');

        } catch (error) {
            console.error('Error updating status:', error);
            showToast('Failed to update status', 'error');
        }
    }

    async completeConsultation() {
        try {
            await this.performAutoSave();

            const response = await fetch(
                `/api/consultations/${this.currentConsultationId}/status?status=completed`,
                { method: 'PUT' }
            );

            if (!response.ok) throw new Error('Failed to complete consultation');

            this.stopAutoSave();
            showToast('Consultation completed successfully', 'success');
            
            // Navigate to dashboard
            window.app.goToSection('dashboard');

        } catch (error) {
            console.error('Error completing consultation:', error);
            showToast('Failed to complete consultation', 'error');
        }
    }

    async cancelConsultation() {
        if (!confirm('Are you sure you want to cancel this consultation? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch(
                `/api/consultations/${this.currentConsultationId}/cancel`,
                { method: 'DELETE' }
            );

            if (!response.ok) throw new Error('Failed to cancel consultation');

            this.stopAutoSave();
            showToast('Consultation cancelled', 'info');
            
            // Navigate to dashboard
            window.app.goToSection('dashboard');

        } catch (error) {
            console.error('Error cancelling consultation:', error);
            showToast('Failed to cancel consultation', 'error');
        }
    }

    // ----------------------------
    // Navigation Guard
    // ----------------------------
    checkUnsavedChanges() {
        if (this.hasUnsavedChanges) {
            return confirm(
                'You have unsaved changes. Do you want to save as draft before leaving?'
            );
        }
        return true;
    }

    cleanup() {
        this.stopAutoSave();
        this.currentConsultationId = null;
        this.currentPatientId = null;
        this.hasUnsavedChanges = false;
    }
}

// Initialize global instance
window.consultationManager = new ConsultationManager();