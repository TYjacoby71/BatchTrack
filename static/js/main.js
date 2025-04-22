function loadUnits() {
  fetch('/conversion/units')
    .then(response => response.json())
    .then(units => {
      const unitSelectors = document.querySelectorAll('select[data-unit-select]');
      unitSelectors.forEach(select => {
        select.innerHTML = '';
        units.forEach(unit => {
          const option = new Option(unit.name, unit.name);
          select.add(option);
        });
      });
    })
    .catch(error => console.error('Error loading units:', error));
}

// Load units when relevant modals or pages are shown
document.addEventListener('DOMContentLoaded', function() {
  const unitModals = document.querySelectorAll('[data-load-units]');
  unitModals.forEach(modal => {
    modal.addEventListener('show.bs.modal', loadUnits);
  });

  // If we're on a page that needs units loaded immediately
  if (document.querySelector('[data-unit-select]')) {
    loadUnits();
  }
});

function loadUnits() {
  fetch('/conversion/units')
    .then(response => response.json())
    .then(units => {
      const unitSelectors = document.querySelectorAll('select[data-unit-select], #fromUnit, #toUnit');
      unitSelectors.forEach(select => {
        if (!select) return;
        select.innerHTML = '';
        units.forEach(unit => {
          select.add(new Option(unit.name, unit.name));
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