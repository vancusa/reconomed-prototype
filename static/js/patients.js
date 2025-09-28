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
//   - <form id="add-patient-form"></form> for adding patients
//   - <input id="patient-search" /> for live search/filtering
// -----------------------------------------------------------------------------

import { showToast, showModal, hideModal } from './ui.js';

export class PatientManager {
    constructor(app) {
        this.app = app;
        this.patients = [];

        // DOM references
        this.gridContainer = document.getElementById('patients-grid');
        this.addForm = document.getElementById('add-patient-form');
        this.searchInput = document.getElementById('patient-search');
    }

    // -------------------------------------------------------------------------
    // Initialization
    // -------------------------------------------------------------------------
    init() {
        if (this.addForm) {
            this.addForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.addPatient();
            });
        }

        if (this.searchInput) {
            this.searchInput.addEventListener('input', (e) => {
                this.searchPatients(e.target.value);
            });
        }
    }

    // -------------------------------------------------------------------------
    // Data Loading
    // -------------------------------------------------------------------------
    async loadPatients() {
        try {
            const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients));
            if (!response.ok) throw new Error('Failed to load patients');

            this.patients = await response.json();
            this.renderPatients();
        } catch (err) {
            console.error(err);
            showToast('Could not load patients', 'error');
        }
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
            const initials = (patient.given_name[0] || '') + (patient.family_name[0] || '');
            card.innerHTML = `
                <div class="patient-avatar">${initials}</div>
                <div class="patient-info">
                    <h3>${patient.given_name} ${patient.family_name}</h3>
                    <p>${patient.birth_date || ''} ${patient.phone ? '• ' + patient.phone : ''}</p>
                </div>
                <div class="patient-actions">
                    <button class="btn btn-sm btn-primary" data-action="view" data-id="${patient.id}">View</button>
                    <button class="btn btn-sm btn-secondary" data-action="edit" data-id="${patient.id}">Edit</button>
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
    // Search/Filter
    // -------------------------------------------------------------------------
    searchPatients(query) {
        const normalizedQuery = query.toLowerCase();
        const filtered = this.patients.filter(patient => {
            const fullName = `${patient.given_name} ${patient.family_name}`.toLowerCase();
            return fullName.includes(normalizedQuery) ||
                (patient.phone && patient.phone.includes(normalizedQuery));
        });
        this.renderPatients(filtered);
    }

    // -------------------------------------------------------------------------
    // Form Submission / Add Patient
    // -------------------------------------------------------------------------
    async addPatient() {
        if (!this.addForm) return;
        const formData = new FormData(this.addForm);
        const patientData = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(patientData)
            });
            if (!response.ok) throw new Error('Failed to add patient');

            const newPatient = await response.json();
            this.patients.push(newPatient);
            this.renderPatients();
            this.addForm.reset();
            showToast('Patient added successfully', 'success');
        } catch (err) {
            console.error(err);
            showToast('Failed to add patient', 'error');
        }
    }

    // -------------------------------------------------------------------------
    // Actions: view/edit (placeholder for future)
    // -------------------------------------------------------------------------
    handleAction(e) {
        const action = e.target.dataset.action;
        const id = e.target.dataset.id;

        switch (action) {
            case 'view':
                showToast(`Viewing patient ${id}`, 'info');
                break;
            case 'edit':
                showToast(`Editing patient ${id}`, 'info');
                break;
            default:
                console.warn('Unknown patient action:', action);
        }
    }
}