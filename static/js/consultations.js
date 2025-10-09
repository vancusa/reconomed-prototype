// consultations.js
import { showToast } from './ui.js';

/**
 * Initialize consultation tabs and their switching logic
 */
export function initConsultationTabs() {
    const tabButtons = document.querySelectorAll('.consultation-tabs .tab-button');
    const tabContents = document.querySelectorAll('.consultation-tabs .tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.dataset.tab;
            
            // Remove active from all consultation tab buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active to clicked button and corresponding content
            button.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
            
            // Load content for the active consultation tab
            loadConsultationTabContent(targetTab);
        });
    });
    
    // Setup form submission
    setupConsultationForm();
    
    // Load initial content
    loadConsultationTabContent('new-consultation');
}

/**
 * Setup consultation form submission
 */
function setupConsultationForm() {
    const form = document.getElementById('new-consultation-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await submitConsultation();
        });
    }
    
    // Audio recording button (placeholder for now)
    const audioBtn = document.getElementById('start-audio-recording');
    if (audioBtn) {
        audioBtn.addEventListener('click', () => {
            showToast('Audio recording - coming soon', 'info');
        });
    }
}

/**
 * Submit new consultation
 */
async function submitConsultation() {
    const form = document.getElementById('new-consultation-form');
    const formData = new FormData(form);
    
    const consultationData = {
        patient_id: formData.get('patient_id'),
        consultation_type: formData.get('consultation_type'),
        structured_data: {
            notes: formData.get('notes')
        }
    };
    
    // Validation
    if (!consultationData.patient_id) {
        showToast('Please select a patient', 'error');
        return;
    }
    
    if (!consultationData.consultation_type) {
        showToast('Please select consultation type', 'error');
        return;
    }
    
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, ''), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(consultationData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create consultation');
        }
        
        const result = await response.json();
        
        showToast('Consultation saved successfully', 'success');
        form.reset();
        
        // Refresh counts
        updateConsultationTabCounts();
        
    } catch (error) {
        console.error('Failed to create consultation:', error);
        showToast(error.message || 'Failed to save consultation', 'error');
    }
}

/**
 * Load content based on active consultation tab
 */
function loadConsultationTabContent(tabName) {
    switch(tabName) {
        case 'new-consultation':
            loadPatientListForConsultation();
            break;
        case 'patient-review':
            setupPatientReviewSearch();
            break;
        case 'discharge':
            loadDischargePatients();
            break;
        default:
            console.log(`Loading content for ${tabName} tab`);
    }
    
    // Update consultation tab counts
    updateConsultationTabCounts();
}

/**
 * Load patients for consultation dropdown
 */
async function loadPatientListForConsultation() {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients, ''));
        if (!response.ok) throw new Error('Failed to load patients');
        
        const data = await response.json();
        const patients = data.patients || data; // Handle both paginated and non-paginated
        
        const select = document.getElementById('consultation-patient');
        
        if (select) {
            select.innerHTML = '<option value="">Choose a patient...</option>' +
                patients.map(patient => 
                    `<option value="${patient.id}">${patient.given_name} ${patient.family_name}</option>`
                ).join('');
        }
    } catch (error) {
        console.error('Failed to load patients for consultation:', error);
        showToast('Failed to load patient list', 'error');
    }
}

/**
 * Setup patient review search functionality
 */
