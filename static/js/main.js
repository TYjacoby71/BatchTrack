// CSRF Helper
function getCSRFToken() {
  var tokenElement = document.querySelector('input[name="csrf_token"]');
  return tokenElement ? tokenElement.value : '';
}

// Batch Snapshot Manager
const batchSnapshot = {
  data: {
    recipe_ingredients: [],
    recipe_containers: [],
    extra_ingredients: [],
    extra_containers: [],
    timers: []
  },

  addIngredient(ingredient) {
    this.data.extra_ingredients.push({
      id: ingredient.id,
      name: ingredient.name,
      amount: parseFloat(ingredient.amount),
      unit: ingredient.unit,
      cost_per_unit: ingredient.cost_per_unit || 0
    });
    this.updateUI();
  },

  addContainer(container) {
    this.data.extra_containers.push({
      id: container.id,
      name: container.name,
      quantity: parseInt(container.quantity),
      cost: parseFloat(container.cost)
    });
    this.updateUI();
  },

  addTimer(timer) {
    this.data.timers.push({
      name: timer.name,
      duration_seconds: parseInt(timer.duration) * 60
    });
  },

  serialize() {
    return JSON.stringify(this.data);
  },

  load(snapshotString) {
    try {
      if (!snapshotString) {
        this.data = {
          recipe_ingredients: [],
          recipe_containers: [],
          extra_ingredients: [],
          extra_containers: [],
          timers: []
        };
      } else {
        this.data = JSON.parse(snapshotString);
      }
      // Ensure all required arrays exist
      this.data.recipe_ingredients = this.data.recipe_ingredients || [];
      this.data.recipe_containers = this.data.recipe_containers || [];
      this.data.extra_ingredients = this.data.extra_ingredients || [];
      this.data.extra_containers = this.data.extra_containers || [];
      this.data.timers = this.data.timers || [];
      this.updateUI();
    } catch (e) {
      console.error('Failed to load snapshot:', e);
      // Initialize with empty data on error
      this.data = {
        recipe_ingredients: [],
        recipe_containers: [],
        extra_ingredients: [],
        extra_containers: [],
        timers: []
      };
    }
  },

  restore() {
    const snapshotElem = document.getElementById('recipe-snapshot');
    if (snapshotElem) {
      this.load(snapshotElem.value);
    }
  },

  updateUI() {
    this.updateSummaryTable();
    document.getElementById('recipe-snapshot').value = this.serialize();
  },

  updateSummaryTable() {
    const summaryTable = document.querySelector('.batch-summary table tbody');
    if (!summaryTable) return;

    let html = '';

    // Recipe ingredients (blue)
    if (this.data.recipe_ingredients) {
      this.data.recipe_ingredients.forEach(item => {
        html += this.renderTableRow('info', item.name, 'recipe', item.amount, item.unit, item.cost_per_unit);
      });
    }

    // Recipe containers (blue)
    if (this.data.recipe_containers) {
      this.data.recipe_containers.forEach(item => {
        html += this.renderTableRow('info', item.name, 'recipe container', item.quantity, 'count', item.cost);
      });
    }

    // Extra ingredients (yellow)
    this.data.extra_ingredients.forEach(item => {
      html += this.renderTableRow('warning', item.name, 'extra', item.amount, item.unit, item.cost_per_unit);
    });

    // Extra containers (red)
    this.data.extra_containers.forEach(item => {
      html += this.renderTableRow('danger', item.name, 'extra container', item.quantity, 'count', item.cost);
    });

    summaryTable.innerHTML = html;
  },

  renderTableRow(colorClass, name, type, quantity, unit, cost) {
    const total = quantity * (cost || 0);
    return `<tr class="table-${colorClass}">
      <td>${name} (${type})</td>
      <td>${quantity}</td>
      <td>${unit}</td>
      <td>$${cost || 0}</td>
      <td>$${total.toFixed(2)}</td>
    </tr>`;
  }
};

