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
    document.querySelectorAll('.view-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        this.toggleView(btn.dataset.view);
      });
    });

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

  },

  /**
   * Switch tab by key
   */
  switchTab(tabKey) {
    document.querySelectorAll('.document-tabs .tab-button').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabKey);
    });
    document.querySelectorAll('.document-tabs .tab-content').forEach(div => {
      div.classList.toggle('active', div.id === `${tabKey}-tab`);
    });
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
        const data = await DocumentActions.fetchUnprocessed();
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
      case 'image': return 'Imagine';
      case 'pdf': return 'Document PDF';
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
    if (!isoString) return 'Data upload necunoscută';
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return 'Data upload necunoscută';

    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    const timeOpts = { hour: '2-digit', minute: '2-digit' };

    if (sameDay) {
      return `Încărcat azi, ${d.toLocaleTimeString(undefined, timeOpts)}`;
    }
    return `Încărcat la ${d.toLocaleDateString()} ${d.toLocaleTimeString(undefined, timeOpts)}`;
  },

  /**
   * Render uploaded documents in the Unprocessed tab
   */
  renderUploads(documents) {
    console.log('Render unprocessed uploads...');
  const container =  document.getElementById('file-container');
  const empty = document.getElementById('empty-state');
  if (!container) {
    console.error('File container not found in Unprocessed tab');
    return;
  }

  //console.log("Sunt aici si am gasit container");
  container.innerHTML = '';
  if (!documents.length) {
    empty.style.display = 'block';
    return;
  }

  if (empty) empty.style.display = 'none';

  documents.forEach(doc => {
    const category = this.getUploadCategory(doc);
    const iconClass = this.getUploadIconClass(category);
    const label = this.getUploadLabel(category);
    const dateText = this.formatUploadDate(doc.uploaded_at);

    const el = document.createElement('div');
    el.classList.add('upload-card');
    el.dataset.id = doc.id;

    el.innerHTML = `
    <label class="upload-card-label">
        <div class="upload-card-main">
          <div class="upload-card-icon ${category}">
            <i class="fas ${iconClass}"></i>
          </div>
          <div class="upload-card-meta">
            <div class="upload-card-title">${label}</div>
            <div class="upload-card-date">${dateText}</div>
          </div>
        </div>
      </label>
    `;

    container.appendChild(el);
  });

  const selectAll = document.getElementById('select-all');
  if (selectAll) {
    selectAll.onchange = (e) => {
      const allChecks = container.querySelectorAll('.file-checkbox');
      allChecks.forEach(cb => (cb.checked = e.target.checked));
    };
  }
}
}