function setupPatientReviewSearch() {
    const searchInput = document.getElementById('review-patient-search');
    if (!searchInput) return;
    
    // Remove existing listeners
    const newInput = searchInput.cloneNode(true);
    searchInput.parentNode.replaceChild(newInput, searchInput);
    
    newInput.addEventListener('input', debounce(async (e) => {
        const query = e.target.value.trim();
        if (query.length >= 2) {
            await searchPatientsForReview(query);
        } else if (query.length === 0) {
            // Reset to empty state
            document.getElementById('review-results').innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">🔍</div>
                    <h4>Search for a patient to review their history</h4>
                    <p>Enter patient name, CNP, or phone number above</p>
                </div>
            `;
        }
    }, 300));
}

/**
 * Search patients for review and show their consultation history
 */
async function searchPatientsForReview(query) {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients, `?search=${encodeURIComponent(query)}`));
        if (!response.ok) throw new Error('Failed to search patients');
        
        const data = await response.json();
        const patients = data.patients || data;
        
        await renderPatientReviewResults(patients);
    } catch (error) {
        console.error('Failed to search patients:', error);
        showToast('Failed to search patients', 'error');
    }
}

/**
 * Render patient search results with their consultation history
 */
async function renderPatientReviewResults(patients) {
    const container = document.getElementById('review-results');
    if (!container) return;
    
    if (patients.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">❌</div>
                <h4>No patients found</h4>
                <p>Try a different search term</p>
            </div>
        `;
        return;
    }
    
    // For each patient, fetch their consultations
    const patientCards = await Promise.all(patients.map(async (patient) => {
        try {
            const consultationsResponse = await fetch(
                apiUrl(API_CONFIG.ENDPOINTS.consultations, `?patient_id=${patient.id}`)
            );
            const consultations = consultationsResponse.ok ? await consultationsResponse.json() : [];
            
            return `
                <div class="patient-review-card">
                    <div class="patient-review-header">
                        <h3>${patient.given_name} ${patient.family_name}</h3>
                        <span class="patient-review-cnp">CNP: ${patient.cnp || 'N/A'}</span>
                    </div>
                    <div class="patient-review-consultations">
                        <h4>Consultation History (${consultations.length})</h4>
                        ${consultations.length > 0 ? `
                            <div class="consultations-list">
                                ${consultations.slice(0, 5).map(c => `
                                    <div class="consultation-item">
                                        <span class="consultation-date">
                                            ${new Date(c.consultation_date).toLocaleDateString('ro-RO')}
                                        </span>
                                        <span class="consultation-type">${c.consultation_type}</span>
                                        <span class="consultation-status status-${c.status}">${c.status}</span>
                                    </div>
                                `).join('')}
                                ${consultations.length > 5 ? `<p class="text-secondary">+ ${consultations.length - 5} more</p>` : ''}
                            </div>
                        ` : '<p class="text-secondary">No consultations yet</p>'}
                    </div>
                </div>
            `;
        } catch (error) {
            console.error(`Failed to load consultations for patient ${patient.id}:`, error);
            return `
                <div class="patient-review-card">
                    <div class="patient-review-header">
                        <h3>${patient.given_name} ${patient.family_name}</h3>
                        <span class="patient-review-cnp">CNP: ${patient.cnp || 'N/A'}</span>
                    </div>
                    <p class="text-error">Failed to load consultation history</p>
                </div>
            `;
        }
    }));
    
    container.innerHTML = patientCards.join('');
}

/**
 * Load patients with discharge-ready consultations
 */
async function loadDischargePatients() {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, 'pending-discharge'));
        if (!response.ok) throw new Error('Failed to load discharge consultations');
        
        const data = await response.json();
        const consultations = data.consultations || [];
        
        // Get unique patients from consultations
        const patientIds = [...new Set(consultations.map(c => c.patient_id))];
        
        // Populate discharge patient dropdown
        const select = document.getElementById('discharge-patient');
        if (select && patientIds.length > 0) {
            // Fetch patient details
            const patients = await Promise.all(
                patientIds.map(async (id) => {
                    try {
                        const resp = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients, id));
                        return resp.ok ? await resp.json() : null;
                    } catch {
                        return null;
                    }
                })
            );
            
            const validPatients = patients.filter(p => p !== null);
            
            select.innerHTML = '<option value="">Choose patient...</option>' +
                validPatients.map(patient => 
                    `<option value="${patient.id}">${patient.given_name} ${patient.family_name}</option>`
                ).join('');
            
            // Setup patient selection handler
            select.addEventListener('change', async (e) => {
                const patientId = e.target.value;
                if (patientId) {
                    await loadPatientConsultationsForDischarge(patientId, consultations);
                }
            });
        } else if (select) {
            select.innerHTML = '<option value="">No patients ready for discharge</option>';
        }
        
        renderDischargeConsultations(consultations);
        
    } catch (error) {
        console.error('Failed to load discharge consultations:', error);
        showToast('Failed to load discharge consultations', 'error');
    }
}

/**
 * Load specific patient's consultations for discharge
 */
async function loadPatientConsultationsForDischarge(patientId, allConsultations) {
    const patientConsultations = allConsultations.filter(c => c.patient_id === patientId);
    const container = document.getElementById('patient-consultations');
    
    if (!container) return;
    
    if (patientConsultations.length === 0) {
        container.innerHTML = '<p class="text-secondary">No consultations ready for discharge</p>';
        return;
    }
    
    container.innerHTML = patientConsultations.map(consultation => `
        <div class="consultation-discharge-card">
            <div class="consultation-discharge-header">
                <span class="consultation-date">
                    ${new Date(consultation.consultation_date).toLocaleDateString('ro-RO')}
                </span>
                <span class="consultation-type-badge">${consultation.consultation_type}</span>
            </div>
            <div class="consultation-discharge-actions">
                <button class="btn-primary" onclick="generateDischargeNote('${consultation.id}')">
                    <i class="fas fa-file-export"></i> Generate Discharge Note
                </button>
            </div>
        </div>
    `).join('');
}

/**
 * Render discharge consultations summary
 */
function renderDischargeConsultations(consultations) {
    const container = document.getElementById('patient-consultations');
    if (!container) return;
    
    if (consultations.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📋</div>
                <h4>No consultations ready for discharge</h4>
                <p>Sign consultations to make them available for discharge</p>
            </div>
        `;
    } else {
        container.innerHTML = `
            <div class="discharge-summary">
                <p>${consultations.length} consultation${consultations.length !== 1 ? 's' : ''} ready for discharge</p>
                <p class="text-secondary">Select a patient above to generate discharge notes</p>
            </div>
        `;
    }
}

/**
 * Generate discharge note for consultation
 */
window.generateDischargeNote = async function(consultationId) {
    try {
        const response = await fetch(
            apiUrl(API_CONFIG.ENDPOINTS.consultations, `discharge/${consultationId}`),
            { method: 'POST' }
        );
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate discharge note');
        }
        
        const result = await response.json();
        
        showToast('Discharge note generated successfully', 'success');
        
        // Refresh discharge list
        loadDischargePatients();
        updateConsultationTabCounts();
        
        // TODO: Show discharge note preview/download
        console.log('Discharge note:', result.discharge_note);
        
    } catch (error) {
        console.error('Failed to generate discharge note:', error);
        showToast(error.message || 'Failed to generate discharge note', 'error');
    }
};

/**
 * Update consultation tab count badges
 */
async function updateConsultationTabCounts() {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, 'counts'));
        if (!response.ok) throw new Error('Failed to load counts');
        
        const counts = await response.json();
        
        document.getElementById('active-consultations').textContent = counts.active_consultations || 0;
        document.getElementById('review-pending').textContent = counts.review_pending || 0;
        document.getElementById('discharge-ready').textContent = counts.discharge_ready || 0;
        
    } catch (error) {
        console.error('Failed to update consultation counts:', error);
    }
}

// Utility function for search debouncing
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}