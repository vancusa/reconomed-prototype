// document-manager.js
// ES Module version
// Handles fetching, rendering, and validation of documents

import { showToast, showModal, hideModal } from './ui.js';
import { handleFileSelect, setupUploadArea } from './upload-handler.js';

/* *
 * Load documents for a specific patient from the API.
 * @param {string|number} patientId - Patient ID
 * @param {string} apiBase - API base URL
 * @returns {Promise<Array>} - Array of documents
 */
export async function loadPatientDocuments(patientId, apiBase = '/') {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `/patient/${patientId}`));
        if (!response.ok) throw new Error('Failed to load documents');
        const documents = await response.json();
        renderDocuments(documents);
        return documents;
    } catch (error) {
        console.error('Failed to load documents:', error);
        showToast('Failed to load documents', 'error');
        return [];
    }
}

/* *
 * Render a list of documents into the DOM.
 * @param {Array} docs - Documents to render
 */
export function renderDocuments(docs) {
    const container = document.getElementById('documents-list');
    if (!container) return;

    if (docs.length === 0) {
        container.innerHTML = '<p class="text-center">No documents found for this patient.</p>';
        return;
    }

    container.innerHTML = docs.map(doc => {
        const status = doc.is_validated ? 'validated' :
                     doc.document_type === 'pending_ocr' ? 'pending' : 'processing';
        
        const statusIcon = status === 'validated' ? 'fas fa-check-circle' :
                          status === 'pending' ? 'fas fa-clock' :
                          'fas fa-cog fa-spin';

        return `
            <div class="document-item">
                <div class="document-icon ${status}">
                    <i class="${statusIcon}"></i>
                </div>
                <div class="document-info">
                    <div class="document-name">${doc.filename}</div>
                    <div class="document-meta">
                        Type: ${doc.document_type} • Created: ${new Date(doc.created_at).toLocaleDateString()}
                    </div>
                </div>
                <div class="document-actions">
                    ${status === 'processing' ? `
                        <button class="btn-small primary" onclick="app.openValidationModal(${doc.id})">
                            <i class="fas fa-edit"></i> Validate
                        </button>
                    ` : ''}
                    <button class="btn-small secondary" onclick="app.viewDocument(${doc.id})">
                        <i class="fas fa-eye"></i> View
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

/* *
 * Open the validation modal for a specific document.
 * @param {number} documentId - ID of the document to validate
 * @param {string} apiBase - API base URL
 */
export async function openValidationModal(documentId, apiBase = '/') {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `/${documentId}/validation`));
        if (!response.ok) throw new Error('Failed to fetch validation data');
        const validation = await response.json();

        renderValidationModal(validation);
        showModal('validation-modal');
    } catch (error) {
        console.error('Failed to load validation data:', error);
        showToast('Failed to load validation data', 'error');
    }
}

/* *
 * Render validation modal content with extracted fields.
 * @param {Object} validation - Validation data from the API
 */
function renderValidationModal(validation) {
    const content = document.getElementById('validation-content');
    const doc = validation.document;

    content.innerHTML = `
        <div class="validation-layout">
            <div class="validation-preview">
                <h3>Original Document</h3>
                <div class="document-preview">
                    <p><strong>Filename:</strong> ${doc.filename}</p>
                    <p><strong>Type:</strong> ${doc.document_type}</p>
                    <div class="ocr-text">
                        <strong>Extracted Text:</strong>
                        <pre>${doc.ocr_text}</pre>
                    </div>
                </div>
            </div>
            <div class="validation-form">
                <h3>Validation Form</h3>
                <form id="validation-form">
                    ${validation.validation_fields.map(field => `
                        <div class="form-group">
                            <label for="field-${field.field}">${field.label}</label>
                            ${field.type === 'textarea' ? 
                                `<textarea id="field-${field.field}" name="${field.field}" ${field.required ? 'required' : ''}>${field.value}</textarea>` :
                                `<input type="${field.type}" id="field-${field.field}" name="${field.field}" value="${field.value}" ${field.required ? 'required' : ''}>`
                            }
                        </div>
                    `).join('')}
                    
                    ${validation.suggestions.length > 0 ? `
                        <div class="validation-suggestions">
                            <h4>Suggestions:</h4>
                            <ul>
                                ${validation.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    
                    <div class="form-actions">
                        <button type="button" class="btn-secondary" onclick="app.closeValidationModal()">Cancel</button>
                        <button type="submit" class="btn-primary">Validate Document</button>
                    </div>
                </form>
            </div>
        </div>
    `;

    // Handle form submission
    document.getElementById('validation-form').addEventListener('submit', async e => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const validatedData = Object.fromEntries(formData.entries());
        try 
        {
            await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `/${doc.id}/validate`),
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(validatedData)
            });
            showToast('Document validated successfully!', 'success');
            hideModal('validation-modal');
        }
        catch {
            showToast('Validation failed', 'error');
        }
    });
}

