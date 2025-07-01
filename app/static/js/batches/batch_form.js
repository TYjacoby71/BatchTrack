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