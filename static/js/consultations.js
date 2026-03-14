// consultations.js - Consult screen (two-panel layout)
// Replaces the old 4-tab wizard with a focused consult experience.

import { showToast, showLoading, hideLoading } from './ui.js';

export class ConsultationManager {
    constructor(app) {
        this.app = app;
        this.currentConsultationId = null;
        this.currentPatientId = null;
        this.autoSaveInterval = null;
        this.autoSaveDebounceTimer = null;
        this.autoSaveInFlight = false;
        this.hasUnsavedChanges = false;
        this.pinnedFiles = [];
        this.isAmendment = false;
        this.specialtyTemplates = this.initializeTemplates();
    }

    initializeTemplates() {
        return {
            internal_medicine: {
                name: "Medicină Internă",
                fields: [
                    { id: "chief_complaint", label: "Motiv prezentare", type: "textarea" },
                    { id: "history_present_illness", label: "Istoricul bolii actuale", type: "textarea" },
                    { id: "review_systems", label: "Anamneza pe aparate", type: "textarea" },
                    { id: "physical_exam", label: "Examen clinic", type: "textarea" },
                    { id: "assessment", label: "Diagnostic", type: "textarea" },
                    { id: "plan", label: "Plan terapeutic", type: "textarea" }
                ]
            },
            cardiology: {
                name: "Cardiologie",
                fields: [
                    { id: "chief_complaint", label: "Motiv prezentare", type: "textarea" },
                    { id: "cardiac_history", label: "Antecedente cardiologice", type: "textarea" },
                    { id: "blood_pressure", label: "Tensiune arterială", type: "text", placeholder: "120/80 mmHg" },
                    { id: "heart_rate", label: "Frecvență cardiacă", type: "text", placeholder: "72 bpm" },
                    { id: "ecg_findings", label: "ECG", type: "textarea" },
                    { id: "cardiac_exam", label: "Examen cardiologic", type: "textarea" },
                    { id: "assessment", label: "Diagnostic", type: "textarea" },
                    { id: "plan", label: "Plan terapeutic", type: "textarea" }
                ]
            },
            respiratory: {
                name: "Pneumologie",
                fields: [
                    { id: "chief_complaint", label: "Motiv prezentare", type: "textarea" },
                    { id: "respiratory_history", label: "Antecedente respiratorii", type: "textarea" },
                    { id: "spo2", label: "SpO2", type: "text", placeholder: "98%" },
                    { id: "respiratory_rate", label: "Frecvență respiratorie", type: "text", placeholder: "16/min" },
                    { id: "lung_sounds", label: "Auscultație pulmonară", type: "textarea" },
                    { id: "spirometry", label: "Spirometrie", type: "textarea" },
                    { id: "assessment", label: "Diagnostic", type: "textarea" },
                    { id: "plan", label: "Plan terapeutic", type: "textarea" }
                ]
            },
            gynecology: {
                name: "Ginecologie",
                fields: [
                    { id: "chief_complaint", label: "Motiv prezentare", type: "textarea" },
                    { id: "menstrual_history", label: "Istoric menstrual", type: "textarea" },
                    { id: "pregnancy_history", label: "Istoric obstetrical", type: "textarea" },
                    { id: "gynecological_exam", label: "Examen ginecologic", type: "textarea" },
                    { id: "assessment", label: "Diagnostic", type: "textarea" },
                    { id: "plan", label: "Plan terapeutic", type: "textarea" }
                ]
            }
        };
    }

    // ----------------------------
    // Load Consultation (main entry point)
    // ----------------------------
    async loadConsultation(consultationId) {
        try {
            showLoading();
            this.cleanup();
            this.currentConsultationId = consultationId;

            // Fetch consultation data and patient history in parallel
            const [consultRes, historyRes] = await Promise.all([
                fetch(`/api/consultations/${consultationId}`),
                fetch(`/api/consultations/${consultationId}/patient-history`)
            ]);

            if (!consultRes.ok) throw new Error('Failed to load consultation');
            if (!historyRes.ok) throw new Error('Failed to load patient history');

            const consultation = await consultRes.json();
            const history = await historyRes.json();

            this.currentPatientId = consultation.patient_id;
            this.pinnedFiles = consultation.pinned_files || [];
            this.isAmendment = !!(consultation.amendment_history && consultation.amendment_history.length > 0);

            // Set status to in_progress if currently scheduled
            if (consultation.status === 'scheduled') {
                await fetch(`/api/consultations/${consultationId}/status?status=in_progress`, { method: 'PUT' });
                consultation.status = 'in_progress';
            }

            this.renderConsultScreen(consultation, history);
            this.startAutoSave();

            hideLoading();
        } catch (error) {
            hideLoading();
            console.error('Error loading consultation:', error);
            showToast('Failed to load consultation', 'error');
        }
    }

