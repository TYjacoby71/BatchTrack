
// Container management for batch in progress

let availableContainers = [];
let currentBatchId = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Get batch ID from URL
    const pathParts = window.location.pathname.split('/');
    currentBatchId = pathParts[pathParts.length - 1];
    window.currentBatchId = currentBatchId;
    
    // Load available containers
    loadAvailableContainers();
    
    // Load current containers
    refreshContainerDisplay();
    
    // Set up event listeners
    setupEventListeners();
});

function setupEventListeners() {
    // Update help text when reason changes
    const reasonSelect = document.getElementById('container-reason');
    if (reasonSelect) {
        reasonSelect.addEventListener('change', updateReasonHelp);
    }
    
    // Validate yield when estimated yield changes
    const yieldInput = document.getElementById('estimated-yield');
    if (yieldInput) {
        yieldInput.addEventListener('change', validateContainerYield);
    }
}

function showAddContainerModal(defaultReason = 'primary_packaging') {
    // Set default reason
    const reasonSelect = document.getElementById('container-reason');
    if (reasonSelect) {
        reasonSelect.value = defaultReason;
        updateReasonHelp();
    }
    
    // Load available containers if not already loaded
    if (availableContainers.length === 0) {
        loadAvailableContainers();
    }
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('addContainerModal'));
    modal.show();
}

// Make sure this function is globally available
window.showAddContainerModal = showAddContainerModal;

function loadAvailableContainers() {
    fetch('/api/containers/available')
        .then(response => response.json())
        .then(data => {
            availableContainers = data;
            populateContainerSelect();
        })
        .catch(error => {
            console.error('Error loading containers:', error);
            showAlert('Error loading available containers', 'warning');
        });
}

function populateContainerSelect() {
    const select = document.getElementById('container-item');
    if (!select) return;
    
    // Clear existing options except the first one
    select.innerHTML = '<option value="">Select Container</option>';
    
    // Add container options
    availableContainers.forEach(container => {
        const option = document.createElement('option');
        option.value = container.id;
        option.textContent = `${container.name} (${container.size || 'Unknown'} ${container.unit || ''})`;
        option.dataset.cost = container.cost_per_unit || 0;
        option.dataset.stock = container.stock_amount || 0;
        select.appendChild(option);
    });
}

function updateReasonHelp() {
    const reason = document.getElementById('container-reason')?.value;
    const helpText = document.getElementById('reason-help');
    const oneTimeOption = document.getElementById('one-time-option');
    
    if (!helpText) return;
    
    const helpTexts = {
        'primary_packaging': 'Standard containers for packaging your product',
        'overflow': 'Additional containers needed because yield exceeded expectations',
        'broke_container': 'Replacement containers for broken ones (broken containers will be excluded from final product count)',
        'test_sample': 'Containers for test samples (will not count toward final product)',
        'other': 'Other reason (please specify in notes)'
    };
    
    helpText.textContent = helpTexts[reason] || '';
    
    // Show one-time option for broke_container
    if (oneTimeOption) {
        if (reason === 'broke_container') {
            oneTimeOption.style.display = 'block';
        } else {
            oneTimeOption.style.display = 'none';
            const oneTimeCheck = document.getElementById('one-time-use');
            if (oneTimeCheck) oneTimeCheck.checked = false;
        }
    }
}

