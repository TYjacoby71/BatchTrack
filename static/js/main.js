
async function checkProductionStock() {
    const form = document.querySelector('.production-plan-form');
    const formData = new FormData(form);
    
    try {
        const response = await fetch(window.location.href, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const result = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(result, 'text/html');
        
        // Update only the stock check results section
        const stockCheckResults = doc.querySelector('.stock-check-results');
        if (stockCheckResults) {
            const currentResults = document.querySelector('.stock-check-results');
            if (currentResults) {
                currentResults.replaceWith(stockCheckResults);
            } else {
                form.appendChild(stockCheckResults);
            }
        }
        
        // Reinitialize any necessary event listeners
        initializeEventListeners();
        
    } catch (error) {
        console.error('Error checking stock:', error);
        alert('Error checking stock. Please try again.');
    }
}

function initializeEventListeners() {
    // Add any event listeners that need to be reinitialized after content update
    document.getElementById('showContainerSelection')?.addEventListener('click', function() {
        const containerSelection = document.getElementById('containerSelection');
        containerSelection.style.display = 'block';
        this.style.display = 'none';
        addContainerRow();
    });

    document.getElementById('addAnotherContainer')?.addEventListener('click', function() {
        addContainerRow();
    });
}


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


document.addEventListener('DOMContentLoaded', function() {
  // Quick Add Unit Handler
  function initQuickAddUnit() {
    const saveButton = document.getElementById('saveQuickUnit');
    if (!saveButton) {
      console.warn('Save button not found: saveQuickUnit');
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

async function checkStock() {
  const recipeSelect = document.getElementById('recipeSelect');
  const scaleInput = document.getElementById('scaleInput');

  if (!recipeSelect || !scaleInput) {
    console.error('Required elements not found');
    return;
  }

  const recipeId = recipeSelect.value;
  const scale = parseFloat(scaleInput.value || '1.0');

  if (!recipeId || isNaN(scale) || scale <= 0) {
    alert('Please select a recipe and enter a valid scale');
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
        scale: scale
      })
    });

    if (!response.ok) {
      throw new Error('Network response was not ok');
    }

    const data = await response.json();

    const tableBody = document.getElementById('stockCheckTableBody');
    if (!tableBody) {
      console.error('Stock check table body not found');
      return;
    }

    tableBody.innerHTML = data.stock_check.map(item => `
      <tr class="${item.status === 'OK' ? 'table-success' : item.status === 'LOW' ? 'table-warning' : 'table-danger'}">
        <td>${item.name}</td>
        <td>${item.needed} ${item.unit}</td>
        <td>${item.available} ${item.unit}</td>
        <td>${item.status}</td>
      </tr>
    `).join('');

    document.querySelector('.stock-check-results').style.display = 'block';
  } catch (error) {
    console.error('Error checking stock:', error);
    alert('Error checking stock. Please try again.');
  }
}
