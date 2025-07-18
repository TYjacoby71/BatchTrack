// Expiration alerts integration
document.addEventListener('DOMContentLoaded', function() {
    loadExpirationSummary();

    // Refresh every 5 minutes
    setInterval(loadExpirationSummary, 5 * 60 * 1000);
});

function loadExpirationSummary() {
    fetch('/api/expiration-summary')
        .then(response => response.json())
        .then(data => {
            updateExpirationSummary(data);
        })
        .catch(error => {
            console.error('Failed to load expiration summary:', error);
        });
}

function updateExpirationSummary(data) {
    const container = document.getElementById('expiration-summary-container');
    if (!container) return;

    // Update summary counts with safe element access
    const expiredCountEl = document.getElementById('expired-count');
    const expiringSoonCountEl = document.getElementById('expiring-soon-count');

    if (expiredCountEl) {
        expiredCountEl.textContent = data.expired_count || 0;
    }
    if (expiringSoonCountEl) {
        expiringSoonCountEl.textContent = data.expiring_soon_count || 0;
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