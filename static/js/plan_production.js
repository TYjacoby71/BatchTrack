
// Plan Production Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
  // Initialize all event listeners
  initializeEventListeners();
  
  // Calculate initial projected yield
  updateProjectedYield();
});

function initializeEventListeners() {
  const scaleInput = document.getElementById('scale');
  if (scaleInput) {
    scaleInput.addEventListener('input', updateProjectedYield);
  }

  const checkStockBtn = document.getElementById('checkStockBtn');
  if (checkStockBtn) {
    checkStockBtn.addEventListener('click', checkStock);
  }

  const addContainerBtn = document.getElementById('addContainerBtn');
  if (addContainerBtn) {
    addContainerBtn.addEventListener('click', addContainerRow);
  }
}

function updateProjectedYield() {
  const projectedYieldElement = document.getElementById('projectedYield');
  const scaleInput = document.getElementById('scale');

  if (!projectedYieldElement || !scaleInput) return;

  const baseYield = parseFloat(projectedYieldElement.dataset.baseYield) || 0;
  const scale = parseFloat(scaleInput.value) || 1;
  const unit = projectedYieldElement.dataset.baseUnit || '';

  const newYield = (baseYield * scale).toFixed(2);
  projectedYieldElement.textContent = `${newYield} ${unit}`;
}

function checkStock() {
  const recipeId = document.querySelector('input[name="recipe_id"]').value;
  const scale = parseFloat(document.getElementById('scale').value) || 1.0;

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
  const projectedYieldElement = document.getElementById('projectedYield');
  const scaleInput = document.getElementById('scale');
  const fillProgressBar = document.getElementById('fillProgressBar');
  const remainingDisplay = document.getElementById('remainingToContain');
  const flexModeToggle = document.getElementById('flexMode');
  const containmentError = document.getElementById('containmentError');
  const startBatchButton = document.getElementById('startBatchButton');

  if (!projectedYieldElement || !scaleInput) return;

  const baseYield = parseFloat(projectedYieldElement.dataset.baseYield) || 0;
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
