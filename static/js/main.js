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

// Initialize unit loading when unit converter modal opens
const unitConverterModal = document.getElementById('unitConverterModal');
if (unitConverterModal) {
  unitConverterModal.addEventListener('show.bs.modal', loadUnits);
}

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

      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

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
  loadUnits();
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

function loadUnits() {
  fetch('/conversion/units', {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    credentials: 'same-origin'
  })
    .then(response => {
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      return response.json();
    })
    .then(units => {
      if (!units || (Array.isArray(units) && units.length === 0)) {
        console.warn('No units available');
        return;
      }
      const unitSelectors = document.querySelectorAll('select[data-unit-select], #fromUnit, #toUnit');
      unitSelectors.forEach(select => {
        if (!select) return;
        select.innerHTML = '';
        //Added grouping of units by category
        const unitGroups = {};
        units.forEach(unit => {
          const category = unit.type || 'Other';
          if (!unitGroups[category]) {
            unitGroups[category] = [];
          }
          unitGroups[category].push(unit);
        });

        for (const category in unitGroups) {
          const optgroup = document.createElement('optgroup');
          optgroup.label = category;
          unitGroups[category].forEach(unit => {
            const option = new Option(unit.name, unit.name);
            optgroup.appendChild(option);
          });
          select.appendChild(optgroup);
        }
        // Initialize Select2 with search
        $(select).select2({
          placeholder: 'Search for a unit...',
          width: '100%',
          allowClear: true
        });
      });
    })
    .catch(error => console.error('Error loading units:', error));
}

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

// Batch save handler
function saveBatch(event) {
    if (event) {
        event.preventDefault();
    }
    
    const batchId = window.location.pathname.split('/').pop();
    const form = document.getElementById('batchForm');
    if (!form) {
        console.error('Batch form not found');
        return;
    }

    const data = {
        notes: form.querySelector('textarea[name="notes"]')?.value || '',
        tags: form.querySelector('input[name="tags"]')?.value || '',
        output_type: form.querySelector('select[name="output_type"]')?.value,
        product_id: form.querySelector('select[name="product_id"]')?.value,
        variant_label: form.querySelector('input[name="variant_label"]')?.value,
        final_quantity: parseFloat(form.querySelector('input[name="final_quantity"]')?.value) || 0,
        output_unit: form.querySelector('select[name="output_unit"]')?.value || '',
        ingredients: Array.from(form.querySelectorAll('.ingredient-row')).map(row => ({
            id: parseInt(row.querySelector('select[name="ingredients[]"]').value),
            amount: parseFloat(row.querySelector('input[name="amounts[]"]').value),
            unit: row.querySelector('select[name="units[]"]').value
        })),
        containers: Array.from(form.querySelectorAll('.container-row')).map(row => ({
            id: parseInt(row.querySelector('select[name="containers[]"]').value),
            qty: parseInt(row.querySelector('input[name="container_amounts[]"]').value),
            cost_each: parseFloat(row.querySelector('input[name="container_costs[]"]').value) || 0
        })),
        timers: Array.from(form.querySelectorAll('.timer-row')).map(row => ({
            name: row.querySelector('input[name="timers[]"]').value,
            duration_seconds: parseInt(row.querySelector('input[name="timer_durations[]"]').value)
        }))
    };

    const csrfToken = form.querySelector('input[name="csrf_token"]').value;

    fetch(`/batches/${batchId}/save`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            // Keep form values after save
            const notesField = form.querySelector('textarea[name="notes"]');
            const tagsField = form.querySelector('input[name="tags"]');
            if (notesField) notesField.value = data.notes || notesField.value;
            if (tagsField) tagsField.value = data.tags || tagsField.value;
            alert('Batch saved successfully');
        }
    })
    .catch(error => {
        console.error('Error saving batch:', error);
        alert('Error saving batch');
    });
}

// Density Reference Functionality
document.addEventListener('DOMContentLoaded', function() {
  fetch('/data/density_reference.json')
    .then(response => response.json())
    .then(data => {
      const tableBody = document.getElementById('densityTableBody');
      const searchInput = document.getElementById('densitySearch');

      function renderDensityTable(items) {
        tableBody.innerHTML = items.map(item => `
          <tr>
            <td>${item.name}</td>
            <td>${item.density_g_per_ml}</td>
            <td>${item.category || ''}</td>
            <td>
              <button class="btn btn-sm btn-primary" onclick="useDensity(${item.density_g_per_ml})">
                Use
              </button>
            </td>
          </tr>
        `).join('');
      }

      renderDensityTable(data.common_densities);

      searchInput?.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filtered = data.common_densities.filter(item => 
          item.name.toLowerCase().includes(searchTerm) ||
          (item.category && item.category.toLowerCase().includes(searchTerm))
        );
        renderDensityTable(filtered);
      });

      window.useDensity = function(density) {
        document.getElementById('density').value = density;
        bootstrap.Modal.getInstance(document.getElementById('densityModal')).hide();
      };
    });
});