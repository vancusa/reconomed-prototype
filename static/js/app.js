// app.js
import { checkAuthentication, logout } from './auth.js';
import { Navigation } from './navigation.js';
import { PatientManager } from './patients.js';
import { DocumentManager } from './documents.js';
import { ConsultationManager } from './consultations.js';
import { AgendaManager } from './agenda.js';
import { showLoading, hideLoading, showToast, showModal, hideModal} from './ui.js';
import { initDocumentTabs } from './document-manager.js';

// =========================================================================
// API CONFIGURATION
// =========================================================================
const API_CONFIG = {
    BASE_URL: '/api',
    ENDPOINTS: {
        auth: '/auth/',
        clinics:'/clinics/',
        consultations: '/consultations/',
        documents: '/documents/',
        patients: '/patients/',
        search: '/search/'
    }
};

function apiUrl(endpoint, path = '') {
    return `${API_CONFIG.BASE_URL}${endpoint}${path}`;
}

window.API_CONFIG = API_CONFIG;
window.apiUrl = apiUrl;

// =========================================================================
// APPLICATION
// =========================================================================
class ReconoMedApp {
    constructor() {
        this.apiBase = '/';
        this.currentUser = null;
        this.patients = [];
        this.documents = [];
        this.selectedPatient = null;

        this.navigation = new Navigation(this);
        this.patientManager = new PatientManager(this);
        this.documentManager = new DocumentManager(this);
        this.consultationManager = new ConsultationManager(this);
        this.agendaManager = new AgendaManager(this);
    }

    async init() {
        if (!checkAuthentication(this)) {
            window.location.href = '/static/login.html';
            return;
        }

        try {
            this.navigation.init();
            this.patientManager.init();
            this.documentManager.init();
            this.agendaManager.init();
            initDocumentTabs();
        } catch (err) {
            console.error('UI initialization failed:', err);
            showToast('Interface setup failed', 'error');
            return;
        }

        await this.loadInitialData();
    }

    async loadInitialData() {
        try {
            showLoading();
            await this.patientManager.loadPatients();
            await this.agendaManager.loadAgenda();
        } catch (err) {
            console.error('Data loading failed:', err);
            showToast('Failed to load initial data', 'error');
        } finally {
            hideLoading();
        }
    }

    goToSection(sectionId) {
        this.navigation.navigateTo(sectionId);
    }
}

// =========================================================================
// STARTUP
// =========================================================================
const app = new ReconoMedApp();

document.addEventListener('DOMContentLoaded', () => {
    app.init();
});

window.app = app;

// Make consultationManager available globally for any remaining inline handlers
window.consultationManager = app.consultationManager;

// =========================================================================
// GLOBAL MODAL FUNCTIONS for HTML onclick handlers
// =========================================================================
window.closeAddPatientModal = function() {
    const form = document.getElementById('add-patient-form');
    const modal = document.getElementById('add-patient-modal');
    const modalTitle = modal.querySelector('.modal-header h2');
    const submitButton = form.querySelector('button[type="submit"]');

    modalTitle.textContent = 'Add New Patient';
    submitButton.innerHTML = '<i class="fas fa-plus"></i> Add Patient';
    form.dataset.mode = 'create';
    delete form.dataset.patientId;
    form.reset();

    hideModal('add-patient-modal');
};

window.showAddPatientModal = function() {
    const form = document.getElementById('add-patient-form');
    const modal = document.getElementById('add-patient-modal');
    const modalTitle = modal.querySelector('.modal-header h2');
    const submitButton = form.querySelector('button[type="submit"]');

    modalTitle.textContent = 'Add New Patient';
    submitButton.innerHTML = '<i class="fas fa-plus"></i> Add Patient';
    form.dataset.mode = 'create';
    delete form.dataset.patientId;
    form.reset();

    showModal('add-patient-modal');
};

// View Patient Modal
window.closeViewPatientModal = function() {
    hideModal('view-patient-modal');
};

window.closePatientDetailsModal = function() {
    hideModal('patient-details-modal');
};

// GDPR modal functions
window.closeGDPRModal = function() {
    hideModal('gdpr-modal');
};

window.closeWithdrawConsentModal = function() {
    hideModal('withdraw-consent-modal');
    document.getElementById('withdraw-consent-form').reset();
};

// Consent History
window.closeConsentHistoryModal = function() {
    hideModal('consent-history-modal');
};

// Deferred global function assignments (need app to be created first)
document.addEventListener('DOMContentLoaded', () => {
    window.app.editPatientFromView = () => app.patientManager.editPatientFromView();
    window.app.manageGDPRFromView = () => app.patientManager.manageGDPRFromView();
    window.app.withdrawConsent = (type) => app.patientManager.withdrawConsent(type);
    window.app.grantConsent = (type) => app.patientManager.grantConsent(type);
    window.app.renewConsent = (type) => app.patientManager.renewConsent(type);
    window.app.nextPatientsPage = () => app.patientManager.nextPage();
    window.app.previousPatientsPage = () => app.patientManager.previousPage();
    window.app.exportConsentHistory = () => app.patientManager.exportConsentHistory();
});

// Logout
const logoutButton = document.getElementById('logout-button');
if (logoutButton) {
    logoutButton.addEventListener('click', () => {
        logout();
    });
}
