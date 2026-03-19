// Simplified expiration alerts system
document.addEventListener('DOMContentLoaded', function() {
    // Only load if we're on the expiration alerts page
    if (window.location.pathname.includes('/expiration/alerts')) {
        loadExpirationSummary();
        // Refresh every 5 minutes
        setInterval(loadExpirationSummary, 5 * 60 * 1000);
    }
});

async function loadExpirationSummary() {
    try {
        const response = await fetch('/expiration/api/summary');
        if (response.ok) {
            const data = await response.json();
            updateExpirationBadge(data.expired_total || 0);
        }
    } catch (error) {
        console.error('Failed to load expiration summary:', error);
    }
}

function updateExpirationBadge(count) {
    const badge = document.getElementById('expiration-badge');
    if (badge) {
        badge.textContent = count;
        badge.style.display = count > 0 ? 'inline' : 'none';
    }
}

function getCSRFToken() {
    const tokenMeta = document.querySelector('meta[name=csrf-token]');
    if (tokenMeta) return tokenMeta.getAttribute('content');

    const csrfInput = document.querySelector('input[name=csrf_token]');
    if (csrfInput) return csrfInput.value;

    return '';
}

async function requestConfirmation(options) {
    if (typeof window.showConfirmDialog === 'function') {
        return window.showConfirmDialog(options);
    }
    if (typeof window.showAlert === 'function') {
        window.showAlert('warning', 'Confirmation dialog is currently unavailable.');
    }
    return false;
}

async function markAsExpired(type, id) {
    const confirmed = await requestConfirmation({
        title: 'Mark item as expired?',
        message: 'Mark this item as expired and remove it from inventory?\n\nThis action cannot be undone. Proceed?',
        confirmText: 'Mark expired',
        confirmVariant: 'danger'
    });
    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch('/expiration/api/mark-expired', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken() 
            },
            body: JSON.stringify({ type, id })
        });

        const data = await response.json();

        if (response.ok) {
            showAlert('success', `Marked ${data.expired_count || 1} item as expired`);
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showAlert('error', data.error || 'Failed to mark item as expired');
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('error', 'Network error occurred');
    }
}

async function archiveExpired() {
    const confirmed = await requestConfirmation({
        title: 'Archive expired items?',
        message: 'Archive all expired items with zero quantity? This cannot be undone.',
        confirmText: 'Archive items',
        confirmVariant: 'danger'
    });
    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch('/expiration/api/archive-expired', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRFToken() }
        });

        const data = await response.json();

        if (response.ok) {
            showAlert('success', `Archived ${data.archived_count} expired items`);
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showAlert('error', 'Error archiving items');
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('error', 'Network error occurred');
    }
}

function showAlert(type, message) {
    if (typeof window.showAlert === 'function') {
        window.showAlert(type, message);
        return;
    }
    console.log(`[${type}] ${message}`);
}

// Safe data initialization
function safeJsonParse(data, fallback = {}) {
    try {
        return typeof data === 'string' ? JSON.parse(data) : data;
    } catch (error) {
        return fallback;
    }
}

// Initialize with safe defaults - avoid global variable conflicts
window.expirationData = window.expirationData || {};
window.productData = window.productData || {};