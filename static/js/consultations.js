// static/js/consultations.js
import { showToast } from './ui.js';

class ConsultationManager {
    constructor() {
        this.currentConsultationId = null;
        this.currentTemplate = null;
        this.autoSaveInterval = null;
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
    }

    init() {
        // Start new consultation
        document.getElementById('start-new-consultation')?.addEventListener('click', 
            () => this.showPatientSelectionModal()
        );
        
        // Audio recording controls
        document.getElementById('start-recording')?.addEventListener('click',
            () => this.startAudioRecording()
        );
        
        document.getElementById('stop-recording')?.addEventListener('click',
            () => this.stopAudioRecording()
        );
        
        // Save buttons
        document.getElementById('save-as-draft')?.addEventListener('click',
            () => this.saveConsultation('draft')
        );
        
        document.getElementById('save-as-completed')?.addEventListener('click',
            () => this.saveConsultation('completed')
        );
    }

    //helper method
    //TODO make it not hardocoded!
    async getDoctorSpecialties() {
        // Get from user profile or hardcode for demo
        return ['internal_medicine', 'cardiology', 'respiratory', 'gynecology', 'obstetrics'];
    }

    //helper method
    formatSpecialtyName(specialty) {
        const names = {
            'internal_medicine': 'Internal Medicine',
            'cardiology': 'Cardiology',
            'respiratory': 'Respiratory Medicine',
            'gynecology': 'Gynecology',
            'obstetrics': 'Obstetrics (pregancy tracker)'
        };
        return names[specialty] || specialty;
    }

    //helper method
    getClinicId() {
        return window.clinicManager?.getClinicId() || null;
    }

