// Expiration alerts integration
document.addEventListener('DOMContentLoaded', function() {
    loadExpirationSummary();

    // Refresh every 5 minutes
    setInterval(loadExpirationSummary, 5 * 60 * 1000);
});

async function loadExpirationSummary() {
    try {
        const response = await fetch('/expiration/api/summary');
        if (response.ok) {
            const data = await response.json();
            updateExpirationBadge(data.expired_total);
        }
    } catch (error) {
        console.error('Failed to load expiration summary:', error);
    }
}

function updateExpirationBadge(count) {
    const badge = document.getElementById('expiration-badge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count;
            badge.style.display = 'inline';
        } else {
            badge.style.display = 'none';
        }
    }
}

// Function to check expiration status for inventory items
async function checkInventoryExpiration(inventoryItemId, callback) {
    try {
        const response = await fetch(`/expiration/api/inventory-status/${inventoryItemId}`);
        if (response.ok) {
            const data = await response.json();
            if (callback) callback(data);
        }
    } catch (error) {
        console.error('Failed to check inventory expiration:', error);
    }
}

// Function to check expiration status for products
async function checkProductExpiration(productId, callback) {
    try {
        const response = await fetch(`/expiration/api/product-status/${productId}`);
        if (response.ok) {
            const data = await response.json();
            if (callback) callback(data);
        }
    } catch (error) {
        console.error('Failed to check product expiration:', error);
    }
}

// Auto-refresh expiration data
function refreshExpirationData() {
    fetch('/expiration/api/expiration-summary')
        .then(response => response.json())
        .then(data => {
            console.log('Expiration summary loaded:', data);
            updateExpirationCounts(data);
        })
        .catch(error => {
            console.error('Failed to load expiration summary:', error);
        });
}

function updateExpirationCounts(data) {
    // Update badge counts
    const expiredBadge = document.querySelector('[data-expired-count]');
    const expiringSoonBadge = document.querySelector('[data-expiring-count]');

    if (expiredBadge && data.expired_count !== undefined) {
        expiredBadge.textContent = data.expired_count;
        expiredBadge.style.display = data.expired_count > 0 ? 'inline' : 'none';
    }

    if (expiringSoonBadge && data.expiring_soon_count !== undefined) {
        expiringSoonBadge.textContent = data.expiring_soon_count;
        expiringSoonBadge.style.display = data.expiring_soon_count > 0 ? 'inline' : 'none';
    }
}

// Mark item as expired
function markAsExpired(itemType, itemId) {
    if (!confirm('Are you sure you want to mark this item as expired?')) {
        return;
    }

    fetch('/expiration/api/mark-expired', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            type: itemType,
            id: itemId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('success', data.message || 'Item marked as expired successfully');
            // Reload the page to update the display
            window.location.reload();
        } else {
            showAlert('error', data.error || 'Failed to mark item as expired');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('error', 'An error occurred while marking the item as expired');
    });
}

// Archive expired items
function archiveExpired() {
    if (!confirm('Archive all expired items with zero quantity?')) {
        return;
    }

    fetch('/expiration/api/archive-expired', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        showAlert('success', 'Archived ' + data.archived_count + ' expired items');
        // Reload to update display
        setTimeout(() => window.location.reload(), 1000);
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('error', 'Failed to archive expired items');
    });
}

// Show alert helper
function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-' + (type === 'success' ? 'success' : 'danger') + ' alert-dismissible fade show';
    alertDiv.innerHTML = message + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';

    // Insert at top of main content
    const mainContent = document.querySelector('.container-fluid') || document.body;
    mainContent.insertBefore(alertDiv, mainContent.firstChild);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Only refresh if we're on the expiration alerts page
    if (window.location.pathname.includes('/expiration/alerts')) {
        refreshExpirationData();
        // Set up periodic refresh
        setInterval(refreshExpirationData, 30000); // Every 30 seconds
    }
});