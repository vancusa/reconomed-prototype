// documents.navigation.js
// Handles UI updates, tab switching, view toggles, and DOM rendering for Documents

import { DocumentActions } from './documents.actions.js';
import { showToast } from '../ui.js';

export const DocumentNavigation = {
  currentView: 'grid',
  activeTab: 'unprocessed',
  tabs: [],
  tabCounts: {},
  contentArea: null,
  validationModal: null,
  validationInitialOcrText: '',
  patientSearchTimeout: null,

  /**
   * Initialize tab and event bindings
   */
  async init() {
    this.tabs = Array.from(document.querySelectorAll('.document-tabs .tab-button'));
    this.contentArea = document.querySelector('.document-tabs__content');
    this.tabCounts = {
      unprocessed: document.getElementById('unprocessed-count'),
      processing: document.getElementById('processing-count'),
      validation: document.getElementById('validation-count'),
      completed: document.getElementById('completed-count'),
      error: document.getElementById('error-count'),
    };
    // Modal elements
    this.validationModal = document.getElementById('validation-modal');
    this.validationOcrField = document.getElementById('validation-ocr-text');
    this.validationPreviewLink = document.getElementById('validation-preview-link');
    this.validationPatientSelect = document.getElementById('validation-patient-select');
    this.validationPatientSearch = document.getElementById('validation-patient-search');
    this.validationDocumentTypeSelect = document.getElementById('validation-document-type');
    this.validationFileName = document.getElementById('validation-filename');
    this.validationCompleteBtn = document.getElementById('validation-complete');
    this.validationRejectBtn = document.getElementById('validation-reject');

    this.bindUIEvents();
    await this.switchTab('unprocessed');
  },

  /**
   * Initialize tab and modal listeners
   */

  bindUIEvents() {
    // Tab switching
    this.tabs.forEach(btn => {
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
      if (typeof DocumentActions.batchAssign === 'function') {
          await DocumentActions.batchAssign(selected, patientId);
          await this.refreshUnprocessedList();
        }
        else {
          showToast('Batch assign not available', 'warning');
        }
      });
    }

    const startOCRBtn = document.getElementById('start-processing');
    if (startOCRBtn) {
      startOCRBtn.addEventListener('click', async () => {
        showToast('Uploads are processed automatically after upload.', 'info');
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
        
        const patientId = window.app?.documentManager?.currentUploadPatientId || null;
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

    if (this.validationCompleteBtn) {
      this.validationCompleteBtn.addEventListener('click', () => this.handleCompleteAction());
    }

    if (this.validationRejectBtn) {
      this.validationRejectBtn.addEventListener('click', () => this.confirmReject());
    }

    if (this.validationPatientSelect) {
      this.validationPatientSelect.addEventListener('change', () => this.updateCompleteButtonState());
    }

    if (this.validationPatientSearch) {
      this.validationPatientSearch.addEventListener('input', (e) => this.handlePatientSearch(e.target.value));
    }

    const closeBtn = document.getElementById('validation-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.closeValidationModal());
    }

    setInterval(async () => {
      if (this.activeTab === 'processing') {
        await this.switchTab('processing');
      }
      if (this.activeTab === 'validation') {
        await this.switchTab('validation');
      }
    }, 4000);
  },

  /**
   * Switch tab by key
   */
  async switchTab(tabKey) {
    // 1. UI: activate buttons + tab content
    this.tabs.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabKey);
    });

    document.querySelectorAll('.document-tabs .tab-content').forEach(div => {
      div.classList.toggle('active', div.id === `${tabKey}-tab`);
    });

    // 2. DATA LOADING based on tab
    // Update active tab styling
    this.activeTab = tabKey;
    
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
    
    this.updateTabCount(tabKey, uploads?.length || 0);

    switch(tabKey) {
      case 'unprocessed':
        this.renderUploads(uploads|| []);
        break;
      case 'processing':
        this.renderProcessing(uploads|| []);
        break;
      case 'validation':
        this.renderValidation(uploads)|| [];
        break;
      case 'completed':
        this.renderCompleted(uploads|| []);
        break;
      case 'error':
        this.renderErrors(uploads|| []);
        break;
    }
  },

  renderError(tabKey, error) {
    const container = this.contentArea?.querySelector(`#${tabKey}-tab`);
    if (!container) return;
    container.innerHTML = `<div class="error-message">Could not load ${tabKey} uploads. ${error?.message || ''}</div>`;
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

  updateTabCount(tabKey, count) {
    if (this.tabCounts[tabKey]) {
      this.tabCounts[tabKey].textContent = count;
    }

    if (tabKey === 'validation') {
      const pending = document.getElementById('validation-pending');
      if (pending) pending.textContent = count;
    }

    if (tabKey === 'completed') {
      const completed = document.getElementById('completed-total');
      if (completed) completed.textContent = count;
    }

    if (tabKey === 'error') {
      const error = document.getElementById('error-total');
      if (error) error.textContent = count;
    }
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
        const docs = await DocumentActions.fetchTab("unprocessed");
        console.log('Fetched unprocessed data:', docs);
        this.renderUploads(docs || []);
    } catch (err) {
        console.error('refreshUnprocessedList error:', err);
    }
  },

  /* 
    Refreshes the processing queue
  */
  async refreshProcessingQueue() {
    const uploads = await DocumentActions.fetchTab('processing');
    this.updateTabCount('processing', uploads?.length || 0);
    this.renderProcessing(uploads || []);
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

  /*
    Helper to standardize status text
  */
 getStatusConfig(context, doc) {
    // context: 'processing' | 'validation' | 'completed'
    const state = doc.job_state;

    if (context === 'processing') {
      if (state === 'processing') {
        return { text: 'Processing OCR…', variant: 'info', showDots: true };
      }
      return { text: 'Queued for OCR', variant: 'muted', showDots: true };
    }

    if (context === 'validation') {
      return { text: 'Ready for validation', variant: 'warning', showDots: false };
    }

    if (context === 'completed') {
      return { text: 'Completed', variant: 'success', showDots: false };
    }

    if (context === 'error') {
      return { text: 'OCR failed', variant: 'danger', showDots: false };
    }

    return { text: null, variant: null, showDots: false };
  },


  /*
   Factory for single card creation
  */
  createDocumentCard(doc, options = {}) {
    const {
      statusConfig = null,   // {text, variant, showDots}
      primaryActionLabel = null,
      onPrimaryAction = null,
      secondaryActionLabel = null,
      onSecondaryAction = null,
      onCardClick = null,
    } = options;

    const category  = this.getUploadCategory(doc);
    const iconClass = this.getUploadIconClass(category);
    const label     = doc.document_type || this.getUploadLabel(category);
    const dateText  = this.formatUploadDate(doc.uploaded_at);
    const patientText = doc.patient_id ? `Patient assigned` : 'Patient not assigned';

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
            <div class="upload-card-patient">${patientText}</div>
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
            ${
              doc.ocr_snippet
                ? `<div class="upload-card-snippet">${doc.ocr_snippet}</div>`
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
            secondaryActionLabel
              ? `<button class="cancel-btn" data-role="secondary">${secondaryActionLabel}</button>`
              : ''
          }
        </div>
      </div>
    `;

    if (typeof onCardClick === 'function') {
      card.addEventListener('click', () => onCardClick(doc));
    }

    // Actions
    const primaryBtn = card.querySelector('button[data-role="primary"]');
    if (primaryBtn && typeof onPrimaryAction === 'function') {
      primaryBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        onPrimaryAction(doc, primaryBtn);
      });
    }

    const secondaryBtn = card.querySelector('button[data-role="secondary"]');
    if (secondaryBtn && typeof onSecondaryAction === 'function') {
      secondaryBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        onSecondaryAction(doc, secondaryBtn);
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
        onCardClick: () => window.open(doc.preview_url || '#', '_blank')
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
        secondaryActionLabel: 'Reject',
        onSecondaryAction: (d) => this.confirmReject(d),
        onCardClick: (d) => this.openValidationForm(d),
      });

      container.appendChild(card);
    });
  },

  renderCompleted(docs) {
    const container = document.getElementById('completed-list');
    container.innerHTML = '';

    if (!docs.length) {
      container.innerHTML = '<div class="empty-message">No completed documents.</div>';
      return;
    }

    docs.forEach(doc => {
      const statusConfig = this.getStatusConfig('completed', doc);

      const card = this.createDocumentCard(doc, {
        statusConfig,
        primaryActionLabel: 'Preview',
        onPrimaryAction: (d) => window.open(d.preview_url || '#', '_blank'),
        onCardClick: (d) => window.open(d.preview_url || '#', '_blank'),
      });

      container.appendChild(card);
    });
  },

  renderErrors(docs) {
    const container = document.getElementById('error-list');
    container.innerHTML = '';

    if (!docs.length) {
      container.innerHTML = '<div class="empty-message">No OCR errors.</div>';
      return;
    }

    docs.forEach(doc => {
      const statusConfig = this.getStatusConfig('error', doc);
      const card = this.createDocumentCard(doc, {
        statusConfig,
        primaryActionLabel: 'Preview',
        onPrimaryAction: (d) => window.open(d.preview_url || '#', '_blank'),
        secondaryActionLabel: 'Delete',
        onSecondaryAction: (d) => this.confirmReject(d),
        onCardClick: (d) => window.open(d.preview_url || '#', '_blank'),
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
    this.updateTabCount('unprocessed', documents.length);

    if (!documents.length) {
      if (empty) empty.style.display = 'block';
      return;
    }

    if (empty) empty.style.display = 'none';

    documents.forEach(doc => {
      const card = this.createDocumentCard(doc,{
        onCardClick: () => {
          if (doc.preview_url) {
            window.open(doc.preview_url, '_blank');
          }
        }
      });
      container.appendChild(card);
    });
  },

  /**
   * Open validation form (modal or panel)
   */
  async openValidationForm(upload) {
    try {
      const { metadata, ocr, previewUrl } = await DocumentActions.fetchUploadDetails(upload.id);
      if (!metadata) throw new Error('No details available');
      if (metadata.job_state && metadata.job_state !== 'ocr_done') {
        showToast('OCR not finished yet. Check the Processing tab.', 'warning');
        await this.switchTab('processing');
        return;
      }

      this.validationInitialOcrText = ocr?.ocr_text || '';

      if (this.validationModal) {
        this.validationModal.dataset.uploadId = upload.id;
        this.validationModal.style.display = 'flex';
        this.validationModal.classList.add('open');
      }

      if (this.validationOcrField) {
        this.validationOcrField.value = this.validationInitialOcrText;
      }
      
      if (this.validationPreviewLink) {
        this.validationPreviewLink.href = metadata.preview_url || previewUrl || '#';
      }

      if (this.validationFileName) {
        this.validationFileName.textContent = metadata.filename || '';
      }

      if (this.validationDocumentTypeSelect) {
        this.validationDocumentTypeSelect.value = metadata.document_type || '';
      }

      if (this.validationPatientSearch) {
        this.validationPatientSearch.value = '';
      }

      await this.populatePatientSelect(metadata.patient_id);
      this.updateCompleteButtonState();
    } catch (err) {
      console.error('openValidationForm error:', err);
      showToast('Error loading validation data', 'error');
    }
  },

  async populatePatientSelect(selectedId = null) {
    if (!this.validationPatientSelect) return;

    const patientManager = window.app?.patientManager;
    let patients = patientManager?.patients || [];

    if ((!patients || !patients.length) && patientManager?.fetchPatientsRaw) {
      const raw = await patientManager.fetchPatientsRaw();
      patients = raw?.patients || [];
    }

    const preselected = selectedId || window.app?.documentManager?.currentUploadPatientId || '';

    this.validationPatientSelect.innerHTML = '<option value=\"\">Select patient...</option>';
    patients.forEach(p => {
      const fullName = [p.family_name, p.given_name].filter(Boolean).join(' ').trim() || 'Unnamed';
      const option = document.createElement('option');
      option.value = p.id;
      option.textContent = fullName;
      if (preselected && p.id === preselected) {
        option.selected = true;
      }
      this.validationPatientSelect.appendChild(option);
    });
    
    
     const hasPreselected = preselected && patients.some(p => p.id === preselected);
    if (preselected && !hasPreselected && patientManager?.getPatientById) {
      const patient = await patientManager.getPatientById(preselected);
      if (patient) {
        const option = document.createElement('option');
        option.value = patient.id;
        option.textContent = [patient.family_name, patient.given_name].filter(Boolean).join(' ').trim() || 'Selected patient';
        option.selected = true;
        this.validationPatientSelect.appendChild(option);
      }
    }
  },

  handlePatientSearch(value) {
    if (!window.app?.patientManager?.searchPatients) return;
    clearTimeout(this.patientSearchTimeout);
    this.patientSearchTimeout = setTimeout(async () => {
      const results = await window.app.patientManager.searchPatients(value || '');
      this.validationPatientSelect.innerHTML = '<option value=\"\">Select patient...</option>';
      results.forEach(p => {
        const fullName = [p.family_name, p.given_name].filter(Boolean).join(' ').trim() || 'Unnamed';
        const option = document.createElement('option');
        option.value = p.id;
        option.textContent = fullName;
        this.validationPatientSelect.appendChild(option);
      });
      this.updateCompleteButtonState();
    }, 200);
  },

  updateCompleteButtonState() {
    if (this.validationCompleteBtn && this.validationPatientSelect) {
      this.validationCompleteBtn.disabled = !this.validationPatientSelect.value;
    }
  },

  closeValidationModal() {
    if (this.validationModal) {
      this.validationModal.classList.remove('open');
      this.validationModal.style.display = 'none';
      this.validationModal.dataset.uploadId = '';
    }
    this.validationInitialOcrText = '';
    if (this.validationOcrField) this.validationOcrField.value = '';
    if (this.validationPatientSelect) this.validationPatientSelect.value = '';
    if (this.validationPatientSearch) this.validationPatientSearch.value = '';
    this.updateCompleteButtonState();
  },

 async handleCompleteAction() {
    if (!this.validationModal) return;
    const uploadId = this.validationModal.dataset.uploadId;
    const patientId = this.validationPatientSelect?.value;
    const editedText = this.validationOcrField?.value || '';
    const documentType = this.validationDocumentTypeSelect?.value || null;

    if (!patientId) {
      showToast('Select a patient first', 'warning');
      return;
    }

    try {
      if (this.validationCompleteBtn) {
        this.validationCompleteBtn.disabled = true;
        this.validationCompleteBtn.textContent = 'Completing...';
      }
      const editedOcrText = editedText !== this.validationInitialOcrText ? editedText : null;
      await DocumentActions.completeUpload(uploadId, patientId, editedOcrText, documentType);
      showToast('Completed', 'success');
      this.closeValidationModal();
      await this.switchTab('validation');
      await this.switchTab('completed');
    } catch (err) {
      console.error('Complete error', err);
      if (err.status === 409) {
        showToast('OCR not finished. Please retry later.', 'warning');
      } else if (err.status === 404) {
        showToast('Patient not found. Refresh patient list.', 'error');
        await this.populatePatientSelect();
      } else if (err.status === 403) {
        showToast('Not allowed for this clinic.', 'error');
      } else {
        showToast(err.message || 'Could not complete upload', 'error');
      }
    } finally {
      if (this.validationCompleteBtn) {
        this.validationCompleteBtn.disabled = false;
        this.validationCompleteBtn.textContent = 'Assign patient & complete';
      }
    }
  },

  async confirmReject(upload) {
    const id = upload?.id || this.validationModal?.dataset?.uploadId;
    if (!id) return;
    const confirmed = window.confirm('Reject & delete this upload permanently?');
    if (!confirmed) return;

    try {
      if (this.validationRejectBtn) {
        this.validationRejectBtn.disabled = true;
      }
      await DocumentActions.rejectUpload(id);
      showToast('Deleted', 'success');
      this.closeValidationModal();
      if (this.activeTab) {
        await this.switchTab(this.activeTab);
      } else {
        await this.switchTab('validation');
      }
    } catch (err) {
      console.error('Reject failed', err);
      if (err.status === 404) {
        showToast('Already deleted. Refreshing list.', 'warning');
        await this.switchTab(this.activeTab || 'validation');
      } else {
        showToast('Could not delete, try again', 'error');
      }
    } finally {
      if (this.validationRejectBtn) {
        this.validationRejectBtn.disabled = false;
      }
    }
  },
}