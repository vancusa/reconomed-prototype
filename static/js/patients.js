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
            // Debounced search
            // Debouncing = Instead of running the search function immediately every time a user types a character 
            // (which can be resource-intensive, especially for network requests), debouncing ensures the function 
            // is only executed after a specific period of inactivity has passed since the last event (e.g., the last keypress).
            let searchTimeout;
        
            this.searchInput.addEventListener('input', (e) => {
                const value = e.target.value;  // capture immediately
                //console.log('Search input detected:', value);
                //console.log('Clearing existing timeout...');
                clearTimeout(searchTimeout);
                //console.log('Setting new timeout...');
                searchTimeout = setTimeout(() => {
                    //console.log('--- DEBOUNCED SEARCH EXECUTING ---')
                    this.searchPatients(value);
                }, 300);
        });
        // Sort change handler
        if (this.sortSelect) {
            this.sortSelect.addEventListener('change', (e) => {
                this.currentSort = e.target.value;
                this.loadPatients(1, this.searchInput?.value || '');
            });
        }
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
    async loadPatients(page = 1, searchQuery = '') {
        try {
            //console.log('loadPatients called - page:', page, 'search:', searchQuery);
            // Build URL with pagination parameters
            let url = apiUrl(API_CONFIG.ENDPOINTS.patients, ``);
            const params = new URLSearchParams({
                page: page,
                per_page: this.perPage
            });
            
            if (searchQuery) {
                params.append('search', searchQuery);
            }
            
            url += `?${params.toString()}`;
            
            //console.log('Fetching URL:', url);

            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to load patients');

            const data = await response.json();
            
            // Update state from paginated response
            this.patients = data.patients;
            this.currentPage = data.page;
            this.totalPages = data.total_pages;
            this.totalPatients = data.total;
            this.hasNext = data.has_next;
            this.hasPrev = data.has_prev;
            
            // Update UI
            this.renderPatients();
            this.updatePaginationControls();
            this.updatePatientCount();

        } catch (err) {
            console.error(err);
            showToast('Could not load patients', 'error');
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
            await this.loadPatients(this.currentPage + 1, this.searchInput?.value || '');
        }
    }

    async previousPage() {
        if (this.hasPrev) {
            await this.loadPatients(this.currentPage - 1, this.searchInput?.value || '');
        }
    }

    // -------------------------------------------------------------------------
    // Search with Pagination Reset
    // -------------------------------------------------------------------------
    async searchPatients(query) {
        // Reset to page 1 when searching
        
        //console.log('searchPatients called with:', query);
        
        await this.loadPatients(1, query);
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
                    <p>${patient.birth_date || ''} ${patient.phone ? '• ' + patient.phone : ''}</p>
                </div>
                <div class="patient-actions">
                    <button class="btn btn-sm btn-primary" data-action="view" data-id="${patient.id}">View</button>
                    <button class="btn btn-sm btn-secondary" data-action="edit" data-id="${patient.id}">Edit</button>
                    <button class="btn btn-sm btn-tertiary" data-action="gdpr" data-id="${patient.id}">GDPR</button>
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
            console.log(response);
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
        const action = e.target.dataset.action;
        const id = e.target.dataset.id;

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
            default:
                console.warn('Unknown patient action:', action);
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
    // View Patient (placeholder for now)
    // -------------------------------------------------------------------------
    viewPatient(patientId) {
        showToast(`View patient ${patientId} - coming soon`, 'info');
    }

    // -------------------------------------------------------------------------
    // Manage GDPR (placeholder for now)
    // -------------------------------------------------------------------------
    manageGDPR(patientId) {
        showToast(`GDPR management for ${patientId} - coming soon`, 'info');
    }
}