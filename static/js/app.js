// app.js
import { checkAuthentication, logout } from './auth.js';
import { Navigation } from './navigation.js';
import { PatientManager } from './patients.js';
import { DocumentManager } from './documents.js';
import { ConsultationManager } from './consultations.js';
import { showLoading, hideLoading, showToast, showModal, hideModal} from './ui.js';
import { startLiveClock } from './utils.js';
import { ClinicManager } from './clinics.js';   

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
        consultationCounts: '/consultations/counts',
        dashboard: '/dashboard/',
        documents: '/documents/', 
        patients: '/patients/',
        search: '/search/'
    }  
};

/**
 * Builds API URLs with path parameter substitution and trailing slash handling.
 * Strips trailing slashes before query strings to avoid 307 redirects in Codespaces.
 */
function apiUrl(endpoint, path = '', params = {}) {
    let url = `${API_CONFIG.BASE_URL}${endpoint}`;
    
    // 1. Substitute path parameters (like :clinicId)
    if (params.clinicId) {
        url = url.replace(':clinicId', params.clinicId);
    }
    
    // 2. Strip trailing slash if path starts with query string (prevents 307 redirects)
    if (path.startsWith('?')) {
        url = url.replace(/\/$/, '');
    }
    
    // 3. Append the rest of the path
    return `${url}${path}`;
}

function apiFetch(input, init = {}) {
  return fetch(input, withUserHeader(init));
}

// Export for ES modules
export { API_CONFIG, apiUrl, apiFetch };

// Keep backward compatibility for legacy scripts
if (typeof window !== 'undefined') {
  window.API_CONFIG = API_CONFIG;
  window.apiUrl = apiUrl;
  window.apiFetch = apiFetch;
}

// =========================================================================
// Request helpers: ensure X-User header is present for backend context
// =========================================================================
function getStoredUserEmail() {
  if (typeof window === 'undefined') return null;
  // Prefer the hydrated app instance
  if (window.app?.currentUser?.email) return window.app.currentUser.email;

  // Fallback to localStorage (used by login screen)
  try {
    const raw = localStorage.getItem('reconomed_user');
    if (raw) {
      const parsed = JSON.parse(raw);
      return parsed?.email || parsed?.username || null;
    }
  } catch (e) {
    // ignore parsing errors, return null
  }
  return null;
}

function withUserHeader(init = {}) {
  const headers = new Headers(init.headers || {});
  const email = getStoredUserEmail();

  if (email && !headers.has('X-User')) {
    headers.set('X-User', email);
  }

  return { ...init, headers };
}

