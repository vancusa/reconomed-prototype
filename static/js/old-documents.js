// documents.js
// -----------------------------------------------------------------------------
// Manages patient documents: listing, uploading, validating, and previewing
// -----------------------------------------------------------------------------
//
// Responsibilities:
//  - Fetch and render a patient's documents
//  - Handle new uploads (delegating compression/validation to helpers if needed)
//  - Support validation workflow (approve/reject)
//  - Provide document preview/download
//
// NOTE: This module assumes your backend exposes endpoints like:
//   GET    /api/patients/:id/documents
//   POST   /api/patients/:id/documents
//   GET    /api/documents/:docId/download
//   POST   /api/documents/:docId/validate
//
// -----------------------------------------------------------------------------

import { showToast, showModal, hideModal } from './ui.js';

export class DocumentManager {
    constructor(app) {
        this.app = app;
        this.documents = [];
        this.currentPatientId = null;

        // DOM references
        this.docListContainer = document.getElementById('document-list');
        this.uploadInput = document.getElementById('document-upload');
        this.validationModal = document.getElementById('validation-modal');
    }

    // -------------------------------------------------------------------------
    // Initialization
    // -------------------------------------------------------------------------
    init() {
        if (this.uploadInput) {
            this.uploadInput.addEventListener('change', (e) => this.handleUpload(e));
        }
    }

    // -------------------------------------------------------------------------
    // Fetch & Render
    // -------------------------------------------------------------------------
    async loadDocuments(patientId) {
        this.currentPatientId = patientId;
        try {
            const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients, `/${patientId}/documents`));
            if (!response.ok) throw new Error('Failed to fetch documents');

            this.documents = await response.json();
            this.renderDocuments();
        } catch (err) {
            console.error(err);
            showToast('Could not load documents', 'error');
        }
    }

    renderDocuments() {
        if (!this.docListContainer) return;
        this.docListContainer.innerHTML = '';

        if (this.documents.length === 0) {
            this.docListContainer.innerHTML = '<p>No documents available</p>';
            return;
        }

        this.documents.forEach(doc => {
            const item = document.createElement('div');
            item.className = 'document-item';
            item.innerHTML = `
                <span class="doc-name">${doc.name}</span>
                <span class="doc-status ${doc.status}">${doc.status}</span>
                <button class="btn btn-sm btn-primary" data-action="preview" data-id="${doc.id}">Preview</button>
                <button class="btn btn-sm btn-secondary" data-action="download" data-id="${doc.id}">Download</button>
                ${this.app.currentUser?.role === 'doctor' || this.app.currentUser?.role === 'admin'
                    ? `<button class="btn btn-sm btn-success" data-action="validate" data-id="${doc.id}">Validate</button>` 
                    : ''}
            `;
            this.docListContainer.appendChild(item);
        });

        // Attach event delegation
        this.docListContainer.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleAction(e));
        });
    }

    // -------------------------------------------------------------------------
    // Upload Handling
    // -------------------------------------------------------------------------
    async handleUpload(event) {
        const file = event.target.files[0];
        if (!file || !this.currentPatientId) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.patients, `/${this.currentPatientId}/documents`),
            {
                method: 'POST',
                body: formData
            });
            if (!response.ok) throw new Error('Upload failed');

            const newDoc = await response.json();
            this.documents.push(newDoc);
            this.renderDocuments();
            showToast('Document uploaded successfully', 'success');
        } catch (err) {
            console.error(err);
            showToast('Failed to upload document', 'error');
        } finally {
            this.uploadInput.value = ''; // reset input
        }
    }

    // -------------------------------------------------------------------------
    // Document Actions
    // -------------------------------------------------------------------------
    async handleAction(e) {
        const action = e.target.dataset.action;
        const docId = e.target.dataset.id;

        switch (action) {
            case 'preview':
                this.previewDocument(docId);
                break;
            case 'download':
                this.downloadDocument(docId);
                break;
            case 'validate':
                this.openValidationModal(docId);
                break;
        }
    }

    async previewDocument(docId) {
        // Could be inline modal, PDF viewer, etc.
        showToast(`Previewing document ${docId}`, 'info');
        // Example: showModal('document-preview-modal');
    }

    async downloadDocument(docId) {
        try {
            window.open(`/api/documents/${docId}/download`, '_blank');
        } catch (err) {
            console.error(err);
            showToast('Download failed', 'error');
        }
    }

    openValidationModal(docId) {
        if (!this.validationModal) return;
        this.validationModal.dataset.docId = docId;
        showModal('validation-modal');

        const approveBtn = this.validationModal.querySelector('#approve-doc');
        const rejectBtn = this.validationModal.querySelector('#reject-doc');

        approveBtn.onclick = () => this.validateDocument(docId, true);
        rejectBtn.onclick = () => this.validateDocument(docId, false);
    }

    async validateDocument(docId, approved) {
        try {
            const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `/${docId}/validate`), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ approved })
            });
            if (!response.ok) throw new Error('Validation failed');

            const updatedDoc = await response.json();
            this.documents = this.documents.map(doc => 
                doc.id === updatedDoc.id ? updatedDoc : doc
            );
            this.renderDocuments();
            hideModal('validation-modal');
            showToast(approved ? 'Document approved' : 'Document rejected', 'success');
        } catch (err) {
            console.error(err);
            showToast('Validation failed', 'error');
        }
    }

    uploadDocumentForPatient(patientId) {
        window.app.goToSection('documents');
        // Pre-select patient in batch-patient dropdown
        const patientSelect = document.getElementById('batch-patient');
        if (patientSelect) {
            patientSelect.value = patientId;
        }
        // Focus upload area
        document.getElementById('upload-dropzone')?.scrollIntoView({ behavior: 'smooth' });
    }
}