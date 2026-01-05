// documents.actions.js
// Handles backend calls and data-level operations for the Documents module

import { apiUrl, API_CONFIG } from '../app.js';
import { showToast } from '../ui.js';

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
        headers: {},
        body: formData,
      });
      if (!response.ok) throw new Error('Upload failed');

      const data = await response.json();
      showToast('Files uploaded successfully', 'success');
      
      //start OCR imediatly automatic
      await this.startOCR(patientId);
      
      return data;
    }
    catch (err) {
      console.error('Upload error:', err);
      showToast('Error uploading files', 'error');
      return null;
    }
  },

  async fetchTab(tab) {
    const response = await fetch(
      `/api/documents/uploads?tab=${tab}`,
      {
        headers: {
          "X-User": window.app.currentUser.username
        }
      }
    );
    if (!response.ok) throw new Error(`Failed to fetch ${tab} uploads`);
    return response.json();
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
    const response = await fetch(`/api/uploads/${uploadId}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        patient_id: patientId,
        edited_ocr_text: editedOcrText,
        document_type: documentType
      })
    });
    if (!response.ok) throw new Error('Failed to complete upload');
    return response.json();
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
    const [metadata, ocr] = await Promise.all([
      fetch(`/api/uploads/${uploadId}`).then(r => r.json()),
      fetch(`/api/uploads/${uploadId}/ocr`).then(r => r.json())
    ]);
    return { metadata, ocr, previewUrl: `/api/uploads/${uploadId}/download` };
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

};
