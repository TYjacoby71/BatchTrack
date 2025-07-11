
// Expiration alerts integration
document.addEventListener('DOMContentLoaded', function() {
    loadExpirationSummary();
    
    // Refresh every 5 minutes
    setInterval(loadExpirationSummary, 5 * 60 * 1000);
});

function loadExpirationSummary() {
    fetch('/expiration/api/summary')
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok');
        })
        .then(data => {
            updateExpirationBadge(data.expired_total || data.expired_count);
        })
        .catch(error => {
            console.error('Failed to load expiration summary:', error);
        });
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
function checkInventoryExpiration(inventoryItemId, callback) {
    fetch(`/expiration/api/inventory-status/${inventoryItemId}`)
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok');
        })
        .then(data => {
            if (callback) callback(data);
        })
        .catch(error => {
            console.error('Failed to check inventory expiration:', error);
        });
}

// Function to check expiration status for products
function checkProductExpiration(productId, callback) {
    fetch(`/expiration/api/product-status/${productId}`)
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok');
        })
        .then(data => {
            if (callback) callback(data);
        })
        .catch(error => {
            console.error('Failed to check product expiration:', error);
        });
}
