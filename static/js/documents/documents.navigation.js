// documents.navigation.js
// Handles UI updates, tab switching, view toggles, and DOM rendering for Documents

import { DocumentActions } from './documents.actions.js';
import { showToast } from '../ui.js';

export const DocumentNavigation = {
  currentView: 'grid',

  /**
   * Initialize tab and event bindings
   */
  bindUIEvents() {
    // Tab switching
    document.querySelectorAll('.document-tabs .tab-button').forEach(btn => {
      btn.addEventListener('click', () => {
        this.switchTab(btn.dataset.tab);
      });
    });

    // View toggles
    //document.querySelectorAll('.view-toggle').forEach(btn => {
      //btn.addEventListener('click', () => {
        //this.toggleView(btn.dataset.view);
      //});
    //});

    // Batch actions
    const applyPatientBtn = document.getElementById('apply-batch-patient');
    if (applyPatientBtn) {
      applyPatientBtn.addEventListener('click', async () => {
        const selected = this.getSelectedUploads();
        const patientId = document.getElementById('batch-patient').value;
        if (!selected.length || !patientId) {
          showToast('Select files and a patient first', 'warning');
          return;
        }
        await DocumentActions.batchAssign(selected, patientId);
        await this.refreshUnprocessedList();
      });
    }

    const startOCRBtn = document.getElementById('start-processing');
    if (startOCRBtn) {
      startOCRBtn.addEventListener('click', async () => {
        const selected = this.getSelectedUploads();
        if (!selected.length) {
          showToast('Select files first', 'warning');
          return;
        }
        await DocumentActions.startOCR(selected);
        await this.refreshUnprocessedList();
      });
    }

    // ---- Upload drag & drop ----
    const dropzone = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');

    if (dropzone && fileInput) {
    // Highlight on drag over
    ['dragenter', 'dragover'].forEach(evt =>
        dropzone.addEventListener(evt, e => {
        e.preventDefault();
        dropzone.classList.add('dragging');
        })
    );

    // Remove highlight
    ['dragleave', 'drop'].forEach(evt =>
        dropzone.addEventListener(evt, e => {
        e.preventDefault();
        dropzone.classList.remove('dragging');
        })
    );

    // Handle drop
    dropzone.addEventListener('drop', async e => {
        e.preventDefault();
        const files = e.dataTransfer.files;
        if (!files.length) return;
        
        const patientId = window.app?.documents?.currentUploadPatientId || null;
        await DocumentActions.uploadFiles(files, patientId);
        await this.refreshUnprocessedList();
    });

    // Click-to-upload
    dropzone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async e => {
        const files = e.target.files;
        if (!files.length) return;
        
        const patientId = window.app?.documents?.currentUploadPatientId || null;
        await DocumentActions.uploadFiles(files, patientId);
        await this.refreshUnprocessedList();
    });
    }

    const approveBtn = document.getElementById('validation-approve');
    if (approveBtn) {
      approveBtn.addEventListener('click', () => this.approveValidation());
    }

    const rejectBtn = document.getElementById('validation-reject');
    if (rejectBtn) {
      rejectBtn.addEventListener('click', () => this.rejectValidation());
    }

    setInterval(async () => {
      const activeTab = document.querySelector('.tab-button.active')?.dataset.tab;
      if (activeTab === 'processing') {
        await this.refreshProcessingQueue();
      }
      if (activeTab === 'validation') {
        await this.switchTab('validation');
      }
    }, 4000);


    const closeBtn = document.getElementById('validation-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        document.getElementById('validation-modal').classList.remove('open');
      });
    }

  },

  /**
   * Switch tab by key
   */
  async switchTab(tabKey) {
    // 1. UI: activate buttons + tab content
    document.querySelectorAll('.document-tabs .tab-button').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabKey);
    });

    document.querySelectorAll('.document-tabs .tab-content').forEach(div => {
      div.classList.toggle('active', div.id === `${tabKey}-tab`);
    });

    // 2. DATA LOADING based on tab
    // Update active tab styling
    this.tabs.forEach(t => t.classList.remove('active'));
    this.tabs.find(t => t.dataset.tab === tabKey)?.classList.add('active');
    
    // Load data
    try {
      const uploads = await DocumentActions.fetchTab(tabKey);
      this.renderTab(tabKey, uploads);
    } catch (error) {
      console.error(`Error loading ${tabKey} tab:`, error);
      this.renderError(tabKey, error);
    }
  },

  /**
   * Dispatches uploads to appropriate renderer based on active tab
    * @param {string} tabKey - Tab identifier (unprocessed|processing|validation|completed|error)
    * @param {Array} uploads - Upload objects from backend
   * @returns nothing
   */
  renderTab(tabKey, uploads) {
    const container = this.contentArea.querySelector(`#${tabKey}-tab`);
    if (!container) return;
    
    switch(tabKey) {
      case 'unprocessed':
        this.renderUploads(uploads);
        break;
      case 'processing':
        this.renderProcessing(uploads);
        break;
      case 'validation':
        this.renderValidation(uploads);
        break;
      case 'completed':
        this.renderCompleted(uploads);
        break;
      case 'error':
        this.renderErrors(uploads);
        break;
    }
  },


  /**
   * Toggle view mode (grid / list)
   */
  toggleView(view) {
    this.currentView = view;
    const container = document.getElementById('file-container');
    if (container) {
      container.classList.toggle('grid', view === 'grid');
      container.classList.toggle('list', view === 'list');
    }
    document.querySelectorAll('.view-toggle').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === view);
    });
  },

  /**
   * Get IDs of selected uploads
   */
  getSelectedUploads() {
    const checkboxes = document.querySelectorAll('.file-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.dataset.id);
  },

  /**
   * Refresh Unprocessed list after an update
   */
  async refreshUnprocessedList() {
    console.log('refreshUnprocessedList() triggered');
    try {
        const data = await DocumentActions.fetchTab("unprocessed");
        console.log('Fetched unprocessed data:', data);

        // Accept both a list and an object with documents key
        const docs = Array.isArray(data) ? data : data.documents;

        if (docs && docs.length > 0) {
        console.log('Rendering uploads:', docs);
        this.renderUploads(docs);
        } else {
        console.warn('No unprocessed documents found');
        this.renderUploads([]); // still clears placeholder if needed
        }
    } catch (err) {
        console.error('refreshUnprocessedList error:', err);
    }
  },

  /* 
    Refreshes the processing queue
  */
  async refreshProcessingQueue() {
    const uploads = await DocumentActions.fetchProcessingQueue();
    DocumentNavigation.renderProcessing(uploads);
  },

  /*
      Helpers for the rendering 
   */
  getUploadCategory(doc) {
    const name = (doc.filename || '').toLowerCase();

    if (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg'))
      return 'image';

    if (name.endsWith('.pdf'))
      return 'pdf';

    return 'document';
  },

  getUploadLabel(category) {
    switch (category) {
      case 'image': return 'Image';
      case 'pdf': return 'PDF';
      default: return 'Document';
    }
  },

 getUploadIconClass(category) {
    switch (category) {
      case 'image':        return 'fa-image';
      case 'lab':          return 'fa-flask';
      case 'prescription': return 'fa-file-prescription';
      case 'id-card':      return 'fa-id-card';
      case 'pdf':          return 'fa-file-pdf';
      default:             return 'fa-file-medical';
    }
  },

  formatUploadDate(isoString) {
    if (!isoString) return 'Unknown date';
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return 'Unknown date';

    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    const timeOpts = { hour: '2-digit', minute: '2-digit' };

    if (sameDay) {
      return `Uploaded today, ${d.toLocaleTimeString(undefined, timeOpts)}`;
    }
    return `Uploaded at ${d.toLocaleDateString()} ${d.toLocaleTimeString(undefined, timeOpts)}`;
  },

  /**
   * Fetch processing queue (queued + processing uploads)
   */
  async fetchProcessingQueue() {
    console.log('Fetching processing queue...');
    try {
      const res = await fetch(
        apiUrl(API_CONFIG.ENDPOINTS.documents, 'processing-queue')
      );
      if (!res.ok) throw new Error('Failed to load processing queue');
      return await res.json();
    } catch (err) {
      console.error('fetchProcessingQueue error:', err);
      return [];
    }
  },

  /*
    Helper to standardize status text
  */
 getStatusConfig(context, doc) {
    // context: 'processing' | 'validation' | 'completed'
    const ocr = doc.ocr_status;
    const val = doc.validation_status;

    if (context === 'processing') {
      if (ocr === 'processing') {
        return { text: 'Processing OCR…', variant: 'info', showDots: true };
      }
      // queued or pending
      return { text: 'Queued for OCR', variant: 'muted', showDots: true };
    }

    if (context === 'validation') {
      // later you can branch on confidence, etc.
      return { text: 'Ready for validation', variant: 'warning', showDots: false };
    }

    if (context === 'completed') {
      if (val === 'rejected') {
        return { text: 'Rejected', variant: 'danger', showDots: false };
      }
      // default: approved / validated
      return { text: 'Validated', variant: 'success', showDots: false };
    }

    return { text: null, variant: null, showDots: false };
  },


  /*
   Factory for single card creation
  */
  createDocumentCard(doc, options = {}) {
    const {
      statusConfig = null,   // {text, variant, showDots}
      showCancel = false,
      onCancel = null,
      primaryActionLabel = null,
      onPrimaryAction = null,
    } = options;

    const category  = this.getUploadCategory(doc);
    const iconClass = this.getUploadIconClass(category);
    const label     = this.getUploadLabel(category);
    const dateText  = this.formatUploadDate(doc.uploaded_at);

    const card = document.createElement('div');
    card.classList.add('upload-card');
    card.dataset.id = doc.id;

    card.innerHTML = `
      <div class="upload-card-label">
        <div class="upload-card-main">
          <div class="upload-card-icon ${category}">
            <i class="fas ${iconClass}"></i>
          </div>
          <div class="upload-card-meta">
            <div class="upload-card-title">${label}</div>
            <div class="upload-card-date">${dateText}</div>
            ${
              statusConfig && statusConfig.text
                ? `<div class="upload-card-status status-${statusConfig.variant || 'muted'}">
                    <span class="status-text">${statusConfig.text}</span>
                    ${
                      statusConfig.showDots
                        ? '<span class="processing-dots">•••</span>'
                        : ''
                    }
                  </div>`
                : ''
            }
          </div>
        </div>
        <div class="upload-card-actions">
          ${
            primaryActionLabel
              ? `<button class="primary-btn" data-role="primary">${primaryActionLabel}</button>`
              : ''
          }
          ${
            showCancel
              ? `<button class="cancel-btn" data-role="cancel">Cancel</button>`
              : ''
          }
        </div>
      </div>
    `;

    // Actions
    const primaryBtn = card.querySelector('button[data-role="primary"]');
    if (primaryBtn && typeof onPrimaryAction === 'function') {
      primaryBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        onPrimaryAction(doc, primaryBtn);
      });
    }

    const cancelBtn = card.querySelector('button[data-role="cancel"]');
    if (cancelBtn && typeof onCancel === 'function') {
      cancelBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        onCancel(doc, cancelBtn);
      });
    }

    return card;
  },


  /*
    Renders processing queue
  */
  renderProcessing(queue) {
    console.log('Render processing queue...');
    const container = document.getElementById('processing-list');
    const totalEl = document.getElementById('processing-total');
    const countBadge = document.getElementById('processing-count');
    
    const self = this;

    if (!container) {
      console.log('Processing container not found');
      return;
    }

    container.innerHTML = '';

    if (!queue || !queue.length) {
      if (totalEl) totalEl.textContent = '0';
      if (countBadge) countBadge.textContent = '0';
      container.innerHTML = `
        <div class="empty-message">
          No documents are currently being processed.
        </div>`;
      return;
    }

    if (totalEl) totalEl.textContent = queue.length;
    if (countBadge) countBadge.textContent = queue.length;

    queue.forEach(doc => {
      const statusConfig = this.getStatusConfig('processing', doc);
      const card = this.createDocumentCard(doc, {
        statusConfig,
        showCancel: true,
        onCancel: async (d) => {
          const res = await fetch(
            apiUrl(API_CONFIG.ENDPOINTS.documents, `processing/${d.id}`),
            { method: 'DELETE' }
          );
          if (res.ok) {
            showToast('Processing canceled', 'success');
            self.refreshProcessingQueue();
          } else {
            showToast('Could not cancel this', 'error');
          }
        },
      });

      container.appendChild(card);
    });
  },

  /*
    Render validation
  */
  renderValidation(docs) {
    const container = document.getElementById('validation-list');
    container.innerHTML = '';

    if (!docs.length) {
      container.innerHTML = '<div class="empty-message">No documents to validate.</div>';
      return;
    }

    docs.forEach(doc => {
      const statusConfig = this.getStatusConfig('validation', doc);

      const card = this.createDocumentCard(doc, {
        statusConfig,
        primaryActionLabel: 'Review',
        onPrimaryAction: (d) => this.openValidationForm(d),
      });

      container.appendChild(card);
    });
  },

  renderCompleted(docs) {
    const container = document.getElementById('validation-list');
    container.innerHTML = '';

    if (!docs.length) {
      container.innerHTML = '<div class="empty-message">No documents to validate.</div>';
      return;
    }

    docs.forEach(doc => {
      const statusConfig = this.getStatusConfig('completed', doc);

      const card = this.createDocumentCard(doc, {
        statusConfig,
        primaryActionLabel: 'Review',
        onPrimaryAction: (d) => this.openValidationForm(d),
      });

      container.appendChild(card);
    });
  },


  /**
   * Render uploaded documents in the Unprocessed tab
   */
  renderUploads(documents) {
    console.log('Render unprocessed uploads...');
    const container = document.getElementById('file-container');
    const empty = document.getElementById('empty-state');

    if (!container) {
      console.error('File container not found in Unprocessed tab');
      return;
    }

    container.innerHTML = '';

    if (!documents.length) {
      if (empty) empty.style.display = 'block';
      return;
    }

    if (empty) empty.style.display = 'none';

    documents.forEach(doc => {
      const card = this.createDocumentCard(doc); // no status, no cancel
      container.appendChild(card);
    });
  },

  /**
   * Open validation form (modal or panel)
   */
  async openValidationForm(upload) {
    try {
      const res = await fetch(
        apiUrl(API_CONFIG.ENDPOINTS.documents, `validation/${upload.id}`)
      );
      if (!res.ok) throw new Error('Failed to load validation details');

      const data = await res.json();

      // SHOW MODAL (you already have a modal component; if not, we add it next)
      const modal = document.getElementById('validation-modal');
      const textEl = document.getElementById('ocr-text');
      const jsonEl = document.getElementById('ocr-json');

      if (textEl) textEl.value = data.ocr_text || '';
      if (jsonEl) jsonEl.value = JSON.stringify(data.extracted_data || {}, null, 2);

      modal.dataset.uploadId = upload.id;
      modal.classList.add('open');
    } catch (err) {
      console.error('openValidationForm error:', err);
      showToast('Error loading validation data', 'error');
    }
  },

  async approveValidation() {
    const modal = document.getElementById('validation-modal');
    const uploadId = modal.dataset.uploadId;

    const corrected = JSON.parse(document.getElementById('ocr-json').value || '{}');

    const res = await fetch(
      apiUrl(API_CONFIG.ENDPOINTS.documents, `validation/${uploadId}/approve`),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ corrected_fields: corrected })
      }
    );

    if (res.ok) {
      showToast('Document approved', 'success');
      modal.classList.remove('open');
      await this.refreshValidationQueue?.();
    } else {
      showToast('Approval failed', 'error');
    }
  },

  async rejectValidation() {
    const modal = document.getElementById('validation-modal');
    const uploadId = modal.dataset.uploadId;

    const res = await fetch(
      apiUrl(API_CONFIG.ENDPOINTS.documents, `validation/${uploadId}/reject`),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Invalid OCR' })
      }
    );

    if (res.ok) {
      showToast('Document rejected', 'warning');
      modal.classList.remove('open');
      await this.refreshValidationQueue?.();
    } else {
      showToast('Rejection failed', 'error');
    }
  },
}