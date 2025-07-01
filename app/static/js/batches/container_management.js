
// Container management for batch in progress

function showAddContainerModal(defaultReason = 'primary_packaging') {
    // Set default reason
    document.getElementById('container-reason').value = defaultReason;
    updateReasonHelp();
    
    // Load available containers
    loadAvailableContainers();
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('addContainerModal'));
    modal.show();
}

function updateReasonHelp() {
    const reason = document.getElementById('container-reason').value;
    const helpText = document.getElementById('reason-help');
    const oneTimeOption = document.getElementById('one-time-option');
    
    const helpTexts = {
        'primary_packaging': 'Standard containers for packaging your product',
        'overflow': 'Additional containers needed because yield exceeded expectations',
        'broke_container': 'Replacement containers for broken ones (broken containers will be excluded from final product count)',
        'test_sample': 'Containers for test samples (will not count toward final product)',
        'other': 'Other reason (please specify in notes)'
    };
    
    helpText.textContent = helpTexts[reason] || '';
    
    // Show one-time option for broke_container
    if (reason === 'broke_container') {
        oneTimeOption.style.display = 'block';
    } else {
        oneTimeOption.style.display = 'none';
        document.getElementById('one-time-use').checked = false;
    }
}

function loadAvailableContainers() {
    fetch('/api/containers/available')
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('container-item');
            select.innerHTML = '<option value="">Select Container</option>';
            
            data.containers.forEach(container => {
                const option = document.createElement('option');
                option.value = container.id;
                option.textContent = `${container.name} (${container.size} ${container.unit}) - Stock: ${container.quantity}`;
                option.dataset.size = container.size;
                option.dataset.unit = container.unit;
                select.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading containers:', error);
            showAlert('Error loading available containers', 'danger');
        });
}

function addContainer() {
    const formData = {
        item_id: document.getElementById('container-item').value,
        quantity: document.getElementById('container-quantity').value,
        reason: document.getElementById('container-reason').value,
        one_time: document.getElementById('one-time-use').checked
    };
    
    if (!formData.item_id || !formData.quantity || !formData.reason) {
        showAlert('Please fill in all required fields', 'warning');
        return;
    }
    
    const batchId = window.currentBatchId; // Assuming this is set globally
    
    fetch(`/batches/${batchId}/add-extra`, {
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
        if (data.success) {
            showAlert('Container added successfully', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addContainerModal')).hide();
            refreshContainerDisplay();
            validateContainerYield();
        } else {
            showAlert(data.message || 'Error adding container', 'danger');
        }
    })
    .catch(error => {
        console.error('Error adding container:', error);
        showAlert('Error adding container', 'danger');
    });
}

function refreshContainerDisplay() {
    const batchId = window.currentBatchId;
    
    fetch(`/api/batches/${batchId}/containers`)
        .then(response => response.json())
        .then(data => {
            displayContainerCards(data.containers);
            updateContainerWarnings(data.validation);
        })
        .catch(error => {
            console.error('Error refreshing containers:', error);
        });
}

function displayContainerCards(containers) {
    const containerCards = document.getElementById('container-cards');
    containerCards.innerHTML = '';
    
    containers.forEach(container => {
        const card = document.createElement('div');
        card.className = 'col-md-4 mb-2';
        
        const statusClass = container.exclude_from_product ? 'border-danger' : 'border-success';
        const statusIcon = container.exclude_from_product ? 'fas fa-times' : 'fas fa-check';
        
        card.innerHTML = `
            <div class="card ${statusClass}">
                <div class="card-body p-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${container.container_name}</strong><br>
                            <small>${container.quantity_used}x ${container.container_size} ${container.unit || ''}</small><br>
                            <small class="text-muted">${container.reason.replace('_', ' ')}</small>
                        </div>
                        <i class="${statusIcon} ${container.exclude_from_product ? 'text-danger' : 'text-success'}"></i>
                    </div>
                </div>
            </div>
        `;
        
        containerCards.appendChild(card);
    });
}

function updateContainerWarnings(validation) {
    const warningsDiv = document.getElementById('container-warnings');
    
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
    } else {
        warningsDiv.style.display = 'none';
    }
}

function validateContainerYield() {
    const batchId = window.currentBatchId;
    const estimatedYield = parseFloat(document.getElementById('estimated-yield')?.value || 0);
    
    if (estimatedYield > 0) {
        fetch(`/api/batches/${batchId}/validate-yield`, {
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

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Update help text when reason changes
    document.getElementById('container-reason')?.addEventListener('change', updateReasonHelp);
    
    // Validate yield when estimated yield changes
    document.getElementById('estimated-yield')?.addEventListener('change', validateContainerYield);
    
    // Initial load of containers
    if (window.currentBatchId) {
        refreshContainerDisplay();
    }
});

function showAlert(message, type) {
    // Simple alert function - you can enhance this
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.insertBefore(alertDiv, document.body.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}
