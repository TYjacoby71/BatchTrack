// Batch form functionality
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('finishBatchModal');
  const modalForm = document.getElementById('finishBatchModalForm');
  const outputTypeSelect = document.getElementById('output_type');

  if (modal) {
    modal.addEventListener('shown.bs.modal', function () {
      if (outputTypeSelect) {
        toggleOutputFields();
      }
    });
  }

  if (outputTypeSelect) {
    outputTypeSelect.addEventListener('change', toggleOutputFields);
  }

  if (!modalForm) {
    console.warn('Modal form not found on initial load');
  }
});

function toggleOutputFields() {
  const outputType = document.getElementById('output_type').value;
  const productFields = document.getElementById('productFields');
  const outputUnit = document.getElementById('output_unit');
  const unitWarning = document.getElementById('unit-warning');

  if (outputType === 'product') {
    productFields.style.display = 'block';
    unitWarning.style.display = 'none';
  } else {
    productFields.style.display = 'none';
    // Query for existing intermediate ingredient
    fetch(`/api/ingredients/intermediate/${recipeName}`)
      .then(response => response.json())
      .then(data => {
        if (data.exists) {
          // Store original unit
          outputUnit.dataset.originalUnit = data.unit;
          // Select matching unit
          outputUnit.value = data.unit;
        }
      });
  }

  // Add change listener for unit selection
  outputUnit.onchange = function() {
    if (outputType === 'ingredient' && outputUnit.dataset.originalUnit) {
      if (outputUnit.value !== outputUnit.dataset.originalUnit) {
        unitWarning.style.display = 'block';
      } else {
        unitWarning.style.display = 'none';
      }
    }
  };
}

function submitFinishBatch() {
  const modalForm = document.getElementById('finishBatchModalForm');
  if (!modalForm) return;

  const finalQtyInput = modalForm.querySelector('#final_quantity');
  const finalQty = parseFloat(finalQtyInput?.value);

  if (!finalQty || isNaN(finalQty) || finalQty <= 0) {
    alert('Please enter a valid final quantity');
    return;
  }

  const formData = new FormData(modalForm);

  fetch(modalForm.action, {
    method: 'POST',
    body: formData,
    headers: {
      'X-CSRFToken': formData.get('csrf_token'),
      'Accept': 'application/json'
    }
  })
  .then(response => {
    if (!response.ok) {
      return response.json().then(err => {
        throw new Error(err.error || 'Batch failed to complete');
      });
    }
    window.location.href = '/batches/';
  })
  .catch(err => {
    alert('Error completing batch: ' + err.message);
  });
}

function toggleBatchTypeFields() {
    const type = document.getElementById('output_type').value;
    const productFields = document.getElementById('productFields');

    if (type === 'product') {
        productFields.style.display = 'block';
        document.getElementById('product_id').required = true;
    } else {
        productFields.style.display = 'none';
        document.getElementById('product_id').required = false;
    }
}

async function loadProductVariants() {
    const productId = document.getElementById('product_id').value;
    const variantSelect = document.getElementById('variant_label');

    if (!productId) {
        variantSelect.innerHTML = '<option value="">Select a product first</option>';
        return;
    }

    try {
        const response = await fetch(`/api/products/${productId}/variants`);
        const variants = await response.json();

        if (variants.length > 0) {
            variantSelect.innerHTML = variants.map(v => 
                `<option value="${v.name}">${v.name}</option>`
            ).join('');
        } else {
            variantSelect.innerHTML = '<option value="">No variants available</option>';
        }
    } catch (error) {
        console.error('Error loading variants:', error);
        variantSelect.innerHTML = '<option value="">Error loading variants</option>';
    }
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    toggleBatchTypeFields();
    var tooltips = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltips.map(function (tooltip) {
        return new bootstrap.Tooltip(tooltip);
    });
});

function markBatchFailed() {
    if (confirm('Are you sure you want to mark this batch as failed?')) {
        const batchId = window.location.pathname.split('/').pop();
        fetch(`/finish-batch/${batchId}/fail`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
            }
        }).then(response => {
            if (response.ok) {
                window.location.href = '/batches/';
            }
        });
    }
}

function saveBatchAndExit() {
    const batchId = window.location.pathname.split('/').pop();
    const notes = document.querySelector('textarea[name="notes"]').value;
    const tags = document.querySelector('input[name="tags"]').value;

    fetch(`/batches/${batchId}/update-notes`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('.csrf-token').value
        },
        body: JSON.stringify({
            notes: notes,
            tags: tags
        })
    })
    .then(response => {
        if (response.ok) {
            window.location.href = '/batches/';
        }
    });
}

function updateRowCost(selectElement) {
    const cost = selectElement.options[selectElement.selectedIndex].dataset.cost;
    const costInput = selectElement.parentElement.querySelector('.cost');
    costInput.value = cost;
}

function addExtraIngredientRow() {
    const template = document.getElementById('extra-ingredient-template');
    const clone = template.content.cloneNode(true);
    document.getElementById('extra-ingredients-container').appendChild(clone);

    // Initialize Select2 on the new row's selects
    const newRow = document.getElementById('extra-ingredients-container').lastElementChild;
    $(newRow).find('.select2-input').select2({
        width: 'resolve',
        dropdownAutoWidth: true
    });

    // Set initial cost
    const select = newRow.querySelector('.ingredient-select');
    updateRowCost(select);
}

function addExtraContainerRow() {
    const template = document.getElementById('extra-container-template');
    const clone = template.content.cloneNode(true);
    document.getElementById('extra-containers-container').appendChild(clone);

    // Initialize Select2 on the new row's selects
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