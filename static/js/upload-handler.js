// upload-handler.js
// ES Module version
// Handles file selection, compression, and uploading documents

import { compressImage } from './image-compression.js';
import { showToast } from './ui.js'; // UI helper for notifications

/* *
 * Handle selection of one or more files (from input or drop).
 * @param {FileList|File[]} files - Selected files
 * @param {string|number} patientId - ID of the patient the files belong to
 * @param {string} apiBase - API base URL
 */
export async function handleFileSelect(files, patientId, apiBase = '/') {
    if (!patientId) {
        showToast('Please select a patient first', 'warning');
        return;
    }

    for (let file of files) {
        await uploadFile(file, patientId, apiBase);
    }
}

/* *
 * Upload a single file to the API.
 * Optionally compresses images before upload.
 * @param {File} file - File to upload
 * @param {string|number} patientId - Patient ID
 * @param {string} apiBase - API base URL
 */
export async function uploadFile(file, patientId, apiBase = '/') {
    try {
        let fileToUpload = file;

        // If file is an image, compress before upload
        if (file.type.startsWith('image/')) {
            fileToUpload = await compressImage(file, { maxWidth: 1600, maxHeight: 1600, quality: 0.7 });
        }

        const formData = new FormData();
        formData.append('file', fileToUpload);

        // Perform upload
        const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `/upload?patient_id=${patientId}`), {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.status}`);
        }

        const result = await response.json();
        showToast(`${file.name} uploaded successfully!`, 'success');

        // Auto-start OCR after short delay
        setTimeout(async () => {
            try {
                await fetch(apiUrl(API_CONFIG.ENDPOINTS.documents, `/${result.document_id}/process-ocr`, { method: 'POST' }));
                showToast('OCR processing completed!', 'success');
            } catch {
                showToast('OCR processing failed', 'error');
            }
        }, 1000);

    } catch (error) {
        console.error('Upload failed:', error);
        showToast(`Failed to upload ${file.name}: ${error.message}`, 'error');
    }
}

/* *
 * Setup drag-and-drop area for file uploads.
 * @param {string} areaId - The ID of the upload area element
 * @param {Function} onFilesSelected - Callback when files are selected
 */
export function setupUploadArea(areaId, onFilesSelected) {
    const uploadArea = document.getElementById(areaId);
    if (!uploadArea) return;

    const preventDefaults = e => {
        e.preventDefault();
        e.stopPropagation();
    };

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.remove('dragover'), false);
    });

    uploadArea.addEventListener('drop', e => {
        const files = e.dataTransfer.files;
        onFilesSelected(files);
    }, false);
}