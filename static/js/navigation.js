//Nav + section switching
// navigation.js
// -----------------------------------------------------------------------------
// Handles navigation within the SPA (Single Page Application).
//
// Responsibilities:
//  - Listen to clicks on navigation links
//  - Switch visible sections dynamically (hide others)
//  - Support programmatic navigation (app.goToSection(...))
//  - Highlight the active nav link for better UX
//  - Allow role-based restrictions (nav items may be hidden in auth.js)
//
// NOTE: Assumes your HTML structure uses:
//   <a href="#" class="nav-link" data-section="patients">Patients</a>
//   <section id="patients" class="section">...</section>
//
// Convention:
//   - Each nav link has data-section="sectionId"
//   - Each section has id="sectionId"
//   - Only one section is visible at a time
// -----------------------------------------------------------------------------

import { showToast } from './ui.js';

export class Navigation {
    constructor(app) {
        this.app = app;

        // DOM references
        this.navLinks = document.querySelectorAll('.nav-link');
        this.sections = document.querySelectorAll('.content-section');
    }

    // -------------------------------------------------------------------------
    // Initialization
    // -------------------------------------------------------------------------
    init() {
        // Bind click listeners on nav links
        this.navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const target = e.currentTarget.dataset.section;
                this.navigateTo(target);
            });
        });

        // Show default section (dashboard or first nav link)
        const defaultSection = this.navLinks[0]?.dataset.section || 'dashboard';
        this.navigateTo(defaultSection);

    }

    // -------------------------------------------------------------------------
    // Core Navigation
    // -------------------------------------------------------------------------
    navigateTo(sectionId) {
        // Hide all sections
        this.sections.forEach(sec => sec.style.display = 'none');

        // Show the target section
        const targetSection = document.getElementById(sectionId);
        if (targetSection) {
            targetSection.style.display = 'block';
        } else {
            console.warn(`Section '${sectionId}' not found`);
            showToast(`Section '${sectionId}' not available`, 'error');
            return;
        }

        // Update nav link highlighting
        this.navLinks.forEach(link => {
            if (link.dataset.section === sectionId) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        // Let the app know the active section changed
        this.app.activeSection = sectionId;
    }

    // -------------------------------------------------------------------------
    // Programmatic Navigation
    // -------------------------------------------------------------------------
    goToSection(sectionId) {
        this.navigateTo(sectionId);
    }
}