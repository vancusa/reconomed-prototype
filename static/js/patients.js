//Patient CRUD + rendering
// patients.js
// -----------------------------------------------------------------------------
// Handles patient-related functionality for the SPA
//
// Responsibilities:
//  - Load, search, render patients
//  - Add new patients via form submission
//  - Support programmatic actions like view/edit
//  - Integrate with UI for notifications and modals
//
// Assumes HTML structure contains:
//   - <div id="patients-grid"></div> for patient cards
//   - <form id="add-patient-form"></form> for adding / editing patients
//   - <input id="patient-search" /> for live search/filtering
// -----------------------------------------------------------------------------

import { showToast, showModal, hideModal } from './ui.js';

export class PatientManager {
    constructor(app) {
        this.app = app;
        this.patients = [];

        //for showing patients with pagination:
        this.currentPage = 1;
        this.perPage = 8;
        this.totalPages = 1;
        this.totalPatients = 0;
        this.hasNext = false;
        this.hasPrev = false;

        // DOM references
        this.gridContainer = document.getElementById('patients-grid');
        this.addForm = document.getElementById('add-patient-form');
        this.searchInput = document.getElementById('patient-search');
        this.sortSelect = document.getElementById('patient-sort');

        //DOM pagination references
        this.paginationContainer = document.getElementById('patients-pagination');
        this.patientCountDisplay = document.getElementById('patient-count-display');
    }

