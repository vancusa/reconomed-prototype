// consultations.js
// ES Module version
// Handles fetching, rendering, and validation of consultations

import { showToast } from './ui.js';

/**
 * Initialize consultation tabs and their switching logic
 */
export function initConsultationTabs() {
    const tabButtons = document.querySelectorAll('.consultation-tabs .tab-button');
    const tabContents = document.querySelectorAll('.consultation-tabs .tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.dataset.tab;
            
            // Remove active from all consultation tab buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active to clicked button and corresponding content
            button.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
            
            // Load content for the active consultation tab
            loadConsultationTabContent(targetTab);
        });
    });
}

/**
 * Load content based on active consultation tab
 * @param {string} tabName - Name of the consultation tab to load
 */
function loadConsultationTabContent(tabName) {
    switch(tabName) {
        case 'new-consultation':
            loadPatientListForConsultation();
            break;
        case 'patient-review':
            setupPatientReviewSearch();
            break;
        case 'discharge':
            loadPendingDischargeConsultations();
            break;
        default:
            console.log(`Loading content for ${tabName} tab`);
    }
    
    // Update consultation tab counts
    updateConsultationTabCounts();
}

/**
 * Load patients for consultation dropdown
 */
async function loadPatientListForConsultation() {
    try {
        const response = await fetch('/api/patients/');
        if (!response.ok) throw new Error('Failed to load patients');
        
        const patients = await response.json();
        const select = document.getElementById('consultation-patient');
        
        if (select) {
            select.innerHTML = '<option value="">Choose a patient...</option>' +
                patients.map(patient => 
                    `<option value="${patient.id}">${patient.given_name} ${patient.family_name}</option>`
                ).join('');
        }
    } catch (error) {
        console.error('Failed to load patients for consultation:', error);
        showToast('Failed to load patient list', 'error');
    }
}

/**
 * Setup patient review search functionality
 */
function setupPatientReviewSearch() {
    const searchInput = document.getElementById('review-patient-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(async (e) => {
            const query = e.target.value.trim();
            if (query.length >= 2) {
                await searchPatientsForReview(query);
            }
        }, 300));
    }
}

/**
 * Search patients for review
 */
async function searchPatientsForReview(query) {
    try {
        const response = await fetch(`/api/patients/?search=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error('Failed to search patients');
        
        const patients = await response.json();
        renderPatientReviewResults(patients);
    } catch (error) {
        console.error('Failed to search patients:', error);
        showToast('Failed to search patients', 'error');
    }
}

/**
 * Load consultations pending discharge
 */
async function loadPendingDischargeConsultations() {
    try {
        const response = await fetch('/api/consultations/pending-discharge');
        if (!response.ok) throw new Error('Failed to load pending discharge consultations');
        
        const consultations = await response.json();
        renderDischargeConsultations(consultations);
    } catch (error) {
        console.error('Failed to load discharge consultations:', error);
        showToast('Failed to load discharge consultations', 'error');
    }
}

/**
 * Update consultation tab count badges
 */
function updateConsultationTabCounts() {
    // Placeholder - update these with real data
    document.getElementById('active-consultations').textContent = '0';
    document.getElementById('review-pending').textContent = '0';
    document.getElementById('discharge-ready').textContent = '0';
}

// Utility function for search debouncing
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Placeholder render functions
function renderPatientReviewResults(patients) {
    const container = document.getElementById('review-results');
    if (container) {
        container.innerHTML = patients.length ? 
            patients.map(p => `<p>${p.given_name} ${p.family_name}</p>`).join('') :
            '<p>No patients found</p>';
    }
}

function renderDischargeConsultations(consultations) {
    const container = document.getElementById('patient-consultations');
    if (container) {
        container.innerHTML = consultations.length ? 
            '<p>Discharge consultations will be displayed here</p>' :
            '<p>No consultations ready for discharge</p>';
    }
}