// Batch Form Manager
const batchForm = {
  save(event) {
    if (event) event.preventDefault();

    const batchId = window.location.pathname.split('/').pop();
    const formData = {
      notes: document.querySelector('textarea[name="notes"]')?.value || '',
      tags: document.querySelector('input[name="tags"]')?.value || '',
      output_type: document.querySelector('#output_type')?.value || 'product',
      final_quantity: document.querySelector('input[name="final_quantity"]')?.value || '0',
      output_unit: document.querySelector('select[name="output_unit"]')?.value || '',
      product_id: document.querySelector('select[name="product_id"]')?.value || null,
      variant_id: document.querySelector('input[name="variant_label"]')?.value || '',
      recipe_snapshot: batchSnapshot.data
    };

    fetch(`/batches/${batchId}/save`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken()
      },
      body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
      if (data.message) {
        alert(data.message);
        window.location.href = '/batches/';
      }
    })
    .catch(error => {
      console.error('Error saving batch:', error);
      alert('Error saving batch');
    });
  }
};

// UI Event Handlers
function addIngredient() {
  const select = document.getElementById('newIngredient');
  const amount = document.getElementById('newIngAmount');
  const unit = document.getElementById('newIngUnit');

  batchSnapshot.addIngredient({
    id: select.value,
    name: select.options[select.selectedIndex].text,
    amount: amount.value,
    unit: unit.value
  });

  amount.value = '';
}

function addContainer() {
  const select = document.getElementById('newContainer');
  const quantity = document.getElementById('newContainerQty');
  const cost = document.getElementById('newContainerCost');

  if (!select.value || !quantity.value || !cost.value) return;

  batchSnapshot.addContainer({
    id: select.value,
    name: select.options[select.selectedIndex].text,
    quantity: quantity.value,
    cost: cost.value
  });

  quantity.value = '';
  cost.value = '';
}

function addTimerRow() {
  const container = document.getElementById('timer-list');
  const div = document.createElement('div');
  div.className = 'timer-row d-flex gap-2 mb-2';
  div.innerHTML = `
    <input type="text" name="timers[]" class="form-control me-2" placeholder="Timer Name" required>
    <input type="number" name="timer_durations[]" class="form-control me-2" placeholder="Duration (minutes)" required>
    <input type="checkbox" name="timer_completed[]" class="form-check-input me-2 timer-completed">
    <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()">✕</button>
  `;
  container.appendChild(div);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  batchSnapshot.restore();

  const outputTypeSelect = document.getElementById('output_type');
  if (outputTypeSelect) {
    outputTypeSelect.addEventListener('change', function() {
      const productFields = document.getElementById('productFields');
      const ingredientFields = document.getElementById('ingredientFields');

      productFields.style.display = this.value === 'product' ? 'block' : 'none';
      ingredientFields.style.display = this.value === 'product' ? 'none' : 'block';
    });
  }

  // Initialize Select2 dropdowns
  $('select[data-unit-select]').select2({
    placeholder: 'Select a unit',
    allowClear: true,
    width: '100%'
  });

  $('.ingredient-select').select2({
    placeholder: 'Select ingredients',
    allowClear: true,
    width: '100%'
  });

  $('.container-select:not([x-data])').select2({
    placeholder: 'Select containers',
    allowClear: true,
    multiple: true,
    width: '100%'
  });

  // Initialize tooltips
  $('[data-bs-toggle="tooltip"]').tooltip();
});

// Modal Handlers
function showCompleteBatchModal() {
  const modal = new bootstrap.Modal(document.getElementById('completeBatchModal'));
  modal.show();
}

function submitCompleteBatch() {
  const form = document.getElementById('completeBatchForm');
  const formData = new FormData(form);
  const batchId = window.location.pathname.split('/').pop();

  fetch(`/batches/${batchId}/finish`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCSRFToken()
    },
    body: JSON.stringify(Object.fromEntries(formData))
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      window.location.href = '/batches/';
    } else {
      alert(data.error || 'Error completing batch');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error completing batch');
  });
}

