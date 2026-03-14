// agenda.js
// AgendaManager - Primary working screen for doctors.
// Shows today's scheduled patients and past unfinished consultations.

import { showToast } from './ui.js';

export class AgendaManager {
    constructor(app) {
        this.app = app;
        this.currentDate = new Date();
        this.todayItems = [];
        this.attentionItems = [];
        this.searchTimeout = null;
        this.deleteTargetId = null;
    }

    init() {
        // Date navigator buttons
        document.getElementById('agenda-prev')?.addEventListener('click', () => this.navigateDate(-1));
        document.getElementById('agenda-next')?.addEventListener('click', () => this.navigateDate(1));
        document.getElementById('agenda-today-btn')?.addEventListener('click', () => this.goToToday());

        // Add Patient button
        document.getElementById('agenda-add-patient')?.addEventListener('click', () => this.showAddPatientOverlay());

        // Patient search in overlay
        const searchInput = document.getElementById('agenda-patient-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => this.searchPatients(e.target.value), 300);
            });
        }

        // Delete confirmation
        document.getElementById('confirm-delete-consult')?.addEventListener('click', () => this.confirmDelete());

        // Reload agenda when section becomes visible
        document.addEventListener('section-changed', (e) => {
            if (e.detail.section === 'agenda') {
                this.loadAgenda();
            }
        });

        // Set doctor name
        this.updateDoctorName();
        this.updateDateDisplay();
    }

    updateDoctorName() {
        const el = document.getElementById('agenda-doctor-name');
        if (el && this.app.currentUser) {
            el.textContent = `Dr. ${this.app.currentUser.full_name || this.app.currentUser.name || ''}`;
        }
    }

    updateDateDisplay() {
        const el = document.getElementById('agenda-date-display');
        if (el) {
            const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            el.textContent = this.currentDate.toLocaleDateString('ro-RO', options);
        }
    }

    navigateDate(offset) {
        this.currentDate.setDate(this.currentDate.getDate() + offset);
        this.updateDateDisplay();
        this.loadAgenda();
    }

    goToToday() {
        this.currentDate = new Date();
        this.updateDateDisplay();
        this.loadAgenda();
    }

    formatDateParam() {
        const d = this.currentDate;
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }

    async loadAgenda() {
        try {
            const [todayRes, attentionRes] = await Promise.all([
                fetch(`/api/consultations/agenda?date=${this.formatDateParam()}`),
                fetch('/api/consultations/agenda/needs-attention')
            ]);

            if (todayRes.ok) {
                this.todayItems = await todayRes.json();
            } else {
                this.todayItems = [];
            }

            if (attentionRes.ok) {
                this.attentionItems = await attentionRes.json();
            } else {
                this.attentionItems = [];
            }

            this.renderToday();
            this.renderAttention();
        } catch (err) {
            console.error('Failed to load agenda:', err);
            showToast('Failed to load agenda', 'error');
        }
    }

    getUserRole() {
        return this.app.currentUser?.role || 'doctor';
    }

    renderToday() {
        const container = document.getElementById('agenda-list');
        if (!container) return;

        if (this.todayItems.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No consultations scheduled</p></div>';
            return;
        }

        const isDoctor = this.getUserRole() === 'doctor' || this.getUserRole() === 'admin';

        container.innerHTML = this.todayItems.map(item => {
            const time = this.formatTime(item.consultation_date);
            const stateClass = this.getStateClass(item);
            const stateIndicator = this.getStateIndicator(item);
            const specialtyLabel = this.getSpecialtyLabel(item.specialty);

            return `
                <div class="agenda-row ${stateClass}" data-id="${item.id}" data-patient-id="${item.patient_id}">
                    <span class="agenda-time">${time}</span>
                    <span class="agenda-patient-name">${item.patient_name}</span>
                    <span class="agenda-specialty">${specialtyLabel}</span>
                    <span class="agenda-state">${stateIndicator}</span>
                    ${isDoctor ? `
                        <div class="agenda-row-actions">
                            <button class="btn-icon btn-sm agenda-action-menu" title="Actions">
                                <i class="fas fa-ellipsis-v"></i>
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

        // Bind click handlers
        container.querySelectorAll('.agenda-row').forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.closest('.agenda-action-menu') || e.target.closest('.agenda-context-menu')) return;
                this.openConsult(row.dataset.id);
            });
        });

        // Bind action menu (three-dot) for doctors
        if (isDoctor) {
            container.querySelectorAll('.agenda-action-menu').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const row = btn.closest('.agenda-row');
                    this.showContextMenu(e, row);
                });
            });
        }
    }

    renderAttention() {
        const container = document.getElementById('attention-list');
        if (!container) return;

        if (this.attentionItems.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>All caught up</p></div>';
            return;
        }

        container.innerHTML = this.attentionItems.map(item => {
            const origDate = this.formatShortDate(item.consultation_date);
            const specialtyLabel = this.getSpecialtyLabel(item.specialty);

            return `
                <div class="agenda-row attention-row" data-id="${item.id}">
                    <span class="agenda-time attention-date">${origDate}</span>
                    <span class="agenda-patient-name">${item.patient_name}</span>
                    <span class="agenda-specialty">${specialtyLabel}</span>
                    <span class="agenda-state"><span class="attention-dot"></span></span>
                </div>
            `;
        }).join('');

        container.querySelectorAll('.agenda-row').forEach(row => {
            row.addEventListener('click', () => this.openConsult(row.dataset.id));
        });
    }

    getStateClass(item) {
        if (item.status === 'in_progress') return 'state-in-progress';
        if (item.status === 'pending_review') return 'state-pending-review';
        if (item.status === 'completed') return 'state-completed';
        return '';
    }

    getStateIndicator(item) {
        if (item.status === 'in_progress') return '<span class="state-icon state-icon-active" title="In progress">&#9673;</span>';
        if (item.status === 'pending_review') return '<span class="attention-dot" title="Needs attention"></span>';
        if (item.status === 'completed' && item.has_discharge) return '<span class="state-icon state-icon-done" title="Completed with discharge">&#10003; &#128196;</span>';
        if (item.status === 'completed') return '<span class="state-icon state-icon-done" title="Completed">&#10003;</span>';
        return '';
    }

    formatTime(dateStr) {
        if (!dateStr) return '\u2014';
        const d = new Date(dateStr);
        const h = String(d.getHours()).padStart(2, '0');
        const m = String(d.getMinutes()).padStart(2, '0');
        if (h === '00' && m === '00') return '\u2014';
        return `${h}:${m}`;
    }

    formatShortDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
    }

    getSpecialtyLabel(specialty) {
        const labels = {
            'internal_medicine': 'Med. Internă',
            'cardiology': 'Cardiologie',
            'respiratory': 'Pneumologie',
            'gynecology': 'Ginecologie'
        };
        return labels[specialty] || specialty || '';
    }

    // Context menu for row actions
    showContextMenu(e, row) {
        // Remove any existing context menus
        document.querySelectorAll('.agenda-context-menu').forEach(m => m.remove());

        const item = this.todayItems.find(i => i.id === row.dataset.id) ||
                     this.attentionItems.find(i => i.id === row.dataset.id);
        if (!item) return;

        const menu = document.createElement('div');
        menu.className = 'agenda-context-menu';

        let menuItems = '';
        if (item.status === 'completed') {
            menuItems += `<button class="context-menu-item" data-action="amend"><i class="fas fa-edit"></i> Amend</button>`;
        }
        if (item.status !== 'completed') {
            menuItems += `<button class="context-menu-item context-menu-danger" data-action="delete"><i class="fas fa-trash"></i> Delete</button>`;
        }

        menu.innerHTML = menuItems;

        // Position near the button
        const rect = e.target.closest('.agenda-action-menu').getBoundingClientRect();
        menu.style.position = 'fixed';
        menu.style.top = `${rect.bottom + 4}px`;
        menu.style.left = `${rect.left - 100}px`;
        menu.style.zIndex = '1000';

        document.body.appendChild(menu);

        menu.querySelectorAll('.context-menu-item').forEach(btn => {
            btn.addEventListener('click', (ev) => {
                ev.stopPropagation();
                const action = btn.dataset.action;
                menu.remove();
                if (action === 'delete') this.showDeleteModal(item.id);
                if (action === 'amend') this.amendConsult(item.id);
            });
        });

        // Close on click outside
        const closeMenu = (ev) => {
            if (!menu.contains(ev.target)) {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            }
        };
        setTimeout(() => document.addEventListener('click', closeMenu), 10);
    }

    showDeleteModal(consultationId) {
        this.deleteTargetId = consultationId;
        document.getElementById('delete-consult-modal')?.classList.add('active');
    }

    closeDeleteModal() {
        this.deleteTargetId = null;
        document.getElementById('delete-consult-modal')?.classList.remove('active');
    }

    async confirmDelete() {
        if (!this.deleteTargetId) return;
        try {
            const res = await fetch(`/api/consultations/${this.deleteTargetId}`, { method: 'DELETE' });
            if (res.ok) {
                showToast('Consultation deleted', 'success');
                this.closeDeleteModal();
                await this.loadAgenda();
            } else {
                const data = await res.json();
                showToast(data.detail || 'Failed to delete', 'error');
            }
        } catch (err) {
            showToast('Failed to delete consultation', 'error');
        }
    }

    async amendConsult(consultationId) {
        try {
            const res = await fetch(`/api/consultations/${consultationId}/amend`, { method: 'POST' });
            if (res.ok) {
                showToast('Consultation reopened for amendment', 'info');
                this.openConsult(consultationId);
            } else {
                const data = await res.json();
                showToast(data.detail || 'Failed to amend', 'error');
            }
        } catch (err) {
            showToast('Failed to amend consultation', 'error');
        }
    }

    openConsult(consultationId) {
        if (this.app.consultationManager) {
            this.app.consultationManager.loadConsultation(consultationId);
        }
        this.app.navigation.navigateTo('consult');
    }

    // --- Add Patient Overlay ---
    showAddPatientOverlay() {
        document.getElementById('add-to-agenda-modal')?.classList.add('active');
        const input = document.getElementById('agenda-patient-search');
        if (input) {
            input.value = '';
            input.focus();
        }
        document.getElementById('agenda-patient-results').innerHTML =
            '<div class="empty-state"><p>Type to search for a patient</p></div>';
    }

    closeAddPatientOverlay() {
        document.getElementById('add-to-agenda-modal')?.classList.remove('active');
    }

    async searchPatients(query) {
        const container = document.getElementById('agenda-patient-results');
        if (!container) return;

        if (!query || query.length < 2) {
            container.innerHTML = '<div class="empty-state"><p>Type to search for a patient</p></div>';
            return;
        }

        try {
            const res = await fetch(`/api/patients?search=${encodeURIComponent(query)}&per_page=10`);
            if (!res.ok) throw new Error('Search failed');
            const data = await res.json();
            const patients = data.patients || data;

            if (patients.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>No patients found</p>
                        <a href="#" class="agenda-add-new-patient-link">Add new patient</a>
                    </div>
                `;
                container.querySelector('.agenda-add-new-patient-link')?.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.closeAddPatientOverlay();
                    if (window.showAddPatientModal) window.showAddPatientModal();
                });
                return;
            }

            container.innerHTML = patients.map(p => `
                <div class="agenda-search-result" data-patient-id="${p.id}">
                    <span class="result-name">${p.given_name} ${p.family_name}</span>
                    <span class="result-detail">${p.cnp || ''} ${p.phone || ''}</span>
                </div>
            `).join('') + `
                <div class="agenda-search-result add-new">
                    <span class="result-name"><i class="fas fa-plus"></i> Add new patient</span>
                </div>
            `;

            container.querySelectorAll('.agenda-search-result[data-patient-id]').forEach(el => {
                el.addEventListener('click', () => this.addPatientToAgenda(el.dataset.patientId));
            });

            container.querySelector('.agenda-search-result.add-new')?.addEventListener('click', () => {
                this.closeAddPatientOverlay();
                if (window.showAddPatientModal) window.showAddPatientModal();
            });

        } catch (err) {
            console.error('Patient search error:', err);
            container.innerHTML = '<div class="empty-state"><p>Search failed</p></div>';
        }
    }

    async addPatientToAgenda(patientId) {
        try {
            // Get doctor's first specialty
            const specialty = this.app.currentUser?.specialties?.[0] || 'internal_medicine';

            const res = await fetch('/api/consultations/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ patient_id: patientId, specialty: specialty })
            });

            if (!res.ok) {
                const data = await res.json();
                showToast(data.detail || 'Failed to create consultation', 'error');
                return;
            }

            const consultation = await res.json();
            this.closeAddPatientOverlay();
            showToast('Patient added to agenda', 'success');
            this.openConsult(consultation.id);
        } catch (err) {
            showToast('Failed to add patient', 'error');
        }
    }

    // Start consult from Patients section
    async startConsultFromPatient(patientId) {
        try {
            const specialty = this.app.currentUser?.specialties?.[0] || 'internal_medicine';

            const res = await fetch('/api/consultations/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ patient_id: patientId, specialty: specialty })
            });

            if (!res.ok) {
                const data = await res.json();
                showToast(data.detail || 'Failed to start consultation', 'error');
                return;
            }

            const consultation = await res.json();
            showToast('Consultation started', 'success');
            this.openConsult(consultation.id);
        } catch (err) {
            showToast('Failed to start consultation', 'error');
        }
    }
}
