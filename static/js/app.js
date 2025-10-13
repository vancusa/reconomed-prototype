// app.js
import { checkAuthentication, logout } from './auth.js';
import { Navigation } from './navigation.js';
import { PatientManager } from './patients.js';
import { DocumentManager } from './documents.js';
import { ConsultationManager } from './consultations.js';
import { showLoading, hideLoading, showToast, showModal, hideModal} from './ui.js';
import { startLiveClock } from './utils.js';
import { initDocumentTabs } from './document-manager.js';
//import { initConsultationTabs } from './consultations.js';
//import { loadPatientDocuments, renderDocuments } from './document-manager.js';
//import { handleFileSelect, setupUploadArea } from './upload-handler.js';
//import { compressImage } from './image-compression.js';


// =========================================================================
// API CONFIGURATION 
// for consistent endpoint management
// put them in alphabetical order, like in the routers folder, so that you can check easily
// =========================================================================
const API_CONFIG = {
    BASE_URL: '/api',  // Change to '/api/v1' or '/api/v2' when needed
    ENDPOINTS: {
        auth: '/auth/',
        clinics:'/clinics/',
        consultations: '/consultations/',
        dashboard: '/dashboard/',
        documents: '/documents/', 
        patients: '/patients/',
        search: '/search/'
    }
};

// Helper function to build API URLs
function apiUrl(endpoint, path = '') {
    return `${API_CONFIG.BASE_URL}${endpoint}${path}`;
}

// Export for use in other modules
window.API_CONFIG = API_CONFIG;
window.apiUrl = apiUrl;
// =========================================================================
// END API CONFIGURATION
// =========================================================================


class ReconoMedApp {
    // =========================================================================
    // CONSTRUCTOR: Object Creation Only
    // =========================================================================
    // Purpose: Create the object and set up basic properties
    // When called: Immediately when "new ReconoMedApp()" runs
    // What it does: Sets initial values, creates child objects
    // What it DOESN'T do: Touch the DOM, make network calls, or access external resources
    constructor() {
        // Basic application properties
        this.apiBase = '/';
        this.currentUser = null;
        this.patients = [];
        this.documents = [];
        this.selectedPatient = null;
        
        // Create manager instances (but don't initialize them yet)
        // These constructors should also only set properties, not touch DOM
        this.navigation = new Navigation(this);
        this.patientManager = new PatientManager(this);
        this.documentManager = new DocumentManager(this);
        this.consultationManager = new ConsultationManager(this);
    }

    // =========================================================================
    // INIT METHOD: Object Initialization
    // =========================================================================
    // Purpose: Set up the application after DOM is ready
    // When called: Manually after page loads (DOMContentLoaded)
    // What it does: Touch DOM, set up event listeners, make network calls
    async init() {
        // =====================================================================
        // STEP 1: Authentication Check (can redirect, so do this first)
        // =====================================================================
        if (!checkAuthentication(this)) {
            window.location.href = '/static/login.html';
            return; // Exit if not authenticated
        }

        // =====================================================================
        // STEP 2: UI Component Initialization (synchronous DOM setup)
        // =====================================================================
        // These methods set up event listeners and find DOM elements
        // They should be fast and not make network calls
        try {
            this.navigation.init();        // Set up nav click handlers
            this.patientManager.init();    // Set up form submissions, search
            this.documentManager.init();   // Set up upload handlers
            initDocumentTabs();            // Set up document tab switching
        } catch (err) {
            console.error('UI initialization failed:', err);
            showToast('Interface setup failed', 'error');
            return; // Don't continue if UI setup failed
        }

        // =====================================================================
        // STEP 3: Data Loading (asynchronous network calls)
        // =====================================================================
        // Load initial data from backend
        // This can be slow and might fail, so handle gracefully
        await this.loadInitialData();

        // =====================================================================
        // STEP 4: Make it pretty
        // =====================================================================
        // Start live clock to have on the dashboard
        startLiveClock('date-time');
    }

    // =========================================================================
    // DATA LOADING: Separate Async Operations
    // =========================================================================
    async loadInitialData() {
        try {
            showLoading(); // Show spinner while loading
            
            // Load patients from backend
            await this.patientManager.loadPatients();
            
            //Fetch consultation stats from backend
            const statsResponse = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, 'today/stats'));
            if (!statsResponse.ok) {
                throw new Error(`HTTP error! status: ${statsResponse.status}`);
            }
            const todayStats = await statsResponse.json(); // Data is: { "patients_today": N }

            this.updateDashboardStats(todayStats); // Pass the new stats to the update function

