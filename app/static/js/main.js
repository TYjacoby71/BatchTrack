import { cachedFetch } from './core/CacheManager.js';

window.cachedFetch = cachedFetch;

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
  // Define select2Config outside conditional blocks to avoid scoping issues
  const select2Config = {
    placeholder: 'Select...',
    allowClear: true,
    width: '100%'
  };

  // Initialize all Select2 dropdowns (only if jQuery and Select2 are available)
  if (typeof $ !== 'undefined' && $.fn.select2) {

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
  }

  // Add Ingredient name field - Select2 with AJAX global search and tags for custom entries
  if (typeof $ !== 'undefined' && $.fn.select2) {
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
            return { q: params.term, type: 'ingredient', group: 'ingredient' };
          },
          processResults: function (data) {
            var expanded = [];
            (data.results || []).forEach(function(item){
                if (item && Array.isArray(item.forms) && item.forms.length){
                  var baseIngredientName = (item.ingredient && item.ingredient.name) || item.ingredient_name || null;
                  item.forms.forEach(function(form){
                    var physical = form.physical_form || {};
                    var display = form.display_name || form.text || form.name || '';
                    if (!display && baseIngredientName && (physical && physical.name)){
                      display = baseIngredientName + ' (' + physical.name + ')';
                    }
                    if (!display){
                      display = item.display_name || item.text || item.name || '';
                    }
                    expanded.push({
                      id: form.id,
                      text: display,
                      name: display,
                      display_name: display,
                      raw_name: form.raw_name || form.name || form.text || item.raw_name || item.name || '',
                      default_unit: form.default_unit || form.unit || item.default_unit || item.unit || null,
                      unit: form.default_unit || form.unit || item.default_unit || item.unit || null,
                      density: typeof form.density === 'number' ? form.density : item.density,
                      ingredient_id: form.ingredient_id || (item.ingredient && item.ingredient.id) || item.ingredient_id || null,
                      ingredient_name: form.ingredient_name || baseIngredientName,
                      physical_form_id: form.physical_form_id || (physical && physical.id) || null,
                      physical_form_name: form.physical_form_name || (physical && physical.name) || null,
                      default_is_perishable: form.default_is_perishable,
                      recommended_shelf_life_days: form.recommended_shelf_life_days,
                      recommended_usage_rate: form.recommended_usage_rate || item.recommended_usage_rate,
                      recommended_fragrance_load_pct: form.recommended_fragrance_load_pct || item.recommended_fragrance_load_pct,
                      aliases: form.aliases || item.aliases || [],
                      certifications: form.certifications || item.certifications || [],
                    });
                  });
                } else if (item) {
                  var itemDisplay = item.display_name || item.text || item.name || '';
                  if (!itemDisplay && item.ingredient_name && item.physical_form_name){
                    itemDisplay = item.ingredient_name + ' (' + item.physical_form_name + ')';
                  }
                  expanded.push({
                    id: item.id,
                    text: itemDisplay,
                    name: itemDisplay,
                    display_name: itemDisplay,
                    raw_name: item.raw_name || item.name || item.text || '',
                    default_unit: item.default_unit || item.unit || null,
                    unit: item.default_unit || item.unit || null,
                    density: item.density,
                    ingredient_id: (item.ingredient && item.ingredient.id) || item.ingredient_id || null,
                    ingredient_name: (item.ingredient && item.ingredient.name) || item.ingredient_name || null,
                    physical_form_id: (item.physical_form && item.physical_form.id) || item.physical_form_id || null,
                    physical_form_name: (item.physical_form && item.physical_form.name) || item.physical_form_name || null,
                    default_is_perishable: item.default_is_perishable,
                    recommended_shelf_life_days: item.recommended_shelf_life_days,
                    recommended_usage_rate: item.recommended_usage_rate,
                    recommended_fragrance_load_pct: item.recommended_fragrance_load_pct,
                    aliases: item.aliases || [],
                    certifications: item.certifications || [],
                  });
                }
            });
            return { results: expanded };
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

    // Function to populate unit field when global item is selected
    function populateUnitFromGlobalItem(globalItemData) {
      if (globalItemData && globalItemData.default_unit) {
        const unitSelect = document.querySelector('select[name="unit"]');
        if (unitSelect) {
          // Set the unit select to the global item's default unit
          unitSelect.value = globalItemData.default_unit;
          console.log('🔧 GLOBAL ITEM: Populated unit field with', globalItemData.default_unit);
        }
      }
    }

    // Make the function globally available for Select2 callbacks
    window.populateUnitFromGlobalItem = populateUnitFromGlobalItem;

    $nameSelect.on('select2:select', function (e) {
      const data = e.params.data || {};
      // If selecting a global item (numeric id), set hidden FK and update visible name to text
      if (data.id && !isNaN(Number(data.id))) {
        hiddenGlobalId.value = data.id;
        // Ensure the select shows the chosen name
        const option = new Option(data.text, data.text, true, true);
        $nameSelect.append(option).trigger('change');
        // Apply suggested defaults when available
        try {
          if (data.default_unit) {
            const unitSelect = document.querySelector('#addIngredientForm select[name="unit"]');
            if (unitSelect) unitSelect.value = data.default_unit;
          }
          // Populate perishable defaults
          const perishableCheckbox = document.getElementById('addIngredientPerishable');
          const shelfLifeInput = document.getElementById('addIngredientShelfLife');
          
          if (typeof data.default_is_perishable !== 'undefined' && perishableCheckbox) {
            perishableCheckbox.checked = !!data.default_is_perishable;
            // Manually trigger Alpine.js reactivity by setting the x-model value
            const form = document.getElementById('addIngredientForm');
            if (form && form.__x) {
              form.__x.$data.isPerishable = !!data.default_is_perishable;
            }
          }
          
          if (shelfLifeInput && data.recommended_shelf_life_days) {
            shelfLifeInput.value = data.recommended_shelf_life_days;
          }
        } catch (error) {
          console.log('Error applying global item defaults:', error);
        }
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
  }

  // Add Container name field - Select2 with AJAX global search and tags for custom entries
  if (typeof $ !== 'undefined' && $.fn.select2) {
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
        // Apply suggested capacity unit when available
        try {
          if (data.capacity_unit) {
            const sel = document.querySelector('#addContainerForm select[name="capacity_unit"]');
            if (sel) sel.value = data.capacity_unit;
          }
          // Apply container meta suggestions when available
          const mat = document.querySelector('#addContainerForm input[name="container_material"]');
          if (mat && data.container_material) mat.value = data.container_material;
          const typ = document.querySelector('#addContainerForm input[name="container_type"]');
          if (typ && data.container_type) typ.value = data.container_type;
          const sty = document.querySelector('#addContainerForm input[name="container_style"]');
          if (sty && data.container_style) sty.value = data.container_style;
          const col = document.querySelector('#addContainerForm input[name="container_color"]');
          if (col && data.container_color) col.value = data.container_color;
        } catch (_) {}
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
  }

  // Bootstrap tooltips (only if jQuery is available)
  if (typeof $ !== 'undefined' && $.fn.tooltip) {
    $('[data-bs-toggle="tooltip"]').tooltip();
  }

  // Removed legacy quick-add modal transition handlers

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