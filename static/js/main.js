// Add CSRF token to fetch headers
// Unit mapping now handled by form submit

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

      const csrfToken = document.querySelector('input[name="csrf_token"]').value;

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

// Save batch data to server
function saveBatch(event) {
    if (event) {
        event.preventDefault();
    }

    const batchId = window.location.pathname.split('/').pop();
    const csrfTokenInput = document.querySelector('input[name="csrf_token"]');
    
    if (!csrfTokenInput) {
        console.error('CSRF token input not found');
        alert('CSRF token not found - please refresh the page');
        return;
    }

    const csrfToken = csrfTokenInput.value;

    // Collect form data
    const formData = {
        notes: document.querySelector('[name="notes"]')?.value || '',
        tags: document.querySelector('[name="tags"]')?.value || '',
        output_type: document.querySelector('#output_type')?.value || null,
        final_quantity: document.querySelector('[name="final_quantity"]')?.value || '0',
        output_unit: document.querySelector('[name="output_unit"]')?.value || '',
        product_id: document.querySelector('[name="product_id"]')?.value || null,
        ingredients: Array.from(document.querySelectorAll('.ingredient-row')).map(row => ({
            id: row.querySelector('select[name="ingredient_id"]')?.value || null,
            amount: row.querySelector('input[name="amount"]')?.value || '0',
            unit: row.querySelector('select[name="unit"]')?.value || 'g'
        })),
        containers: Array.from(document.querySelectorAll('.container-row')).map(row => ({
            id: row.querySelector('select')?.value || null,
            qty: row.querySelector('input[type="number"]')?.value || '0',
            cost_each: row.querySelector('input[type="number"]:last-child')?.value || '0'
        })),
        timers: Array.from(document.querySelectorAll('.timer-row')).map(row => ({
            name: row.querySelector('input[type="text"]')?.value || '',
            duration_seconds: parseInt(row.querySelector('input[type="number"]')?.value || '0') * 60
        }))
    };

    fetch(`/batches/${batchId}/save`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(formData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.message) {
            alert(data.message);
        }
    })
    .catch(error => {
        console.error('Error saving batch:', error);
        alert('Error saving batch. Please check the form and try again.');
    });
}

function cancelBatch() {
    if (confirm('Are you sure you want to cancel this batch? This will attempt to restore used inventory.')) {
        const batchId = window.location.pathname.split('/').pop();
        fetch(`/batches/cancel/${batchId}`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name="csrf_token"]').value
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

// Timer management functions
function addTimerRow() {
    const container = document.getElementById('timer-list');
    const div = document.createElement('div');
    div.className = 'timer-row d-flex gap-2 mb-2';

    div.innerHTML = `
        <input type="text" name="timers[]" class="form-control me-2" placeholder="Timer Name" required>
        <input type="number" name="timer_durations[]" class="form-control me-2" placeholder="Duration (seconds)" required>
        <input type="checkbox" name="timer_completed[]" class="form-check-input me-2 timer-completed">
        <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()">✕</button>
    `;

    container.appendChild(div);
}

// Helper functions for other batch operations
function finishBatch(action) {
    if (confirm(`Are you sure you want to ${action} this batch?`)) {
        const form = document.getElementById('batchForm');
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'action';
        input.value = action;
        form.appendChild(input);
        form.submit();
    }
}

function cancelBatch() {
    if (confirm('Are you sure you want to cancel this batch? This will attempt to restore used inventory.')) {
        const batchId = window.location.pathname.split('/').pop();
        fetch(`/batches/cancel/${batchId}`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name="csrf_token"]').value
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

// Density Reference Functionality