function addContainer() {
    const containerSelect = document.getElementById('container-item');
    const quantityInput = document.getElementById('container-quantity');
    const reasonSelect = document.getElementById('container-reason');
    const oneTimeCheck = document.getElementById('one-time-use');
    
    if (!containerSelect || !quantityInput || !reasonSelect) {
        showAlert('Form elements not found', 'danger');
        return;
    }
    
    const formData = {
        item_id: containerSelect.value,
        quantity: parseInt(quantityInput.value),
        reason: reasonSelect.value,
        one_time: oneTimeCheck ? oneTimeCheck.checked : false
    };
    
    // Validation
    if (!formData.item_id || !formData.quantity || !formData.reason) {
        showAlert('Please fill in all required fields', 'warning');
        return;
    }
    
    if (formData.quantity <= 0) {
        showAlert('Quantity must be greater than 0', 'warning');
        return;
    }
    
    // Check stock availability (unless one-time use)
    if (!formData.one_time) {
        const selectedOption = containerSelect.selectedOptions[0];
        const availableStock = parseFloat(selectedOption?.dataset.stock || 0);
        
        if (formData.quantity > availableStock) {
            const confirmMsg = `Only ${availableStock} units available in stock. Do you want to proceed with one-time use instead?`;
            if (confirm(confirmMsg)) {
                formData.one_time = true;
            } else {
                return;
            }
        }
    }
    
    // Submit to server
    fetch(`/add-extra/${currentBatchId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            extra_containers: [formData]
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showAlert('Container added successfully', 'success');
            
            // Hide modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('addContainerModal'));
            if (modal) modal.hide();
            
            // Reset form
            resetContainerForm();
            
            // Refresh displays
            refreshContainerDisplay();
            validateContainerYield();
        } else {
            const errorMsg = data.errors ? 
                data.errors.map(err => `${err.item}: ${err.message}`).join('\n') :
                'Error adding container';
            showAlert(errorMsg, 'danger');
        }
    })
    .catch(error => {
        console.error('Error adding container:', error);
        showAlert('Error adding container', 'danger');
    });
}

function resetContainerForm() {
    const form = document.getElementById('add-container-form');
    if (form) {
        form.reset();
        updateReasonHelp();
    }
}

function refreshContainerDisplay() {
    if (!currentBatchId) return;
    
    fetch(`/api/batches/${currentBatchId}/containers`)
        .then(response => response.json())
        .then(data => {
            updateContainerCards(data.containers || []);
            updateContainerSummary(data.summary || {});
        })
        .catch(error => {
            console.error('Error loading containers:', error);
        });
}

function updateContainerCards(containers) {
    const containerCardsDiv = document.getElementById('container-cards');
    if (!containerCardsDiv) return;
    
    if (containers.length === 0) {
        containerCardsDiv.innerHTML = '<div class="col-12"><p class="text-muted">No containers added yet</p></div>';
        return;
    }
    
    containerCardsDiv.innerHTML = containers.map(container => `
        <div class="col-md-6 col-lg-4 mb-3">
            <div class="card h-100 ${getContainerCardClass(container.reason)}">
                <div class="card-body">
                    <h6 class="card-title">${container.name}</h6>
                    <p class="card-text">
                        <small class="text-muted">Quantity: ${container.quantity}</small><br>
                        <small class="text-muted">Reason: ${getReasonDisplayName(container.reason)}</small>
                        ${container.one_time_use ? '<br><span class="badge bg-warning">One-time use</span>' : ''}
                        ${container.exclude_from_product ? '<br><span class="badge bg-danger">Excluded from product</span>' : ''}
                    </p>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeContainer(${container.id})">
                        <i class="fas fa-trash"></i> Remove
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

function getContainerCardClass(reason) {
    const classes = {
        'primary_packaging': 'border-primary',
        'overflow': 'border-info',
        'broke_container': 'border-danger',
        'test_sample': 'border-warning',
        'other': 'border-secondary'
    };
    return classes[reason] || 'border-secondary';
}

function getReasonDisplayName(reason) {
    const names = {
        'primary_packaging': 'Primary Packaging',
        'overflow': 'Overflow',
        'broke_container': 'Broken Container',
        'test_sample': 'Test Sample',
        'other': 'Other'
    };
    return names[reason] || reason;
}

function updateContainerSummary(summary) {
    const summaryDiv = document.getElementById('container-summary');
    if (!summaryDiv) return;
    
    summaryDiv.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                <strong>Total Containers:</strong> ${summary.total_containers || 0}<br>
                <strong>Total Capacity:</strong> ${summary.total_capacity || 0} ${summary.capacity_unit || 'units'}
            </div>
            <div class="col-md-6">
                <strong>For Product:</strong> ${summary.product_containers || 0}<br>
                <strong>Product Capacity:</strong> ${summary.product_capacity || 0} ${summary.capacity_unit || 'units'}
            </div>
        </div>
    `;
}

function removeContainer(containerId) {
    if (!confirm('Are you sure you want to remove this container?')) {
        return;
    }
    
    fetch(`/api/batches/${currentBatchId}/containers/${containerId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Container removed successfully', 'success');
            refreshContainerDisplay();
            validateContainerYield();
        } else {
            showAlert(data.message || 'Error removing container', 'danger');
        }
    })
    .catch(error => {
        console.error('Error removing container:', error);
        showAlert('Error removing container', 'danger');
    });
}

function validateContainerYield() {
    const estimatedYield = parseFloat(document.getElementById('estimated-yield')?.value || 0);
    
    if (estimatedYield > 0 && currentBatchId) {
        fetch(`/api/batches/${currentBatchId}/validate-yield`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ estimated_yield: estimatedYield })
        })
        .then(response => response.json())
        .then(data => {
            updateContainerWarnings(data);
        })
        .catch(error => {
            console.error('Error validating yield:', error);
        });
    }
}

function updateContainerWarnings(validation) {
    const warningsDiv = document.getElementById('container-warnings');
    if (!warningsDiv) return;
    
    if (validation.warnings && validation.warnings.length > 0) {
        warningsDiv.style.display = 'block';
        warningsDiv.innerHTML = `
            <div class="alert alert-warning">
                <h6><i class="fas fa-exclamation-triangle"></i> Container Validation:</h6>
                <ul class="mb-0">
                    ${validation.warnings.map(warning => `<li>${warning}</li>`).join('')}
                </ul>
            </div>
        `;
    } else if (validation.suggestions && validation.suggestions.length > 0) {
        warningsDiv.style.display = 'block';
        warningsDiv.innerHTML = `
            <div class="alert alert-info">
                <h6><i class="fas fa-lightbulb"></i> Suggestions:</h6>
                <ul class="mb-0">
                    ${validation.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                </ul>
            </div>
        `;
    } else {
        warningsDiv.style.display = 'none';
    }
}

// Utility functions
function getCSRFToken() {
    const token = document.querySelector('input[name="csrf_token"]')?.value ||
                  document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    return token || '';
}

function showAlert(message, type = 'info') {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert at top of main content
    const mainContent = document.querySelector('.container, main, body');
    if (mainContent) {
        mainContent.insertBefore(alertDiv, mainContent.firstChild);
    }
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}
