// Batch form functionality
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('finishBatchModal');
  const modalForm = document.getElementById('finishBatchModalForm');
  const outputTypeSelect = document.getElementById('output_type');

  function toggleOutputFields() {
    const productFields = document.getElementById('productFields');
    if (productFields) {
      productFields.style.display = outputTypeSelect.value === 'product' ? 'block' : 'none';
    }
  }

  function toggleShelfLife() {
    const isPerishable = document.getElementById('is_perishable').checked;
    const shelfLifeField = document.getElementById('shelfLifeField');
    if (shelfLifeField) {
      shelfLifeField.style.display = isPerishable ? 'block' : 'none';
    }
  }

  function updateExpirationDate() {
    const shelfLifeDays = document.getElementById('shelf_life_days').value;
    if (shelfLifeDays) {
      const expirationDate = new Date();
      expirationDate.setDate(expirationDate.getDate() + parseInt(shelfLifeDays));
      document.getElementById('expiration_date_display').value = expirationDate.toISOString().split('T')[0];
      document.getElementById('expiration_date').value = expirationDate.toISOString().split('T')[0];
    }
  }

  window.submitFinishBatch = function() {
    if (!modalForm) return;

    const finalQtyInput = modalForm.querySelector('#final_quantity');
    const finalQty = parseFloat(finalQtyInput?.value);
    const isPerishable = document.getElementById('is_perishable').checked;

    if (!finalQty || finalQty <= 0) {
      alert('Please enter a valid final quantity');
      return;
    }

    const formData = new FormData(modalForm);
    formData.set('is_perishable', isPerishable ? 'on' : 'off');

    if (isPerishable) {
      const shelfLife = document.getElementById('shelf_life_days').value;
      if (!shelfLife || parseInt(shelfLife) <= 0) {
        alert('Please enter valid shelf life days for perishable items');
        return;
      }
      formData.set('shelf_life_days', shelfLife);
      formData.set('expiration_date', document.getElementById('expiration_date').value);
    }

    fetch(modalForm.action, {
      method: 'POST',
      body: formData
    })
    .then(response => {
      if (!response.ok) throw new Error('Network response was not ok');
      return response.json();
    })
    .then(data => {
      if (data.status === 'success') {
        window.location.href = data.redirect_url;
      } else {
        alert(data.message || 'Error completing batch');
      }
    })
    .catch(error => {
      console.error('Error:', error);
      alert('Error completing batch. Please try again.');
    });
  };

  if (outputTypeSelect) {
    outputTypeSelect.addEventListener('change', toggleOutputFields);
  }

  // Initialize tooltips
  if (typeof bootstrap !== 'undefined') {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }

  if (modal) {
    modal.addEventListener('shown.bs.modal', function () {
      if (outputTypeSelect) {
        toggleOutputFields();
        toggleShelfLife();
      }
    });
  }

  if (!modalForm) {
    console.warn('Modal form not found on initial load');
  }
});

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
      function displayErrors(errors) {
        const message = errors.map(err =>
          `❌ ${err.ingredient}: ${err.message}`
        ).join("\n\n");

        alert("Save failed:\n\n" + message);
      }

      displayErrors(data.errors);
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