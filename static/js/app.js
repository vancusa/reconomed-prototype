// app.js
import { checkAuthentication, logout } from './auth.js';
import { Navigation } from './navigation.js';
import { PatientManager } from './patients.js';
import { DocumentManager } from './documents.js';
import { showLoading, hideLoading, showToast, showModal, hideModal} from './ui.js';
import { startLiveClock } from './utils.js';
import { initDocumentTabs } from './document-manager.js';
import { initConsultationTabs } from './consultations.js';

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
            initConsultationTabs();        // Set up consultation tab switching
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
            
            // Update dashboard with loaded data
            this.updateDashboardStats();
            
        } catch (err) {
            console.error('Data loading failed:', err);
            showToast('Failed to load initial data', 'error');
            // Application still works, just without initial data
        } finally {
            hideLoading(); // Hide spinner regardless of success/failure
        }
    }

    // =========================================================================
    // UTILITY METHODS: Application Logic
    // =========================================================================
    updateDashboardStats() {
        // Update dashboard counters with current data
        const totalPatientsEl = document.getElementById('total-patients');
        if (totalPatientsEl) {
            totalPatientsEl.textContent = this.patients.length;
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