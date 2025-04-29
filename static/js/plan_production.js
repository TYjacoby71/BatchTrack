// Plan Production Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
  // Button handlers
  const checkStockBtn = document.getElementById('checkStockBtn');
  if (checkStockBtn) {
    checkStockBtn.addEventListener('click', checkStock);
  }

  const addContainerBtn = document.getElementById('addContainerBtn');
  if (addContainerBtn) {
    addContainerBtn.addEventListener('click', addContainerRow);
  }

  const exportShoppingListBtn = document.getElementById('exportShoppingListBtn');
  if (exportShoppingListBtn) {
    exportShoppingListBtn.addEventListener('click', exportShoppingList);
  }
});

function checkStock() {
  const recipeId = document.querySelector('input[name="recipe_id"]').value;
  const scale = document.querySelector('input[name="scale"]').value || 1.0;

  fetch('/api/check-stock', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
    },
    body: JSON.stringify({ recipe_id: recipeId, scale: scale })
  })
  .then(response => response.json())
  .then(data => {
    renderStockResults(data.stock_check);
    document.getElementById('ingredientStockSection').style.display = 'block';
    document.getElementById('startBatchButton').style.display = data.all_ok ? 'block' : 'none';
  })
  .catch(error => {
    console.error('Error checking stock:', error);
    alert('Failed to check stock.');
  });
}

function renderStockResults(stockCheck) {
  const container = document.getElementById('ingredientStockResults');
  if (!container) return;

  let html = '<table class="table"><thead><tr><th>Item</th><th>Needed</th><th>Available</th><th>Status</th></tr></thead><tbody>';

  stockCheck.forEach(item => {
    const statusClass = item.status === 'OK' ? 'text-success' :
                       item.status === 'LOW' ? 'text-warning' : 'text-danger';
    html += `
      <tr>
        <td>${item.name}</td>
        <td>${item.needed} ${item.unit}</td>
        <td>${item.available} ${item.unit}</td>
        <td class="${statusClass}">${item.status}</td>
      </tr>`;
  });

  html += '</tbody></table>';
  container.innerHTML = html;
}

function addContainerRow() {
  const containerArea = document.getElementById('containerSelectionArea');
  if (!containerArea || !window.containers) return;

  const row = document.createElement('div');
  row.className = 'container-row d-flex align-items-center gap-2 mb-2';
  row.innerHTML = `
    <select class="form-select container-select" required>
      <option value="">Select Container</option>
      ${window.containers.map(container => `
        <option value="${container.id}" data-capacity="${container.storage_amount}" data-unit="${container.storage_unit}">
          ${container.name} (${container.storage_amount} ${container.storage_unit})
        </option>
      `).join('')}
    </select>
    <input type="number" class="form-control container-quantity" min="1" value="1" required>
    <button type="button" class="btn btn-danger btn-sm remove-container">×</button>
  `;

  row.querySelector('.remove-container').addEventListener('click', () => {
    row.remove();
    updateContainmentProgress();
  });

  row.querySelector('.container-quantity').addEventListener('change', updateContainmentProgress);
  row.querySelector('.container-select').addEventListener('change', updateContainmentProgress);

  containerArea.appendChild(row);
  updateContainmentProgress();
}

function updateContainmentProgress() {
  const scaleInput = document.querySelector('input[name="scale"]');
  const baseYield = parseFloat(scaleInput.closest('[x-data]').getAttribute('x-data').match(/baseYield:\s*([\d.]+)/)[1]);
  const scale = parseFloat(scaleInput.value) || 1;
  const totalNeeded = baseYield * scale;

  let totalContained = 0;

  document.querySelectorAll('.container-row').forEach(row => {
    const select = row.querySelector('.container-select');
    const quantity = row.querySelector('.container-quantity');
    if (select && quantity && select.value) {
      const capacity = parseFloat(select.selectedOptions[0].dataset.capacity) || 0;
      totalContained += capacity * parseInt(quantity.value);
    }
  });

  const percent = Math.min((totalContained / totalNeeded) * 100, 100);
  const fillProgressBar = document.getElementById('fillProgressBar');
  const remainingDisplay = document.getElementById('remainingToContain');
  const flexModeToggle = document.getElementById('flexMode');
  const containmentError = document.getElementById('containmentError');
  const startBatchButton = document.getElementById('startBatchButton');

  if (fillProgressBar) {
    fillProgressBar.style.width = `${percent}%`;
    fillProgressBar.textContent = `${Math.round(percent)}%`;
  }

  if (remainingDisplay) {
    remainingDisplay.textContent = `Remaining to contain: ${Math.max(totalNeeded - totalContained, 0).toFixed(2)}`;
  }

  if (flexModeToggle && containmentError && startBatchButton) {
    if (!flexModeToggle.checked && totalContained < totalNeeded) {
      containmentError.style.display = 'block';
      containmentError.innerText = 'You must fully contain this batch to proceed.';
      startBatchButton.disabled = true;
    } else {
      containmentError.style.display = 'none';
      startBatchButton.disabled = false;
    }
  }
}

function exportShoppingList() {
  let csv = 'Type,Name,Needed,Available,Status\n';
  const data = window.stockCheckData || [];

  data.forEach(item => {
    if (item.status !== 'OK') {
      csv += `${item.type},${item.name},${item.needed},${item.available},${item.status}\n`;
    }
  });

  const blob = new Blob([csv], { type: 'text/csv' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'shopping_list.csv';
  link.click();
}