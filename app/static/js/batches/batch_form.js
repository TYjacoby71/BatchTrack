// Batch form functionality
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('finishBatchModal');
  const modalForm = document.getElementById('finishBatchModalForm');
  const outputTypeSelect = document.getElementById('output_type');

  if (modal) {
    modal.addEventListener('shown.bs.modal', function () {
      const form = document.getElementById('finishBatchModalForm');
      if (form && outputTypeSelect) {
        toggleOutputFields();
        toggleShelfLife();
      }
    });
  }

  if (modalForm) {
    modalForm.addEventListener('submit', function(e) {
      // Form validation can be added here
      return true;
    });
  }

  if (outputTypeSelect) {
    outputTypeSelect.addEventListener('change', toggleOutputFields);
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

function toggleOutputFields() {
  const type = document.getElementById('output_type').value;
  const productFields = document.getElementById('productFields');
  const productSelect = document.getElementById('product_id');

  if (productFields && productSelect) {
    const isProduct = type === 'product';
    productFields.style.display = isProduct ? 'block' : 'none';
    productSelect.required = isProduct;
  }
}

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
  const cost = selectElement.options[selectElement.selectedIndex].dataset.cost;
  const costInput = selectElement.parentElement.querySelector('.cost');
  if (costInput) {
    costInput.value = cost;
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

let currentContainerId = null;
let currentContainerItemId = null;
let currentQuantity = 0;

function showContainerAdjustModal(containerId, containerName, currentQty) {
    currentContainerId = containerId;
    currentQuantity = currentQty;
    document.getElementById('containerName').textContent = containerName;
    document.getElementById('currentQuantity').textContent = currentQty;

    // Reset form
    document.getElementById('adjustmentType').value = 'quantity';
    document.getElementById('totalQuantity').value = currentQty;
    document.getElementById('adjustmentNotes').value = '';
    showAdjustmentOptions();

    const modal = new bootstrap.Modal(document.getElementById('containerAdjustModal'));
    modal.show();
}

function showAdjustmentOptions() {
    const type = document.getElementById('adjustmentType').value;

    document.getElementById('quantityAdjustment').style.display = type === 'quantity' ? 'block' : 'none';
    document.getElementById('containerReplacement').style.display = type === 'replace' ? 'block' : 'none';
    document.getElementById('damageReason').style.display = type === 'damage' ? 'block' : 'none';
}

function saveContainerAdjustment() {
    const type = document.getElementById('adjustmentType').value;
    const notes = document.getElementById('adjustmentNotes').value;
    const batchId = getCurrentBatchId();

    let data = {
        adjustment_type: type,
        notes: notes
    };

    if (type === 'quantity') {
        const newTotal = parseInt(document.getElementById('totalQuantity').value);
        data.new_total_quantity = newTotal;
    } else if (type === 'replace') {
        data.new_container_id = document.getElementById('newContainer').value;
        data.new_quantity = parseInt(document.getElementById('newQuantity').value);
    } else if (type === 'damage') {
        data.damage_quantity = parseInt(document.getElementById('damageQuantity').value);
    }

    fetch(`/api/batches/${batchId}/containers/${currentContainerId}/adjust`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Container adjusted successfully', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error: ' + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error adjusting container:', error);
        showAlert('Failed to adjust container', 'error');
    });
}

// Event listener for adjustment type changes
document.addEventListener('DOMContentLoaded', function() {
    const adjustmentSelect = document.getElementById('adjustmentType');
    if (adjustmentSelect) {
        adjustmentSelect.addEventListener('change', showAdjustmentOptions);
    }
});