// Unit loading and conversion functions
async function loadUnits() {
  try {
    const response = await fetch('/conversion/units');
    const units = await response.json();
    return units;
  } catch (error) {
    console.error('Error loading units:', error);
    return [];
  }
}

// DOM Ready handler
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

  // Quick Add Unit Handler
  function initQuickAddUnit() {
    const saveButton = document.getElementById('saveQuickUnit');
    if (!saveButton) {
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


  // Container selection handlers
  const containerSection = document.getElementById('containerSelection');
  const btnAddInitial = document.getElementById('showContainerSelection');
  const containerRows = document.getElementById('container-rows');
  const btnAddMore = document.getElementById('addAnotherContainerBtn');

  if (btnAddInitial) {
    btnAddInitial.addEventListener('click', () => {
      btnAddInitial.style.display = 'none';
      containerSection.style.display = 'block';
      addContainerRow();
    });
  }

  if (btnAddMore) {
    btnAddMore.addEventListener('click', addContainerRow);
  }

  if (containerRows) {
    containerRows.addEventListener('click', (e) => {
      if (e.target.classList.contains('remove-container')) {
        e.target.closest('.container-entry').remove();
        handleContainerVisibility();
      }
    });
  }
});

// Helper functions
function handleContainerVisibility() {
  const containerSection = document.getElementById('containerSelection');
  const btnAddInitial = document.getElementById('showContainerSelection');
  const containerRows = document.getElementById('container-rows');

  if (!containerSection || !btnAddInitial || !containerRows) return;

  const hasRows = !!containerRows.querySelector('.container-entry');
  containerSection.style.display = hasRows ? 'block' : 'none';
  btnAddInitial.style.display = hasRows ? 'none' : 'inline-block';
}

function addContainerRow() {
  const containerRows = document.getElementById('container-rows');
  if (!containerRows) return;

  const containerRow = document.createElement('div');
  containerRow.className = 'container-entry d-flex align-items-center gap-2 mb-2';
  containerRow.innerHTML = `
    <select name="container_ids[]" class="form-select" required>
      <option value="">Select a container</option>
      {% for container in containers %}
        <option value="{{ container.id }}">{{ container.name }} ({{ container.quantity }} {{ container.unit }} in stock)</option>
      {% endfor %}
    </select>
    <input type="number" name="container_quantities[]" class="form-control w-25" placeholder="Qty" min="1" required>
    <button type="button" class="btn btn-danger btn-sm remove-container">✕</button>
  `;
  containerRows.appendChild(containerRow);
}

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