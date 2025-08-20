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
  if (updateForm) updateForm.style.display = 'none';

  if (form) {
    if (form.style.display === 'none') {
      form.style.display = 'block';
      if (form && typeof form.reset === 'function') {
            form.reset();
        }
    } else {
      form.style.display = 'none';
    }
  }
}

function toggleUpdateForm() {
  const form = document.getElementById('updateInventoryForm');
  const addForm = document.getElementById('addIngredientForm');
  if (addForm) addForm.style.display = 'none';

  if (form) {
    if (form.style.display === 'none') {
      form.style.display = 'block';
      if (form && typeof form.reset === 'function') {
            form.reset();
        }
    } else {
      form.style.display = 'none';
    }
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
        const serverTime = new Date(data.user_time || data.server_utc);
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

// Global alert function for showing messages
function showAlert(type, message) {
  // Create alert element
  const alertDiv = document.createElement('div');
  alertDiv.className = `alert alert-${type} alert-dismissible fade show mt-3`;
  alertDiv.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;

  // Insert at top of main content
  const mainContent = document.querySelector('main') || document.querySelector('.container').firstChild;
  if (mainContent) {
    if (mainContent.parentNode) {
      mainContent.parentNode.insertBefore(alertDiv, mainContent);
    }
  } else {
    document.body.insertBefore(alertDiv, document.body.firstChild);
  }

  // Auto-hide after 5 seconds
  setTimeout(() => {
    if (alertDiv.parentNode) {
      alertDiv.remove();
    }
  }, 5000);
}

document.addEventListener('DOMContentLoaded', function() {
  // Initialize clock
  updateClock();
  setInterval(updateClock, 30000);

  // Debug navigation clicks
  console.log('Page loaded:', window.location.pathname);

  // Track permissions navigation attempts
  document.addEventListener('click', function(e) {
    const link = e.target.closest('a[href*="permissions"]');
    if (link) {
      console.log('Permissions link clicked:', {
        href: link.href,
        text: link.textContent.trim(),
        timestamp: new Date().toISOString()
      });
    }
  });
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

  // Note: Quick add components (unit, container, ingredient) now have their own 
  // embedded scripts and don't need initialization here
});

// Unit filtering function (kept separate as it's called from HTML)
window.filterUnits = function(filterValue) {
  const filter = filterValue || document.getElementById('unitFilter')?.value || 'all';
  const unitCards = document.querySelectorAll('.card.mb-3');

  unitCards.forEach(card => {
    const typeElement = card.querySelector('h5');
    if (typeElement) {
      const type = typeElement.textContent.toLowerCase();
      card.style.display = filter === 'all' || filter === type ? '' : 'none';
    }
  });
}