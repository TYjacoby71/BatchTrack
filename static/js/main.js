document.addEventListener('DOMContentLoaded', function() {
  // Quick Add Unit cancel handler
  document.getElementById('cancelQuickUnit')?.addEventListener('click', () => {
    const unitModal = bootstrap.Modal.getInstance(document.getElementById('quickAddUnitModal'));
    if (unitModal) unitModal.hide();

    setTimeout(() => {
      const ingredientModal = new bootstrap.Modal(document.getElementById('quickAddIngredientModal'));
      ingredientModal.show();
      document.getElementById('ingredientName')?.focus();
    }, 300);
  });

  // Quick Add Ingredient cancel handler
  document.getElementById('cancelQuickIngredient')?.addEventListener('click', () => {
    const modal = bootstrap.Modal.getInstance(document.getElementById('quickAddIngredientModal'));
    if (modal) modal.hide();
  });
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

// Helper function to update stock check table
async function checkStock() {
  const recipeId = document.getElementById('recipeSelect').value;
  const scale = parseFloat(document.getElementById('scaleInput').value);
  
  if (!recipeId) {
    alert('Please select a recipe');
    return;
  }
  
  if (!scale || scale <= 0) {
    alert('Please enter a scale greater than 0');
    return;
  }

  try {
    const response = await fetch('/stock/check', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        recipe_id: recipeId,
        scale: parseFloat(scale)
      })
    });

    if (!response.ok) throw new Error('Network response was not ok');
    const data = await response.json();
    updateStockCheckTable(data);
    
    // Show step 2 after successful stock check
    document.getElementById('step1').style.display = 'none';
    document.getElementById('step2').style.display = 'block';
    
  } catch (error) {
    console.log('Error checking stock:', error);
  }
}

function updateStockCheckTable(data) {
  const tableBody = document.getElementById('stockCheckTableBody');
  const startBatchControls = document.getElementById('startBatchControls');
  
  if (!tableBody || !data) return;

  // Update table contents
  tableBody.innerHTML = data.stock_check.map(item => {
    const showUnit = item.type !== 'container';
    return `
      <tr class="${item.status === 'OK' ? 'table-success' : item.status === 'LOW' ? 'table-warning' : 'table-danger'}">
        <td>${item.type || 'ingredient'}</td>
        <td>${item.name}</td>
        <td>${item.needed}${showUnit ? ' ' + item.unit : ''}</td>
        <td>${item.available}${showUnit ? ' ' + item.unit : ''}</td>
        <td>${showUnit ? item.unit : '-'}</td>
        <td>
          <span class="badge ${item.status === 'OK' ? 'bg-success' : item.status === 'LOW' ? 'bg-warning' : 'bg-danger'}">
            ${item.status}
          </span>
        </td>
      </tr>
    `;
  }).join('');

  // Show/hide start batch controls based on stock check results
  if (startBatchControls) {
    startBatchControls.style.display = data.all_ok ? 'block' : 'none';
  }
}