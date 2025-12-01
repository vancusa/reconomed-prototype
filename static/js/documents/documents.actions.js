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
   * Batch-assign selected uploads to a patient (used in Validation screen)
   * - For each uploadId, calls: PUT /documents/uploads/{upload_id}/patient?patient_id=...
   */
  async batchAssign(uploadIds, patientId) {
    if (!uploadIds || !uploadIds.length || !patientId) {
      return;
    }

    try {
      const requests = uploadIds.map((id) => {
        const query = `uploads/${encodeURIComponent(id)}/patient?patient_id=${encodeURIComponent(patientId)}`;
        return fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, query), {
          method: 'PUT',
        });
      });

      const responses = await Promise.all(requests);

      const allOk = responses.every((res) => res.ok);
      if (!allOk) {
        throw new Error('One or more assignments failed');
      }

      showToast('Documentele au fost asociate pacientului', 'success');
      // Optionally parse JSON for each if you need updated objects:
      // const payloads = await Promise.all(responses.map(r => r.json()));
      // return payloads;
      return true;
    } catch (err) {
      console.error('Batch assign error:', err);
      showToast('Eroare la asocierea documentelor cu pacientul', 'error');
      return null;
    }
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
   * Start OCR processing for pending uploads
   * - patientId is optional; if given, backend queues only that patient's uploads
   */
  async startOCR(patientId = null) {
    try {
      const query = patientId
        ? `?patient_id=${encodeURIComponent(patientId)}`
        : '';

      const res = await fetch(
        apiUrl(API_CONFIG.ENDPOINTS.documents, `uploads/batch-ocr${query}`),
        { method: 'POST' }
      );

      if (!res.ok) throw new Error('Failed to start OCR');
      showToast('OCR processing started', 'info');
      return await res.json();
    }
    catch (err) {
      console.error('startOCR error:', err);
      showToast('Error starting OCR', 'error');
      return null;
    }
  },
};
