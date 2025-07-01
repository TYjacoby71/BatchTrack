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
  const isPerishableElement = document.getElementById('is_perishable');
  if (!isPerishableElement) return;

  const isPerishable = isPerishableElement.checked;
  const shelfLifeField = document.getElementById('shelfLifeField');

  if (shelfLifeField) {
    shelfLifeField.style.display = isPerishable ? 'block' : 'none';
    const shelfLifeInput = document.getElementById('shelf_life_days');
    if (shelfLifeInput) {
      shelfLifeInput.required = isPerishable;
      if (!isPerishable) {
        shelfLifeInput.value = '';
        const expDateElement = document.getElementById('expiration_date');
        const expDateDisplayElement = document.getElementById('expiration_date_display');
        if (expDateElement) expDateElement.value = '';
        if (expDateDisplayElement) expDateDisplayElement.value = '';
      }
    }
  }
}

function toggleOutputFields() {
  const outputTypeElement = document.getElementById('output_type');
  if (!outputTypeElement) return;

  const type = outputTypeElement.value;
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

function addExtraItemRow(type) {
  const container = document.getElementById('extra-ingredients-container');
  const templateId = type === 'ingredient' ? 'extra-ingredient-template' : 'extra-container-template';
  const template = document.getElementById(templateId);

  if (!template || !container) {
    console.error(`Template ${templateId} or container not found`);
    return;
  }

  const clone = template.content.cloneNode(true);
  container.appendChild(clone);
}

function updateRowCost(selectElement) {
  const selectedOption = selectElement.options[selectElement.selectedIndex];
  const cost = selectedOption.dataset.cost || 0;
  const unit = selectedOption.dataset.unit || '';

  const row = selectElement.closest('.extra-row');
  const costInput = row.querySelector('.cost');
  if (costInput) {
    costInput.value = cost;
  }

  if (unit) {
    const unitSelect = row.querySelector('.unit');
    if (unitSelect) {
      unitSelect.value = unit;
    }
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
    const reasonSelect = row.querySelector('.reason');
    const costInput = row.querySelector('.cost');

    if (!itemSelect.value || !qtyInput.value) return;

    const itemData = {
      item_id: parseInt(itemSelect.value),
      quantity: parseFloat(qtyInput.value),
      reason: reasonSelect.value,
      cost: parseFloat(costInput.value) || 0
    };

    if (type === 'ingredient') {
      const unitSelect = row.querySelector('.unit');
      itemData.unit = unitSelect.value;
      extraIngredients.push(itemData);
    } else if (type === 'container') {
      extraContainers.push(itemData);
    }
  });

  if (extraIngredients.length === 0 && extraContainers.length === 0) {
    alert('No extra items to save');
    return;
  }

  const batchId = window.location.pathname.split('/').pop();
  const csrfToken = document.querySelector('.csrf-token').value;

  fetch(`/batches/add-extra/${batchId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken
    },
    body: JSON.stringify({
      extra_ingredients: extraIngredients,
      extra_containers: extraContainers
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      alert('Extra items saved successfully');
      window.location.reload();
    } else {
      const errorMessages = data.errors?.map(e => `${e.item}: ${e.message}`).join('\n') || 'Unknown error';
      alert('Error saving extras:\n' + errorMessages);
    }
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error saving extras');
  });
}

function saveBatchNotes() {
  const batchId = window.location.pathname.split('/').pop();
  const notesElement = document.querySelector('textarea[name="notes"]');
  const tagsElement = document.querySelector('input[name="tags"]');
  const csrfElement = document.querySelector('input[name="csrf_token"]');

  if (!notesElement || !tagsElement || !csrfElement) {
    console.error('Required form elements not found');
    return Promise.reject('Form elements missing');
  }

  const notes = notesElement.value;
  const tags = tagsElement.value;
  const csrf = csrfElement.value;

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

function openBatchInventorySummary(batchId) {
  // This function opens the FIFO modal or inventory summary
  const modal = document.getElementById('fifoInsightModal');
  if (modal) {
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
  }
}

// Utility functions
function getCurrentBatchId() {
    // Try to get from window object first
    if (window.currentBatchId) {
        return window.currentBatchId;
    }

    // Extract from URL as fallback
    const pathParts = window.location.pathname.split('/');
    return pathParts[pathParts.length - 1];
}

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