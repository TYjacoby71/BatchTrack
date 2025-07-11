// Get CSRF token from meta tag
function getCSRFToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content;
}

function handleModalTransition(fromModalId, toModalId, focusElementId) {
  const fromModal = document.getElementById(fromModalId);
  const bootstrapFromModal = bootstrap.Modal.getInstance(fromModal);
  bootstrapFromModal?.hide();

  if (toModalId) {
    const toModal = document.getElementById(toModalId);
    const bootstrapToModal = new bootstrap.Modal(toModal);
    bootstrapToModal.show();
    if (focusElementId) {
      toModal.addEventListener('shown.bs.modal', function () {
        document.getElementById(focusElementId)?.focus();
      });
    }
  }
}

function toggleIngredientForm() {
  const form = document.getElementById('addIngredientForm');
  const updateForm = document.getElementById('updateInventoryForm');
  updateForm.style.display = 'none';

  if (form.style.display === 'none') {
    form.style.display = 'block';
    form.reset();
  } else {
    form.style.display = 'none';
  }
}

function toggleUpdateForm() {
  const form = document.getElementById('updateInventoryForm');
  const addForm = document.getElementById('addIngredientForm');
  addForm.style.display = 'none';

  if (form.style.display === 'none') {
    form.style.display = 'block';
    form.reset();
  } else {
    form.style.display = 'none';
  }
}



async function updateClock() {
  const clock = document.getElementById('clock');
  if (clock) {
    try {
      // Get server time to stay in sync with timezone utilities
      const response = await fetch('/api/server-time');
      if (response.ok) {
        const data = await response.json();
        const serverTime = new Date(data.current_time);
        clock.textContent = '🕐 ' + serverTime.toLocaleTimeString();
      } else {
        // Fallback to local time if server endpoint unavailable
        const now = new Date();
        clock.textContent = '🕐 ' + now.toLocaleTimeString();
      }
    } catch (error) {
      // Fallback to local time on error
      const now = new Date();
      clock.textContent = '🕐 ' + now.toLocaleTimeString();
    }
  }
}

document.addEventListener('DOMContentLoaded', function() {
  // Initialize clock
  updateClock();
  setInterval(updateClock, 1000);
  // Initialize all Select2 dropdowns
  const select2Config = {
    placeholder: 'Select...',
    allowClear: true,
    width: '100%'
  };

  $('select[data-unit-select]').select2({
    ...select2Config,
    placeholder: 'Select a unit'
  });

  $('.ingredient-select').select2({
    ...select2Config,
    placeholder: 'Select ingredients'
  });

  $('.container-select:not([x-data])').select2({
    ...select2Config,
    placeholder: 'Select containers',
    multiple: true
  });

  // Bootstrap tooltips
  $('[data-bs-toggle="tooltip"]').tooltip();

  // Quick add modal transitions
  document.getElementById('cancelQuickUnit')?.addEventListener('click', () => {
    handleModalTransition('quickAddUnitModal', 'quickAddIngredientModal', 'ingredientName');
  });

  document.getElementById('cancelQuickIngredient')?.addEventListener('click', () => {
    handleModalTransition('quickAddIngredientModal');
  });

  // Container form logic
  const recipeForm = document.getElementById('recipeForm');
  if (recipeForm) {
    const requiresContainersCheckbox = document.getElementById('requiresContainers');
    const allowedContainersSection = document.getElementById('allowedContainersSection');
    if (requiresContainersCheckbox && allowedContainersSection) {
      requiresContainersCheckbox.addEventListener('change', function() {
        allowedContainersSection.style.display = this.checked ? 'block' : 'none';
      });
    }
  }

  // Quick Add Unit Handler
  function initQuickAddUnit() {
    const saveButton = document.getElementById('saveQuickUnit');
    if (!saveButton) {
      // Element doesn't exist on this page, skip initialization
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

      fetch('/quick-add/unit', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken()
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
        handleModalTransition('quickAddUnitModal', 'quickAddIngredientModal', 'ingredientName');

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

  // Quick Add Container form handler
  const quickAddContainerForm = document.getElementById('quickAddContainerForm');
  if (quickAddContainerForm) {
    quickAddContainerForm.addEventListener('submit', function(e) {
      e.preventDefault();
      // Your existing form submission logic here
    });
  }
});

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips only if bootstrap is available
    if (typeof bootstrap !== 'undefined') {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

        // Initialize any modals that need JS
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            new bootstrap.Modal(modal);
        });
    }
});

// Unit filtering function (kept separate as it's called from HTML)
window.filterUnits = function() {
  const filter = document.getElementById('unitFilter');
  if (!filter) return;
  const unitCards = document.querySelectorAll('.card.mb-3');

  unitCards.forEach(card => {
    const type = card.querySelector('h5').textContent.toLowerCase();
    card.style.display = filter === 'all' || filter === type ? '' : 'none';
  });
}