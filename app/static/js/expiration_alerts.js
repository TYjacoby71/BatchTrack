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