    async startConsultation(patientId, specialty) {
        try {
            // Step 1: Create draft consultation
            const response = await fetch(
                apiUrl(API_CONFIG.ENDPOINTS.consultations,'start'),
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ patient_id: patientId, specialty: specialty })
                }
            );
            
            if (!response.ok) throw new Error('Failed to start consultation');
            
            const consultation = await response.json();
            this.currentConsultationId = consultation.id;
            
            // Step 2: Load template
            await this.loadTemplate(specialty);
            
            // Step 3: Show document selection modal for pre-filling
            await this.showDocumentSelectionModal(patientId);
            
            // Step 4: Render split-view consultation interface
            await this.renderConsultationView();
            
            // Step 5: Start auto-save
            this.startAutoSave();
            
        } catch (error) {
            showToast('Failed to start consultation: ' + error.message, 'error');
        }
    }
    
    async loadTemplate(specialty) {
        try {
            // --- Construct the dynamic parts ---
            const templatePath = `templates/${specialty}`; 
            const url = window.apiUrl(window.API_CONFIG.ENDPOINTS.consultations,templatePath);

            // Example URL result: /api/v1/consultations/templates/{specialty}
            
            console.log(`Fetching template from URL: ${url}`); 
            
            const response = await fetch(url);

            if (!response.ok) throw new Error('Failed to load template');
            
            this.currentTemplate = await response.json();
            
        } catch (error) {
            showToast('Failed to load consultation template', 'error');
            throw error;
        }
    }
    
    async showDocumentSelectionModal(patientId) {
        // Fetch patient documents
        try{
                const url = window.apiUrl(window.API_CONFIG.ENDPOINTS.documents,`patients/${patientId}/documents`);
                //console.log(url);
                const response = await fetch(url);
                const documents = await response.json();
                if (documents!=null)
                {
                    // Show modal with document checkboxes
                    const modalHTML = `
                        <div class="modal" id="document-selection-modal">
                            <div class="modal-content">
                                <h3>Select Documents to Include</h3>
                                <p>Choose documents to pre-fill consultation data:</p>
                                <div class="document-list">
                                    ${documents.map(doc => `
                                        <label class="document-checkbox">
                                            <input type="checkbox" value="${doc.id}" 
                                                data-type="${doc.document_type}">
                                            ${doc.original_filename} (${doc.document_type})
                                        </label>
                                    `).join('')}
                                </div>
                                <div class="modal-actions">
                                    <button onclick="consultationManager.preFillConsultation()">
                                        Continue with Selected Documents
                                    </button>
                                    <button onclick="consultationManager.skipPreFill()">
                                        Skip - Start Blank
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    document.body.insertAdjacentHTML('beforeend', modalHTML);
                }
        }
        catch (error) {
            showToast('Failed to show document selection', 'error');
            throw error;
        }
    }
    
    async preFillConsultation() {
        const selectedDocs = Array.from(
            document.querySelectorAll('#document-selection-modal input:checked')
        ).map(cb => cb.value);
        
        if (selectedDocs.length > 0) {
            try {
                const response = await fetch(
                    `/api/v1/${getClinicId()}/consultations/${this.currentConsultationId}/pre-fill`,
                    {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ selected_documents: selectedDocs })
                    }
                );
                
                if (!response.ok) throw new Error('Pre-fill failed');
                
                const consultation = await response.json();
                this.currentConsultationData = consultation.structured_data;
                
            } catch (error) {
                showToast('Failed to pre-fill consultation', 'error');
            }
        }
        
        // Close modal and continue
        document.getElementById('document-selection-modal').remove();
        await this.renderConsultationView();
    }
    
    async renderConsultationView() {
        const container = document.getElementById('consultation-container');
        
        // Get doctor's specialties
        const doctorSpecialties = await this.getDoctorSpecialties();
        
        const specialtyOptions = doctorSpecialties.map(spec => {
            const selected = spec === this.currentTemplate.specialty ? 'selected' : '';
            return `<option value="${spec}" ${selected}>${this.formatSpecialtyName(spec)}</option>`;
        }).join('');

        // Split view: left = template form, right = patient history
        container.innerHTML = `
            <div class="consultation-split-view">
                <!-- Left: Consultation Form -->
                <div class="consultation-form-panel">
                    <div class="consultation-header">
                        <h2>
                            <select id="specialty-selector" onchange="consultationManager.changeSpecialty(this.value)">
                                ${specialtyOptions}
                            </select>
                            Consultation
                        </h2>
                        <div class="audio-controls">
                            <button id="start-recording" class="btn-record">
                                <i class="fas fa-microphone"></i> Start Recording
                            </button>
                            <button id="stop-recording" class="btn-stop" style="display:none;">
                                <i class="fas fa-stop"></i> Stop Recording
                            </button>
                            <span id="recording-timer" style="display:none;">00:00</span>
                        </div>
                    </div>
                    
                    <form id="consultation-form" class="consultation-template-form">
                        ${this.renderTemplateSections()}
                    </form>
                    
                    <div class="consultation-actions">
                        <button id="save-as-draft" class="btn-secondary">
                            Save as Draft
                        </button>
                        <button id="save-as-completed" class="btn-primary">
                            Save as Completed
                        </button>
                        <button id="delete-consultation" class="btn-danger">
                            Delete Consultation
                        </button>
                    </div>
                </div>
                
                <!-- Right: Patient History (reused from View Patient modal) -->
                <div class="patient-context-panel">
                    <div id="patient-history-container">
                        <!-- Load View Patient's Documents & History tab -->
                    </div>
                </div>
            </div>
        `;
        
        // Load patient history in right panel
        await this.loadPatientHistoryPanel();
        
        // Re-attach event listeners
        this.attachFormEventListeners();
    }
    
    renderTemplateSections() {
        return this.currentTemplate.sections.map(section => `
            <div class="template-section ${section.collapsible ? 'collapsible' : ''}">
                <div class="section-header">
                    <h3>${section.section_name}</h3>
                    ${section.section_description ? 
                        `<p class="section-description">${section.section_description}</p>` 
                        : ''}
                    ${section.collapsible ? 
                        `<button class="collapse-toggle"><i class="fas fa-chevron-down"></i></button>` 
                        : ''}
                </div>
                <div class="section-fields">
                    ${section.fields.map(field => this.renderTemplateField(field, section.section_id)).join('')}
                </div>
            </div>
        `).join('');
    }
    
    renderTemplateField(field, sectionId) {
        const fieldId = `${sectionId}_${field.field_id}`;
        const value = this.getFieldValue(sectionId, field.field_id);
        const confidence = this.getFieldValue(sectionId, `${field.field_id}_confidence`);
        
        const confidenceBadge = confidence ? 
            `<span class="confidence-badge confidence-${confidence}">${confidence}</span>` 
            : '';
        
        switch (field.field_type) {
            case 'text':
            case 'number':
                return `
                    <div class="form-field">
                        <label for="${fieldId}">
                            ${field.field_name} 
                            ${field.required ? '<span class="required">*</span>' : ''}
                            ${confidenceBadge}
                        </label>
                        <input 
                            type="${field.field_type}" 
                            id="${fieldId}"
                            name="${fieldId}"
                            value="${value || ''}"
                            placeholder="${field.placeholder || ''}"
                            ${field.required ? 'required' : ''}
                            ${field.units ? `data-units="${field.units}"` : ''}
                        >
                        ${field.units ? `<span class="field-units">${field.units}</span>` : ''}
                    </div>
                `;
            
            case 'textarea':
                return `
                    <div class="form-field">
                        <label for="${fieldId}">
                            ${field.field_name}
                            ${field.required ? '<span class="required">*</span>' : ''}
                            ${confidenceBadge}
                        </label>
                        <textarea 
                            id="${fieldId}"
                            name="${fieldId}"
                            rows="4"
                            placeholder="${field.placeholder || ''}"
                            ${field.required ? 'required' : ''}
                        >${value || ''}</textarea>
                    </div>
                `;
            
            case 'select':
                return `
                    <div class="form-field">
                        <label for="${fieldId}">
                            ${field.field_name}
                            ${field.required ? '<span class="required">*</span>' : ''}
                        </label>
                        <select id="${fieldId}" name="${fieldId}" ${field.required ? 'required' : ''}>
                            <option value="">Select...</option>
                            ${field.options.map(opt => `
                                <option value="${opt.value}" ${value === opt.value ? 'selected' : ''}>
                                    ${opt.label}
                                </option>
                            `).join('')}
                        </select>
                    </div>
                `;
            
            case 'icd10':
                return `
                    <div class="form-field icd10-field">
                        <label for="${fieldId}">
                            ${field.field_name}
                            ${field.required ? '<span class="required">*</span>' : ''}
                        </label>
                        <textarea 
                            id="${fieldId}"
                            name="${fieldId}"
                            rows="3"
                            placeholder="${field.placeholder || 'Describe diagnoses...'}"
                            ${field.required ? 'required' : ''}
                        >${value || ''}</textarea>
                        <div id="${fieldId}_codes" class="icd10-codes">
                            ${this.renderICD10Codes(sectionId, field.field_id)}
                        </div>
                    </div>
                `;
            
            default:
                return `<p>Unsupported field type: ${field.field_type}</p>`;
        }
    }
    
    renderICD10Codes(sectionId, fieldId) {
		const codes = this.getFieldValue(sectionId, 'icd10_codes') || [];
		
		if (codes.length === 0) {
			return `
				<p class="no-codes">
					Describe diagnoses above, then click "Extract ICD-10 Codes" button
				</p>
			`;
		}
		
		return `
			<div class="icd10-suggestions">
				<p class="suggestion-note">
					<i class="fas fa-info-circle"></i>
					Suggested codes - please review and modify as needed
				</p>
				${codes.map((code, index) => `
					<div class="icd10-code-item suggestion">
						<div class="code-header">
							<strong>${code.icd10_code}</strong>
							<span class="confidence-badge confidence-${code.confidence}">
								${code.confidence}
							</span>
						</div>
						<div class="code-description">
							<div class="romanian">${code.diagnosis_romanian}</div>
							<div class="icd-full">${code.icd10_description}</div>
							${code.notes ? `
								<div class="code-notes">
									<i class="fas fa-exclamation-triangle"></i>
									${code.notes}
								</div>
							` : ''}
						</div>
						<div class="code-actions">
							<button onclick="consultationManager.editICD10Code(${index})" 
									class="btn-icon" title="Edit Code">
								<i class="fas fa-edit"></i>
							</button>
							<button onclick="consultationManager.approveICD10Code(${index})" 
									class="btn-icon btn-approve" title="Approve">
								<i class="fas fa-check"></i>
							</button>
							<button onclick="consultationManager.removeICD10Code(${index})" 
									class="btn-icon" title="Remove">
								<i class="fas fa-times"></i>
							</button>
						</div>
					</div>
				`).join('')}
			</div>
			
			<button class="btn-secondary btn-add-manual" 
					onclick="consultationManager.addManualICD10Code()">
				<i class="fas fa-plus"></i> Add Code Manually
			</button>
		`;
	}

	// Allow doctor to manually add/edit codes
	addManualICD10Code() {
		const modal = document.createElement('div');
		modal.className = 'modal';
		modal.innerHTML = `
			<div class="modal-content">
				<div class="modal-header">
					<h3>Add ICD-10 Code Manually</h3>
					<button class="modal-close" onclick="this.closest('.modal').remove()">
						<i class="fas fa-times"></i>
					</button>
				</div>
				<div class="modal-body">
					<div class="form-field">
						<label>ICD-10 Code *</label>
						<input type="text" id="manual-icd-code" 
							   placeholder="e.g., A16.1" 
							   pattern="[A-Z][0-9]{2}\.?[0-9]?.*">
					</div>
					<div class="form-field">
						<label>Diagnosis (Romanian) *</label>
						<input type="text" id="manual-diagnosis-ro" 
							   placeholder="e.g., Tuberculoza pulmonară">
					</div>
					<div class="form-field">
						<label>Notes (optional)</label>
						<textarea id="manual-notes" rows="2" 
								  placeholder="Additional codes required, special considerations..."></textarea>
					</div>
				</div>
				<div class="modal-footer">
					<button class="btn-secondary" onclick="this.closest('.modal').remove()">
						Cancel
					</button>
					<button class="btn-primary" onclick="consultationManager.saveManualICD10Code()">
						Add Code
					</button>
				</div>
			</div>
		`;
		
		document.body.appendChild(modal);
	}

	saveManualICD10Code() {
		const code = document.getElementById('manual-icd-code').value.trim();
		const diagnosis = document.getElementById('manual-diagnosis-ro').value.trim();
		const notes = document.getElementById('manual-notes').value.trim();
		
		if (!code || !diagnosis) {
			showToast('Code and diagnosis are required', 'error');
			return;
		}
		
		// Get current codes
		const currentCodes = this.getFieldValue('diagnosis', 'icd10_codes') || [];
		
		// Add new code
		currentCodes.push({
			icd10_code: code,
			diagnosis_romanian: diagnosis,
			icd10_description: diagnosis, // Same for manual entry
			confidence: "manual",
			notes: notes,
			approved: true
		});
		
		// Update consultation data
		if (!this.currentConsultationData.diagnosis) {
			this.currentConsultationData.diagnosis = {};
		}
		this.currentConsultationData.diagnosis.icd10_codes = currentCodes;
		
		// Re-render
		this.updateICD10Display(currentCodes);
		
		// Close modal
		document.querySelector('.modal').remove();
		
		showToast('Code added', 'success');
	}
   
    getFieldValue(sectionId, fieldId) {
        if (!this.currentConsultationData) return null;
        if (!this.currentConsultationData[sectionId]) return null;
        return this.currentConsultationData[sectionId][fieldId];
    }
    
    // Auto-save functionality
    startAutoSave() {
        // Auto-save every 60 seconds
        this.autoSaveInterval = setInterval(async () => {
            await this.autoSaveConsultation();
        }, 60000);
    }
    
    async autoSaveConsultation() {
        if (!this.currentConsultationId) return;
        
        try {
            const formData = this.collectFormData();
            
            const response = await fetch(
                `/api/v1/${getClinicId()}/consultations/${this.currentConsultationId}/auto-save`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ structured_data: formData })
                }
            );
            
            if (!response.ok) throw new Error('Auto-save failed');
            
            // Show subtle notification
            this.showAutoSaveIndicator();
            
        } catch (error) {
            console.error('Auto-save error:', error);
            // Don't show error toast - silent failure for auto-save
        }
    }
    
    collectFormData() {
        const formData = {};
        
        this.currentTemplate.sections.forEach(section => {
            const sectionData = {};
            
            section.fields.forEach(field => {
                const fieldId = `${section.section_id}_${field.field_id}`;
                const element = document.getElementById(fieldId);
                
                if (element) {
                    sectionData[field.field_id] = element.value;
                }
            });
            
            formData[section.section_id] = sectionData;
        });
        
        return formData;
    }
    
    showAutoSaveIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'auto-save-indicator';
        indicator.innerHTML = '<i class="fas fa-check"></i> Auto-saved';
        document.body.appendChild(indicator);
        
        setTimeout(() => indicator.remove(), 2000);
    }
    
    // Audio recording functionality
    async startAudioRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };
            
            this.mediaRecorder.onstop = async () => {
                await this.processRecordedAudio();
            };
            
            this.mediaRecorder.start();
            this.isRecording = true;
            
            // Update UI
            document.getElementById('start-recording').style.display = 'none';
            document.getElementById('stop-recording').style.display = 'inline-block';
            document.getElementById('recording-timer').style.display = 'inline-block';
            
            // Start recording timer
            this.startRecordingTimer();
            
            showToast('Recording started', 'success');
            
        } catch (error) {
            showToast('Microphone access denied: ' + error.message, 'error');
        }
    }
    
    startRecordingTimer() {
        let seconds = 0;
        this.recordingTimerInterval = setInterval(() => {
            seconds++;
            const minutes = Math.floor(seconds / 60);
            const secs = seconds % 60;
            document.getElementById('recording-timer').textContent = 
                `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        }, 1000);
    }
    
    stopAudioRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            
            // Stop all tracks
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            
            // Clear timer
            clearInterval(this.recordingTimerInterval);
            
            // Update UI
            document.getElementById('start-recording').style.display = 'inline-block';
            document.getElementById('stop-recording').style.display = 'none';
            document.getElementById('recording-timer').style.display = 'none';
            
            showToast('Processing audio...', 'info');
        }
    }
    
    async processRecordedAudio() {
        try {
            // Create audio blob
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            
            // Upload to server
            const formData = new FormData();
            formData.append('audio_file', audioBlob, 'consultation_audio.webm');
            
            const uploadResponse = await fetch(
                `/api/v1/${getClinicId()}/consultations/${this.currentConsultationId}/audio/upload`,
                {
                    method: 'POST',
                    body: formData
                }
            );
            
            if (!uploadResponse.ok) throw new Error('Audio upload failed');
            
            // Process audio (transcribe + extract fields)
            showToast('Transcribing and extracting data...', 'info');
            
            const processResponse = await fetch(
                `/api/v1/${getClinicId()}/consultations/${this.currentConsultationId}/audio/process`,
                {
                    method: 'POST'
                }
            );
            
            if (!processResponse.ok) throw new Error('Audio processing failed');
            
            const result = await processResponse.json();
            
            // Update form with extracted data
            this.currentConsultationData = result.extracted_data;
            await this.updateFormWithExtractedData(result.extracted_data);
            
            // Show transcript in modal for review
            this.showTranscriptModal(result.transcript, result.extracted_data);
            
            showToast('Audio processed successfully', 'success');
            
        } catch (error) {
            showToast('Audio processing failed: ' + error.message, 'error');
            console.error('Audio processing error:', error);
        }
    }
    
    async updateFormWithExtractedData(extractedData) {
        // Update form fields with extracted data
        for (const [sectionId, sectionData] of Object.entries(extractedData)) {
            for (const [fieldId, fieldValue] of Object.entries(sectionData)) {
                // Skip confidence fields
                if (fieldId.endsWith('_confidence')) continue;
                
                const element = document.getElementById(`${sectionId}_${fieldId}`);
                if (element && fieldValue) {
                    // Highlight auto-filled fields
                    element.value = fieldValue;
                    element.classList.add('auto-filled');
                    
                    // Add confidence indicator
                    const confidence = sectionData[`${fieldId}_confidence`];
                    if (confidence) {
                        this.addConfidenceBadge(element, confidence);
                    }
                }
            }
        }
        
        // Special handling for ICD-10 codes
        if (extractedData.diagnosis?.icd10_codes) {
            this.updateICD10Display(extractedData.diagnosis.icd10_codes);
        }
    }
    
    addConfidenceBadge(element, confidence) {
        const badge = document.createElement('span');
        badge.className = `confidence-badge confidence-${confidence}`;
        badge.textContent = confidence;
        
        // Insert after the input element
        element.parentNode.insertBefore(badge, element.nextSibling);
    }
    
    updateICD10Display(codes) {
        const container = document.getElementById('diagnosis_diagnoses_codes');
        if (!container) return;
        
        container.innerHTML = codes.map((code, index) => `
            <div class="icd10-code-item">
                <div class="code-header">
                    <strong>${code.icd10_code}</strong>
                    <span class="confidence-badge confidence-${code.confidence}">
                        ${code.confidence}
                    </span>
                </div>
                <div class="code-description">
                    <div class="romanian">${code.condition_romanian}</div>
                    <div class="english">${code.condition_english}</div>
                    <div class="icd-description">${code.icd10_description}</div>
                </div>
                <div class="code-actions">
                    <button onclick="consultationManager.editICD10Code(${index})" 
                            class="btn-icon" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button onclick="consultationManager.removeICD10Code(${index})" 
                            class="btn-icon" title="Remove">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    showTranscriptModal(transcript, extractedData) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.id = 'transcript-review-modal';
        
        modal.innerHTML = `
            <div class="modal-content large">
                <div class="modal-header">
                    <h2>Audio Transcript Review</h2>
                    <button class="modal-close" onclick="this.closest('.modal').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="transcript-container">
                        <h3>Full Transcript</h3>
                        <div class="transcript-text">
                            ${transcript}
                        </div>
                    </div>
                    <div class="extracted-summary">
                        <h3>Extracted Data Summary</h3>
                        <div class="extraction-summary">
                            ${this.renderExtractionSummary(extractedData)}
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-primary" onclick="this.closest('.modal').remove()">
                        Continue Editing Form
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
    }
    
    renderExtractionSummary(extractedData) {
        let summary = '';
        
        for (const [sectionId, sectionData] of Object.entries(extractedData)) {
            const section = this.currentTemplate.sections.find(s => s.section_id === sectionId);
            if (!section) continue;
            
            summary += `<div class="section-summary">
                <h4>${section.section_name}</h4>
                <ul>`;
            
            for (const [fieldId, fieldValue] of Object.entries(sectionData)) {
                if (fieldId.endsWith('_confidence') || !fieldValue) continue;
                
                const field = section.fields.find(f => f.field_id === fieldId);
                if (!field) continue;
                
                const confidence = sectionData[`${fieldId}_confidence`] || 'unknown';
                
                summary += `
                    <li>
                        <strong>${field.field_name}:</strong> ${fieldValue}
                        <span class="confidence-badge confidence-${confidence}">${confidence}</span>
                    </li>
                `;
            }
            
            summary += `</ul></div>`;
        }
        
        return summary;
    }
    
    // Patient history panel (right side)
    async loadPatientHistoryPanel() {
        try {
            const response = await fetch(
                `/api/v1/${getClinicId()}/consultations/${this.currentConsultationId}/patient-history`
            );
            
            if (!response.ok) throw new Error('Failed to load patient history');
            
            const historyData = await response.json();
            
            // Render using the same component as View Patient modal's Documents & History tab
            this.renderPatientHistory(historyData);
            
        } catch (error) {
            console.error('Failed to load patient history:', error);
        }
    }
    
    renderPatientHistory(historyData) {
        const container = document.getElementById('patient-history-container');
        
        container.innerHTML = `
            <div class="patient-history-panel">
                <div class="patient-header">
                    <h3>${historyData.patient.given_name} ${historyData.patient.family_name}</h3>
                    <p>CNP: ${historyData.patient.cnp}</p>
                    <p>Birth Date: ${historyData.patient.birth_date}</p>
                </div>
                
                <div class="history-tabs">
                    <button class="tab-btn active" data-tab="consultations">
                        Consultations (${historyData.consultations.length})
                    </button>
                    <button class="tab-btn" data-tab="documents">
                        Documents (${historyData.documents.length})
                    </button>
                </div>
                
                <div class="history-content">
                    <div id="consultations-history" class="tab-content active">
                        ${this.renderConsultationsHistory(historyData.consultations)}
                    </div>
                    <div id="documents-history" class="tab-content">
                        ${this.renderDocumentsHistory(historyData.documents)}
                    </div>
                </div>
            </div>
        `;
        
        // Attach tab switching
        container.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tab = e.target.dataset.tab;
                
                container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                
                e.target.classList.add('active');
                container.querySelector(`#${tab}-history`).classList.add('active');
            });
        });
    }
    
    renderConsultationsHistory(consultations) {
        if (consultations.length === 0) {
            return '<p class="empty-state">No previous consultations</p>';
        }
        
        return `
            <div class="consultations-timeline">
                ${consultations.map(consult => `
                    <div class="consultation-item">
                        <div class="consultation-header">
                            <strong>${consult.specialty}</strong>
                            <span class="date">${new Date(consult.consultation_date).toLocaleDateString('ro-RO')}</span>
                        </div>
                        <button class="btn-link" onclick="consultationManager.viewConsultationDetails('${consult.id}')">
                            View Details
                        </button>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    renderDocumentsHistory(documents) {
        if (documents.length === 0) {
            return '<p class="empty-state">No documents</p>';
        }
        
        // Group by document type
        const grouped = documents.reduce((acc, doc) => {
            const type = doc.document_type || 'Other';
            if (!acc[type]) acc[type] = [];
            acc[type].push(doc);
            return acc;
        }, {});
        
        return Object.entries(grouped).map(([type, docs]) => `
            <div class="document-group">
                <h4>${type}</h4>
                <div class="documents-list">
                    ${docs.map(doc => `
                        <div class="document-item">
                            <i class="fas fa-file-alt"></i>
                            <span>${doc.filename}</span>
                            <button onclick="consultationManager.viewDocument('${doc.id}')" 
                                    class="btn-icon">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    }
    
    // Save consultation
    async saveConsultation(status) {
        try {
            // Collect form data
            const formData = this.collectFormData();
            
            // Validate required fields
            if (status === 'completed' && !this.validateForm()) {
                showToast('Please fill all required fields', 'error');
                return;
            }
            
            // Save data
            const saveResponse = await fetch(
                `/api/v1/${getClinicId()}/consultations/${this.currentConsultationId}/auto-save`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ structured_data: formData })
                }
            );
            
            if (!saveResponse.ok) throw new Error('Save failed');
            
            // Update status
            const statusResponse = await fetch(
                `/api/v1/${getClinicId()}/consultations/${this.currentConsultationId}/status`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: status })
                }
            );
            
            if (!statusResponse.ok) throw new Error('Status update failed');
            
            // Clear auto-save interval
            if (this.autoSaveInterval) {
                clearInterval(this.autoSaveInterval);
            }
            
            showToast(
                status === 'completed' 
                    ? 'Consultation completed successfully' 
                    : 'Consultation saved as draft',
                'success'
            );
            
            // Navigate back to consultations list
            setTimeout(() => {
                window.location.href = '#consultations';
                app.loadConsultationsList();
            }, 1500);
            
        } catch (error) {
            showToast('Failed to save consultation: ' + error.message, 'error');
        }
    }
    
    validateForm() {
        let isValid = true;
        
        this.currentTemplate.sections.forEach(section => {
            section.fields.forEach(field => {
                if (field.required) {
                    const fieldId = `${section.section_id}_${field.field_id}`;
                    const element = document.getElementById(fieldId);
                    
                    if (!element || !element.value.trim()) {
                        element?.classList.add('error');
                        isValid = false;
                    } else {
                        element?.classList.remove('error');
                    }
                }
            });
        });
        
        return isValid;
    }
    
    attachFormEventListeners() {
        // Re-attach all event listeners after rendering
        document.getElementById('start-recording')?.addEventListener('click',
            () => this.startAudioRecording()
        );
        
        document.getElementById('stop-recording')?.addEventListener('click',
            () => this.stopAudioRecording()
        );
        
        document.getElementById('save-as-draft')?.addEventListener('click',
            () => this.saveConsultation('draft')
        );
        
        document.getElementById('save-as-completed')?.addEventListener('click',
            () => this.saveConsultation('completed')
        );
        
        document.getElementById('delete-consultation')?.addEventListener('click',
            () => this.deleteConsultation()
        );
    }
    
    async deleteConsultation() {
        if (!confirm('Are you sure you want to delete this consultation?')) {
            return;
        }
        
        try {
            const response = await fetch(
                `/api/v1/${getClinicId()}/consultations/${this.currentConsultationId}/cancel`,
                { method: 'DELETE' }
            );
            
            if (!response.ok) throw new Error('Delete failed');
            
            // Clear auto-save
            if (this.autoSaveInterval) {
                clearInterval(this.autoSaveInterval);
            }
            
            showToast('Consultation deleted', 'success');
            
            // Navigate back
            window.location.href = '#consultations';
            app.loadConsultationsList();
            
        } catch (error) {
            showToast('Failed to delete consultation: ' + error.message, 'error');
        }
    }

    async startFromPatient(patientId) {
        // Get doctor's default specialty (or show selection modal if multiple)
        const defaultSpecialty = 'internal_medicine'; // You can make this configurable
        
        await this.startConsultation(patientId, defaultSpecialty);
    }

    async changeSpecialty(newSpecialty) {
        try {
            const response = await fetch(
                `/api/v1/${getClinicId()}/consultations/${this.currentConsultationId}/specialty`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ specialty: newSpecialty })
                }
            );
            
            if (!response.ok) throw new Error('Failed to change specialty');
            
            // Reload template
            await this.loadTemplate(newSpecialty);
            await this.renderConsultationView();
            
            showToast('Specialty changed to ' + newSpecialty, 'success');
        } catch (error) {
            showToast('Failed to change specialty: ' + error.message, 'error');
        }
    }

}

export { ConsultationManager };