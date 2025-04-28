
// Plan Production Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('planProductionForm');
  const flexModeToggle = document.getElementById('flexMode');
  const autoFillSection = document.getElementById('autoFillSection');
  const containerArea = document.getElementById('containerSelectionArea');
  const addContainerBtn = document.getElementById('addContainerBtn');
  const progressBar = document.getElementById('fillProgressBar');
  const remainingDisplay = document.getElementById('remainingToContain');
  const containmentError = document.getElementById('containmentError');
  const overrideButton = document.getElementById('overrideButton');

  // Event Listeners
  if (form) form.addEventListener('submit', handleFormSubmit);
  if (flexModeToggle) flexModeToggle.addEventListener('change', handleFlexModeToggle);
  if (addContainerBtn) addContainerBtn.addEventListener('click', addContainerRow);
  
  // Initial setup
  updateContainmentProgress();

  function handleFlexModeToggle() {
    autoFillSection.style.display = !flexModeToggle.checked ? 'block' : 'none';
    updateContainmentProgress();
  }

  function updateContainmentProgress() {
    if (!progressBar) return;
    
    const totalNeeded = 100; // Example
    let totalContained = 0;

    document.querySelectorAll('.container-row').forEach(row => {
      const select = row.querySelector('.container-select');
      const quantity = row.querySelector('.container-quantity');
      
      if (select.value && quantity.value) {
        const option = select.selectedOptions[0];
        const capacity = parseFloat(option.dataset.capacity) || 0;
        totalContained += capacity * parseInt(quantity.value);
      }
    });

    const percentage = Math.min((totalContained / totalNeeded) * 100, 100);
    progressBar.style.width = `${percentage}%`;
    progressBar.textContent = `${Math.round(percentage)}%`;
    
    if (remainingDisplay) {
      remainingDisplay.textContent = `Remaining to contain: ${Math.max(totalNeeded - totalContained, 0)} units`;
    }
    
    // Show error if can't contain fully in strict mode
    if (containmentError && flexModeToggle) {
      containmentError.style.display = !flexModeToggle.checked && totalContained < totalNeeded ? 'block' : 'none';
    }
  }

  function handleFormSubmit(e) {
    e.preventDefault();

    const formData = new FormData(form);
    const containers = [];
    document.querySelectorAll('.container-row').forEach(row => {
      const select = row.querySelector('.container-select');
      const quantity = row.querySelector('.container-quantity');
      if (select.value && quantity.value) {
        containers.push({
          id: select.value,
          quantity: quantity.value
        });
      }
    });

    const payload = {
      recipe_id: formData.get('recipe_id'),
      scale: formData.get('scale'),
      flex_mode: formData.get('flex_mode') ? true : false,
      containers: containers
    };

    fetch('/api/check-stock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        alert('Stock Check Error: ' + data.error);
        return;
      }

      renderStockCheckResults(data.stock_check, data.all_ok);
    })
    .catch(err => {
      console.error(err);
      alert('Failed to check stock.');
    });
  }

  function renderStockCheckResults(results, allOk) {
    const resultsContainer = document.getElementById('stockCheckResults');
    if (!resultsContainer) return;
    
    resultsContainer.innerHTML = '';

    let lowOrNeededItems = [];

    results.forEach(item => {
      const statusColor = (item.status === 'OK') ? 'text-success' :
                          (item.status === 'LOW') ? 'text-warning' : 'text-danger';
      const row = document.createElement('div');
      row.innerHTML = `
        <div class="d-flex justify-content-between">
          <div>${item.type.toUpperCase()}: ${item.name}</div>
          <div class="${statusColor}">${item.status}</div>
        </div>
      `;
      resultsContainer.appendChild(row);

      if (item.status !== 'OK') {
        lowOrNeededItems.push(item);
      }
    });

    const startBatchButton = document.getElementById('startBatchButton');
    const exportListButton = document.getElementById('exportShoppingListButton');

    if (allOk) {
      if (startBatchButton) startBatchButton.style.display = 'block';
      if (exportListButton) exportListButton.style.display = 'none';
    } else {
      if (startBatchButton) startBatchButton.style.display = 'none';
      if (exportListButton) {
        exportListButton.style.display = 'block';
        exportListButton.onclick = function() {
          exportShoppingList(lowOrNeededItems);
        };
      }
    }
  }

  function exportShoppingList(items) {
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "Item Type,Item Name,Needed Quantity,Available Quantity,Status\n";

    items.forEach(item => {
      csvContent += `${item.type},${item.name},${item.needed},${item.available},${item.status}\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "shopping_list.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
});