    // ----------------------------
    // Render the two-panel layout
    // ----------------------------
    renderConsultScreen(consultation, history) {
        const container = document.getElementById('consult-container');
        if (!container) return;

        container.innerHTML = `
            <div class="consult-layout">
                <!-- Left Panel: Patient History -->
                <div class="consult-left-panel">
                    <div class="patient-info-banner">
                        <h3>${history.patient.given_name} ${history.patient.family_name}</h3>
                        <div class="patient-meta">
                            <span>CNP: ${history.patient.cnp || 'N/A'}</span>
                            <span>Data nașterii: ${history.patient.birth_date || 'N/A'}</span>
                        </div>
                    </div>

                    <div class="history-sections">
                        ${this.renderHistorySection('Consultații anterioare', 'consultations', history.consultations)}
                        ${this.renderHistorySection('Documente', 'documents', history.documents)}
                    </div>
                </div>

                <!-- Right Panel: Consult Form -->
                <div class="consult-right-panel">
                    ${this.isAmendment ? this.renderAmendmentBanner(consultation) : ''}

                    <div class="consult-form-header">
                        <div class="specialty-selector-container">
                            <label>Specialitate:</label>
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
                            <span id="save-status-text">Salvat</span>
                        </div>
                    </div>

                    <!-- Dynamic Form -->
                    <form id="consultation-form" class="consultation-form">
                        ${this.renderConsultationForm(consultation.specialty, consultation.structured_data)}
                    </form>

                    <!-- Audio Recording -->
                    <div class="audio-recording-section">
                        <button class="btn-secondary btn-sm" id="start-audio-btn">
                            <i class="fas fa-microphone"></i> Înregistrare audio
                        </button>
                        <span id="recording-duration" style="display:none">00:00</span>
                    </div>

                    <!-- Discharge Preview Area (hidden initially) -->
                    <div id="discharge-preview-area" style="display:none">
                        <h4>Scrisoare medicală</h4>
                        <textarea id="discharge-text" class="discharge-textarea" rows="12"></textarea>
                        <div class="discharge-actions">
                            <button class="btn-secondary" id="edit-discharge-btn">
                                <i class="fas fa-edit"></i> Editează
                            </button>
                            <button class="btn-primary" id="sign-close-btn">
                                <i class="fas fa-signature"></i> Semnează & Închide
                            </button>
                        </div>
                    </div>

                    <!-- Action Buttons -->
                    <div class="consult-actions" id="consult-action-buttons">
                        <button class="btn-secondary" id="exit-consult-btn">
                            <i class="fas fa-arrow-left"></i> Ieșire
                        </button>
                        <button class="btn-primary" id="save-draft-btn">
                            <i class="fas fa-save"></i> Salvează ciornă
                        </button>
                        <button class="btn-success" id="complete-btn">
                            <i class="fas fa-check"></i> Finalizează
                        </button>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
    }

    renderAmendmentBanner(consultation) {
        const originalSignedAt = consultation.signed_at
            ? new Date(consultation.signed_at).toLocaleString('ro-RO')
            : 'N/A';
        return `
            <div class="amendment-banner">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Amendament — Semnătura originală: ${originalSignedAt}</span>
            </div>
        `;
    }

    renderHistorySection(title, type, items) {
        if (!items || items.length === 0) {
            return `
                <div class="history-section">
                    <h4 class="history-section-title">${title} (0)</h4>
                    <p class="empty-message">Nimic de afișat</p>
                </div>
            `;
        }

        let itemsHtml = '';
        if (type === 'consultations') {
            itemsHtml = items.map(c => {
                const isPinned = this.pinnedFiles.includes(c.id);
                const date = new Date(c.consultation_date).toLocaleDateString('ro-RO');
                const specialtyName = this.specialtyTemplates[c.specialty]?.name || c.specialty;
                const preview = c.structured_data?.chief_complaint || c.structured_data?.assessment || '';
                return `
                    <div class="history-item ${isPinned ? 'pinned' : ''}" data-file-id="${c.id}" data-type="consultation">
                        <div class="history-item-header">
                            <strong>${specialtyName}</strong>
                            <span class="history-item-date">${date}</span>
                            <button class="pin-btn ${isPinned ? 'pinned' : ''}" title="${isPinned ? 'Anulează fixarea' : 'Fixează pentru externare'}">📌</button>
                        </div>
                        ${preview ? `<div class="history-item-preview">${this.truncate(preview, 100)}</div>` : ''}
                    </div>
                `;
            }).join('');
        } else {
            itemsHtml = items.map(d => {
                const isPinned = this.pinnedFiles.includes(d.id);
                const date = new Date(d.created_at).toLocaleDateString('ro-RO');
                return `
                    <div class="history-item ${isPinned ? 'pinned' : ''}" data-file-id="${d.id}" data-type="document">
                        <div class="history-item-header">
                            <i class="fas fa-file-medical"></i>
                            <strong>${d.filename}</strong>
                            <span class="history-item-date">${date}</span>
                            <button class="pin-btn ${isPinned ? 'pinned' : ''}" title="${isPinned ? 'Anulează fixarea' : 'Fixează pentru externare'}">📌</button>
                        </div>
                        <div class="document-type-badge">${d.document_type || 'Document'}</div>
                    </div>
                `;
            }).join('');
        }

        return `
            <div class="history-section">
                <h4 class="history-section-title">${title} (${items.length})</h4>
                ${itemsHtml}
            </div>
        `;
    }

    renderConsultationForm(specialty, structuredData = {}) {
        const template = this.specialtyTemplates[specialty];
        if (!template) return '<p>Șablon negăsit</p>';

        return template.fields.map(field => {
            const value = structuredData[field.id] || '';
            if (field.type === 'textarea') {
                return `
                    <div class="form-group">
                        <label for="${field.id}">${field.label}</label>
                        <textarea id="${field.id}" name="${field.id}" rows="3"
                            placeholder="${field.placeholder || ''}"
                            class="form-control">${value}</textarea>
                    </div>
                `;
            } else {
                return `
                    <div class="form-group">
                        <label for="${field.id}">${field.label}</label>
                        <input type="${field.type}" id="${field.id}" name="${field.id}"
                            value="${value}" placeholder="${field.placeholder || ''}"
                            class="form-control" />
                    </div>
                `;
            }
        }).join('');
    }

    truncate(str, len) {
        if (!str) return '';
        return str.length > len ? str.substring(0, len) + '...' : str;
    }

    // ----------------------------
    // Event Listeners
    // ----------------------------
    setupEventListeners() {
        // Specialty change
        document.getElementById('consultation-specialty')?.addEventListener('change', (e) => {
            this.changeSpecialty(e.target.value);
        });

        // Form input tracking
        const form = document.getElementById('consultation-form');
        if (form) {
            form.addEventListener('input', () => {
                this.hasUnsavedChanges = true;
                this.updateSaveIndicator('unsaved');
                this.debouncedAutoSave();
            });
        }

        // Pin buttons
        document.querySelectorAll('.pin-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const item = btn.closest('.history-item');
                const fileId = item?.dataset.fileId;
                if (fileId) this.togglePin(fileId, item, btn);
            });
        });

        // Action buttons
        document.getElementById('exit-consult-btn')?.addEventListener('click', () => this.exitConsult());
        document.getElementById('save-draft-btn')?.addEventListener('click', () => this.saveDraft());
        document.getElementById('complete-btn')?.addEventListener('click', () => this.completeConsultation());

        // Discharge actions
        document.getElementById('edit-discharge-btn')?.addEventListener('click', () => {
            document.getElementById('discharge-text')?.focus();
        });
        document.getElementById('sign-close-btn')?.addEventListener('click', () => this.signAndClose());

        // Audio recording placeholder
        document.getElementById('start-audio-btn')?.addEventListener('click', () => {
            showToast('Înregistrare audio — în dezvoltare', 'info');
        });
    }

    // ----------------------------
    // Pin/Unpin files
    // ----------------------------
    togglePin(fileId, itemEl, btnEl) {
        const idx = this.pinnedFiles.indexOf(fileId);
        if (idx >= 0) {
            this.pinnedFiles.splice(idx, 1);
            itemEl?.classList.remove('pinned');
            btnEl?.classList.remove('pinned');
        } else {
            this.pinnedFiles.push(fileId);
            itemEl?.classList.add('pinned');
            btnEl?.classList.add('pinned');
        }
        this.hasUnsavedChanges = true;
        this.debouncedAutoSave();
    }

    // ----------------------------
    // Auto-Save (30s interval + debounce on change)
    // ----------------------------
    startAutoSave() {
        this.stopAutoSave();
        this.autoSaveInterval = setInterval(async () => {
            if (this.hasUnsavedChanges) {
                await this.performAutoSave();
            }
        }, 30000);
    }

    stopAutoSave() {
        if (this.autoSaveInterval) {
            clearInterval(this.autoSaveInterval);
            this.autoSaveInterval = null;
        }
        if (this.autoSaveDebounceTimer) {
            clearTimeout(this.autoSaveDebounceTimer);
            this.autoSaveDebounceTimer = null;
        }
    }

    debouncedAutoSave() {
        if (this.autoSaveDebounceTimer) clearTimeout(this.autoSaveDebounceTimer);
        this.autoSaveDebounceTimer = setTimeout(() => this.performAutoSave(), 2000);
    }

    async performAutoSave() {
        if (this.autoSaveInFlight || !this.currentConsultationId) return;

        try {
            this.autoSaveInFlight = true;
            this.updateSaveIndicator('saving');

            const formData = this.collectFormData();

            const response = await fetch(
                `/api/consultations/${this.currentConsultationId}/auto-save`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        structured_data: formData,
                        pinned_files: this.pinnedFiles
                    })
                }
            );

            if (!response.ok) throw new Error('Auto-save failed');

            this.hasUnsavedChanges = false;
            this.updateSaveIndicator('saved');
        } catch (error) {
            console.error('Auto-save error:', error);
            this.updateSaveIndicator('error');
        } finally {
            this.autoSaveInFlight = false;
        }
    }

    collectFormData() {
        const form = document.getElementById('consultation-form');
        if (!form) return {};
        const formData = {};
        form.querySelectorAll('input, textarea, select').forEach(input => {
            if (input.name) formData[input.name] = input.value;
        });
        return formData;
    }

    updateSaveIndicator(status) {
        const icon = document.getElementById('save-status-icon');
        const text = document.getElementById('save-status-text');
        if (!icon || !text) return;

        const states = {
            unsaved: { icon: 'fa-circle text-warning', text: 'Modificări nesalvate' },
            saving: { icon: 'fa-spinner fa-spin text-info', text: 'Se salvează...' },
            saved: { icon: 'fa-check-circle text-success', text: 'Salvat' },
            error: { icon: 'fa-exclamation-circle text-danger', text: 'Eroare la salvare' }
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

            const consultation = await response.json();
            const form = document.getElementById('consultation-form');
            if (form) {
                form.innerHTML = this.renderConsultationForm(newSpecialty, consultation.structured_data);
            }

            showToast(`Specialitate schimbată: ${this.specialtyTemplates[newSpecialty]?.name}`, 'success');
        } catch (error) {
            console.error('Error changing specialty:', error);
            showToast('Eroare la schimbarea specialității', 'error');
        }
    }

    // ----------------------------
    // Action Buttons
    // ----------------------------
    exitConsult() {
        this.stopAutoSave();
        // Autosave has preserved everything, just go back
        this.app.navigation.navigateTo('agenda');
        this.cleanup();
    }

    async saveDraft() {
        try {
            await this.performAutoSave();

            // Set status to pending_review
            const response = await fetch(
                `/api/consultations/${this.currentConsultationId}/status?status=pending_review`,
                { method: 'PUT' }
            );

            if (!response.ok) {
                const data = await response.json();
                showToast(data.detail || 'Eroare la salvarea ciornei', 'error');
                return;
            }

            showToast('Ciornă salvată — apare în Agendă', 'success');
        } catch (error) {
            showToast('Eroare la salvarea ciornei', 'error');
        }
    }

    async completeConsultation() {
        try {
            // First auto-save
            await this.performAutoSave();

            showLoading();

            // Generate discharge via AI
            const genRes = await fetch(
                `/api/consultations/${this.currentConsultationId}/generate-discharge`,
                { method: 'POST' }
            );

            let dischargeText = '';
            if (genRes.ok) {
                const data = await genRes.json();
                dischargeText = data.discharge_text || '';
            }

            hideLoading();

            // Show discharge preview inline
            this.showDischargePreview(dischargeText);

        } catch (error) {
            hideLoading();
            console.error('Error completing consultation:', error);
            showToast('Eroare la finalizarea consultației', 'error');
        }
    }

    showDischargePreview(text) {
        const area = document.getElementById('discharge-preview-area');
        const textarea = document.getElementById('discharge-text');
        const actionButtons = document.getElementById('consult-action-buttons');

        if (area && textarea) {
            textarea.value = text;
            area.style.display = 'block';
            textarea.focus();
        }

        // Hide the normal action buttons
        if (actionButtons) actionButtons.style.display = 'none';
    }

    async signAndClose() {
        try {
            const dischargeText = document.getElementById('discharge-text')?.value || '';

            showLoading();

            const response = await fetch(
                `/api/consultations/${this.currentConsultationId}/complete`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ discharge_text: dischargeText })
                }
            );

            if (!response.ok) {
                const data = await response.json();
                hideLoading();
                showToast(data.detail || 'Eroare la semnare', 'error');
                return;
            }

            this.stopAutoSave();
            hideLoading();
            showToast('Consultație semnată și închisă', 'success');

            // Return to agenda
            this.app.navigation.navigateTo('agenda');
            this.cleanup();

        } catch (error) {
            hideLoading();
            console.error('Error signing consultation:', error);
            showToast('Eroare la semnarea consultației', 'error');
        }
    }

    // ----------------------------
    // Cleanup
    // ----------------------------
    cleanup() {
        this.stopAutoSave();
        this.currentConsultationId = null;
        this.currentPatientId = null;
        this.hasUnsavedChanges = false;
        this.pinnedFiles = [];
        this.isAmendment = false;
    }
}