// Patch fetch globally to always include X-User unless already provided
if (typeof window !== 'undefined' && window.fetch && !window._reconomedFetchPatched) {
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init) => originalFetch(input, withUserHeader(init));
  window._reconomedFetchPatched = true;
}
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
        this.clinicManager = new ClinicManager();
        this.dashboardPollingId = null;
        this.dashboardPollingIntervalMs = 3000;
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
        // STEP 2: Load Clinic Data (needed by all managers)
        // =====================================================================
        try {
            await this.clinicManager.loadClinicData();
            window.clinicManager = this.clinicManager; // Make globally available
        } catch (err) {
            console.error('Clinic data loading failed:', err);
            showToast('Failed to load clinic information', 'error');
            return; // Can't proceed without clinic data
        }

        // =====================================================================
        // STEP 3: UI Component Initialization (synchronous DOM setup)
        // =====================================================================
        // These methods set up event listeners and find DOM elements
        // They should be fast and not make network calls
        try {
            this.navigation.init();        // Set up nav click handlers
            this.patientManager.init();    // Set up form submissions, search
            await this.documentManager.init();   // Set up upload handlers
            this.consultationManager.init(); // Set up consultation event listeners
           } catch (err) {
            console.error('UI initialization failed:', err);
            showToast('Interface setup failed', 'error');
            return; // Don't continue if UI setup failed
        }

        // =====================================================================
        // STEP 4: Data Loading (asynchronous network calls)
        // =====================================================================
        // Load initial data from backend
        // This can be slow and might fail, so handle gracefully
        await this.loadInitialData();

        // =====================================================================
        // STEP 5: Make it pretty
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
            this.updateDashboardStats();
            await this.loadTodayConsultations();

        } catch (err) {
            console.error('Data loading failed:', err);
            showToast('Failed to load initial data', 'error');
            // Application still works, just without initial data
        } finally {
            hideLoading(); // Hide spinner regardless of success/failure
        }
    }

    async refreshActivity() {
        await this.loadTodayConsultations();
    }

    handleSectionChange(sectionId) {
        if (sectionId === 'dashboard') {
            this.startDashboardPolling();
        } else {
            this.stopDashboardPolling();
        }
        this.documentManager?.nav?.handleSectionChange?.(sectionId);
    }

    startDashboardPolling() {
        if (this.dashboardPollingId) return;
        this.loadTodayConsultations();
        this.dashboardPollingId = setInterval(() => {
            if (this.activeSection !== 'dashboard') return;
            this.loadTodayConsultations();
        }, this.dashboardPollingIntervalMs);
    }

    stopDashboardPolling() {
        if (!this.dashboardPollingId) return;
        clearInterval(this.dashboardPollingId);
        this.dashboardPollingId = null;
    }

    // =========================================================================
    // UTILITY METHODS: Application Logic
    // =========================================================================
    updateDashboardStats() {
        // 1. Update total patients (existing logic)
        const totalPatientsEl = document.getElementById('total-patients');
        if (totalPatientsEl) {
            totalPatientsEl.textContent = this.patients.length;
        }
    }

    async loadTodayConsultations() {
        try {
            const queueRes = await apiFetch(apiUrl(API_CONFIG.ENDPOINTS.consultations, 'today/queue'));
            if (!queueRes.ok) throw new Error('Failed to load today consultations');
            const queue = await queueRes.json();

            const validationRes = await apiFetch(apiUrl(API_CONFIG.ENDPOINTS.documents, 'uploads?tab=validation'));
            if (!validationRes.ok) throw new Error('Failed to load validation uploads');
            const validationData = await validationRes.json();
            const validationCount = validationData?.items?.length || 0;

            this.updateDashboardTodayCards(queue, validationCount);
            this.renderTodayConsultations(queue);
        } catch (err) {
            console.error('Failed to load today consultations:', err);
        }
    }

    updateDashboardTodayCards(queue, validationCount) {
        const doneEl = document.getElementById('consults-done-today');
        if (doneEl) doneEl.textContent = queue?.completed?.length ?? 0;

        const remainingEl = document.getElementById('consults-remaining-today');
        if (remainingEl) remainingEl.textContent = queue?.remaining?.length ?? 0;

        const validationEl = document.getElementById('docs-needing-validation');
        if (validationEl) validationEl.textContent = validationCount ?? 0;
    }

    renderTodayConsultations(queue) {
        const remainingContainer = document.getElementById('today-consultations-remaining');
        const completedContainer = document.getElementById('today-consultations-completed');
        if (!remainingContainer || !completedContainer) return;

        const remaining = queue?.remaining || [];
        const completed = queue?.completed || [];

        remainingContainer.innerHTML = this.buildConsultationList(remaining, 'No remaining consultations today.');
        completedContainer.innerHTML = this.buildConsultationList(completed, 'No completed consultations yet.');
    }

    buildConsultationList(items, emptyMessage) {
        if (!items.length) {
            return `<div class="empty-message">${emptyMessage}</div>`;
        }
        return items.map(item => {
            const timeText = item.consultation_date
                ? new Date(item.consultation_date).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
                : 'No time';
            const statusText = (item.status || '').replace('_', ' ');
            return `
                <div class="consultation-item">
                    <div class="consultation-item__info">
                        <div class="consultation-item__title">${item.patient_name}</div>
                        <div class="consultation-item__meta">${item.specialty} · ${timeText}</div>
                    </div>
                    <span class="consultation-item__status">${statusText || 'status'}</span>
                </div>
            `;
        }).join('');
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
window.consultationManager = app.consultationManager;
window.clinicManager = app.clinicManager;
window.documentManager = app.DocumentManager;


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
