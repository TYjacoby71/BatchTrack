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

  // Initialize tooltips only if bootstrap is available
  if (typeof bootstrap !== 'undefined') {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(trigger => new bootstrap.Tooltip(trigger));
  }

  // Initialize shelf life toggle if element exists
  const isPerishableElement = document.getElementById('is_perishable');
  if (isPerishableElement) {
    isPerishableElement.addEventListener('change', toggleShelfLife);
  }

  // Initialize shelf life input listener if element exists
  const shelfLifeElement = document.getElementById('shelf_life_days');
  if (shelfLifeElement) {
    shelfLifeElement.addEventListener('input', updateExpirationDate);
  }
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

function addExtraItemRow(type) {
  const container = document.getElementById('extra-ingredients-container');
  const template = document.getElementById(`extra-${type}-template`);
  
  if (!template || !container) {
    console.error('Template or container not found:', type);
    return;
  }
  
  const clone = template.content.cloneNode(true);
  container.appendChild(clone);
}

function saveExtras() {
  const extraRows = document.querySelectorAll('#extra-ingredients-container .extra-row');
  const extras = [];
  
  extraRows.forEach(row => {
    const type = row.dataset.type;
    const itemSelect = row.querySelector('.item-select');
    const qtyInput = row.querySelector('.qty');
    const costInput = row.querySelector('.cost');
    const unitSelect = row.querySelector('.unit');
    
    if (itemSelect.value && qtyInput.value) {
      const extra = {
        type: type,
        item_id: itemSelect.value,
        quantity: parseFloat(qtyInput.value),
        cost: parseFloat(costInput.value) || 0
      };
      
      if (unitSelect) {
        extra.unit = unitSelect.value;
      }
      
      extras.push(extra);
    }
  });
  
  if (extras.length === 0) {
    showAlert('No extra items to save', 'warning');
    return;
  }
  
  const batchId = getCurrentBatchId();
  const csrf = getCSRFToken();
  
  fetch(`/batches/${batchId}/add-extras`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrf
    },
    body: JSON.stringify({ extras: extras })
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Extra items saved successfully', 'success');
      // Clear the form
      document.getElementById('extra-ingredients-container').innerHTML = '';
      // Reload page to show updated cost summary
      window.location.reload();
    } else {
      showAlert('Error saving extra items: ' + (data.message || 'Unknown error'), 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('Error saving extra items', 'error');
  });
}

function openBatchInventorySummary(batchId) {
  // This function opens the FIFO modal or inventory summary
  const modal = document.getElementById('fifoInsightModal');
  if (modal) {
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
  }
}