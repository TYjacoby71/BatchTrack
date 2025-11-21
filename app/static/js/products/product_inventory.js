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

// Load size labels for a variant
function loadSizeLabels(variantId, targetSelectId) {
    if (!variantId) {
        const targetSelect = document.getElementById(targetSelectId);
        if (targetSelect) {
            targetSelect.innerHTML = '<option value="">Select Size</option>';
        }
        return;
    }

    fetch(`/api/products/variants/${variantId}/sizes`)
        .then(response => response.json())
        .then(sizes => {
            const targetSelect = document.getElementById(targetSelectId);
            if (targetSelect) {
                targetSelect.innerHTML = '<option value="">Select Size</option>';
                sizes.forEach(size => {
                    const option = document.createElement('option');
                    option.value = size.size_label;
                    option.textContent = size.size_label;
                    targetSelect.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error loading size labels:', error);
        });
}

// Adjust SKU inventory via canonical route
function adjustSkuInventory(skuId, adjustmentData = {}, options = {}) {
    const url = `/products/inventory/adjust/${skuId}`;
    const { reloadOnSuccess = false } = options;

    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(adjustmentData)
    })
    .then(async response => {
        const contentType = response.headers.get('content-type') || '';
        const isJson = contentType.includes('application/json');
        const payload = isJson ? await response.json() : {};

        if (!response.ok || payload.success === false) {
            const errorMessage = payload.message || payload.error || `Inventory adjustment failed (status ${response.status})`;
            throw new Error(errorMessage);
        }

        if (payload.message) {
            showNotification(payload.message, 'success');
        }

        if (reloadOnSuccess) {
            window.location.reload();
        }

        return payload;
    })
    .catch(error => {
        console.error('Error adjusting inventory:', error);
        showNotification(error.message || 'Network error occurred', 'error');
        throw error;
    });
}

// Add inventory from batch
function addInventoryFromBatch(batchData) {
    const url = '/products/inventory/add-from-batch';
    
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