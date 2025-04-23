
document.addEventListener('DOMContentLoaded', function() {
  const quickAddForm = document.getElementById('quickAddIngredientForm');
  if (quickAddForm) {
    quickAddForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      const name = document.getElementById('new-ingredient-name').value;
      const unit = document.getElementById('new-ingredient-unit').value;

      fetch('/ingredient', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify({ name, unit })
      })
      .then(res => res.json())
      .then(data => {
        if (data && data.id && data.name) {
          const dropdown = document.querySelector('#ingredient-select');
          const option = new Option(data.name, data.id, true, true);
          dropdown.add(option);
        }
        const modal = bootstrap.Modal.getInstance(document.getElementById('quickAddIngredientModal'));
        modal.hide();
      })
      .catch(err => {
        console.error('Quick add failed', err);
      });
    });
  }
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

// Load units when page loads and when converter modal opens
document.addEventListener('DOMContentLoaded', loadUnits);
document.getElementById('unitConverterModal')?.addEventListener('show.bs.modal', loadUnits);

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