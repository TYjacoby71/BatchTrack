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

async function markAsExpired(type, id) {
    if (!confirm('Mark this item as expired and remove it from inventory?\n\nThis action cannot be undone. Proceed?')) {
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
    if (!confirm('Archive all expired items with zero quantity? This cannot be undone.')) {
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
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show`;
    alertDiv.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;

    const mainContent = document.querySelector('.container-fluid') || document.body;
    mainContent.insertBefore(alertDiv, mainContent.firstChild);

    setTimeout(() => alertDiv.remove(), 5000);
}

// Safe data initialization
function safeJsonParse(data, fallback = {}) {
    try {
        return typeof data === 'string' ? JSON.parse(data) : data;
    } catch {
        return fallback;
    }
}

// Initialize with safe defaults - avoid global variable conflicts
window.expirationData = window.expirationData || {};
window.productData = window.productData || {};