
// Batch form functionality
document.addEventListener('DOMContentLoaded', function() {
  initializeTooltips();
  initializeModalHandlers();
  initializeFormHandlers();
});

function initializeTooltips() {
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipTriggerList.forEach(trigger => new bootstrap.Tooltip(trigger));
}

function initializeModalHandlers() {
  const modal = document.getElementById('finishBatchModal');
  if (modal) {
    modal.addEventListener('shown.bs.modal', function() {
      const form = document.getElementById('finishBatchModalForm');
      if (form && document.getElementById('output_type')) {
        toggleOutputFields();
        toggleShelfLife();
      }
    });
  }
}

function initializeFormHandlers() {
  const outputTypeSelect = document.getElementById('output_type');
  if (outputTypeSelect) {
    outputTypeSelect.addEventListener('change', toggleOutputFields);
  }
}

function updateExpirationDate() {
  const shelfLife = document.getElementById('shelf_life_days')?.value;
  if (shelfLife && parseInt(shelfLife) > 0) {
    const expirationDate = new Date();
    expirationDate.setDate(expirationDate.getDate() + parseInt(shelfLife));
    const dateString = expirationDate.toISOString().split('T')[0];
    document.getElementById('expiration_date').value = dateString;
    document.getElementById('expiration_date_display').value = dateString;
  }
}

function toggleShelfLife() {
  const isPerishable = document.getElementById('is_perishable')?.checked;
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
  const type = document.getElementById('output_type')?.value;
  const productFields = document.getElementById('productFields');
  const productSelect = document.getElementById('product_id');
  
  if (productFields && productSelect) {
    const isProduct = type === 'product';
    productFields.style.display = isProduct ? 'block' : 'none';
    productSelect.required = isProduct;
  }
}

function addExtraItemRow(type) {
  const template = document.getElementById(`extra-${type}-template`);
  if (!template) return;
  
  const clone = template.content.cloneNode(true);
  const container = document.getElementById('extra-ingredients-container');
  container.appendChild(clone);

  const newRow = container.lastElementChild;
  initializeSelect2(newRow);
  updateRowCost(newRow.querySelector('.item-select'));
}

function initializeSelect2(row) {
  $(row).find('.select2').select2({
    width: 'resolve',
    dropdownAutoWidth: true,
    placeholder: 'Select...',
    allowClear: true,
    theme: 'bootstrap-5'
  });
}

function updateRowCost(selectElement) {
  if (!selectElement) return;
  const cost = selectElement.options[selectElement.selectedIndex]?.dataset.cost;
  const costInput = selectElement.parentElement.querySelector('.cost');
  if (costInput && cost) {
    costInput.value = cost;
  }
}

async function saveExtras() {
  const rows = document.querySelectorAll(".extra-row");
  const extras = Array.from(rows).map(row => ({
    item_id: parseInt(row.querySelector(".item-select").value),
    quantity: parseFloat(row.querySelector(".qty").value) || 0,
    cost_per_unit: parseFloat(row.querySelector(".cost").value) || 0,
    type: row.dataset.type,
    ...(row.dataset.type === 'ingredient' && {
      unit: row.querySelector(".unit").value
    })
  }));

  const batchId = window.location.pathname.split('/').pop();
  
  try {
    const response = await fetch(`/batches/add-extra/${batchId}`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-CSRFToken": document.querySelector('input[name="csrf_token"]').value
      },
      body: JSON.stringify({ extras })
    });

    const data = await response.json();
    
    if (data.errors) {
      displayErrors(data.errors);
    } else {
      // Clear existing extras
      document.getElementById('extra-ingredients-container').innerHTML = '';
      
      // Update summary table
      await updateSummaryTable();
      
      alert("Extra ingredients saved successfully");
    }
  } catch (err) {
    alert("Error saving extras: " + err.message);
    console.error(err);
  }
}

async function updateSummaryTable() {
  const response = await fetch(window.location.href);
  const html = await response.text();
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');
  const newSummary = doc.querySelector('.batch-summary');
  const currentSummary = document.querySelector('.batch-summary');
  if (newSummary && currentSummary) {
    currentSummary.innerHTML = newSummary.innerHTML;
  }
}

function displayErrors(errors) {
  const message = errors.map(err =>
    `❌ ${err.ingredient}: ${err.message}`
  ).join("\n\n");
  alert("Save failed:\n\n" + message);
}

function markBatchFailed() {
  if (!confirm('Mark this batch as failed? This action cannot be undone.')) return;
  
  submitForm('fail');
}

function cancelBatch() {
  if (!confirm('Cancel this batch? Ingredients will be returned to inventory.')) return;
  
  submitForm('cancel');
}

function submitForm(action) {
  const batchId = window.location.pathname.split('/').pop();
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `/batches/${action}/${batchId}`;

  const csrf = document.querySelector('input[name="csrf_token"]').value;
  const csrfInput = document.createElement('input');
  csrfInput.type = 'hidden';
  csrfInput.name = 'csrf_token';
  csrfInput.value = csrf;

  form.appendChild(csrfInput);
  document.body.appendChild(form);
  form.submit();
}

async function saveBatchNotes() {
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
