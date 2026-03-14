// navigation.js
// Handles SPA section switching and navigation events.

import { showToast } from './ui.js';

export class Navigation {
    constructor(app) {
        this.app = app;
        this.navLinks = document.querySelectorAll('.nav-link');
        this.sections = document.querySelectorAll('.content-section');
    }

    init() {
        this.navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const target = e.currentTarget.dataset.section;
                this.navigateTo(target);
            });
        });

        // Default to agenda
        const defaultSection = 'agenda';
        this.navigateTo(defaultSection);
    }

    navigateTo(sectionId) {
        // Hide all sections
        this.sections.forEach(sec => sec.style.display = 'none');

        // Show target section
        const targetSection = document.getElementById(sectionId);
        if (targetSection) {
            targetSection.style.display = 'block';
        } else {
            console.warn(`Section '${sectionId}' not found`);
            showToast(`Section '${sectionId}' not available`, 'error');
            return;
        }

        // Update nav link highlighting (consult section has no nav link)
        this.navLinks.forEach(link => {
            if (link.dataset.section === sectionId) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        this.app.activeSection = sectionId;

        // Fire custom event for managers to hook into
        document.dispatchEvent(new CustomEvent('section-changed', {
            detail: { section: sectionId }
        }));
    }

    goToSection(sectionId) {
        this.navigateTo(sectionId);
    }
}
