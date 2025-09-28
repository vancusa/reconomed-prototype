//UI helpers (toast, loading, modal)
// ui.js

// ---------- Loading ----------
export function showLoading() {
    document.getElementById('loading')?.classList.add('active');
}

export function hideLoading() {
    document.getElementById('loading')?.classList.remove('active');
}

// ---------- Toasts ----------
export function showToast(message, type = 'info') {
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

// ---------- Modals ----------
export function showModal(id) {
    document.getElementById(id)?.classList.add('active');
}

export function hideModal(id) {
    document.getElementById(id)?.classList.remove('active');
}

// ---------- Stats & Counters ----------
export function updateStatCard(elementId, value) {
    const card = document.getElementById(elementId);
    const statCard = card?.closest('.stat-card');
    
    if (!card || !statCard) return;

    if (value === 0 || value === '-') {
        statCard.setAttribute('data-count', '0');
    } else {
        statCard.removeAttribute('data-count');
        card.textContent = value;
    }
}

export function setTabCount(elementId, count) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = count;
        element.setAttribute('data-count', count);
    }
}