/**
 * Initialize document manager tabs and their switching logic
 */
export function initDocumentTabs() {
    const tabButtons = document.querySelectorAll('.document-tabs .tab-button');
    const tabContents = document.querySelectorAll('.document-tabs .tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.dataset.tab;
            
            // Remove active from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active to clicked button and corresponding content
            button.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
            
            // Load content for the active tab
            loadTabContent(targetTab);
        });
    });
}

/**
 * Load content based on active tab
 * @param {string} tabName - Name of the tab to load content for
 */
function loadTabContent(tabName) {
    switch(tabName) {
        case 'unprocessed':
            loadUnprocessedUploads();
            break;
        case 'processing':
            loadProcessingQueue();
            break;
        case 'validation':
            loadValidationQueue();
            break;
        case 'completed':
            loadCompletedDocuments();
            break;
    }
    
    // Update tab counts
    updateTabCounts();
}

/**
 * Load unprocessed uploads from backend
 */
async function loadUnprocessedUploads() {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, '/uploads/unprocessed'));
        if (!response.ok) throw new Error('Failed to load unprocessed uploads');
        
        const uploads = await response.json();
        renderUnprocessedUploads(uploads);
    } catch (error) {
        console.error('Failed to load unprocessed uploads:', error);
        showToast('Failed to load unprocessed uploads', 'error');
    }
}

/**
 * Load processing queue from backend
 */
async function loadProcessingQueue() {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, '/processing-queue'));
        if (!response.ok) throw new Error('Failed to load processing queue');
        
        const queue = await response.json();
        renderProcessingQueue(queue);
    } catch (error) {
        console.error('Failed to load processing queue:', error);
        showToast('Failed to load processing queue', 'error');
    }
}

/**
 * Load validation queue from backend
 */
async function loadValidationQueue() {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, '/validation-queue'));
        if (!response.ok) throw new Error('Failed to load validation queue');
        
        const validationQueue = await response.json();
        renderValidationQueue(validationQueue);
    } catch (error) {
        console.error('Failed to load validation queue:', error);
        showToast('Failed to load validation queue', 'error');
    }
}

/**
 * Load completed documents from backend
 */
async function loadCompletedDocuments() {
    try {
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, '/completed'));
        if (!response.ok) throw new Error('Failed to load completed documents');
        
        const completed = await response.json();
        renderCompletedDocuments(completed);
    } catch (error) {
        console.error('Failed to load completed documents:', error);
        showToast('Failed to load completed documents', 'error');
    }
}

/**
 * Update tab count badges
 */
function updateTabCounts() {
    // This will be implemented when you connect to real backend data
    // For now, placeholder counts
    document.getElementById('unprocessed-count').textContent = '0';
    document.getElementById('processing-count').textContent = '0';
    document.getElementById('validation-count').textContent = '0';
    document.getElementById('completed-count').textContent = '0';
}

// Placeholder render functions - implement these based on your UI needs
function renderUnprocessedUploads(uploads) {
    const container = document.getElementById('file-container');
    if (container) {
        container.innerHTML = uploads.length ? 
            '<p>Unprocessed uploads will be displayed here</p>' : 
            '<p>No unprocessed uploads</p>';
    }
}

function renderProcessingQueue(queue) {
    const container = document.getElementById('processing-list');
    if (container) {
        container.innerHTML = queue.length ? 
            '<p>Processing queue will be displayed here</p>' : 
            '<p>No documents processing</p>';
    }
}

function renderValidationQueue(validationQueue) {
    const container = document.getElementById('validation-list');
    if (container) {
        container.innerHTML = validationQueue.length ? 
            '<p>Validation queue will be displayed here</p>' : 
            '<p>No documents pending validation</p>';
    }
}

function renderCompletedDocuments(completed) {
    const container = document.getElementById('completed-list');
    if (container) {
        container.innerHTML = completed.length ? 
            '<p>Completed documents will be displayed here</p>' : 
            '<p>No completed documents</p>';
    }
}