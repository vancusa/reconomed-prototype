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
  validationSelectedPatientId: null,
  patientSearchResults: [],
  patientSearchActiveIndex: -1,

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
    this.uploadsToolbar = document.getElementById('uploads-toolbar');
    this.selectAllLabel = document.getElementById('select-all-label');
    this.selectAllCheckbox = document.getElementById('select-all');
    this.totalUploads = document.getElementById('total-uploads');
    this.uploadArea = document.getElementById('upload-area');
    this.uploadCountBadge = document.getElementById('upload-count');
    this.processingTitle = document.getElementById('processing-title');
    this.processingBody = document.getElementById('processing-body');
    // Modal elements
    this.validationModal = document.getElementById('validation-modal');
    this.validationOcrField = document.getElementById('validation-ocr-text');
    this.validationPreviewLink = document.getElementById('validation-preview-link');
    this.validationSnippet = document.getElementById('validation-ocr-snippet');
    this.validationExpandBtn = document.getElementById('validation-expand-ocr');
    this.validationExpandedPanel = document.getElementById('validation-expanded');
    this.validationPatientSearch = document.getElementById('validation-patient-search');
    this.validationPatientResults = document.getElementById('validation-patient-results');
    this.validationDocumentTypeSelect = document.getElementById('validation-document-type');
    this.validationFileName = document.getElementById('validation-filename');
    this.validationCompleteBtn = document.getElementById('validation-complete');
    this.validationRejectBtn = document.getElementById('validation-reject');
    this.validationToggleFullscreen = document.getElementById('validation-toggle-fullscreen');
    this.tabCountCache = { unprocessed: 0, processing: 0, validation: 0 };
    this.maxUploads = window.clinicManager?.clinicData?.max_uploads || 20;

    if (!this.contentArea) {
      console.warn('Document tabs content area not found. Skipping document navigation init.');
      return;
    }

    this.bindUIEvents();
    this.updateUploadQuotaBadge();
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
     document.querySelectorAll('.view-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        this.toggleView(btn.dataset.view);
      });
    });
    this.toggleView(this.currentView);

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
        
        const patientId = window.app?.documentManager?.currentUploadPatientId || null;
        await DocumentActions.uploadFiles(files, patientId);
        await this.refreshUnprocessedList();
    });
    }

    if (this.validationExpandBtn) {
      this.validationExpandBtn.addEventListener('click', () => this.setValidationExpanded(true));
    }

    if (this.validationCompleteBtn) {
      this.validationCompleteBtn.addEventListener('click', () => this.handleCompleteAction());
    }

    if (this.validationRejectBtn) {
      this.validationRejectBtn.addEventListener('click', () => this.confirmReject());
    }

    if (this.validationPatientSearch) {
      this.validationPatientSearch.addEventListener('input', (e) => this.handlePatientSearch(e.target.value));
      this.validationPatientSearch.addEventListener('keydown', (e) => this.handlePatientSearchKeydown(e));
    }

    const closeBtn = document.getElementById('validation-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.closeValidationModal());
    }

    if (this.validationToggleFullscreen) {
      this.validationToggleFullscreen.addEventListener('click', () => this.toggleValidationFullscreen());
    }

    if (this.validationPreviewLink) {
      this.validationPreviewLink.addEventListener('click', async (event) => {
        event.preventDefault();
        await DocumentActions.openPreview(this.validationPreviewLink.href);
      });
    }

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && this.validationModal?.classList.contains('open')) {
        this.closeValidationModal();
      }
    });

    document.addEventListener('click', (event) => {
      if (!this.validationPatientResults || !this.validationPatientSearch) return;
      const clickedInsideResults = this.validationPatientResults.contains(event.target);
      const clickedInsideInput = this.validationPatientSearch.contains(event.target);
      if (!clickedInsideResults && !clickedInsideInput) {
        this.clearPatientResults();
      }
    });

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
    if (this.uploadArea) {
      this.uploadArea.classList.toggle('is-hidden', tabKey !== 'unprocessed');
    }
    
    // Load data
    try {
      const uploads = await DocumentActions.fetchTab(tabKey);
      await this.renderTab(tabKey, uploads);
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
  async renderTab(tabKey, uploads) {
    let container = null;
    if (this.contentArea) {
      container = this.contentArea.querySelector(`#${tabKey}-tab`);
    }
    if (!container) {
      container = document.getElementById(`${tabKey}-tab`);
    }
    if (!container) return;
    
    this.updateTabCount(tabKey, uploads?.length || 0);

    switch(tabKey) {
      case 'unprocessed':
        this.renderUploads(uploads|| []);
        break;
      case 'processing':
        await this.renderProcessing(uploads|| []);
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

    if (this.tabCountCache && Object.prototype.hasOwnProperty.call(this.tabCountCache, tabKey)) {
      this.tabCountCache[tabKey] = count;
      this.updateUploadQuotaBadge();
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

  updateUploadQuotaBadge() {
    if (!this.uploadCountBadge) return;
    const maxUploads = window.clinicManager?.clinicData?.max_uploads || this.maxUploads || 20;
    const total = Object.values(this.tabCountCache || {}).reduce((sum, value) => sum + (value || 0), 0);
    this.uploadCountBadge.textContent = `${total}/${maxUploads} uploads used`;
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
    await this.renderProcessing(uploads || []);
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

  formatValidatedDate(isoString) {
    if (!isoString) return null;
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return null;
    return `Completed ${d.toLocaleDateString()} ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`;
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
      actions = [],
      showCompletedMeta = false,
      onCardClick = null,
    } = options;

    const category  = this.getUploadCategory(doc);
    const iconClass = this.getUploadIconClass(category);
    const label     = doc.document_type || this.getUploadLabel(category);
    const dateText  = this.formatUploadDate(doc.uploaded_at);
    const patientText = doc.patient_name
      ? `Patient: ${doc.patient_name}`
      : doc.patient_id
        ? 'Patient assigned'
        : 'Patient not assigned';
    const completedAt = this.formatValidatedDate(doc.validated_at);
    const showDocType = showCompletedMeta && doc.document_type;

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
              showDocType
                ? `<div class="upload-card-document-type">Document type: ${doc.document_type}</div>`
                : ''
            }
            ${
              showCompletedMeta && completedAt
                ? `<div class="upload-card-completed-at">${completedAt}</div>`
                : ''
            }
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
           actions
              .map((action, index) => {
                const variantClass = action.variant === 'danger'
                  ? 'btn-danger'
                  : action.variant === 'secondary'
                    ? 'btn-secondary'
                    : 'btn-primary';
                const mutedClass = action.muted ? 'action-muted' : '';
                const disabledAttr = action.disabled ? 'disabled' : '';
                const iconMarkup = action.icon ? `<i class="fas ${action.icon}"></i>` : '';
                return `<button class="btn-small ${variantClass} ${mutedClass}" data-action-index="${index}" ${disabledAttr}>${iconMarkup}${action.label}</button>`;
              })
              .join('')
          }
        </div>
      </div>
    `;

    if (typeof onCardClick === 'function') {
      card.addEventListener('click', () => onCardClick(doc));
    }

    // Actions
    card.querySelectorAll('button[data-action-index]').forEach(btn => {
      const action = actions[Number(btn.dataset.actionIndex)];
      if (!action || typeof action.onClick !== 'function') return;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        action.onClick(doc, btn);
      });
    });

    return card;
  },

  /*
    Renders processing queue
  */
  async renderProcessing(queue) {
    console.log('Render processing queue...');
    const container = document.getElementById('processing-list');
    const countBadge = document.getElementById('processing-count');

    if (!container) {
      console.log('Processing container not found');
      return;
    }

    container.innerHTML = '';
    const processingCount = queue?.length || 0;
    let queuedCount = 0;
    if (processingCount === 0) {
      try {
        const queuedUploads = await DocumentActions.fetchTab('unprocessed');
        queuedCount = queuedUploads?.length || 0;
      } catch (error) {
        console.warn('Could not load queued count', error);
      }
    }
    if (countBadge) countBadge.textContent = processingCount;

    if (this.processingTitle && this.processingBody) {
      if (processingCount > 0) {
        this.processingTitle.textContent = 'Processing';
        this.processingBody.textContent = `Processing ${processingCount} documents automatically.`;
      } else if (queuedCount > 0) {
        this.processingTitle.textContent = 'Queue';
        this.processingBody.textContent = `No documents are processing right now. ${queuedCount} are queued and will run automatically.`;
      } else {
        this.processingTitle.textContent = 'Nothing to process';
        this.processingBody.textContent = 'There are no queued documents.';
      }
    }

    if (!processingCount) {
      return;
    }

    queue.forEach(doc => {
      const statusConfig = this.getStatusConfig('processing', doc);
      const card = this.createDocumentCard(doc, { statusConfig });

      container.appendChild(card);
    });
  },

  /*
    Render validation
  */
  renderValidation(docs) {
    const container = document.getElementById('validation-list');
    if (!container) return;
    container.innerHTML = '';

    if (!docs.length) {
      container.innerHTML = '<div class="empty-message">No documents to validate.</div>';
      return;
    }

    docs.forEach(doc => {
      const statusConfig = this.getStatusConfig('validation', doc);

      const actions = [
        {
          label: 'Assign & complete',
          icon: 'fa-check',
          variant: 'primary',
          disabled: doc.job_state !== 'ocr_done',
          onClick: (d) => this.openValidationForm(d, { confirmFirst: true }),
        },
        {
          label: 'Review / Edit',
          icon: 'fa-pen',
          variant: 'secondary',
          muted: true,
          onClick: (d) => this.openValidationForm(d, { confirmFirst: false, reviewMode: true }),
        },
        {
          label: 'Reject',
          icon: 'fa-trash',
          variant: 'danger',
          onClick: (d) => this.confirmReject(d),
        },
      ];


      const card = this.createDocumentCard(doc, {
        statusConfig,
        actions,
        onCardClick: (d) => this.openValidationForm(d, { confirmFirst: false, reviewMode: true }),
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
        showCompletedMeta: true,
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
      const actions = [
        {
          label: 'Delete',
          icon: 'fa-trash',
          variant: 'danger',
          onClick: (d) => this.confirmReject(d),
        },
      ];
      const card = this.createDocumentCard(doc, {
        statusConfig,
        actions,
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
    const count = documents.length;

    if (!container) {
      console.error('File container not found in Unprocessed tab');
      return;
    }

    container.innerHTML = '';
    this.updateTabCount('unprocessed', count);
    if (this.totalUploads) {
      this.totalUploads.textContent = count;
    }
    if (this.uploadsToolbar) {
      this.uploadsToolbar.classList.toggle('is-hidden', count === 0);
    }
    if (this.selectAllLabel) {
      this.selectAllLabel.style.display = count > 0 ? 'inline-flex' : 'none';
    }
    if (this.selectAllCheckbox) {
      this.selectAllCheckbox.checked = false;
      this.selectAllCheckbox.disabled = count === 0;
    }

    if (!documents.length) {
      if (empty) empty.style.display = 'block';
      return;
    }

    if (empty) empty.style.display = 'none';

    documents.forEach(doc => {
      const card = this.createDocumentCard(doc);
      container.appendChild(card);
    });
  },

  /**
   * Open validation form (modal or panel)
   */
  async openValidationForm(upload, options = {}) {
    try {
      const { metadata, ocr, previewUrl } = await DocumentActions.fetchUploadDetails(upload.id);
      if (!metadata) throw new Error('No details available');
      if (metadata.job_state && metadata.job_state !== 'ocr_done') {
        showToast('OCR not finished yet. Check the Processing tab.', 'warning');
        await this.switchTab('processing');
        return;
      }

      const confirmFirst = options.confirmFirst === true;
      const reviewMode = options.reviewMode === true;
      this.validationInitialOcrText = ocr?.ocr_text || '';
      this.setValidationExpanded(!confirmFirst);
      this.setValidationMode({ reviewMode });

      if (this.validationModal) {
        this.validationModal.dataset.uploadId = upload.id;
        this.validationModal.style.display = 'flex';
        this.validationModal.classList.add('open');
        this.validationModal.classList.remove('validation-modal--fullscreen');
        document.body.classList.add('modal-open');
      }

      if (this.validationOcrField) {
        this.validationOcrField.value = this.validationInitialOcrText;
      }
      
      if (this.validationSnippet) {
        this.validationSnippet.textContent = upload?.ocr_snippet || 'No OCR snippet available yet.';
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
        this.validationPatientSearch.dataset.patientId = '';
      }

       if (this.validationToggleFullscreen) {
        this.validationToggleFullscreen.innerHTML = '<i class="fas fa-expand"></i> Expand OCR';
      }

      this.clearSelectedPatient();
      const preselectedPatientId = metadata.patient_id || window.app?.documentManager?.currentUploadPatientId || null;
      if (preselectedPatientId) {
        await this.setSelectedPatientById(preselectedPatientId);
      }
      this.updateCompleteButtonState();
    } catch (err) {
      console.error('openValidationForm error:', err);
      showToast('Error loading validation data', 'error');
    }
  },

 setValidationMode({ reviewMode = false } = {}) {
    if (!this.validationModal) return;
    this.validationModal.classList.toggle('validation-modal--review', reviewMode);
  },

   async setSelectedPatientById(patientId) {
    if (!patientId) return;
    const patientManager = window.app?.patientManager;
    let patient = null;
    if (patientManager?.getPatientById) {
      patient = await patientManager.getPatientById(patientId);
    }
    if (!patient && patientManager?.patients) {
      patient = patientManager.patients.find(p => p.id === patientId) || null;
    }
    if (patient) {
      this.setSelectedPatient(patient);
    }
  },

   buildPatientLabel(patient) {
    return [patient?.given_name, patient?.family_name].filter(Boolean).join(' ').trim() || 'Unnamed';
  },

  buildPatientMeta(patient) {
    return patient?.phone || patient?.cnp || patient?.birth_date || 'No secondary identifier';
  },

  setSelectedPatient(patient) {
    if (!patient || !this.validationPatientSearch) return;
    const label = this.buildPatientLabel(patient);
    this.validationSelectedPatientId = patient.id;
    this.validationPatientSearch.value = label;
    this.validationPatientSearch.dataset.patientId = patient.id;
    this.clearPatientResults();
    this.updateCompleteButtonState();
  },

  clearSelectedPatient() {
    this.validationSelectedPatientId = null;
    if (this.validationPatientSearch) {
      this.validationPatientSearch.dataset.patientId = '';
    }
    this.updateCompleteButtonState();
  },

  renderPatientResults(results = []) {
    if (!this.validationPatientResults) return;
    this.validationPatientResults.innerHTML = '';
    if (!results.length) {
      this.validationPatientResults.classList.remove('is-open');
      return;
    }
    results.forEach((patient, index) => {
      const item = document.createElement('div');
      item.className = 'patient-search-result';
      if (index === this.patientSearchActiveIndex) {
        item.classList.add('active');
      }
      item.dataset.index = index;
      item.innerHTML = `
        <span class="patient-name">${this.buildPatientLabel(patient)}</span>
        <span class="patient-meta">${this.buildPatientMeta(patient)}</span>
      `;
      item.addEventListener('click', () => this.setSelectedPatient(patient));
      this.validationPatientResults.appendChild(item);
    });
    this.validationPatientResults.classList.add('is-open');
  },

  clearPatientResults() {
    if (!this.validationPatientResults) return;
    this.validationPatientResults.innerHTML = '';
    this.validationPatientResults.classList.remove('is-open');
    this.patientSearchResults = [];
    this.patientSearchActiveIndex = -1;
  },

  handlePatientSearch(value) {
    if (!window.app?.patientManager?.searchPatients) return;
    clearTimeout(this.patientSearchTimeout);
    this.clearSelectedPatient();
    const query = value.trim();
    if (!query) {
      this.clearPatientResults();
      return;
    }
    this.patientSearchTimeout = setTimeout(async () => {
      const results = await window.app.patientManager.searchPatients(query || '');
      this.patientSearchResults = results || [];
      this.patientSearchActiveIndex = this.patientSearchResults.length ? 0 : -1;
      this.renderPatientResults(this.patientSearchResults);
    }, 200);
  },

  handlePatientSearchKeydown(event) {
    if (!this.patientSearchResults.length) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.patientSearchActiveIndex = Math.min(
        this.patientSearchActiveIndex + 1,
        this.patientSearchResults.length - 1
      );
      this.renderPatientResults(this.patientSearchResults);
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.patientSearchActiveIndex = Math.max(this.patientSearchActiveIndex - 1, 0);
      this.renderPatientResults(this.patientSearchResults);
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      const selected = this.patientSearchResults[this.patientSearchActiveIndex];
      if (selected) {
        this.setSelectedPatient(selected);
      }
    }
  },

  updateCompleteButtonState() {
    if (this.validationCompleteBtn) {
      this.validationCompleteBtn.disabled = !this.validationSelectedPatientId;
    }
  },

  setValidationExpanded(expanded) {
    if (this.validationExpandedPanel) {
      this.validationExpandedPanel.style.display = expanded ? 'block' : 'none';
    }
    if (this.validationSnippet) {
      this.validationSnippet.style.display = expanded ? 'none' : 'block';
    }
    if (this.validationExpandBtn) {
      this.validationExpandBtn.style.display = expanded ? 'none' : 'inline-flex';
    }
  },

  toggleValidationFullscreen() {
    if (!this.validationModal || !this.validationToggleFullscreen) return;
    const isFullscreen = this.validationModal.classList.toggle('validation-modal--fullscreen');
    this.validationToggleFullscreen.innerHTML = isFullscreen
      ? '<i class="fas fa-compress"></i> Exit full-screen'
      : '<i class="fas fa-expand"></i> Expand OCR';
  },

  closeValidationModal() {
    if (this.validationModal) {
      this.validationModal.classList.remove('open', 'validation-modal--review', 'validation-modal--fullscreen');
      this.validationModal.style.display = 'none';
      this.validationModal.dataset.uploadId = '';
    }
    this.validationInitialOcrText = '';
    if (this.validationOcrField) this.validationOcrField.value = '';
    if (this.validationPatientSearch) this.validationPatientSearch.value = '';
    this.clearSelectedPatient();
    this.clearPatientResults();
    document.body.classList.remove('modal-open');
    this.setValidationExpanded(true);
    if (this.validationCompleteBtn) {
      this.validationCompleteBtn.innerHTML = '<i class="fas fa-check"></i> Assign &amp; complete';
    }
    this.updateCompleteButtonState();
  },

  async handleCompleteAction() {
    if (!this.validationModal) return;
    const uploadId = this.validationModal.dataset.uploadId;
    const patientId = this.validationSelectedPatientId || this.validationPatientSearch?.dataset?.patientId;
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
        this.clearSelectedPatient();
      } else if (err.status === 403) {
        showToast('Not allowed for this clinic.', 'error');
      } else {
        showToast(err.message || 'Could not complete upload', 'error');
      }
    } finally {
      if (this.validationCompleteBtn) {
        this.validationCompleteBtn.disabled = false;
        this.validationCompleteBtn.innerHTML = '<i class="fas fa-check"></i> Assign &amp; complete';
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
