//Authentication handling
// auth.js
import { showModal, hideModal } from './ui.js';

// ---------- Authentication ----------
export function checkAuthentication(app) {
    const user = localStorage.getItem('reconomed_user');
    if (!user) return false;

    try {
        app.currentUser = JSON.parse(user);
        applyRoleBasedAccess(app.currentUser.role);
        updateUserInterface(app.currentUser);
        return true;
    } catch (e) {
        localStorage.removeItem('reconomed_user');
        return false;
    }
}

export function logout() {
    
    localStorage.removeItem('reconomed_user');
    window.location.href = '/static/login.html';
}

// ---------- Role Helpers ----------
function updateUserInterface(user) {
    const userNameEl = document.querySelector('.user-name');
    const userRoleEl = document.querySelector('.user-role');

    if (userNameEl && userRoleEl) {
        userNameEl.textContent = user.name || 'User';
        userRoleEl.textContent = getRoleDisplayName(user.role);
    }
}

function getRoleDisplayName(role) {
    const roleMap = {
        doctor: 'Doctor',
        nurse: 'Nurse',
        admin: 'Administrator',
        billing: 'Billing Clerk',
    };
    return roleMap[role] || 'User';
}

function applyRoleBasedAccess(role) {
    // ----- Navigation -----
    const navLinks = document.querySelectorAll('.nav-link');
    const rolePermissions = {
        doctor: ['dashboard', 'patients', 'documents', 'consultations'],
        nurse: ['dashboard', 'patients', 'documents'],
        admin: ['dashboard', 'patients', 'documents', 'consultations'],
        billing: ['dashboard', 'patients'],
    };
    const allowedSections = rolePermissions[role] || ['dashboard'];

    navLinks.forEach(link => {
        const section = link.dataset.section;
        if (!allowedSections.includes(section)) {
            link.style.display = 'none';
        }
    });

    // ----- Admin-only features -----
    if (role !== 'admin') {
        document.querySelectorAll('.admin-only')
            .forEach(el => el.style.display = 'none');
    }

    // ----- Billing restrictions -----
    if (role === 'billing') {
        const uploadArea = document.getElementById('upload-area');
        if (uploadArea) uploadArea.style.display = 'none';
    }
}