function cancelBatch() {
  if (confirm('Are you sure you want to cancel this batch? This will attempt to restore used inventory.')) {
    const batchId = window.location.pathname.split('/').pop();
    fetch(`/batches/cancel/${batchId}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCSRFToken()
      }
    })
    .then(response => {
      if (response.ok) {
        window.location.href = '/batches/';
      } else {
        alert('Error cancelling batch');
      }
    });
  }
}

//Add CSRF token to fetch headers
//Unit mapping now handled by form submit

$(document).ready(function() {
  // Initialize all global Select2 dropdowns (ingredients page, recipes page, etc.)
  $('select[data-unit-select]').select2({
    placeholder: 'Select a unit',
    allowClear: true,
    width: '100%'
  });

  $('.ingredient-select').select2({
    placeholder: 'Select ingredients',
    allowClear: true,
    width: '100%'
  });

  // Bootstrap tooltips site-wide
  $('[data-bs-toggle="tooltip"]').tooltip();

  // Quick add modal transitions (for ingredients and units)
  document.getElementById('cancelQuickUnit')?.addEventListener('click', () => {
    const unitModal = bootstrap.Modal.getInstance(document.getElementById('quickAddUnitModal'));
    if (unitModal) unitModal.hide();

    setTimeout(() => {
      const ingredientModal = new bootstrap.Modal(document.getElementById('quickAddIngredientModal'));
      ingredientModal.show();
      document.getElementById('ingredientName')?.focus();
    }, 300);
  });

  document.getElementById('cancelQuickIngredient')?.addEventListener('click', () => {
    const modal = bootstrap.Modal.getInstance(document.getElementById('quickAddIngredientModal'));
    if (modal) modal.hide();
  });
  // Initialize Select2 only for non-Alpine container selects
  $('.container-select:not([x-data])').select2({
        placeholder: 'Select containers',
        allowClear: true,
        multiple: true,
        width: '100%'
    });
});

document.addEventListener('DOMContentLoaded', function() {
  // Only handle container checkbox logic on recipe form
  if (document.getElementById('recipeForm')) {
    const requiresContainersCheckbox = document.getElementById('requiresContainers');
    const allowedContainersSection = document.getElementById('allowedContainersSection');

    if (requiresContainersCheckbox && allowedContainersSection) {
      requiresContainersCheckbox.addEventListener('change', function() {
        if (this.checked) {
          allowedContainersSection.style.display = 'block';
        } else {
          allowedContainersSection.style.display = 'none';
        }
      });
    }
  }

  // Quick Add Container form handler
  const quickAddContainerForm = document.getElementById('quickAddContainerForm');
  if (quickAddContainerForm) {
    quickAddContainerForm.addEventListener('submit', function(e) {
      e.preventDefault();
      // Your existing form submission logic here
    });
  }
});

// Unit loading now handled by Jinja templates
document.addEventListener('DOMContentLoaded', function() {
  // Quick Add Unit Handler
  function initQuickAddUnit() {
    const saveButton = document.getElementById('saveQuickUnit');
    if (!saveButton) {
      // Retry after a short delay if button not found
      setTimeout(initQuickAddUnit, 100);
      return;
    }

    saveButton.addEventListener('click', () => {
      const name = document.getElementById('unitName').value.trim();
      const type = document.getElementById('unitType').value;

      if (!name) {
        alert('Unit name required');
        return;
      }

      console.log(`Creating unit: ${name} (${type})`);

      const csrfToken = getCSRFToken();

      fetch('/quick-add/unit', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ name, type })
      })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          alert('Error: ' + data.error);
          return;
        }

        // Insert unit into ingredient modal dropdown
        const unitSelect = document.getElementById('quickIngredientUnit');
        if (unitSelect) {
          const newOption = new Option(data.name, data.name, false, true);
          unitSelect.add(newOption);
          unitSelect.value = data.name;
        }

        // Add to quick ingredient unit dropdown
        const quickUnit = document.getElementById('new-ingredient-unit');
        if (quickUnit) {
          quickUnit.add(new Option(data.name, data.name, false, true));
          quickUnit.value = data.name;
        }

        // Update all other unit dropdowns
        document.querySelectorAll("select[name='units[]']").forEach(select => {
          const option = new Option(data.name, data.name);
          select.add(option);
        });

        // Handle modal transitions
        const unitModal = bootstrap.Modal.getInstance(document.getElementById('quickAddUnitModal'));
        if (unitModal) {
          unitModal.hide();
          setTimeout(() => {
            const ingredientModal = new bootstrap.Modal(document.getElementById('quickAddIngredientModal'));
            ingredientModal.show();
            document.getElementById('ingredientName')?.focus();
          }, 300);
        }

        // Reset form
        document.getElementById('unitName').value = '';
        document.getElementById('unitType').selectedIndex = 0;
      })
      .catch(err => {
        console.error(err);
        alert("Failed to add unit");
      });
    });
  }

  initQuickAddUnit();
});

function filterUnits() {
  const filter = document.getElementById('unitFilter').value;
  const unitCards = document.querySelectorAll('.card.mb-3');

  unitCards.forEach(card => {
    const type = card.querySelector('h5').textContent.toLowerCase();
    if (filter === 'all' || filter === type) {
      card.style.display = '';
    } else {
      card.style.display = 'none';
    }
  });
}

// Unit loading now handled by Jinja templates directly

function displayResult(element, text) {
  element.innerHTML = `
    <p>${text}</p>
    <button class="btn btn-sm btn-secondary" onclick="copyToClipboard('${text}')">Copy</button>
  `;
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert('Copied to clipboard!');
  }).catch(err => {
    console.error('Failed to copy:', err);
  });
}

function convertUnits() {
  const amount = document.getElementById('amount').value;
  const fromUnit = document.getElementById('fromUnit').value;
  const toUnit = document.getElementById('toUnit').value;
  const ingredientId = document.getElementById('ingredientId').value;
  const resultDiv = document.getElementById('converterResult');

  fetch(`/convert/convert/${amount}/${fromUnit}/${toUnit}?ingredient_id=${ingredientId}`)
    .then(response => response.json())
    .then(data => {
      if (data.error && data.error.includes("without density")) {
        const useDefault = confirm(
          `Heads up! You're converting ${fromUnit} to ${toUnit}, which requires a density.\n` +
          `This ingredient doesn't have one defined.\n\nWould you like to:\n✅ Use water (1.0 g/mL)\nℹ️ Or go define it manually?`
        );
        if (useDefault) {
          fetch(`/convert/convert/${amount}/${fromUnit}/${toUnit}?ingredient_id=${ingredientId}&density=1.0`)
            .then(r => r.json())
            .then(result => {
              displayResult(resultDiv, `${amount} ${fromUnit} = ${result.result} ${result.unit}`);
            });
        } else {
          resultDiv.innerHTML = '<p class="text-danger">Conversion canceled.</p>';
        }
      } else {
        displayResult(resultDiv, `${amount} ${fromUnit} = ${data.result} ${data.unit}`);
      }
    })
    .catch(err => {
      resultDiv.innerHTML = `<p class="text-danger">Error: ${err.message}</p>`;
    });
}

