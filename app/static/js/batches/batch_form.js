// Timer Functions
function startTimer(name, duration) {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('duration', duration);
  formData.append('csrf_token', document.querySelector('input[name="csrf_token"]').value);

  fetch('/timers/start', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      location.reload();
    } else {
      alert('Error starting timer: ' + data.message);
    }
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error starting timer');
  });
}

function stopTimer(timerId) {
  const formData = new FormData();
  formData.append('csrf_token', document.querySelector('input[name="csrf_token"]').value);

  fetch(`/timers/${timerId}/stop`, {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      location.reload();
    } else {
      alert('Error stopping timer: ' + data.message);
    }
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error stopping timer');
  });
}

function deleteTimer(timerId) {
  if (!confirm('Are you sure you want to delete this timer?')) {
    return;
  }

  const formData = new FormData();
  formData.append('csrf_token', document.querySelector('input[name="csrf_token"]').value);

  fetch(`/timers/${timerId}/delete`, {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      location.reload();
    } else {
      alert('Error deleting timer: ' + data.message);
    }
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error deleting timer');
  });
}

// Extra Items Functions
function addExtraItemRow(type) {
  const container = document.getElementById('extra-ingredients-container');
  const template = document.getElementById(`extra-${type}-template`);

  if (!template || !container) {
    console.error(`Template or container not found for type: ${type}`);
    return;
  }

  const clone = template.content.cloneNode(true);
  container.appendChild(clone);
}

function updateRowCost(selectElement) {
  const row = selectElement.closest('.extra-row');
  const costInput = row.querySelector('.cost');
  const unitSelect = row.querySelector('.unit');

  if (!selectElement.value) {
    costInput.value = '';
    return;
  }

  const selectedOption = selectElement.selectedOptions[0];
  const cost = selectedOption.dataset.cost || 0;
  const unit = selectedOption.dataset.unit;

  costInput.value = cost;

  // Update unit for ingredients
  if (unitSelect && unit) {
    unitSelect.value = unit;
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

  fetch(`/batches/${batchId}/add-extras`, {
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
    if (data.status === 'success') {
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

// Batch Notes Functions
async function saveBatchNotes() {
  const notesTextarea = document.querySelector('textarea[name="notes"]');
  const tagsInput = document.querySelector('input[name="tags"]');
  const csrfToken = document.querySelector('input[name="csrf_token"]').value;

  const formData = {
    notes: notesTextarea ? notesTextarea.value : '',
    tags: tagsInput ? tagsInput.value : ''
  };

  try {
    const batchId = window.location.pathname.split('/').pop();
    const response = await fetch(`/batches/${batchId}/update-notes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify(formData)
    });

    const data = await response.json();
    if (response.ok) {
      return true;
    } else {
      alert('Error saving notes: ' + data.error);
      return false;
    }
  } catch (error) {
    console.error('Error saving notes:', error);
    alert('Error saving notes');
    return false;
  }
}

// Batch Action Functions
function cancelBatch() {
  if (confirm('Are you sure you want to cancel this batch? This action cannot be undone.')) {
    const batchId = window.location.pathname.split('/').pop();
    window.location.href = `/batches/${batchId}/cancel`;
  }
}

function markBatchFailed() {
  if (confirm('Are you sure you want to mark this batch as failed? This action cannot be undone.')) {
    const batchId = window.location.pathname.split('/').pop();
    // You'll need to create this route
    window.location.href = `/batches/${batchId}/mark-failed`;
  }
}

// Validation Functions
function validateBatchForm() {
  // Add any validation logic here
  return true;
}

// Batch Inventory Summary
function openBatchInventorySummary(batchId) {
  // Open modal or redirect to batch inventory summary
  window.open(`/batches/${batchId}/inventory-summary`, '_blank');
}