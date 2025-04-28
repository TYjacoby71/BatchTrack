
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
  flexModeToggle.addEventListener('change', handleFlexModeToggle);
  addContainerBtn.addEventListener('click', addContainerRow);
  form.addEventListener('submit', handleFormSubmit);
  
  // Initial setup
  updateContainmentProgress();

  function handleFlexModeToggle() {
    autoFillSection.style.display = !flexModeToggle.checked ? 'block' : 'none';
    updateContainmentProgress();
  }

  function addContainerRow() {
    const row = document.createElement('div');
    row.className = 'container-row d-flex align-items-center gap-2 mb-2';
    row.innerHTML = `
      <select class="form-select container-select" required>
        <option value="">Select Container</option>
        {% for container in containers %}
        <option value="{{ container.id }}" 
                data-capacity="{{ container.storage_amount }}"
                data-unit="{{ container.storage_unit }}">
          {{ container.name }} ({{ container.storage_amount }} {{ container.storage_unit }})
        </option>
        {% endfor %}
      </select>
      <input type="number" class="form-control container-quantity" 
             min="1" value="1" required>
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
    // This is a placeholder - actual calculation will depend on your unit system
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
    
    remainingDisplay.textContent = `Remaining to contain: ${Math.max(totalNeeded - totalContained, 0)} units`;
    
    // Show error if can't contain fully in strict mode
    if (!flexModeToggle.checked && totalContained < totalNeeded) {
      containmentError.style.display = 'block';
    } else {
      containmentError.style.display = 'none';
    }
  }

  function handleFormSubmit(e) {
    e.preventDefault();
    // Collect form data and send to stock check endpoint
    const formData = new FormData(form);
    // Add container data
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
    formData.append('containers', JSON.stringify(containers));
    
    // Submit to your stock check endpoint
    // Implementation depends on your backend API
  }
});