// Stock check functionality is now handled in plan_production.html template
// Assuming data.stock_check is an array of objects with at least 'type', 'name', 'needed', 'available', 'unit', and 'status' properties.
function updateStockCheckTable(data) {
  const tableBody = document.getElementById('stockCheckTableBody');
  const startBatchBtn = document.getElementById('startBatchBtn');

  if (!tableBody) return;

  tableBody.innerHTML = data.stock_check.map(item => {
    const showUnit = item.type !== 'container';
    return `
      <tr class="${item.status === 'OK' ? 'table-success' : item.status === 'LOW' ? 'table-warning' : 'table-danger'}">
        <td>${item.type || 'ingredient'}</td>
        <td>${item.name}</td>
        <td>${item.needed}${showUnit ? ' ' + item.unit : ''}</td>
        <td>${item.available}${showUnit ? ' ' + item.unit : ''}</td>
        <td>${showUnit ? item.unit : '-'}</td>
        <td>${item.status}</td>
      </tr>
    `;
  }).join('');

  if (startBatchBtn) {
    startBatchBtn.style.display = data.all_ok ? 'block' : 'none';
  }
}


// Remove duplicate function declarations and use object methods directly
function addContainer(container) {
    if (batchSnapshot && typeof batchSnapshot.addContainer === 'function') {
        batchSnapshot.addContainer(container);
    }
}

function addIngredient(ingredient) {
    if (batchSnapshot && typeof batchSnapshot.addIngredient === 'function') {
        batchSnapshot.addIngredient(ingredient);
    }
}

function saveBatch(event) {
    if (batchForm && typeof batchForm.save === 'function') {
        batchForm.save(event);
    }
}

function showCompleteBatchModal() {
    var modalElement = document.getElementById('completeBatchModal');
    if (modalElement) {
        var modal = new bootstrap.Modal(modalElement);
        modal.show();
    }
}

window.cancelBatch = function() {
    if (confirm('Are you sure you want to cancel this batch? This will attempt to restore used inventory.')) {
        const batchId = window.location.pathname.split('/').pop();
        fetch(`/batches/cancel/${batchId}`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => {
            if (response.ok) {
                window.location.href = '/batches/';
            } else {
                alert('Error cancelling batch');
            }
        });
    }
};

window.showCompleteBatchModal = function() {
    const modal = new bootstrap.Modal(document.getElementById('completeBatchModal'));
    modal.show();
};

// Density Reference Functionality