    // -------------------------------------------------------------------------
    // Initialization
    // -------------------------------------------------------------------------
    init() {
        if (this.addForm) {
            this.addForm.onsubmit = (e) => {
            e.preventDefault();
            this.addPatient();
            };
        //    this.addForm.addEventListener('submit', (e) => {
        //        e.preventDefault();
        //        this.addPatient();
        //    });
        }

        //console.log('PatientManager init called');
        //console.log('Search input found:', this.searchInput);

        if (this.searchInput) {
            //console.log('Adding search listener');
            // Debounced search - Debouncing = Instead of running the search function immediately every time a user types a character  (which can be resource-intensive, especially for network requests), debouncing ensures the function is only executed after a specific period of inactivity has passed since the last event (e.g., the last keypress).
            let searchTimeout;
        
            this.searchInput.addEventListener('input', (e) => {
                const value = e.target.value;  // capture immediately
                //console.log('Search input detected:', value);
                //console.log('Clearing existing timeout...');
                clearTimeout(searchTimeout);
                //console.log('Setting new timeout...');
                searchTimeout = setTimeout(() => {
                    //console.log('--- DEBOUNCED SEARCH EXECUTING ---')
                    this.loadPatients(value);
                }, 300);
            });
        }
        // Sort change handler
        if (this.sortSelect) {
            this.sortSelect.addEventListener('change', (e) => {
                this.currentSort = e.target.value;
                this.loadPatients(1, this.searchInput?.value || '');
            });
        }
    
    
        // Pagination button handlers
        const prevBtn = document.getElementById('patients-prev');
        const nextBtn = document.getElementById('patients-next');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.previousPage());
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.nextPage());
        }
    }

    // -------------------------------------------------------------------------
    // Data Loading
    // -------------------------------------------------------------------------
    /**
     * Load patients into Patients tab with pagination and rendering.
     */
    async loadPatients(searchQuery = '',page = 1) {
        try {
            page = page || this.currentPage || 1;
            const data = await this.fetchPatientsRaw(searchQuery,page);

            this.patients = data.patients;
            this.currentPage = data.page;
            this.totalPages = data.total_pages;
            this.totalPatients = data.total;
            this.hasNext = data.has_next;
            this.hasPrev = data.has_prev;

            // UI updates
            this.renderPatients();
            this.updatePaginationControls();
            this.updatePatientCount();

            return data;

        } catch (err) {
            console.error(err);
            showToast('Could not load patients', 'error');
            return { patients: [] };
        }
    }


    // -------------------------------------------------------------------------
    // Pagination Controls
    // -------------------------------------------------------------------------
    updatePaginationControls() {
        if (!this.paginationContainer) return;
        
        // Show pagination only if there's more than one page
        if (this.totalPages <= 1) {
            this.paginationContainer.style.display = 'none';
            return;
        }
        
        this.paginationContainer.style.display = 'flex';
        
        // Update pagination info
        const showingStart = (this.currentPage - 1) * this.perPage + 1;
        const showingEnd = Math.min(this.currentPage * this.perPage, this.totalPatients);
        
        document.getElementById('patients-showing').textContent = 
            `${showingStart}-${showingEnd}`;
        document.getElementById('patients-total').textContent = this.totalPatients;
        document.getElementById('patients-page').textContent = this.currentPage;
        
        // Enable/disable pagination buttons
        const prevBtn = document.getElementById('patients-prev');
        const nextBtn = document.getElementById('patients-next');
        
        if (prevBtn) prevBtn.disabled = !this.hasPrev;
        if (nextBtn) nextBtn.disabled = !this.hasNext;
    }

    updatePatientCount() {
        if (this.patientCountDisplay) {
            this.patientCountDisplay.textContent = 
                `${this.totalPatients} patient${this.totalPatients !== 1 ? 's' : ''}`;
        }
    }

    // -------------------------------------------------------------------------
    // Pagination Navigation
    // -------------------------------------------------------------------------
    async nextPage() {
        if (this.hasNext) {
            await this.loadPatients(this.searchInput?.value || '',this.currentPage + 1);
        }
    }

    async previousPage() {
        if (this.hasPrev) {
            await this.loadPatients(this.searchInput?.value || '', this.currentPage - 1);
        }
    }

    // -------------------------------------------------------------------------
    // Search with Pagination Reset
    // -------------------------------------------------------------------------
    async searchPatients(query) {
        // Reset to page 1 when searching
        const data = await this.fetchPatientsRaw(query,1);
        return data.patients || [];
    }



    // -------------------------------------------------------------------------
    // Rendering
    // -------------------------------------------------------------------------
    renderPatients() {
        if (!this.gridContainer) return;
        this.gridContainer.innerHTML = '';

        if (this.patients.length === 0) {
            this.gridContainer.innerHTML = '<p>No patients found</p>';
            return;
        }

        this.patients.forEach(patient => {
            const card = document.createElement('div');
            card.className = 'patient-card';
            //const initials = (patient.given_name[0] || '') + (patient.family_name[0] || '');
            card.innerHTML = `
                <div class="patient-info">
                    <h3>${patient.given_name} ${patient.family_name}</h3>
                    <p>${patient.birth_date || patient.phone ? `${patient.birth_date || ''}${patient.phone ? ' • ' + patient.phone : ''}` : '&nbsp;'}</p>
                </div>
                <div class="patient-actions">
                    <button class="btn-icon primary" data-action="view" data-id="${patient.id}" title="View Patient"><i class="fas fa-eye"></i></button>
                    <button class="btn-icon secondary" data-action="edit" data-id="${patient.id}" title="Edit Patient"><i class="fas fa-edit"></i></button>
                    <button class="btn-icon" data-action="gdpr" data-id="${patient.id}" title="GDPR Consent"><i class="fas fa-shield-alt"></i></button>
                    <button class="btn-icon secondary" data-action="consult" data-id="${patient.id}" title="New Consultation"><i class="fas fa-stethoscope"></i></button>
                    <button class="btn-icon primary" data-action="upload" data-id="${patient.id}" title="Upload Document"><i class="fas fa-upload"></i></button>
                </div>
            `;
            this.gridContainer.appendChild(card);
        });

        // Attach event delegation
        this.gridContainer.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleAction(e));
        });
    }

    // -------------------------------------------------------------------------
    // Form Submission / Add or Edit Patient
    // -------------------------------------------------------------------------
    async addPatient() {
        if (!this.addForm) return;
        
        const formData = new FormData(this.addForm);
        const patientData = Object.fromEntries(formData.entries());
        
        // Check if we're editing or creating
        const mode = this.addForm.dataset.mode || 'create';
        const patientId = this.addForm.dataset.patientId;

        try {
            let response;
            
            if (mode === 'edit') {
                // Update existing patient
                response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients, `${patientId}`), {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(patientData)
                });
            } else {
                // Create new patient
                response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients, ``), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(patientData)
                });
            }
            //console.log(response);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Failed to ${mode} patient`);
            }

            // Success - refresh patient list
            await this.loadPatients(this.currentPage, this.searchInput?.value || '');
            
            // Reset form and modal
            this.addForm.reset();
            this.addForm.dataset.mode = 'create';
            delete this.addForm.dataset.patientId;
            hideModal('add-patient-modal');
            
            showToast(
                mode === 'edit' ? 'Patient updated successfully' : 'Patient added successfully', 
                'success'
            );
            
        } catch (err) {
            console.error(err);
            showToast(err.message || 'Failed to save patient', 'error');
        }
    }

    // -------------------------------------------------------------------------
    // Actions: view/edit/gdpr
    // -------------------------------------------------------------------------
    handleAction(e) {
        // Find the button even if icon was clicked
        const button = e.target.closest('button');
        if (!button) return;
        
        const action = button.dataset.action;
        const id = button.dataset.id;
        
        if (!action) {
            console.warn('No action found on button');
            return;
        }

        switch (action) {
            case 'view':
                this.viewPatient(id);
                break;
            case 'edit':
                this.editPatient(id);
                break;
            case 'gdpr':
                this.manageGDPR(id);
                break;
            case 'consult':
                window.app.agendaManager.startConsultFromPatient(id);
                break;
            case 'upload':
                app.navigation.navigateTo('documents',null,id);
                break;
            default:
                console.warn('Unknown patient action:', action);
        }
    }

    /**
     * Retrieves full patient details by ID from the backend.
     * Used when launching a consultation or displaying patient info
     * outside the main patient list context.
     */
    async getPatientById(id) {
        try {
            const url = apiUrl(API_CONFIG.ENDPOINTS.patients, `${id}`);
            const response = await fetch(url);
            if (!response.ok) throw new Error('Patient not found');
            return await response.json();
        } catch (err) {
            console.error('getPatientById error:', err);
            return null;
        }
    }


    /** -------------------------------------------------
     * Fetch patients from backend without touching UI.
     * Returns raw JSON data for reuse in other modules (e.g., Consultations).
     * ---------------------------------------------------
     */
    async fetchPatientsRaw(searchQuery = '',page = 1) {
        try {
            let url = apiUrl(API_CONFIG.ENDPOINTS.patients);
            const params = new URLSearchParams({
            page,
            per_page: this.perPage
            });

            if (searchQuery) params.append('search', searchQuery);
            if (this.currentSort) params.append('sort_by', this.currentSort);
            url += `?${params.toString()}`;
            
            //console.log("URL",url);
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch patients');
            const data = await response.json();
            return data; // ✅ no DOM updates, just data
        } catch (err) {
            console.error('fetchPatientsRaw error:', err);
            showToast('Error fetching patients', 'error');
            return { patients: [], total: 0, total_pages: 1 };
        }
    }


    // -------------------------------------------------------------------------
    // Edit Patient
    // -------------------------------------------------------------------------
    async editPatient(patientId) {
        try {
            // Fetch patient details
            const url = apiUrl(API_CONFIG.ENDPOINTS.patients, `${patientId}`);
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to load patient');
            
            const patient = await response.json();
            
            // Get the modal and form
            const modal = document.getElementById('add-patient-modal');
            const form = document.getElementById('add-patient-form');
            const modalTitle = modal.querySelector('.modal-header h2');
            const submitButton = form.querySelector('button[type="submit"]');
            
            // Change modal to edit mode
            modalTitle.textContent = 'Edit Patient';
            submitButton.textContent = 'Save Changes';
            submitButton.innerHTML = '<i class="fas fa-save"></i> Save Changes';
            
            // Populate form with patient data
            document.getElementById('patient-given-name').value = patient.given_name || '';
            document.getElementById('patient-family-name').value = patient.family_name || '';
            document.getElementById('patient-birth-date').value = patient.birth_date || '';
            document.getElementById('patient-cnp').value = patient.cnp || '';
            document.getElementById('patient-phone').value = patient.phone || '';
            document.getElementById('patient-email').value = patient.email || '';
            document.getElementById('patient-insurance-number').value = patient.insurance_number || '';
            document.getElementById('patient-insurance-house').value = patient.insurance_house || '';
            
            // Store patient ID in form for submission
            form.dataset.patientId = patient.id;
            form.dataset.mode = 'edit';
            
            // Show modal
            showModal('add-patient-modal');
            
        } catch (err) {
            console.error('Failed to load patient for editing:', err);
            showToast('Failed to load patient details', 'error');
        }
    }

    // -------------------------------------------------------------------------
    // View Patient
    // -------------------------------------------------------------------------
    async viewPatient(patientId) {
        try {
            // Fetch patient details
            const url = apiUrl(API_CONFIG.ENDPOINTS.patients, `${patientId}`);
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to load patient');
            
            const patient = await response.json();
            
            // Store current patient ID for edit/GDPR actions
            this.currentViewPatientId = patientId;
            
            // Populate Overview tab
            this.populatePatientOverview(patient);
            
            // Initialize tab switching
            this.initViewPatientTabs();
            
            // Show modal
            showModal('view-patient-modal');
            
        } catch (err) {
            console.error('Failed to load patient:', err);
            showToast('Failed to load patient details', 'error');
        }
    }

    populatePatientOverview(patient) {
        // Update modal title
        document.getElementById('view-patient-title').textContent = 
            `View Patient: ${patient.given_name} ${patient.family_name}`;
        
        // Basic Information
        document.getElementById('view-given-name').textContent = patient.given_name;
        document.getElementById('view-family-name').textContent = patient.family_name;
        document.getElementById('view-birth-date').textContent =  patient.birth_date || 'Not provided';
        document.getElementById('view-cnp').textContent = patient.cnp || 'Not provided';
        
        // Contact Information
        document.getElementById('view-phone').textContent = patient.phone || 'Not provided';
        document.getElementById('view-email').textContent = patient.email || 'Not provided';
        
        // Handle address (might be object or string)
        const addressEl = document.getElementById('view-address');
        if (patient.address && typeof patient.address === 'object') {
            const parts = [
                patient.address.street,
                patient.address.city,
                patient.address.county
            ].filter(Boolean);
            addressEl.textContent = parts.join(', ') || 'Not provided';
        } else {
            addressEl.textContent = patient.address || 'Not provided';
        }
        
        // Insurance Information
        document.getElementById('view-insurance-number').textContent = 
            patient.insurance_number || 'Not provided';
        document.getElementById('view-insurance-house').textContent = 
            patient.insurance_house || 'Not provided';
        
        // GDPR Consent Status
        this.renderGDPRConsentStatus(patient.gdpr_consents || {});
    }

    renderGDPRConsentStatus(consents) {
        const container = document.getElementById('view-gdpr-consents');
        
        if (!consents || Object.keys(consents).length === 0) {
            container.innerHTML = '<p class="text-secondary">No consent information available</p>';
            return;
        }
        
        const consentHTML = Object.entries(consents).map(([key, consent]) => {
            const isGranted = consent.granted && !consent.withdrawn;
            const status = consent.withdrawn ? 'withdrawn' : 
                        (isGranted ? 'granted' : 'not-granted');
            
            const icon = consent.withdrawn ? 'fa-ban' :
                        (isGranted ? 'fa-check-circle' : 'fa-times-circle');
            
            const statusText = consent.withdrawn ? 'Withdrawn' :
                            (isGranted ? 'Granted' : 'Not Granted');
            
            const dateText = consent.granted_at ? 
                new Date(consent.granted_at).toLocaleDateString('ro-RO') : 'N/A';
            
            return `
                <div class="consent-status-item ${status}">
                    <i class="fas ${icon}"></i>
                    <div class="consent-info">
                        <div class="consent-name">
                            ${key.replace('_', ' ').toUpperCase()}: ${statusText}
                        </div>
                        <div class="consent-date">
                            ${isGranted ? `Granted: ${dateText}` : ''}
                            ${consent.expires_at ? ` • Expires: ${new Date(consent.expires_at).toLocaleDateString('ro-RO')}` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = consentHTML;
    }

    initViewPatientTabs() {
        //V4 - Always resets to Overview tab when opening the modal , Prevents duplicate event listeners scoped to the view-patient modal
        const modal = document.getElementById('view-patient-modal');
        const tabButtons = modal.querySelectorAll('.modal-tabs .tab-button');
        const tabContents = modal.querySelectorAll('.modal-body .tab-content');
 
        // Reset to overview tab
        tabButtons.forEach(btn => btn.classList.remove('active'));
        tabContents.forEach(content => content.classList.remove('active'));
        modal.querySelector('.tab-button[data-tab="overview"]')?.classList.add('active');
        document.getElementById('overview-tab')?.classList.add('active');
 
        // Only bind listeners once
        if (!this._viewTabsInitialized) {
            this._viewTabsInitialized = true;
            tabButtons.forEach(button => {
                button.addEventListener('click', () => {
                    const targetTab = button.dataset.tab;
 
                    tabButtons.forEach(btn => btn.classList.remove('active'));
                    tabContents.forEach(content => content.classList.remove('active'));
 
                    button.classList.add('active');
                    document.getElementById(`${targetTab}-tab`)?.classList.add('active');
 
                    if (targetTab === 'documents' && this.currentViewPatientId) {
                        this.loadPatientDocuments(this.currentViewPatientId);
                    }
                });
            });
        }
    }

    async loadPatientDocuments(patientId) {
        //print a log to confirm the function is called and patientId is correct
        //console.log('Loading documents for patient ID:', patientId);
        const container = document.getElementById('documents-list');
        container.innerHTML = '<div class="loading-placeholder">Loading documents...</div>';
        
        try {
            const consultationsPromise = fetch(
                apiUrl(API_CONFIG.ENDPOINTS.consultations, `?patient_id=${patientId}`)
            ).then(response => {
                if (!response.ok) {
                    throw new Error('Failed to load consultations');
                }
                return response.json();
            });

            const documentsPromise = fetch(
                apiUrl(API_CONFIG.ENDPOINTS.documents, `?patient_id=${patientId}`)
            ).then(response => {
                if (!response.ok) {
                    throw new Error('Failed to load documents');
                }
                return response.json();
            });

            const [consultationsResult, documentsResult] = await Promise.allSettled([
                consultationsPromise,
                documentsPromise,
            ]);

            const consultations = consultationsResult.status === 'fulfilled'
                ? consultationsResult.value
                : [];
            const documents = documentsResult.status === 'fulfilled'
                ? documentsResult.value
                : [];
            const consultationsError = consultationsResult.status === 'rejected'
                ? 'Unable to load consultations right now.'
                : '';
            const documentsError = documentsResult.status === 'rejected'
                ? 'Unable to load documents right now.'
                : '';

            if (
                consultations.length === 0 &&
                documents.length === 0 &&
                !consultationsError &&
                !documentsError
            ) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">📄</div>
                        <h4>No consultations or documents yet</h4>
                        <p>Consultations and documents will appear here once created</p>
                    </div>
                `;
                return;
            }

            const documentsSection = documentsError
                ? `
                    <div class="empty-state">
                        <div class="empty-icon">⚠️</div>
                        <h4>${documentsError}</h4>
                        <p>Please try again later.</p>
                    </div>
                `
                : documents.length
                ? this.renderGroupedDocuments(documents)
                : `
                    <div class="empty-state">
                        <div class="empty-icon">📁</div>
                        <h4>No documents yet</h4>
                        <p>Uploaded documents will appear here once available</p>
                    </div>
                `;

            const sortedConsultations = [...consultations].sort((a, b) => {
                const dateA = new Date(a.consultation_date || 0).getTime();
                const dateB = new Date(b.consultation_date || 0).getTime();
                return dateB - dateA;
            });

            const consultationsSection = consultationsError
                ? `
                    <div class="empty-state">
                        <div class="empty-icon">⚠️</div>
                        <h4>${consultationsError}</h4>
                        <p>Please try again later.</p>
                    </div>
                `
                : sortedConsultations.length
                ? sortedConsultations.map(consultation => {
                    const specialtyLabel = consultation.specialty || consultation.consultation_type || 'Consultation';
                    const safeSpecialty = this.escapeHtml(specialtyLabel);
                    const statusLabel = consultation.status || 'unknown';
                    const statusClass = String(statusLabel).toLowerCase().replace(/[^a-z0-9_-]/g, '');
                    return `
                        <div class="consultation-history-item">
                            <div class="consultation-date">
                                ${new Date(consultation.consultation_date).toLocaleDateString('ro-RO', {
                                    year: 'numeric',
                                    month: 'long',
                                    day: 'numeric'
                                })}
                            </div>
                            <div class="consultation-details">
                                <span class="consultation-type-badge">${safeSpecialty}</span>
                                <span class="consultation-status status-${statusClass}">${this.escapeHtml(statusLabel)}</span>
                                ${consultation.is_signed ? '<span class="signed-badge"><i class="fas fa-signature"></i> Signed</span>' : ''}
                            </div>
                        </div>
                    `;
                }).join('')
                : `
                    <div class="empty-state">
                        <div class="empty-icon">🩺</div>
                        <h4>No consultations yet</h4>
                        <p>Consultations will appear here once created</p>
                    </div>
                `;

            container.innerHTML = `
                <div class="documents-section">
                    <h4 class="section-title"><i class="fas fa-notes-medical"></i> Consultations</h4>
                    ${consultationsSection}
                </div>
                <div class="documents-section">
                    <h4 class="section-title"><i class="fas fa-file-medical"></i> Documents</h4>
                    ${documentsSection}
                </div>
            `;
            this.bindDocumentHistoryActions();
        } catch (err) {
            console.error('Failed to load documents or consultations:', err);
            container.innerHTML = `
                <div class="documents-section">
                    <h4 class="section-title"><i class="fas fa-notes-medical"></i> Consultations</h4>
                    <p class="text-error">Unable to load consultations right now.</p>
                </div>
                <div class="documents-section">
                    <h4 class="section-title"><i class="fas fa-file-medical"></i> Documents</h4>
                    <p class="text-error">Unable to load documents right now.</p>
                </div>
            `;
        }
    }

    // Placeholder for future document grouping
    renderGroupedDocuments(documents) {
        // Group documents by type
        const grouped = documents.reduce((acc, doc) => {
            const type = (doc.document_type || 'uncategorized').trim() || 'uncategorized';
            if (!acc[type]) acc[type] = [];
            acc[type].push(doc);
            return acc;
        }, {});
        
        // Render each group
        const html = Object.entries(grouped)
            .sort(([typeA], [typeB]) => typeA.localeCompare(typeB))
            .map(([type, docs]) => {
                const sortedDocs = [...docs].sort((a, b) => {
                    const dateA = new Date(a.created_at || 0).getTime();
                    const dateB = new Date(b.created_at || 0).getTime();
                    return dateB - dateA;
                });

                const titleLabel = this.escapeHtml(type.replace(/_/g, ' ').toUpperCase());
                const groupItems = sortedDocs.map(doc => {
                    const rawFilename = doc.filename || doc.title || 'Untitled';
                    const filename = this.escapeHtml(rawFilename);
                    const encodedFilename = encodeURIComponent(rawFilename);
                    const snippet = doc.text_snippet || '';
                    const truncatedSnippet = snippet
                        ? this.escapeHtml(this.truncateText(snippet, 160))
                        : '';
                    const snippetMarkup = truncatedSnippet
                        ? `<span class="document-snippet">${truncatedSnippet}</span>`
                        : '<span class="document-snippet text-muted">No extracted text</span>';
                    const downloadAction = doc.has_original_file && doc.download_url
                        ? `
                            <a class="btn-small" href="${doc.download_url}" target="_blank" rel="noopener">
                                <i class="fas fa-download"></i>
                            </a>
                        `
                        : '';

                    return `
                        <div class="document-item-row">
                            <div class="document-item-details">
                                <span class="document-date">${new Date(doc.created_at).toLocaleDateString('ro-RO')}</span>
                                <span class="document-title">${filename}</span>
                                ${snippetMarkup}
                            </div>
                            <div class="document-actions">
                                <button
                                    class="btn-small document-view-btn"
                                    data-action="view-document-text"
                                    data-document-id="${doc.id}"
                                    data-full-text-url="${doc.full_text_url}"
                                    data-document-title="${encodedFilename}"
                                >
                                    <i class="fas fa-eye"></i> View
                                </button>
                                ${downloadAction}
                            </div>
                        </div>
                    `;
                }).join('');

                return `
                    <div class="document-group">
                        <div class="document-group-header" onclick="this.classList.toggle('collapsed'); this.nextElementSibling.classList.toggle('collapsed')">
                            <i class="fas fa-chevron-down"></i>
                            <span class="document-group-title">${titleLabel}</span>
                            <span class="document-group-count">${sortedDocs.length}</span>
                        </div>
                        <div class="document-items">
                            ${groupItems}
                        </div>
                    </div>
                `;
            })
            .join('');
        
        return html;
    }

    bindDocumentHistoryActions() {
        const container = document.getElementById('documents-list');
        if (!container || container.dataset.actionsBound) {
            return;
        }

        container.addEventListener('click', (event) => {
            const target = event.target.closest('[data-action="view-document-text"]');
            if (!target) {
                return;
            }
            const documentId = target.dataset.documentId;
            const fullTextUrl = target.dataset.fullTextUrl;
            const documentTitle = target.dataset.documentTitle;
            this.openDocumentTextModal(documentId, fullTextUrl, documentTitle);
        });

        container.dataset.actionsBound = 'true';
    }

    ensureDocumentTextModal() {
        let modal = document.getElementById('document-text-modal');
        if (modal) {
            return modal;
        }

        modal = document.createElement('div');
        modal.id = 'document-text-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content large">
                <div class="modal-header">
                    <h2 id="document-text-modal-title">Extracted Text</h2>
                    <button class="modal-close" data-action="close-document-text-modal">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div id="document-text-modal-content">
                        <div class="loading-placeholder">Loading text...</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" data-action="close-document-text-modal">Close</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                hideModal('document-text-modal');
            }
        });

        modal.querySelectorAll('[data-action="close-document-text-modal"]').forEach(button => {
            button.addEventListener('click', () => hideModal('document-text-modal'));
        });

        return modal;
    }

    async openDocumentTextModal(documentId, fullTextUrl, documentTitle) {
        if (!documentId || !fullTextUrl) {
            showToast('Document text is unavailable.', 'warning');
            return;
        }

        const modal = this.ensureDocumentTextModal();
        const title = modal.querySelector('#document-text-modal-title');
        const content = modal.querySelector('#document-text-modal-content');
        let decodedTitle = '';
        if (documentTitle) {
            try {
                decodedTitle = decodeURIComponent(documentTitle);
            } catch (error) {
                decodedTitle = documentTitle;
            }
        }

        title.textContent = documentTitle
            ? `Extracted Text - ${decodedTitle}`
            : 'Extracted Text';
        content.innerHTML = '<div class="loading-placeholder">Loading text...</div>';
        showModal('document-text-modal');

        try {
            const response = await fetch(fullTextUrl);
            if (!response.ok) {
                throw new Error('Failed to load document text');
            }
            const data = await response.json();
            const text = data?.text || '';
            content.innerHTML = text
                ? `
                    <pre style="white-space: pre-wrap; max-height: 400px; overflow-y: auto; margin: 0;">
${this.escapeHtml(text)}
                    </pre>
                `
                : '<p class="text-muted">No extracted text available.</p>';
        } catch (error) {
            console.error('Failed to load document text:', error);
            content.innerHTML = '<p class="text-error">Unable to load extracted text.</p>';
        }
    }

    escapeHtml(value) {
        if (value === null || value === undefined) {
            return '';
        }
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    truncateText(text, maxLength) {
        if (!text) {
            return '';
        }
        if (text.length <= maxLength) {
            return text;
        }
        return `${text.slice(0, Math.max(0, maxLength - 1))}…`;
    }

    // Actions from modal footer
    editPatientFromView() {
        if (this.currentViewPatientId) {
            hideModal('view-patient-modal');
            this.editPatient(this.currentViewPatientId);
        }
    }

    manageGDPRFromView() {
        if (this.currentViewPatientId) {
            hideModal('view-patient-modal');
            this.manageGDPR(this.currentViewPatientId);
        }
    }

    // -------------------------------------------------------------------------
    // Manage GDPR
    // -------------------------------------------------------------------------
    async manageGDPR(patientId) {
        try {
            // Fetch patient details
            const url = apiUrl(API_CONFIG.ENDPOINTS.patients, `${patientId}`);
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to load patient');
            
            const patient = await response.json();
            
            // Store current patient for actions
            this.currentGDPRPatient = patient;
            
            // Populate GDPR modal
            this.populateGDPRModal(patient);
            
            // Setup event listeners
            this.initGDPRModalListeners();
            
            // Show modal
            showModal('gdpr-modal');
            
        } catch (err) {
            console.error('Failed to load GDPR management:', err);
            showToast('Failed to load GDPR management', 'error');
        }
    }

    populateGDPRModal(patient) {
        // Update modal title
        document.getElementById('gdpr-modal-title').textContent = 
            `GDPR Consent Management: ${patient.given_name} ${patient.family_name}`;
        
        // Patient banner
        document.getElementById('gdpr-patient-name').textContent = 
            `${patient.given_name} ${patient.family_name}`;
        document.getElementById('gdpr-patient-details').textContent = 
            `CNP: ${patient.cnp || 'N/A'} • Born: ${patient.birth_date || 'N/A'}`;
        
        // Render consent cards
        this.renderGDPRConsentCards(patient.gdpr_consents || {});
    }

    renderGDPRConsentCards(consents) {
        const container = document.getElementById('gdpr-consent-list');
        
        // Define consent types with metadata
        const consentTypes = {
            'treatment': {
                name: 'Treatment Consent',
                description: 'Permission to provide medical treatment and care',
                required: true
            },
            'data_processing': {
                name: 'Data Processing',
                description: 'Permission to process personal and medical data',
                required: true
            },
            'research': {
                name: 'Research Participation',
                description: 'Optional participation in medical research studies',
                required: false
            },
            'marketing': {
                name: 'Marketing Communications',
                description: 'Optional newsletters and health information updates',
                required: false
            }
        };
        
        const html = Object.entries(consentTypes).map(([key, meta]) => {
            const consent = consents[key] || { granted: false };
            const isGranted = consent.granted === true && !consent.withdrawn;
            const isWithdrawn = consent.withdrawn === true;
            
            let status, statusText, icon;
            if (isWithdrawn) {
                status = 'withdrawn';
                statusText = 'Withdrawn';
                icon = 'fa-ban';
            } else if (isGranted) {
                status = 'granted';
                statusText = 'Granted';
                icon = 'fa-check-circle';
            } else {
                status = 'not-granted';
                statusText = 'Not Granted';
                icon = 'fa-times-circle';
            }
            
            const dateText = consent.granted_at ? 
                new Date(consent.granted_at).toLocaleDateString('ro-RO') : '';
            
            return `
                <div class="gdpr-consent-card ${status}">
                    <div class="gdpr-consent-header">
                        <div class="gdpr-consent-title">
                            <i class="fas ${icon}"></i>
                            <div>
                                <div class="gdpr-consent-name">
                                    ${meta.name} ${meta.required ? '(Required)' : '(Optional)'}
                                </div>
                            </div>
                        </div>
                        <span class="gdpr-consent-status ${status}">${statusText}</span>
                    </div>
                    <div class="gdpr-consent-details">
                        ${meta.description}
                        ${dateText ? `<br><small>Granted: ${dateText}</small>` : ''}
                        ${consent.expires_at ? `<br><small>Expires: ${new Date(consent.expires_at).toLocaleDateString('ro-RO')}</small>` : ''}
                    </div>
                    <div class="gdpr-consent-actions">
                        ${isGranted ? `
                            <button class="btn-small btn-danger" onclick="app.withdrawConsent('${key}')">
                                <i class="fas fa-ban"></i> Withdraw
                            </button>
                        ` : ''}
                        ${!isGranted && !isWithdrawn ? `
                            <button class="btn-small btn-secondary" onclick="app.grantConsent('${key}')">
                                <i class="fas fa-check"></i> Grant Consent
                            </button>
                        ` : ''}
                        ${isWithdrawn ? `
                            <button class="btn-small btn-secondary" onclick="app.renewConsent('${key}')">
                                <i class="fas fa-redo"></i> Renew Consent
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = html;
    }

    initGDPRModalListeners() {
        // Generate consent forms button
        const generateBtn = document.getElementById('generate-consent-forms-btn');
        if (generateBtn) {
            generateBtn.onclick = () => this.generateConsentForms();
        }
        
        // View history button
        const historyBtn = document.getElementById('view-consent-history-btn');
        if (historyBtn) {
            historyBtn.onclick = () => this.viewConsentHistory();
        }
    }

    // -------------------------------------------------------------------------
    // Consent Actions
    // -------------------------------------------------------------------------
    withdrawConsent(consentType) {
        // Set consent type in withdrawal modal
        document.getElementById('withdraw-consent-type').value = consentType;
        
        // Show withdrawal modal
        showModal('withdraw-consent-modal');
        
        // Setup form submission
        const form = document.getElementById('withdraw-consent-form');
        form.onsubmit = async (e) => {
            e.preventDefault();
            await this.processConsentWithdrawal();
        };
    }

    async processConsentWithdrawal() {
        try {
            const formData = new FormData(document.getElementById('withdraw-consent-form'));
            const withdrawalData = {
                consent_type: formData.get('consent_type'),
                reason: formData.get('reason'),
                notes: formData.get('notes'),
                initiated_by: formData.get('initiated_by')
            };
            
            const url = apiUrl(API_CONFIG.ENDPOINTS.patients, 
                `${this.currentGDPRPatient.id}/gdpr/withdraw-consent`);
            
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(withdrawalData)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to withdraw consent');
            }
            
            showToast('Consent withdrawn successfully', 'success');
            hideModal('withdraw-consent-modal');
            
            // FETCH FRESH PATIENT DATA before reloading modal
            const patientUrl = apiUrl(API_CONFIG.ENDPOINTS.patients, `${this.currentGDPRPatient.id}`);
            const patientResponse = await fetch(patientUrl);
            if (patientResponse.ok) {
                this.currentGDPRPatient = await patientResponse.json();
            }
            
            // Reload GDPR modal with fresh data
            await this.manageGDPR(this.currentGDPRPatient.id);
            
        } catch (err) {
            console.error('Failed to withdraw consent:', err);
            showToast(err.message || 'Failed to withdraw consent', 'error');
        }
    }

    async grantConsent(consentType) {
        if (!this.currentGDPRPatient) return;
        
        try {
            const url = apiUrl(API_CONFIG.ENDPOINTS.patients, 
                `${this.currentGDPRPatient.id}/gdpr/grant-consent`);
            
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    consent_type: consentType,
                    granted_at: new Date().toISOString(),
                    expires_at: null // Or set expiration date if needed
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to grant consent');
            }
            
            showToast(`Consent granted: ${consentType}`, 'success');
            
            // FETCH FRESH PATIENT DATA before reloading modal
            const patientUrl = apiUrl(API_CONFIG.ENDPOINTS.patients, `${this.currentGDPRPatient.id}`);
            const patientResponse = await fetch(patientUrl);
            if (patientResponse.ok) {
                this.currentGDPRPatient = await patientResponse.json();
            }
            
            // Reload GDPR modal with fresh data
            await this.manageGDPR(this.currentGDPRPatient.id);
            
        } catch (err) {
            console.error('Failed to grant consent:', err);
            showToast(err.message || 'Failed to grant consent', 'error');
        }
    }

    async renewConsent(consentType) {
        if (!this.currentGDPRPatient) return;
        
        try {
            const url = apiUrl(API_CONFIG.ENDPOINTS.patients, 
                `${this.currentGDPRPatient.id}/gdpr/renew-consent`);
            
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    consent_type: consentType,
                    renewed_at: new Date().toISOString(),
                    expires_at: null // Or set new expiration
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to renew consent');
            }
            
            showToast(`Consent renewed: ${consentType}`, 'success');
            
            // FETCH FRESH PATIENT DATA before reloading modal
            const patientUrl = apiUrl(API_CONFIG.ENDPOINTS.patients, `${this.currentGDPRPatient.id}`);
            const patientResponse = await fetch(patientUrl);
            if (patientResponse.ok) {
                this.currentGDPRPatient = await patientResponse.json();
            }
            
            // Reload GDPR modal with fresh data
            await this.manageGDPR(this.currentGDPRPatient.id);
            
        } catch (err) {
            console.error('Failed to renew consent:', err);
            showToast(err.message || 'Failed to renew consent', 'error');
        }
    }

    async generateConsentForms() {
        if (!this.currentGDPRPatient) return;
        
        try {
            // Fetch clinic consent templates
            const clinicResponse = await fetch(apiUrl(API_CONFIG.ENDPOINTS.clinics, 'my-clinic'));
            if (!clinicResponse.ok) throw new Error('Failed to fetch clinic templates');
            
            const clinic = await clinicResponse.json();
            
            // Generate PDF with patient data
            await this.createConsentPDF(this.currentGDPRPatient, clinic);
            
            showToast('Consent forms generated and downloaded', 'success');
            
        } catch (err) {
            console.error('Failed to generate consent forms:', err);
            showToast('Failed to generate consent forms', 'error');
        }
    }

    async createConsentPDF(patient, clinic) {
        // Fetch HTML template
        const response = await fetch('/static/templates/gdpr_consent_ro.html'); //in the future, make it variable by clinic
        const template = await response.text();
        
         // --- Extrage textele din DB pentru a evita repetarea ---
        const templates = clinic.gdpr_templates;

        // Replace variables
        const html = template
            .replace(/{{patient_name}}/g, `${patient.given_name} ${patient.family_name}`)
            .replace(/{{cnp}}/g, patient.cnp || 'N/A')
            .replace(/{{clinic_name}}/g, clinic.name || 'Demo Clinic')
            .replace(/{{date}}/g, new Date().toLocaleDateString('ro-RO'))
            // 1. Text Tratament (Existent)
            .replace(/{{treatment_text}}/g, templates?.treatment_ro || 'Text implicit: Consimțământ pentru tratament...')
            
            // 2. TEXT OBLIGATORIU GDPR (Acest câmp lipsea!)
            .replace(/{{data_processing_text}}/g, templates?.data_processing_ro || 'Text implicit: Consimțământ pentru prelucrarea datelor.  Categorii de date prelucrate: Date de identificare (nume, prenume, CNP, adresă), Date medicale (diagnostic, tratament, istoric medical), Date de contact (telefon, email), Date de asigurare medicală')
            
            // 3. (OPȚIONAL) Înlocuiește textul de cercetare (dacă este variabil)
            .replace(/{{research_text}}/g, templates?.research_ro || 'Text implicit: Consimțământ pentru cercetare. Prin prezentul, sunt de acord ca datele mele medicale să fie utilizate în scopuri de cercetare medicală, în formă anonimizată, pentru îmbunătățirea serviciilor medicale și avansarea cunoștințelor medicale.')
            
            // 4. (OPȚIONAL) Înlocuiește textul de marketing (dacă este variabil)
            .replace(/{{marketing_text}}/g, templates?.marketing_ro || 'Text implicit: Consimțământ pentru marketing.  Doresc să primesc comunicări informative despre servicii medicale, programe de sănătate, și oferte speciale din partea clinicii.')
            
            // 5. (OPȚIONAL) Adaugă adresa de email în Footer (dacă ai o variabilă pentru asta)
            .replace(/{{clinic_email}}/g, clinic.email || 'info@demo.ro'); // Asigură-te că folosești variabila clinic.email

        // Convert to PDF using html2pdf
        const opt = {
            margin: 25,
            filename: `consimtamant_${patient.family_name}_${Date.now()}.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2 },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
        };
        
        await html2pdf().set(opt).from(html).save();
    }

    async viewConsentHistory() {
        if (!this.currentGDPRPatient) return;
        
        try {
            const url = apiUrl(API_CONFIG.ENDPOINTS.patients, 
                `${this.currentGDPRPatient.id}/gdpr/consent-history`);
            
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to load history');
            
            const history = await response.json();
            
            // Populate and show modal
            this.showConsentHistoryModal(history);
            
        } catch (err) {
            console.error('Failed to load consent history:', err);
            showToast('Failed to load consent history', 'error');
        }
    }

    showConsentHistoryModal(history) {
        // Update patient info
        document.getElementById('history-patient-name').textContent = 
            `${this.currentGDPRPatient.given_name} ${this.currentGDPRPatient.family_name}`;
        document.getElementById('history-patient-details').textContent = 
            `CNP: ${this.currentGDPRPatient.cnp || 'N/A'}`;
        
        const timeline = document.getElementById('consent-history-timeline');
        
        if (!history || history.length === 0) {
            timeline.innerHTML = `
                <div class="history-empty">
                    <i class="fas fa-history"></i>
                    <h4>No consent history</h4>
                    <p>No consent changes have been recorded yet</p>
                </div>
            `;
        } else {
            const historyHTML = history.map(entry => {
                const action = entry.action.replace('consent_', '');
                const actionClass = action === 'withdrawn' ? 'withdrawn' : 
                                action === 'granted' ? 'granted' : 'renewed';
                
                const actionText = action === 'withdrawn' ? 'Withdrawn' :
                                action === 'granted' ? 'Granted' : 'Renewed';
                
                return `
                    <div class="history-entry ${actionClass}">
                        <div class="history-timestamp">
                            <i class="fas fa-clock"></i> 
                            ${new Date(entry.timestamp).toLocaleString('ro-RO', {
                                year: 'numeric',
                                month: 'long',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit'
                            })}
                        </div>
                        <div class="history-action">
                            <span class="history-consent-type">${entry.details.consent_type?.replace('_', ' ').toUpperCase()}</span>
                            <span class="history-action-badge ${actionClass}">${actionText}</span>
                        </div>
                        <div class="history-details">
                            <div class="history-performed-by">
                                <i class="fas fa-user"></i> By: ${entry.details.granted_by || entry.details.withdrawn_by || entry.details.renewed_by || 'Unknown'}
                            </div>
                            ${entry.details.reason ? `
                                <div class="history-reason">
                                    <strong>Reason:</strong> ${entry.details.reason}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            }).join('');
            
            timeline.innerHTML = historyHTML;
        }
        
        showModal('consent-history-modal');
    }

    exportConsentHistory() {
        showToast('Export to PDF - coming soon', 'info');
        // Future: Generate PDF report of consent history
    }
}
