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

function saveExtras() {
  const rows = document.querySelectorAll(".extra-row");
  const extraIngredients = [];
  const extraContainers = [];

  // Separate ingredients and containers
  rows.forEach(row => {
    const type = row.dataset.type;
    const itemSelect = row.querySelector(".item-select");
    const qtyInput = row.querySelector(".qty");
    const costInput = row.querySelector(".cost");

    if (!itemSelect.value || !qtyInput.value) {
      return;
    }

    const baseData = {
      item_id: parseInt(itemSelect.value),
      quantity: parseFloat(qtyInput.value),
      cost_per_unit: parseFloat(costInput.value) || 0
    };

    if (type === 'ingredient') {
      const unitSelect = row.querySelector(".unit");
      if (!unitSelect.value) {
        return;
      }
      baseData.unit = unitSelect.value;
      extraIngredients.push(baseData);
    } else if (type === 'container') {
      extraContainers.push(baseData);
    }
  });

  const batchId = window.location.pathname.split('/').pop();
  fetch(`/add-extra/${batchId}`, {
    method: "POST",
    headers: { 
      "Content-Type": "application/json",
      "X-CSRFToken": document.querySelector('input[name="csrf_token"]').value
    },
    body: JSON.stringify({ 
      extra_ingredients: extraIngredients,
      extra_containers: extraContainers 
    })
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