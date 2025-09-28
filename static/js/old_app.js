// ReconoMed Frontend Application
class ReconoMedApp {
    constructor() {
        this.apiBase = '/';
        this.currentUser = null;
        this.patients = [];
        this.documents = [];
        this.selectedPatient = null;
        
        this.init();
    }

    async init() {
        // Check authentication first
        if (!this.checkAuthentication()) {
            window.location.href = '/static/login.html';
            return;
        }
    }    

    setTabCount(elementId, count) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = count;
            element.setAttribute('data-count', count);
        }
}        

        this.setupEventListeners();
        this.setupNavigation();
        this.setupDragAndDrop();
        this.updateUserInterface();
        await this.loadInitialData();
        this.updateDashboardStats();
        this.updateConsultationTabCounts();
    }

    checkAuthentication() {
        const user = localStorage.getItem('reconomed_user');
        if (!user) {
            return false;
        }
        
        try {
            this.currentUser = JSON.parse(user);
            return true;
        } catch (error) {
            localStorage.removeItem('reconomed_user');
            return false;
        }
    }

    updateUserInterface() {
        // Update user info in nav
        const userNameEl = document.querySelector('.user-name');
        const userRoleEl = document.querySelector('.user-role');
        
        if (userNameEl && userRoleEl) {
            userNameEl.textContent = this.currentUser.name;
            userRoleEl.textContent = this.getRoleDisplayName(this.currentUser.role);
        }

        // Hide/show features based on role
        this.applyRoleBasedAccess();
    }

    getRoleDisplayName(role) {
        const roleMap = {
            'doctor': 'Doctor',
            'nurse': 'Nurse',
            'admin': 'Administrator',
            'billing': 'Billing Clerk'
        };
        return roleMap[role] || 'User';
    }

    applyRoleBasedAccess() {
        const role = this.currentUser.role;
        
        // Get navigation links
        const navLinks = document.querySelectorAll('.nav-link');
        
        // Role-based navigation access
        const rolePermissions = {
            'doctor': ['dashboard', 'patients', 'documents', 'validation'],
            'nurse': ['dashboard', 'patients', 'documents'],
            'admin': ['dashboard', 'patients', 'documents', 'validation'],
            'billing': ['dashboard', 'patients']
        };
        
        const allowedSections = rolePermissions[role] || ['dashboard'];
        
        navLinks.forEach(link => {
            const section = link.dataset.section;
            if (!allowedSections.includes(section)) {
                link.style.display = 'none';
            }
        });

        // Hide admin-only features for non-admins
        if (role !== 'admin') {
            // Hide patient deletion, system settings, etc.
            const adminOnlyElements = document.querySelectorAll('.admin-only');
            adminOnlyElements.forEach(el => el.style.display = 'none');
        }

        // Limit document upload for billing role
        if (role === 'billing') {
            const uploadArea = document.getElementById('upload-area');
            if (uploadArea) {
                uploadArea.style.display = 'none';
            }
        }
    }

    logout() {
        localStorage.removeItem('reconomed_user');
        window.location.href = '/static/login.html';
    }

    // Event Listeners Setup
    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = e.currentTarget.dataset.section;
                this.showSection(section);
            });
        });

        // Patient form
        document.getElementById('add-patient-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.addPatient();
        });

        // File input
        document.getElementById('file-input').addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files);
        });

        // Patient search
        document.getElementById('patient-search').addEventListener('input', (e) => {
            this.searchPatients(e.target.value);
        });

        // Patient selector for documents
        document.getElementById('patient-select').addEventListener('change', (e) => {
            this.selectedPatient = e.target.value || null;
            this.loadPatientDocuments();
        });

        // Logout button
        document.querySelector('.btn-logout').addEventListener('click', () => {
            this.logout();
        });
    }

    // Navigation
    setupNavigation() {
        // Show dashboard by default
        this.showSection('dashboard');
    }

    showSection(sectionName) {
        // Update nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.querySelector(`[data-section="${sectionName}"]`).classList.add('active');

        // Update content sections
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        document.getElementById(sectionName).classList.add('active');

        // Load section-specific data
        switch(sectionName) {
            case 'patients':
                this.loadPatients();
                break;
            case 'documents':
                this.loadPatientsForSelect();
                break;
            case 'validation':
                this.loadValidationQueue();
                break;
        }
    }

    // Drag and Drop Setup
    setupDragAndDrop() {
        const uploadArea = document.getElementById('upload-area');
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.remove('dragover');
            }, false);
        });

        uploadArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            this.handleFileSelect(files);
        }, false);
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // API Calls
    async apiCall(endpoint, options = {}) {
        try {
            this.showLoading();
            const response = await fetch(this.apiBase + endpoint, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.status}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('API call failed:', error);
            this.showToast('API call failed: ' + error.message, 'error');
            throw error;
        } finally {
            this.hideLoading();
        }
    }

    // Data Loading
    async loadInitialData() {
        try {
            await Promise.all([
                this.loadPatients(),
                this.loadRecentActivity()
            ]);
        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    }

    async loadPatients() {
        try {
            this.patients = await this.apiCall('patients/');
            this.renderPatients();
            this.updateDashboardStats();
        } catch (error) {
            console.error('Failed to load patients:', error);
        }
    }

    async loadPatientsForSelect() {
        if (this.patients.length === 0) {
            await this.loadPatients();
        }
        this.renderPatientSelect();
    }

    async loadPatientDocuments() {
        if (!this.selectedPatient) {
            document.getElementById('documents-list').innerHTML = '<p class="text-center">Please select a patient first.</p>';
            return;
        }

        try {
            this.documents = await this.apiCall(`documents/patient/${this.selectedPatient}`);
            this.renderDocuments();
        } catch (error) {
            console.error('Failed to load documents:', error);
        }
    }

    async loadRecentActivity() {
        // Mock recent activity for now
        const activities = [
            {
                icon: 'fas fa-upload',
                title: 'Document uploaded for Ion Popescu',
                time: '2 minutes ago',
                type: 'upload'
            },
            {
                icon: 'fas fa-check',
                title: 'Lab results validated',
                time: '15 minutes ago',
                type: 'validation'
            },
            {
                icon: 'fas fa-user-plus',
                title: 'New patient added: Maria Ionescu',
                time: '1 hour ago',
                type: 'patient'
            }
        ];

        this.renderRecentActivity(activities);
    }

    async loadValidationQueue() {
        try {
            const pending = await this.apiCall('documents/validation/pending');
            this.renderValidationQueue(pending.documents);
        } catch (error) {
            console.error('Failed to load validation queue:', error);
        }
    }

    // Patient Management
    async addPatient() {
        const formData = new FormData(document.getElementById('add-patient-form'));
        const patientData = Object.fromEntries(formData.entries());

        try {
            const newPatient = await this.apiCall('patients/', {
                method: 'POST',
                body: JSON.stringify(patientData)
            });

            this.patients.push(newPatient);
            this.renderPatients();
            this.closeAddPatientModal();
            this.showToast('Patient added successfully!', 'success');
            this.updateDashboardStats();
        } catch (error) {
            console.error('Failed to add patient:', error);
            this.showToast('Failed to add patient', 'error');
        }
    }

    // File Upload
    async handleFileSelect(files) {
        if (!this.selectedPatient) {
            this.showToast('Please select a patient first', 'warning');
            return;
        }

        for (let file of files) {
            await this.uploadFile(file);
        }
    }

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            // Remove Content-Type header to let browser set it with boundary
            const uploadResult = await fetch(`${this.apiBase}documents/upload?patient_id=${this.selectedPatient}`, {
                method: 'POST',
                body: formData
            });

            if (!uploadResult.ok) {
                throw new Error(`Upload failed: ${uploadResult.status}`);
            }

            const result = await uploadResult.json();
            this.showToast(`${file.name} uploaded successfully!`, 'success');
            
            // Auto-process OCR
            setTimeout(() => {
                this.processOCR(result.document_id);
            }, 1000);

            await this.loadPatientDocuments();
        } catch (error) {
            console.error('Upload failed:', error);
            this.showToast(`Failed to upload ${file.name}: ${error.message}`, 'error');
        }
    }

    async processOCR(documentId) {
        try {
            this.showToast('Processing OCR...', 'info');
            const result = await this.apiCall(`documents/${documentId}/process-ocr`, {
                method: 'POST'
            });
            
            this.showToast('OCR processing completed!', 'success');
            await this.loadPatientDocuments();
        } catch (error) {
            console.error('OCR processing failed:', error);
            this.showToast('OCR processing failed', 'error');
        }
    }

    // Document Validation
    async openValidationModal(documentId) {
        try {
            const validation = await this.apiCall(`documents/${documentId}/validation`);
            this.renderValidationModal(validation);
            document.getElementById('validation-modal').classList.add('active');
        } catch (error) {
            console.error('Failed to load validation data:', error);
            this.showToast('Failed to load validation data', 'error');
        }
    }

    async validateDocument(documentId, validatedData) {
        try {
            await this.apiCall(`documents/${documentId}/validate`, {
                method: 'POST',
                body: JSON.stringify(validatedData)
            });

            this.showToast('Document validated successfully!', 'success');
            this.closeValidationModal();
            await this.loadPatientDocuments();
            await this.loadValidationQueue();
        } catch (error) {
            console.error('Validation failed:', error);
            this.showToast('Validation failed', 'error');
        }
    }

    // *********************************
    // Rendering Functions
    //**********************************

    renderPatients() {
        const container = document.getElementById('patients-grid');
        if (this.patients.length === 0) {
            container.innerHTML = '<p class="text-center">No patients found. Add your first patient to get started.</p>';
            return;
        }

        container.innerHTML = this.patients.map(patient => {
           const initials = (patient.given_name[0] || '') + (patient.family_name[0] || '');
          //const initials = patient.id;
            return `
                <div class="patient-card">
                    <div class="patient-header">
                        <div class="patient-avatar">${initials}</div>
                        <div class="patient-info">
                            <h3>${patient.given_name} ${patient.family_name}</h3>
                            <div class="patient-details">
                                ${patient.birth_date ? `Born: ${patient.birth_date}` : ''}
                                ${patient.phone ? ` • ${patient.phone}` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="patient-actions">
                        <button class="btn-small primary" onclick="app.viewPatient(${patient.id})">
                            <i class="fas fa-eye"></i> View
                        </button>
                        <button class="btn-small secondary" onclick="app.editPatient(${patient.id})">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderPatientSelect() {
        const select = document.getElementById('patient-select');
        select.innerHTML = '<option value="">Select a patient...</option>';
        
        this.patients.forEach(patient => {
            const option = document.createElement('option');
            option.value = patient.id;
            option.textContent = patient.given_name + ' ' + patient.family_name;
            select.appendChild(option);
        });
    }

    renderDocuments() {
        const container = document.getElementById('documents-list');
        if (this.documents.length === 0) {
            container.innerHTML = '<p class="text-center">No documents found for this patient.</p>';
            return;
        }

        container.innerHTML = this.documents.map(doc => {
            const status = doc.is_validated ? 'validated' : 
                         doc.document_type === 'pending_ocr' ? 'pending' : 'processing';
            
            const statusIcon = status === 'validated' ? 'fas fa-check-circle' :
                              status === 'pending' ? 'fas fa-clock' :
                              'fas fa-cog fa-spin';

            return `
                <div class="document-item">
                    <div class="document-icon ${status}">
                        <i class="${statusIcon}"></i>
                    </div>
                    <div class="document-info">
                        <div class="document-name">${doc.filename}</div>
                        <div class="document-meta">
                            Type: ${doc.document_type} • Created: ${new Date(doc.created_at).toLocaleDateString()}
                        </div>
                    </div>
                    <div class="document-actions">
                        ${status === 'processing' ? `
                            <button class="btn-small primary" onclick="app.openValidationModal(${doc.id})">
                                <i class="fas fa-edit"></i> Validate
                            </button>
                        ` : ''}
                        <button class="btn-small secondary" onclick="app.viewDocument(${doc.id})">
                            <i class="fas fa-eye"></i> View
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderRecentActivity(activities) {
        const container = document.getElementById('recent-activity');
        container.innerHTML = activities.map(activity => `
            <div class="activity-item">
                <div class="activity-icon">
                    <i class="${activity.icon}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-title">${activity.title}</div>
                    <div class="activity-time">${activity.time}</div>
                </div>
            </div>
        `).join('');
    }

    renderValidationQueue(documents) {
        const container = document.getElementById('validation-list');
        if (documents.length === 0) {
            container.innerHTML = '<p class="text-center">No documents pending validation.</p>';
            return;
        }

        container.innerHTML = documents.map(doc => `
            <div class="document-item">
                <div class="document-icon pending">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="document-info">
                    <div class="document-name">${doc.filename}</div>
                    <div class="document-meta">
                        Patient ID: ${doc.patient_id} • Type: ${doc.document_type} • Created: ${new Date(doc.created_at).toLocaleDateString()}
                    </div>
                </div>
                <div class="document-actions">
                    <button class="btn-small primary" onclick="app.openValidationModal(${doc.id})">
                        <i class="fas fa-check"></i> Validate
                    </button>
                </div>
            </div>
        `).join('');
    }

    renderValidationModal(validation) {
        const content = document.getElementById('validation-content');
        const doc = validation.document;
        
        content.innerHTML = `
            <div class="validation-layout">
                <div class="validation-preview">
                    <h3>Original Document</h3>
                    <div class="document-preview">
                        <p><strong>Filename:</strong> ${doc.filename}</p>
                        <p><strong>Type:</strong> ${doc.document_type}</p>
                        <div class="ocr-text">
                            <strong>Extracted Text:</strong>
                            <pre>${doc.ocr_text}</pre>
                        </div>
                    </div>
                </div>
                <div class="validation-form">
                    <h3>Validation Form</h3>
                    <form id="validation-form">
                        ${validation.validation_fields.map(field => `
                            <div class="form-group">
                                <label for="field-${field.field}">${field.label}</label>
                                ${field.type === 'textarea' ? 
                                    `<textarea id="field-${field.field}" name="${field.field}" ${field.required ? 'required' : ''}>${field.value}</textarea>` :
                                    `<input type="${field.type}" id="field-${field.field}" name="${field.field}" value="${field.value}" ${field.required ? 'required' : ''}>`
                                }
                            </div>
                        `).join('')}
                        
                        ${validation.suggestions.length > 0 ? `
                            <div class="validation-suggestions">
                                <h4>Suggestions:</h4>
                                <ul>
                                    ${validation.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        
                        <div class="form-actions">
                            <button type="button" class="btn-secondary" onclick="app.closeValidationModal()">Cancel</button>
                            <button type="submit" class="btn-primary">Validate Document</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        // Setup validation form submission
        document.getElementById('validation-form').addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const validatedData = Object.fromEntries(formData.entries());
            this.validateDocument(doc.id, validatedData);
        });
    }

    // Modal Functions
    showAddPatientModal() {
        document.getElementById('add-patient-modal').classList.add('active');
    }

    closeAddPatientModal() {
        document.getElementById('add-patient-modal').classList.remove('active');
        document.getElementById('add-patient-form').reset();
    }

    closeValidationModal() {
        document.getElementById('validation-modal').classList.remove('active');
    }

    // Utility Functions
    showLoading() {
        document.getElementById('loading').classList.add('active');
    }

    hideLoading() {
        document.getElementById('loading').classList.remove('active');
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;

        document.getElementById('toast-container').appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    async updateDashboardStats() {
        document.getElementById('total-patients').textContent = this.patients.length;
        document.getElementById('total-documents').textContent = this.documents.length;
        // DUMMY DATA
        document.getElementById('pending-validation').textContent = '3';
        document.getElementById('validated-documents').textContent = '12';
        document.getElementById('active-consultations').textContent = count;
        document.getElementById('active-consultations').setAttribute('data-count', count);
    }

    async updateConsultationTabCounts() {
        try {
            // For v1, use mock data since you don't have consultation endpoints yet
            const activeConsultations = 0; // TODO: fetch from API
            const dischargeReady = 0; // TODO: fetch from API  
            const reviewPending = 0; // TODO: fetch from API

            this.setTabCount('active-consultations', activeConsultations);
            this.setTabCount('discharge-ready', dischargeReady);
            this.setTabCount('review-pending', reviewPending);
        } catch (error) {
            console.error('Failed to update consultation tab counts:', error);
        }
    }

    updateStatCard(elementId, value) {
        const card = document.getElementById(elementId);
        const statCard = card.closest('.stat-card');
        
        if (value === 0 || value === '-') {
            statCard.setAttribute('data-count', '0');
        } else {
            statCard.removeAttribute('data-count');
            card.textContent = value;
        }
    }

    searchPatients(query) {
        const filteredPatients = this.patients.filter(patient => {
            const fullName = `${patient.given_name} ${patient.family_name}`.toLowerCase();
            return fullName.includes(query) ||
                patient.given_name.toLowerCase().includes(query) ||
                patient.family_name.toLowerCase().includes(query) ||
                (patient.cnp && patient.cnp.includes(query)) ||
                (patient.phone && patient.phone.includes(query));
        });
        
        // Temporarily store original patients
        const originalPatients = this.patients;
        this.patients = filteredPatients;
        this.renderPatients();
        this.patients = originalPatients;
    }

    // Placeholder functions for future implementation
    viewPatient(patientId) {
        this.showToast(`Viewing patient ${patientId}`, 'info');
    }

    editPatient(patientId) {
        this.showToast(`Editing patient ${patientId}`, 'info');
    }

    viewDocument(documentId) {
        this.showToast(`Viewing document ${documentId}`, 'info');
    }
}

// Global Functions (called from HTML)
function showSection(sectionName) {
    app.showSection(sectionName);
}

function showAddPatientModal() {
    app.showAddPatientModal();
}

function closeAddPatientModal() {
    app.closeAddPatientModal();
}

function closeValidationModal() {
    app.closeValidationModal();
}

// Initialize the application
const app = new ReconoMedApp();

// Export for global access
window.app = app;