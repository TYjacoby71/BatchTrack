import { cachedFetch } from './core/CacheManager.js';

window.cachedFetch = cachedFetch;

const ALERT_TYPE_MAP = {
  error: 'danger',
  danger: 'danger',
  warning: 'warning',
  warn: 'warning',
  success: 'success',
  info: 'info',
  primary: 'primary',
  secondary: 'secondary',
  light: 'light',
  dark: 'dark',
};

const KNOWN_ALERT_TYPES = new Set(Object.keys(ALERT_TYPE_MAP));

// Get CSRF token from meta tag
function getCSRFToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content;
}

function normalizeAlertType(type) {
  const key = (type || 'info').toString().toLowerCase();
  return ALERT_TYPE_MAP[key] || 'info';
}

function resolveAlertArgs(arg1, arg2) {
  if (typeof arg1 === 'string' && KNOWN_ALERT_TYPES.has(arg1.toLowerCase()) && typeof arg2 !== 'undefined') {
    return { type: normalizeAlertType(arg1), message: String(arg2) };
  }
  return {
    type: normalizeAlertType(arg2),
    message: String(arg1 ?? ''),
  };
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
function showAlert(arg1, arg2, options = {}) {
  const { type, message } = resolveAlertArgs(arg1, arg2);

  // Create alert element
  const alertDiv = document.createElement('div');
  const extraClass = options.className ? ` ${options.className}` : ' mt-3';
  alertDiv.className = `alert alert-${type} alert-dismissible fade show${extraClass}`;
  alertDiv.setAttribute('role', 'alert');
  alertDiv.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;

  // Insert at top of requested container or main content
  const target = options.containerSelector ? document.querySelector(options.containerSelector) : null;
  const mainContent = target || document.querySelector('main') || document.querySelector('.container') || document.body;
  if (mainContent) {
    if (mainContent.parentNode && mainContent !== document.body) {
      mainContent.parentNode.insertBefore(alertDiv, mainContent);
    } else if (mainContent === document.body) {
      document.body.insertBefore(alertDiv, document.body.firstChild);
    } else {
      mainContent.prepend(alertDiv);
    }
  }

  // Auto-hide after timeout unless disabled
  const autoHideMs = typeof options.autoHideMs === 'number' ? options.autoHideMs : 5000;
  if (autoHideMs > 0) {
    setTimeout(() => {
      if (alertDiv.parentNode) {
        alertDiv.remove();
      }
    }, autoHideMs);
  }

  return alertDiv;
}

function ensureConfirmModal() {
  let modalEl = document.getElementById('appGlobalConfirmModal');
  if (!modalEl) {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
      <div class="modal fade" id="appGlobalConfirmModal" tabindex="-1" aria-labelledby="appGlobalConfirmModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="appGlobalConfirmModalLabel">Please confirm</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <p id="appGlobalConfirmModalMessage" class="mb-0" style="white-space: pre-line;"></p>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" data-role="cancel" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" data-role="confirm">Confirm</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(wrapper.firstElementChild);
    modalEl = document.getElementById('appGlobalConfirmModal');
  }
  return modalEl;
}

function showConfirmDialog(options = {}) {
  const message = options.message || 'Are you sure?';
  if (!window.bootstrap?.Modal) {
    return Promise.resolve(window.confirm(message));
  }

  const modalEl = ensureConfirmModal();
  const titleEl = modalEl.querySelector('#appGlobalConfirmModalLabel');
  const messageEl = modalEl.querySelector('#appGlobalConfirmModalMessage');
  const confirmBtn = modalEl.querySelector('[data-role="confirm"]');
  const cancelBtn = modalEl.querySelector('[data-role="cancel"]');
  const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);

  titleEl.textContent = options.title || 'Please confirm';
  messageEl.textContent = message;
  confirmBtn.textContent = options.confirmText || 'Confirm';
  cancelBtn.textContent = options.cancelText || 'Cancel';
  const confirmVariant = normalizeAlertType(options.confirmVariant || 'primary');
  confirmBtn.className = `btn btn-${confirmVariant === 'danger' ? 'danger' : confirmVariant}`;

  return new Promise((resolve) => {
    let resolved = false;
    const finish = (value) => {
      if (resolved) return;
      resolved = true;
      cleanup();
      resolve(value);
    };
    const onConfirm = (event) => {
      event.preventDefault();
      finish(true);
      modal.hide();
    };
    const onCancel = () => finish(false);
    const onHidden = () => finish(false);
    const cleanup = () => {
      confirmBtn.removeEventListener('click', onConfirm);
      cancelBtn.removeEventListener('click', onCancel);
      modalEl.removeEventListener('hidden.bs.modal', onHidden);
    };

    confirmBtn.addEventListener('click', onConfirm);
    cancelBtn.addEventListener('click', onCancel);
    modalEl.addEventListener('hidden.bs.modal', onHidden);
    modal.show();
  });
}

document.addEventListener('DOMContentLoaded', function() {
  // Debug navigation clicks
  console.log('Page loaded:', window.location.pathname);
  
  // Check if suggestions component is available
  if (typeof window.attachMergedInventoryGlobalTypeahead === 'function') {
    console.log('🔧 MAIN: Suggestions component loaded successfully');
  } else {
    console.warn('🔧 MAIN: Suggestions component not available');
  }

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
};

// Expose shared notification + confirmation helpers globally.
window.showAlert = showAlert;
window.showNotification = showAlert;
window.showConfirmDialog = showConfirmDialog;