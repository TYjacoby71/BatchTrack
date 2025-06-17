/**
 * Batch-aware expiration management for product views
 */

function loadExpirationData(inventoryId, containerId) {
    fetch(`/expiration/api/product-inventory/${inventoryId}/expiration`)
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById(containerId);
            if (!container) return;

            if (!data.is_perishable) {
                container.innerHTML = '<span class="text-muted">Non-perishable</span>';
                return;
            }

            const expirationDate = new Date(data.expiration_date);
            const daysUntil = data.days_until_expiration;

            let badgeClass = 'bg-success';
            let icon = 'fas fa-check-circle';

            if (data.is_expired) {
                badgeClass = 'bg-danger';
                icon = 'fas fa-exclamation-triangle';
            } else if (daysUntil <= 7) {
                badgeClass = 'bg-warning text-dark';
                icon = 'fas fa-clock';
            }

            container.innerHTML = `
                <span class="badge ${badgeClass}">
                    <i class="${icon} me-1"></i>
                    ${expirationDate.toLocaleDateString()} 
                    (${daysUntil} days)
                </span>
            `;
        })
        .catch(error => {
            console.error('Error loading expiration data:', error);
            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = '<span class="text-muted">Error loading expiration</span>';
            }
        });
}

// Auto-load expiration data for elements with data-inventory-id
document.addEventListener('DOMContentLoaded', function() {
    // Only run if we're on a page that actually has expiration elements
    const expirationElements = document.querySelectorAll('[data-inventory-id]');
    if (expirationElements.length === 0) {
        return; // Exit early if no expiration elements found
    }

    expirationElements.forEach(element => {
        const inventoryId = element.getAttribute('data-inventory-id');
        const containerId = element.id;
        if (inventoryId && containerId) {
            loadExpirationData(inventoryId, containerId);
        }
    });
});

// Check if we're on a product view page
if (window.location.pathname.includes('/products/') && window.location.pathname.includes('/view')) {
    document.addEventListener('DOMContentLoaded', function() {
        // Only run expiration check on product view pages if the page has the required elements
        const productContainer = document.querySelector('[data-product-id]');
        if (productContainer) {
            checkProductExpiration();
        }
    });
}