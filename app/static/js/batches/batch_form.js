// Batch form functionality
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('finishBatchModal');
  const modalForm = document.getElementById('finishBatchModalForm');

  if (modal) {
    modal.addEventListener('shown.bs.modal', function () {
      // Modal initialization is now handled in finish_batch_scripts.html
      console.log('Batch form modal opened');
    });
  }

  if (modalForm) {
    modalForm.addEventListener('submit', function(e) {
      // Form validation can be added here
      return true;
    });
  }

  // Initialize tooltips
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipTriggerList.forEach(trigger => new bootstrap.Tooltip(trigger));
});

function updateExpirationDate() {
  const shelfLifeElement = document.getElementById('shelf_life_days');
  if (!shelfLifeElement) return;

  const shelfLife = shelfLifeElement.value;
  if (shelfLife && parseInt(shelfLife) > 0) {
    const expirationDate = new Date();
    expirationDate.setDate(expirationDate.getDate() + parseInt(shelfLife));
    const dateString = expirationDate.toISOString().split('T')[0];

    const expDateElement = document.getElementById('expiration_date');
    const expDateDisplayElement = document.getElementById('expiration_date_display');

    if (expDateElement) expDateElement.value = dateString;
    if (expDateDisplayElement) expDateDisplayElement.value = dateString;
  }
}

function toggleShelfLife() {
  const isPerishable = document.getElementById('is_perishable').checked;
  const shelfLifeField = document.getElementById('shelfLifeField');

  if (shelfLifeField) {
    shelfLifeField.style.display = isPerishable ? 'block' : 'none';
    const shelfLifeInput = document.getElementById('shelf_life_days');
    if (shelfLifeInput) {
      shelfLifeInput.required = isPerishable;
      if (!isPerishable) {
        shelfLifeInput.value = '';
        document.getElementById('expiration_date').value = '';
        document.getElementById('expiration_date_display').value = '';
      }
    }
  }
}

// toggleOutputFields function removed - now handled by conditional template rendering

function markBatchFailed() {
  if (confirm('Mark this batch as failed? This action cannot be undone.')) {
    const batchId = window.location.pathname.split('/').pop();
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `/batches/finish-batch/${batchId}/fail`;

    const csrf = document.querySelector('.csrf-token').value;
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrf_token';
    csrfInput.value = csrf;

    form.appendChild(csrfInput);
    document.body.appendChild(form);
    form.submit();
  }
}

function updateRowCost(selectElement) {
  const row = selectElement.closest('.extra-row');
  const cost = selectElement.options[selectElement.selectedIndex].dataset.cost;
  const unit = selectElement.options[selectElement.selectedIndex].dataset.unit;

  const costInput = row.querySelector('.cost');
  const unitSelect = row.querySelector('.unit');

  if (costInput) {
    costInput.value = cost || 0;
  }

  if (unitSelect && unit) {
    unitSelect.value = unit;
  }
}

function addExtraItemRow(type) {
  const template = document.getElementById(`extra-${type}-template`);
  const clone = template.content.cloneNode(true);
  document.getElementById('extra-ingredients-container').appendChild(clone);

  const newRow = document.getElementById('extra-ingredients-container').lastElementChild;
  const select = newRow.querySelector('.item-select');
  if (select) {
    updateRowCost(select);
  }
}

function getCurrentBatchId() {
    // Try to get from window object first
    if (window.currentBatchId) {
        return window.currentBatchId;
    }

    // Extract from URL as fallback
    const pathParts = window.location.pathname.split('/');
    return pathParts[pathParts.length - 1];
}

// Also add missing utility functions that are referenced in the code
function getCSRFToken() {
    const csrfElement = document.querySelector('.csrf-token') || document.querySelector('input[name="csrf_token"]');
    return csrfElement ? csrfElement.value : '';
}

function showAlert(message, type) {
    // Simple alert implementation - could be enhanced with Bootstrap alerts
    if (type === 'error') {
        alert('Error: ' + message);
    } else if (type === 'success') {
        alert('Success: ' + message);
    } else {
        alert(message);
    }
}

