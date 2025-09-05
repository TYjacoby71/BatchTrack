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
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
  }
}

function toggleUpdateForm() {
  const form = document.getElementById('updateInventoryForm');
  const addForm = document.getElementById('addIngredientForm');
  if (addForm) addForm.style.display = 'none';

  if (form && form.style.display === 'none') {
    form.style.display = 'block';
  } else if (form) {
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
  // Initialize clock - reduce frequency to 1 minute
  updateClock();
  setInterval(updateClock, 60000);

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

  // Add Ingredient name field - Select2 with AJAX global search and tags for custom entries
  const $nameSelect = $('#addIngredientNameSelect');
  if ($nameSelect.length) {
    $nameSelect.select2({
      ...select2Config,
      placeholder: 'Type ingredient name...',
      tags: true, // allow custom entries
      ajax: {
        url: '/api/ingredients/global-items/search',
        dataType: 'json',
        delay: 150,
        data: function (params) {
          return { q: params.term, type: 'ingredient' };
        },
        processResults: function (data) {
          return data;
        },
        cache: true
      },
      minimumInputLength: 1,
      createTag: function (params) {
        const term = $.trim(params.term);
        if (term === '') { return null; }
        return { id: term, text: term, newTag: true };
      }
    });

    // Keep a hidden input for global_item_id if a library item is chosen
    let hiddenGlobalId = document.getElementById('global_item_id');
    if (!hiddenGlobalId) {
      hiddenGlobalId = document.createElement('input');
      hiddenGlobalId.type = 'hidden';
      hiddenGlobalId.name = 'global_item_id';
      hiddenGlobalId.id = 'global_item_id';
      document.getElementById('addIngredientForm')?.appendChild(hiddenGlobalId);
    }

    $nameSelect.on('select2:select', function (e) {
      const data = e.params.data || {};
      // If selecting a global item (numeric id), set hidden FK and update visible name to text
      if (data.id && !isNaN(Number(data.id))) {
        hiddenGlobalId.value = data.id;
        // Ensure the select shows the chosen name
        const option = new Option(data.text, data.text, true, true);
        $nameSelect.append(option).trigger('change');
      } else {
        hiddenGlobalId.value = '';
      }
    });

    // No base category selection in add form; density/category auto-assigned on creation

    // If user clears or changes to a custom name, drop the global link to avoid stale linkage
    $nameSelect.on('change', function () {
      const val = $(this).val();
      // If value is empty or not matching a numeric id selection flow, clear FK
      if (!val || (typeof val === 'string' && val.trim().length > 0)) {
        hiddenGlobalId.value = '';
      }
    });
  }

  // Add Container name field - Select2 with AJAX global search and tags for custom entries
  const $containerNameSelect = $('#addContainerNameSelect');
  if ($containerNameSelect.length) {
    $containerNameSelect.select2({
      ...select2Config,
      placeholder: 'Type container name...',
      tags: true,
      ajax: {
        url: '/api/ingredients/global-items/search',
        dataType: 'json',
        delay: 150,
        data: function (params) {
          return { q: params.term, type: 'container' };
        },
        processResults: function (data) {
          return data;
        },
        cache: true
      },
      minimumInputLength: 1,
      createTag: function (params) {
        const term = $.trim(params.term);
        if (term === '') { return null; }
        return { id: term, text: term, newTag: true };
      }
    });

    // Hidden FK for containers as well
    let hiddenGlobalIdContainer = document.getElementById('global_item_id_container');
    if (!hiddenGlobalIdContainer) {
      hiddenGlobalIdContainer = document.createElement('input');
      hiddenGlobalIdContainer.type = 'hidden';
      hiddenGlobalIdContainer.name = 'global_item_id';
      hiddenGlobalIdContainer.id = 'global_item_id_container';
      document.getElementById('addContainerForm')?.appendChild(hiddenGlobalIdContainer);
    }

    $containerNameSelect.on('select2:select', function (e) {
      const data = e.params.data || {};
      if (data.id && !isNaN(Number(data.id))) {
        hiddenGlobalIdContainer.value = data.id;
        const option = new Option(data.text, data.text, true, true);
        $containerNameSelect.append(option).trigger('change');
      } else {
        hiddenGlobalIdContainer.value = '';
      }
    });

    $containerNameSelect.on('change', function () {
      const val = $(this).val();
      if (!val || (typeof val === 'string' && val.trim().length > 0)) {
        hiddenGlobalIdContainer.value = '';
      }
    });
  }

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