            // Load consultation tab counts
            await this.loadConsultationCounts(); 

        } catch (err) {
            console.error('Data loading failed:', err);
            showToast('Failed to load initial data', 'error');
            // Application still works, just without initial data
        } finally {
            hideLoading(); // Hide spinner regardless of success/failure
        }
    }

    async loadConsultationCounts() {
        try {
            const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, 'counts'));
            if (response.ok) {
                const counts = await response.json();
                document.getElementById('active-consultations').textContent = counts.active_consultations || 0;
                document.getElementById('review-pending').textContent = counts.review_pending || 0;
                document.getElementById('discharge-ready').textContent = counts.discharge_ready || 0;
            }
        } catch (err) {
            console.error('Failed to load consultation counts:', err);
        }
    }
    
    async refreshActivity() {
        try {
            const response = await fetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, 'activity/recent'));
            if (!response.ok) throw new Error('Failed to load activity');
            
            const data = await response.json();
            this.renderRecentActivity(data.activities);
        } catch (err) {
            console.error('Failed to refresh activity:', err);
            showToast('Failed to refresh activity', 'error');
        }
    }

    renderRecentActivity(activities) {
        const container = document.getElementById('recent-activity');
        if (!container) return;
        
        if (activities.length === 0) {
            container.innerHTML = '<p class="text-secondary">No recent activity</p>';
            return;
        }
        
        container.innerHTML = activities.map(activity => `
            <div class="activity-item">
                <i class="${activity.icon}"></i>
                <div class="activity-info">
                    <div class="activity-title">${activity.title}</div>
                    <div class="activity-time">${new Date(activity.timestamp).toLocaleString('ro-RO')}</div>
                </div>
            </div>
        `).join('');
    }

    // =========================================================================
    // UTILITY METHODS: Application Logic
    // =========================================================================
    updateDashboardStats(newStats) {
        // 1. Update total patients (existing logic)
        const totalPatientsEl = document.getElementById('total-patients');
        if (totalPatientsEl) {
            totalPatientsEl.textContent = this.patients.length;
        }

        // 2. NEW LOGIC: Update Patients Today
        const patientsTodayEl = document.getElementById('patients-today');
        
        // Check if the element exists AND if the data was passed in
        if (patientsTodayEl && newStats && newStats.patients_today !== undefined) {
            // Use the value from the fetched object
            patientsTodayEl.textContent = newStats.patients_today;
        }
    }

    // Method to programmatically navigate (called by HTML buttons)
    goToSection(sectionId) {
        this.navigation.navigateTo(sectionId);
    }
}

// =========================================================================
// APPLICATION STARTUP: Global Initialization
// =========================================================================
// Create the app instance (runs constructor immediately)
const app = new ReconoMedApp();

// Wait for DOM to be ready, then initialize
document.addEventListener('DOMContentLoaded', () => {
    app.init(); // This calls the async init method
});

// Make app available globally for HTML onclick handlers
window.app = app;

// =========================================================================
// GLOBAL MODAL FUNCTIONS for HTML onclick handlers
// =========================================================================
window.closeAddPatientModal = function() {
    const form = document.getElementById('add-patient-form');
    const modal = document.getElementById('add-patient-modal');
    const modalTitle = modal.querySelector('.modal-header h2');
    const submitButton = form.querySelector('button[type="submit"]');
    
    // Reset to add mode
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
    
    // Ensure we're in add mode
    modalTitle.textContent = 'Add New Patient';
    submitButton.innerHTML = '<i class="fas fa-plus"></i> Add Patient';
    form.dataset.mode = 'create';
    delete form.dataset.patientId;
    form.reset();
    
    showModal('add-patient-modal');
};

// =========================================================================
// END GLOBAL MODAL FUNCTIONS
// =========================================================================


// =========================================================================
// Global functions for view patient modal
// =========================================================================
window.closeViewPatientModal = function() {
    hideModal('view-patient-modal');
};

window.app.editPatientFromView = () => app.patientManager.editPatientFromView();
window.app.manageGDPRFromView = () => app.patientManager.manageGDPRFromView();
// =========================================================================
// END Global functions for view patient modal
// =========================================================================

// =========================================================================
// GDPR modal functions
// =========================================================================
window.closeGDPRModal = function() {
    hideModal('gdpr-modal');
};

window.closeWithdrawConsentModal = function() {
    hideModal('withdraw-consent-modal');
    document.getElementById('withdraw-consent-form').reset();
};

window.app.withdrawConsent = (type) => app.patientManager.withdrawConsent(type);
window.app.grantConsent = (type) => app.patientManager.grantConsent(type);
window.app.renewConsent = (type) => app.patientManager.renewConsent(type);
// =========================================================================
// end GDPR modal
// =========================================================================

// ========================================================================
// Navigation
// ========================================================================
window.app.nextPatientsPage = () => app.patientManager.nextPage();
window.app.previousPatientsPage = () => app.patientManager.previousPage();
// ========================================================================
//end Navigation
// ========================================================================

// ========================================================================
//Consent History
// ========================================================================
window.closeConsentHistoryModal = function() {
    hideModal('consent-history-modal');
};

window.app.exportConsentHistory = () => app.patientManager.exportConsentHistory();
// ========================================================================
//end Consent History
// ========================================================================

// Prepare for logout: Get the button element
const logoutButton = document.getElementById('logout-button');

// Add the event listener after the DOM is ready
// You can use the imported `logout` function directly.
if (logoutButton) {
    logoutButton.addEventListener('click', () => {
        // The imported 'logout' function from './auth.js' is called here
        logout(); 
    });
}