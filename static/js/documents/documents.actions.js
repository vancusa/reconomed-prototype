// documents.actions.js
// Handles backend calls and data-level operations for the Documents module

import { apiUrl, API_CONFIG } from '../app.js';
import { showToast } from '../ui.js';

function currentUserEmail() {
  if (typeof window === 'undefined') return null;
  if (window.app?.currentUser?.username) return window.app.currentUser.username;
  try {
    const raw = localStorage.getItem('reconomed_user');
    if (raw) {
      const parsed = JSON.parse(raw);
      return parsed?.username || parsed?.email || null;
    }
  } catch (e) {
    return null;
  }
  return null;
}

function withUserHeaders(baseHeaders = {}) {
  const headers = new Headers(baseHeaders);
  const email = currentUserEmail();
  if (email && !headers.has('X-User')) {
    headers.set('X-User', email);
  }
  return headers;
}

export const DocumentActions = {
  /**
   * Upload one or multiple files (no patient required)
   */
  async uploadFiles(files, patientId=null) {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }

    try {
      const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents,'uploads'), {
        method: 'POST',
        headers: withUserHeaders(),
        body: formData,
      });
      if (!response.ok) throw new Error('Upload failed');

      const data = await response.json();
      showToast('Files uploaded successfully', 'success');
      
      return data;
    }
    catch (err) {
      console.error('Upload error:', err);
      showToast('Error uploading files', 'error');
      return null;
    }
  },

  async fetchTab(tab) {
    const tabParam = encodeURIComponent(tab);
    const response = await fetch(
      apiUrl(API_CONFIG.ENDPOINTS.documents, `uploads?tab=${tabParam}`),
      { headers: withUserHeaders() }
    );
    if (!response.ok) throw new Error(`Failed to fetch ${tab} uploads`);
    const data = await response.json();
    return data?.items || [];
  },

  /**
   * Completes upload validation and assigns to patient
   * @param {string} uploadId - Upload UUID
   * @param {string} patientId - Patient UUID to assign
   * @param {string} [editedOcrText] - Corrected OCR text (optional)
   * @param {string} [documentType] - Document type override (optional)
   * @returns {Promise<Object>} Completed document
   */
  async completeUpload(uploadId, patientId, editedOcrText = null, documentType = null) {
    const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `uploads/${uploadId}/complete`), {
      method: 'POST',
      headers: withUserHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ 
        patient_id: patientId,
        edited_ocr_text: editedOcrText,
        document_type: documentType
      })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const err = new Error(data?.detail || 'Failed to complete upload');
      err.status = response.status;
      throw err;
    }
    return data;
  }, 

  /**
   * Batch-set document type for selected uploads (Validation screen)
   * - For each uploadId, calls:
   *   PUT /documents/uploads/{upload_id}/type?document_type=...
   */
  async batchSetType(uploadIds, documentType) {
    if (!uploadIds || !uploadIds.length || !documentType) {
      return;
    }

    try {
      const requests = uploadIds.map((id) => {
        const query = `uploads/${encodeURIComponent(id)}/type?document_type=${encodeURIComponent(documentType)}`;
        return fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, query), {
          method: 'PUT',
          headers: {}
        });
      });

      const responses = await Promise.all(requests);
      const allOk = responses.every((res) => res.ok);
      if (!allOk) {
        throw new Error('One or more type updates failed');
      }

      showToast('Tipul documentelor a fost actualizat', 'success');
      return true;
    } catch (err) {
      console.error('batchSetType error:', err);
      showToast('Eroare la actualizarea tipului documentelor', 'error');
      return null;
    }
  },

  /**
   * Fetches complete upload details including metadata, OCR results, and preview URL
   * @param {string} uploadId - Upload UUID
   * @returns {Promise<{metadata: Object, ocr: Object, previewUrl: string}>}
   */
  async fetchUploadDetails(uploadId) {
    const detailRes = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `uploads/${uploadId}`), {
      headers: withUserHeaders()
    });
    if (!detailRes.ok) {
      const body = await detailRes.json().catch(() => ({}));
      const err = new Error(body?.detail || 'Failed to load upload detail');
      err.status = detailRes.status;
      throw err;
    }

    const metadata = await detailRes.json();

    const ocrRes = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `uploads/${uploadId}/ocr`), {
      headers: withUserHeaders()
    });
    const ocr = ocrRes.ok ? await ocrRes.json() : null;

    return { metadata, ocr, previewUrl: apiUrl(API_CONFIG.ENDPOINTS.documents, `uploads/${uploadId}/download`) };
  },

  /**
   * Opens validation modal with document preview and OCR results
   * @param {string} uploadId - Upload UUID to validate
   */
  async openValidationCard(uploadId) {
    const { metadata, ocr, previewUrl } = await DocumentActions.fetchUploadDetails(uploadId);
    
    // Render split view:
    // Left: <img src="${previewUrl}">
    // Right: Display metadata + ocr.text with confidence highlighting
  },

  /**
   * Reject and delete an upload immediately.
   * @param {string} uploadId
   */
  async rejectUpload(uploadId) {
    const res = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `uploads/${uploadId}`), {
      method: 'DELETE',
      headers: withUserHeaders(),
    });

    if (res.status === 404) {
      const err = new Error('Already deleted');
      err.status = 404;
      throw err;
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const err = new Error(body?.detail || 'Failed to delete upload');
      err.status = res.status;
      throw err;
    }

    return res.json();
  },
};