function saveExtras() {
    const extraRows = document.querySelectorAll('.extra-row');
    const extraIngredients = [];
    const extraContainers = [];

    extraRows.forEach(row => {
        const type = row.dataset.type;
        const itemSelect = row.querySelector('.item-select');
        const qtyInput = row.querySelector('.qty');

        if (!itemSelect.value || !qtyInput.value) {
            return; // Skip incomplete rows
        }

        if (type === 'ingredient') {
            const unitSelect = row.querySelector('.unit');
            extraIngredients.push({
                item_id: parseInt(itemSelect.value),
                quantity: parseFloat(qtyInput.value),
                unit: unitSelect.value
            });
        } else if (type === 'container') {
            const reasonSelect = row.querySelector('.reason');
            const oneTimeCheck = row.querySelector('.one-time');

            extraContainers.push({
                item_id: parseInt(itemSelect.value),
                quantity: parseInt(qtyInput.value),
                reason: reasonSelect ? reasonSelect.value : 'primary_packaging',
                one_time: oneTimeCheck ? oneTimeCheck.checked : false
            });
        }
    });

    if (extraIngredients.length === 0 && extraContainers.length === 0) {
        showAlert('No extra items to save', 'warning');
        return;
    }

    const batchId = getCurrentBatchId();
    if (!batchId) {
        showAlert('Batch ID not found', 'error');
        return;
    }

    fetch(`/add-extra/${batchId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            extra_ingredients: extraIngredients,
            extra_containers: extraContainers
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showAlert('Extra items saved successfully', 'success');

            // Clear all extra rows
            document.querySelectorAll('.extra-row').forEach(row => row.remove());

            // Refresh container display
            if (typeof refreshContainerDisplay === 'function') {
                refreshContainerDisplay();
            }

            // Refresh the page to show updated data
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            const errorMsg = data.errors ? 
                data.errors.map(err => `${err.item}: ${err.message}`).join('\n') :
                'Error saving extra items';
            showAlert(errorMsg, 'error');
        }
    })
    .catch(error => {
        console.error('Error saving extras:', error);
        showAlert('Error saving extra items', 'error');
    });
}

function saveBatchNotes() {
  const batchId = window.location.pathname.split('/').pop();
  const notes = document.querySelector('textarea[name="notes"]').value;
  const tags = document.querySelector('input[name="tags"]').value;
  const csrf = document.querySelector('input[name="csrf_token"]').value;

  return fetch(`/batches/${batchId}/update-notes`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrf
    },
    body: JSON.stringify({ notes, tags })
  });
}

function cancelBatch() {
  if (confirm('Cancel this batch? Ingredients will be returned to inventory.')) {
    const batchId = window.location.pathname.split('/').pop();
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `/batches/cancel/${batchId}`;

    const csrf = document.querySelector('.csrf-token').value;
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrf_token';
    csrfInput.value = csrf;

    form.appendChild(csrfInput);
    document.body.appendChild(form);
    form.submit();
  }
}

// Load variants when product is selected
function loadVariants(productId) {
    console.log('Loading variants for product ID:', productId);
    const variantSelect = document.getElementById('variant_id');

    if (!variantSelect) {
        console.error('Variant select element not found');
        return;
    }

    if (!productId) {
        variantSelect.innerHTML = '<option value="">Select a product first...</option>';
        return;
    }

    variantSelect.innerHTML = '<option value="">Loading variants...</option>';

    fetch(`/products/api/${productId}/variants`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            variantSelect.innerHTML = '<option value="">Select variant...</option>';
            if (data.status === 'success' && data.variants) {
                data.variants.forEach(variant => {
                    const option = document.createElement('option');
                    option.value = variant.id;
                    option.textContent = variant.name;
                    variantSelect.appendChild(option);
                });
                console.log('Loaded variants successfully:', data.variants);
            } else {
                throw new Error(data.message || 'Failed to load variants');
            }
        })
        .catch(error => {
            console.error('Error loading variants:', error);
            variantSelect.innerHTML = '<option value="">Error loading variants</option>';
        });
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Batch form modal opened');

    // Initialize any needed functionality
    const modal = document.getElementById('finishBatchModal');
    if (modal) {
        modal.addEventListener('shown.bs.modal', function () {
            console.log('Modal opened, initializing...');

            // Set up product change handler
            const productSelect = document.getElementById('product_id');
            const variantSelect = document.getElementById('variant_id');

            if (productSelect && variantSelect) {
                productSelect.addEventListener('change', function() {
                    loadVariants(this.value);
                });

                // Load variants for initially selected product
                if (productSelect.value) {
                    loadVariants(productSelect.value);
                }
            } else {
                console.error('Product or variant dropdown not found');
            }
        });
    }
});