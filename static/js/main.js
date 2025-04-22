async function loadUnits() {
  try {
    const response = await fetch('/conversion/units', {
      headers: {
        'Accept': 'application/json'
      }
    });
    const units = await response.json();

    // Populate all unit selectors
    const unitSelectors = document.querySelectorAll('select[data-unit-select], select[name="base_unit"], #fromUnit, #toUnit');
    unitSelectors.forEach(select => {
      const currentValue = select.value;
      select.innerHTML = '';
      units.forEach(unit => {
        const option = document.createElement('option');
        option.value = unit.name;
        option.textContent = unit.name;
        select.appendChild(option);
      });
      // Restore selected value if it exists
      if (currentValue && [...select.options].find(opt => opt.value === currentValue)) {
        select.value = currentValue;
      }
    });

    // Type-specific population for the base unit dropdown
    const typeSelect = document.querySelector('select[name="type"]');
    const baseUnitSelect = document.querySelector('select[name="base_unit"]');

    if (typeSelect && baseUnitSelect) {
      const updateBaseUnits = () => {
        const selectedType = typeSelect.value;
        const typeUnits = units.filter(unit => unit.type === selectedType);
        baseUnitSelect.innerHTML = '';
        typeUnits.forEach(unit => {
          const option = document.createElement('option');
          option.value = unit.name;
          option.textContent = unit.name;
          baseUnitSelect.appendChild(option);
        });
      };

      typeSelect.addEventListener('change', updateBaseUnits);
      updateBaseUnits(); // Initial population
    }
  } catch (error) {
    console.error("Error loading units:", error);
  }
}

// Add event listeners for unit loading
document.addEventListener('DOMContentLoaded', () => {
  loadUnits();

  // Reload units when modals with unit selectors are shown
  const modalsWithUnits = document.querySelectorAll('[data-bs-toggle="modal"]');
  modalsWithUnits.forEach(modalTrigger => {
    modalTrigger.addEventListener('click', loadUnits);
  });
});

document.getElementById('unitConverterModal')?.addEventListener('show.bs.modal', loadUnits);

function displayResult(element, text, note = '') {
  element.innerHTML = `
    <p>${text}</p>
    ${note ? `<p class="text-muted small">${note}</p>` : ''}
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
        let note = '';
        if (data.mapping_used) {
          note = `Using custom mapping: 1 ${fromUnit} = ${data.mapping_multiplier} ${data.unit}`;
        }
        displayResult(resultDiv, `${amount} ${fromUnit} = ${data.result} ${data.unit}`, note);
      }
    })
    .catch(err => {
      resultDiv.innerHTML = `<p class="text-danger">Error: ${err.message}</p>`;
    });
}