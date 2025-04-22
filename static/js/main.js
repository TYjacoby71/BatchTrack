// Unit Management and Conversion
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
      if (!unitSelectors.length) return;

      unitSelectors.forEach(select => {
        if (!select) return;
        select.innerHTML = '';

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

        try {
          $(select).select2({
            placeholder: 'Search for a unit...',
            width: '100%',
            allowClear: true
          });
        } catch (e) {
          console.warn('Select2 not available:', e);
        }
      });
    })
    .catch(error => console.error('Error loading units:', error));
}

// Filter units by type
function filterUnits() {
  const filter = document.getElementById('unitFilter')?.value || 'all';
  const unitCards = document.querySelectorAll('.card.mb-3');

  unitCards.forEach(card => {
    const type = card.querySelector('h5')?.textContent.toLowerCase();
    if (filter === 'all' || filter === type) {
      card.style.display = '';
    } else {
      card.style.display = 'none';
    }
  });
}

// Initialize units when page loads
document.addEventListener('DOMContentLoaded', loadUnits);

// Initialize units when unit converter modal opens
const unitConverterModal = document.getElementById('unitConverterModal');
if (unitConverterModal) {
  unitConverterModal.addEventListener('show.bs.modal', loadUnits);
}

// Unit conversion function
function convertUnits() {
  const amount = document.getElementById('amount')?.value;
  const fromUnit = document.getElementById('fromUnit')?.value;
  const toUnit = document.getElementById('toUnit')?.value;
  const ingredientId = document.getElementById('ingredientId')?.value;
  const resultDiv = document.getElementById('converterResult');

  if (!amount || !fromUnit || !toUnit || !resultDiv) return;

  fetch(`/convert/convert/${amount}/${fromUnit}/${toUnit}?ingredient_id=${ingredientId}`)
    .then(response => response.json())
    .then(data => {
      if (data.error && data.error.includes("without density")) {
        const useDefault = confirm(
          `Converting ${fromUnit} to ${toUnit} requires density.\n` +
          `No density defined. Use water (1.0 g/mL)?`
        );
        if (useDefault) {
          return fetch(`/convert/convert/${amount}/${fromUnit}/${toUnit}?ingredient_id=${ingredientId}&density=1.0`)
            .then(r => r.json());
        }
        throw new Error('Conversion canceled');
      }
      return data;
    })
    .then(data => {
      displayResult(resultDiv, `${amount} ${fromUnit} = ${data.result} ${data.unit}`);
    })
    .catch(err => {
      resultDiv.innerHTML = `<p class="text-danger">Error: ${err.message}</p>`;
    });
}

// Utility functions
function displayResult(element, text) {
  if (!element) return;
  element.innerHTML = `
    <p>${text}</p>
    <button class="btn btn-sm btn-secondary" onclick="copyToClipboard('${text}')">Copy</button>
  `;
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text)
    .then(() => alert('Copied to clipboard!'))
    .catch(err => console.error('Failed to copy:', err));
}

//This part remains from original code.
function checkStock() {
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

  fetch('/stock/check', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      recipe_id: recipeId,
      scale: scale
    })
  })
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.json();
    })
    .then(data => {
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
    })
    .catch(error => {
      console.error('Error checking stock:', error);
      alert('Error checking stock. Please try again.');
    });
}