/**
 * Product inventory management JavaScript
 */

// Load variants for a product
function loadVariants(productId, targetSelectId) {
    if (!productId) {
        const targetSelect = document.getElementById(targetSelectId);
        if (targetSelect) {
            targetSelect.innerHTML = '<option value="">Select Variant</option>';
        }
        return;
    }

    fetch(`/api/products/${productId}/variants`)
        .then(response => response.json())
        .then(variants => {
            const targetSelect = document.getElementById(targetSelectId);
            if (targetSelect) {
                targetSelect.innerHTML = '<option value="">Select Variant</option>';
                variants.forEach(variant => {
                    const option = document.createElement('option');
                    option.value = variant.id;
                    option.textContent = variant.name;
                    targetSelect.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error loading variants:', error);
        });
}

// Adjust SKU inventory
function adjustSkuInventory(skuId, adjustmentData) {
    const url = `/api/products/sku/${skuId}/adjust`;
    
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(adjustmentData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Inventory adjusted successfully', 'success');
            // Reload the page or update the display
            location.reload();
        } else {
            showNotification(data.error || 'Failed to adjust inventory', 'error');
        }
        return data;
    })
    .catch(error => {
        console.error('Error adjusting inventory:', error);
        showNotification('Network error occurred', 'error');
        throw error;
    });
}

// Add inventory from batch
function addInventoryFromBatch(batchData) {
    const url = '/api/products/inventory/add-from-batch';
    
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(batchData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message || 'Inventory added successfully', 'success');
        } else {
            showNotification(data.error || 'Failed to add inventory', 'error');
        }
        return data;
    })
    .catch(error => {
        console.error('Error adding inventory from batch:', error);
        showNotification('Network error occurred', 'error');
        throw error;
    });
}

// Utility function to get CSRF token
function getCSRFToken() {
    const token = document.querySelector('input[name="csrf_token"]') || 
                  document.querySelector('meta[name="csrf-token"]');
    return token ? token.value || token.content : '';
}

// Utility function to show notifications
function showNotification(message, type = 'info') {
    // Try to use existing notification system, fallback to alert
    if (typeof showAlert === 'function') {
        showAlert(message, type);
    } else if (typeof alert === 'function') {
        alert(message);
    } else {
        console.log(`${type.toUpperCase()}: ${message}`);
    }
}

// Make functions globally available
window.loadVariants = loadVariants;
window.adjustSkuInventory = adjustSkuInventory;
window.addInventoryFromBatch = addInventoryFromBatch;