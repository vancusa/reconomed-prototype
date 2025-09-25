// static/js/upload-handler.js
class UploadHandler {
    constructor() {
        this.maxUploads = 20;
        this.currentUploads = 0;
        this.uploads = [];
        this.selectedFiles = new Set();
        this.patients = []; // Will be loaded from API
        
        this.initializeElements();
        this.setupEventListeners();
        this.loadPatients();
        this.loadExistingUploads();
    }

    initializeElements() {
        this.dropzone = document.getElementById('upload-dropzone');
        this.fileInput = document.getElementById('file-input');
        this.uploadPrompt = document.getElementById('upload-prompt');
        this.uploadStatus = document.getElementById('upload-status');
        this.fileContainer = document.getElementById('file-container');
        this.emptyState = document.getElementById('empty-state');
        this.selectAllCheckbox = document.getElementById('select-all');
        this.batchActions = document.getElementById('batch-actions');
    }

    setupEventListeners() {
        // Drag and drop
        this.dropzone.addEventListener('click', () => this.fileInput.click());
        this.dropzone.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.dropzone.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.dropzone.addEventListener('drop', (e) => this.handleDrop(e));
        
        // File input
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        
        // Select all
        this.selectAllCheckbox.addEventListener('change', (e) => this.handleSelectAll(e));
        
        // Batch actions
        document.getElementById('apply-batch-patient').addEventListener('click', () => this.applyBatchPatient());
        document.getElementById('apply-batch-type').addEventListener('click', () => this.applyBatchType());
        document.getElementById('start-processing').addEventListener('click', () => this.startProcessing());
        
        // View toggles
        document.querySelectorAll('.view-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => this.toggleView(e.target.dataset.view));
        });
    }

    async loadPatients() {
        try {
            const response = await fetch('/api/v1/patients');
            const patients = await response.json();
            this.patients = patients;
            this.updatePatientSelects();
        } catch (error) {
            console.error('Failed to load patients:', error);
        }
    }

    updatePatientSelects() {
        const selects = [
            document.getElementById('batch-patient'),
            ...document.querySelectorAll('.patient-select')
        ];
        
        selects.forEach(select => {
            if (!select) return;
            
            // Clear existing options except first
            while (select.children.length > 1) {
                select.removeChild(select.lastChild);
            }
            
            // Add patient options
            this.patients.forEach(patient => {
                const option = document.createElement('option');
                option.value = patient.id;
                option.textContent = `${patient.family_name} ${patient.given_name}`;
                select.appendChild(option);
            });
        });
    }

    async loadExistingUploads() {
        try {
            const response = await fetch('/api/uploads/unprocessed');
            const uploads = await response.json();
            this.uploads = uploads;
            this.renderUploads();
            this.updateCounts();
        } catch (error) {
            console.error('Failed to load existing uploads:', error);
        }
    }

    handleDragOver(e) {
        e.preventDefault();
        this.dropzone.classList.add('drag-over');
    }

    handleDragLeave(e) {
        e.preventDefault();
        this.dropzone.classList.remove('drag-over');
    }

    handleDrop(e) {
        e.preventDefault();
        this.dropzone.classList.remove('drag-over');
        const files = Array.from(e.dataTransfer.files);
        this.processFiles(files);
    }

    handleFileSelect(e) {
        const files = Array.from(e.target.files);
        this.processFiles(files);
    }

    async processFiles(files) {
        if (!this.canUploadMore()) {
            alert(`Upload limit reached. Maximum ${this.maxUploads} files allowed.`);
            return;
        }

        const allowedCount = this.maxUploads - this.currentUploads;
        const filesToProcess = files.slice(0, allowedCount);

        this.showUploadStatus(true);

        try {
            const compressedFiles = await window.imageCompressor.compressMultiple(
                filesToProcess, 
                (current, total, fileName) => {
                    this.updateUploadProgress(`Compressing ${fileName} (${current + 1}/${total})`);
                }
            );

            for (const fileData of compressedFiles) {
                await this.uploadFile(fileData);
            }

            this.showUploadStatus(false);
            this.renderUploads();
            this.updateCounts();
            
        } catch (error) {
            console.error('Upload failed:', error);
            this.showUploadStatus(false);
        }
    }

    async uploadFile(fileData) {
        const formData = new FormData();
        formData.append('file', fileData.compressed);
        formData.append('filename', fileData.original.name);
        formData.append('originalSize', fileData.originalSize);
        formData.append('compressedSize', fileData.compressedSize);

        const response = await fetch('/api/uploads', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            const upload = {
                id: result.id,
                filename: fileData.original.name,
                originalSize: fileData.originalSize,
                compressedSize: fileData.compressedSize,
                filePath: result.filePath,
                uploadedAt: new Date(),
                expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
                patientId: null,
                documentType: null,
                thumbnailUrl: await this.generateThumbnail(fileData.compressed)
            };
            
            this.uploads.push(upload);
            this.currentUploads++;
        }
    }

    async generateThumbnail(file) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    
                    const maxSize = 200;
                    const scale = Math.min(maxSize / img.width, maxSize / img.height);
                    
                    canvas.width = img.width * scale;
                    canvas.height = img.height * scale;
                    
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    resolve(canvas.toDataURL('image/jpeg', 0.8));
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        });
    }

    renderUploads() {
        if (this.uploads.length === 0) {
            this.fileContainer.style.display = 'none';
            this.emptyState.style.display = 'block';
            return;
        }

        this.fileContainer.style.display = 'grid';
        this.emptyState.style.display = 'none';
        
        this.fileContainer.innerHTML = this.uploads.map(upload => 
            this.createUploadHTML(upload)
        ).join('');

        this.setupUploadEventListeners();
    }

    createUploadHTML(upload) {
        const expiryInfo = this.getExpiryStatus(upload.expiresAt);
        const compressionInfo = upload.originalSize !== upload.compressedSize 
            ? `(was ${this.formatFileSize(upload.originalSize)})`
            : '';

        return `
            <div class="file-thumbnail" data-id="${upload.id}">
                <div class="file-thumbnail__checkbox">
                    <input type="checkbox" class="file-checkbox" data-id="${upload.id}">
                </div>
                <div class="file-thumbnail__image">
                    <img src="${upload.thumbnailUrl}" alt="${upload.filename}">
                </div>
                <div class="file-thumbnail__info">
                    <div class="file-thumbnail__header">
                        <span class="filename" title="${upload.filename}">${upload.filename}</span>
                        <span class="expiry-badge ${expiryInfo.status}">${expiryInfo.text}</span>
                    </div>
                    <div class="file-thumbnail__details">
                        <span class="file-size">
                            ${this.formatFileSize(upload.compressedSize)}
                            <span class="compression-info">${compressionInfo}</span>
                        </span>
                        <span class="upload-date">${this.formatDate(upload.uploadedAt)}</span>
                    </div>
                    <div class="file-thumbnail__assignments">
                        <select class="patient-select" data-id="${upload.id}">
                            <option value="">Select Patient...</option>
                            ${this.patients.map(patient => 
                                `<option value="${patient.id}" ${upload.patientId === patient.id ? 'selected' : ''}>
                                    ${patient.family_name} ${patient.given_name}
                                </option>`
                            ).join('')}
                        </select>
                        <select class="document-type-select" data-id="${upload.id}">
                            <option value="">Document Type...</option>
                            <option value="romanian_id" ${upload.documentType === 'romanian_id' ? 'selected' : ''}>Romanian ID</option>
                            <option value="lab_result" ${upload.documentType === 'lab_result' ? 'selected' : ''}>Lab Result</option>
                            <option value="discharge_note" ${upload.documentType === 'discharge_note' ? 'selected' : ''}>Discharge Note</option>
                        </select>
                    </div>
                </div>
            </div>
        `;
    }

    setupUploadEventListeners() {
        // File selection checkboxes
        document.querySelectorAll('.file-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => this.handleFileSelection(e));
        });

        // Patient assignment
        document.querySelectorAll('.patient-select').forEach(select => {
            select.addEventListener('change', (e) => this.handlePatientAssignment(e));
        });

        // Document type assignment
        document.querySelectorAll('.document-type-select').forEach(select => {
            select.addEventListener('change', (e) => this.handleDocumentTypeAssignment(e));
        });
    }

    handleFileSelection(e) {
        const fileId = e.target.dataset.id;
        if (e.target.checked) {
            this.selectedFiles.add(fileId);
        } else {
            this.selectedFiles.delete(fileId);
        }
        this.updateSelectionUI();
    }

    handleSelectAll(e) {
        const checkboxes = document.querySelectorAll('.file-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = e.target.checked;
            const fileId = checkbox.dataset.id;
            if (e.target.checked) {
                this.selectedFiles.add(fileId);
            } else {
                this.selectedFiles.delete(fileId);
            }
        });
        this.updateSelectionUI();
    }

    updateSelectionUI() {
        const selectedCount = this.selectedFiles.size;
        document.getElementById('selected-count').textContent = selectedCount;
        
        if (selectedCount > 0) {
            this.batchActions.style.display = 'block';
        } else {
            this.batchActions.style.display = 'none';
        }
        
        // Update select all checkbox
        const totalFiles = this.uploads.length;
        this.selectAllCheckbox.checked = selectedCount === totalFiles && totalFiles > 0;
        this.selectAllCheckbox.indeterminate = selectedCount > 0 && selectedCount < totalFiles;
    }

    // Utility methods
    canUploadMore() {
        return this.currentUploads < this.maxUploads;
    }

    showUploadStatus(show) {
        this.uploadPrompt.style.display = show ? 'none' : 'flex';
        this.uploadStatus.style.display = show ? 'flex' : 'none';
    }

    updateUploadProgress(message) {
        this.uploadStatus.querySelector('p').textContent = message;
    }

    updateCounts() {
        document.getElementById('upload-count').textContent = `${this.currentUploads}/${this.maxUploads} uploads used`;
        document.getElementById('total-uploads').textContent = this.uploads.length;
        document.getElementById('unprocessed-count').textContent = this.uploads.length;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    formatDate(date) {
        return new Date(date).toLocaleDateString('ro-RO', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    getExpiryStatus(expiryDate) {
        const now = new Date();
        const expiry = new Date(expiryDate);
        const daysLeft = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
        
        if (daysLeft <= 0) return { status: 'expired', text: 'Expired' };
        if (daysLeft <= 7) return { status: 'warning', text: `${daysLeft} days left` };
        return { status: 'ok', text: `${daysLeft} days left` };
    }

    toggleView(viewMode) {
        document.querySelectorAll('.view-toggle').forEach(btn => btn.classList.remove('active'));
        document.querySelector(`[data-view="${viewMode}"]`).classList.add('active');
        
        this.fileContainer.className = `file-container ${viewMode}`;
    }

    // Batch operations (simplified for now)
    applyBatchPatient() {
        const patientId = document.getElementById('batch-patient').value;
        if (!patientId) return;
        
        console.log('Apply patient to selected files:', patientId);
        // TODO: Implement batch patient assignment
    }

    applyBatchType() {
        const documentType = document.getElementById('batch-document-type').value;
        if (!documentType) return;
        
        console.log('Apply document type to selected files:', documentType);
        // TODO: Implement batch type assignment
    }

    startProcessing() {
        const selectedUploads = this.uploads.filter(upload => 
            this.selectedFiles.has(upload.id)
        );
        
        console.log('Start processing:', selectedUploads);
        // TODO: Implement processing queue
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.uploadHandler = new UploadHandler();
});