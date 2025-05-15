// Batch form functionality
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('finishBatchModal');
  const modalForm = document.getElementById('finishBatchModalForm');
  const outputTypeSelect = document.getElementById('output_type');

  if (modal) {
    modal.addEventListener('shown.bs.modal', function () {
      if (outputTypeSelect) {
        toggleOutputFields();
        toggleShelfLife();
      }
    });
  }

  if (outputTypeSelect) {
    outputTypeSelect.addEventListener('change', toggleOutputFields);
  }

  if (!modalForm) {
    console.warn('Modal form not found on initial load');
  }

  // Initialize tooltips
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipTriggerList.forEach(trigger => new bootstrap.Tooltip(trigger));
});

function updateExpirationDate() {
  const shelfLife = document.getElementById('shelf_life_days').value;
  if (shelfLife && parseInt(shelfLife) > 0) {
    const expirationDate = new Date();
    expirationDate.setDate(expirationDate.getDate() + parseInt(shelfLife));
    const dateString = expirationDate.toISOString().split('T')[0];
    document.getElementById('expiration_date').value = dateString;
    document.getElementById('expiration_date_display').value = dateString;
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
    form.action = `/finish-batch/${batchId}/fail`;

    const csrf = document.querySelector('input[name="csrf_token"]').value;
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrf_token';
    csrfInput.value = csrf;

    form.appendChild(csrfInput);
    document.body.appendChild(form);
    form.submit();
  }
}

function submitFinishBatch() {
  const modalForm = document.getElementById('finishBatchModalForm');
  if (!modalForm) return;

  const finalQuantityInput = modalForm.querySelector('#final_quantity');
  if (!finalQuantityInput) {
    alert('Final quantity input not found');
    return;
  }

  const finalQty = finalQuantityInput.value.trim();
  if (!finalQty || parseFloat(finalQty) <= 0) {
    alert('Please enter a valid final quantity');
    return;
  }

  const isPerishable = document.getElementById('is_perishable').checked;
  if (isPerishable) {
    const shelfLife = parseInt(document.getElementById('shelf_life_days').value);
    if (!shelfLife || shelfLife <= 0) {
      alert('Please enter valid shelf life days for perishable items');
      return;
    }
  }

  modalForm.querySelector('input[name="is_perishable"]').value = isPerishable ? 'on' : 'off';
  modalForm.submit();
}

function updateRowCost(selectElement) {
  const cost = selectElement.options[selectElement.selectedIndex].dataset.cost;
  const costInput = selectElement.parentElement.querySelector('.cost');
  if (costInput) {
    costInput.value = cost;
  }
}

function addExtraIngredientRow() {
  const template = document.getElementById('extra-ingredient-template');
  const clone = template.content.cloneNode(true);
  document.getElementById('extra-ingredients-container').appendChild(clone);

  const newRow = document.getElementById('extra-ingredients-container').lastElementChild;
  $(newRow).find('.select2-input').select2({
    width: 'resolve',
    dropdownAutoWidth: true
  });

  const select = newRow.querySelector('.ingredient-select');
  if (select) {
    updateRowCost(select);
  }
}

function addExtraContainerRow() {
  const template = document.getElementById('extra-container-template');
  const clone = template.content.cloneNode(true);
  document.getElementById('extra-containers-container').appendChild(clone);

  const newRow = document.getElementById('extra-containers-container').lastElementChild;
  $(newRow).find('.select2-input').select2({
    width: 'resolve',
    dropdownAutoWidth: true
  });
}

function saveExtraContainers() {
  const rows = document.querySelectorAll(".extra-container-row");
  const extras = Array.from(rows).map(row => ({
    container_id: parseInt(row.querySelector(".container-select").value),
    quantity: parseInt(row.querySelector(".qty").value) || 0,
    cost_per_unit: parseFloat(row.querySelector(".cost").value) || 0,
    container_name: row.querySelector(".container-select option:checked").text
  }));

  const batchId = window.location.pathname.split('/').pop();
  fetch(`/batches/extras-containers/${batchId}`, {
    method: "POST",
    headers: { 
      "Content-Type": "application/json",
      "X-CSRFToken": document.querySelector('input[name="csrf_token"]').value
    },
    body: JSON.stringify({ extras })
  })
  .then(res => {
    if (!res.ok) {
      return res.json().then(err => {
        throw new Error(err.error || 'Failed to save extra containers');
      });
    }
    return res.json();
  })
  .then(data => {
    if (data.errors) {
      const errorMsg = data.errors.map(err => 
        `${err.container}: ${err.message} (Available: ${err.available})`
      ).join('\n');
      alert("Cannot save extra containers:\n" + errorMsg);
    } else {
      alert("Extra containers saved successfully");
      window.location.reload();
    }
  })
  .catch(err => {
    alert(err.message);
    console.error(err);
  });
}

function saveExtras() {
  const rows = document.querySelectorAll(".extra-row");
  const extras = Array.from(rows).map(row => ({
    ingredient_id: row.querySelector(".ingredient-select").value,
    quantity: parseFloat(row.querySelector(".qty").value) || 0,
    unit: row.querySelector(".unit").value,
    cost_per_unit: parseFloat(row.querySelector(".cost").value) || 0,
    ingredient_name: row.querySelector(".ingredient-select option:checked").text
  }));

  const batchId = window.location.pathname.split('/').pop();
  fetch(`/batches/extras/${batchId}`, {
    method: "POST",
    headers: { 
      "Content-Type": "application/json",
      "X-CSRFToken": document.querySelector('input[name="csrf_token"]').value
    },
    body: JSON.stringify({ extras })
  })
  .then(res => {
    if (!res.ok) {
      return res.json().then(err => {
        throw new Error(err.error || 'Failed to save extras');
      });
    }
    return res.json();
  })
  .then(data => {
    if (data.errors) {
      const errorMsg = data.errors.map(err => 
        `${err.ingredient}: ${err.message} (Available: ${err.available} ${err.available_unit})`
      ).join('\n');
      alert("Cannot save extras:\n" + errorMsg);
    } else {
      alert("Extra ingredients saved successfully");
      window.location.reload();
    }
  })
  .catch(err => {
    alert(err.message);
    console.error(err);
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