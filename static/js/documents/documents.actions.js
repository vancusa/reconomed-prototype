// documents.actions.js
// Handles backend calls and data-level operations for the Documents module

import { apiUrl, API_CONFIG } from '../app.js';
import { showToast } from '../ui.js';

export const DocumentActions = {
  /**
   * Upload one or multiple files (no patient required)
   */
  async uploadFiles(files) {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }

    try {
      const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents,'uploads'), {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) throw new Error('Upload failed');
      showToast('Files uploaded successfully', 'success');
      return await response.json();
    } catch (err) {
      console.error('Upload error:', err);
      showToast('Error uploading files', 'error');
      return null;
    }
  },

  /**
   * Fetch unprocessed uploads (for Unprocessed tab)
   */
  async fetchUnprocessed() {
    console.log('Fetching unprocessed uploads...');
    try {
      const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, 'uploads/unprocessed'));
      if (!res.ok) throw new Error('Failed to load uploads');
      return await res.json();
    } catch (err) {
      console.error('fetchUnprocessed error:', err);
      return { documents: [] };
    }
  },

  /**
   * Batch assign selected uploads to a patient
   */
  async batchAssign(documentIds, patientId) {
    try {
      const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, '/batch-assign'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_ids: documentIds, patient_id: patientId }),
      });
      if (!res.ok) throw new Error('Assignment failed');
      showToast('Documents assigned successfully', 'success');
      return await res.json();
    } catch (err) {
      console.error('Batch assign error:', err);
      showToast('Error assigning documents', 'error');
      return null;
    }
  },

  /**
   * Start OCR processing for selected uploads
   */
  async startOCR(documentIds) {
    try {
      const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.uploads, '/batch-ocr'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_ids: documentIds }),
      });
      if (!res.ok) throw new Error('Failed to start OCR');
      showToast('OCR processing started', 'info');
      return await res.json();
    } catch (err) {
      console.error('startOCR error:', err);
      showToast('Error starting OCR', 'error');
      return null;
    }
  },
};
