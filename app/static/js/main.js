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

function ensureToastContainer() {
  let container = document.getElementById('appGlobalToastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'appGlobalToastContainer';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1090';
    document.body.appendChild(container);
  }
  return container;
}

function ensurePromptModal() {
  let modalEl = document.getElementById('appGlobalPromptModal');
  if (!modalEl) {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
      <div class="modal fade" id="appGlobalPromptModal" tabindex="-1" aria-labelledby="appGlobalPromptModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="appGlobalPromptModalLabel">Input required</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <p id="appGlobalPromptModalMessage" class="mb-2" style="white-space: pre-line;"></p>
              <input id="appGlobalPromptModalInput" class="form-control" type="text" />
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" data-role="cancel" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" data-role="confirm">Submit</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(wrapper.firstElementChild);
    modalEl = document.getElementById('appGlobalPromptModal');
  }
  return modalEl;
}

function showToast(message, options = {}) {
  const type = normalizeAlertType(options.type || options.variant || 'info');
  const autoHideMs = typeof options.autoHideMs === 'number' ? options.autoHideMs : 2500;
  const title = options.title || (type === 'danger' ? 'Error' : type === 'success' ? 'Success' : 'Notice');

  if (!window.bootstrap?.Toast) {
    return showAlert(type, message, { autoHideMs });
  }

  const container = ensureToastContainer();
  const toastEl = document.createElement('div');
  const textBgClass = type === 'danger' ? 'text-bg-danger' : `text-bg-${type}`;
  toastEl.className = `toast align-items-center border-0 ${textBgClass}`;
  toastEl.setAttribute('role', 'alert');
  toastEl.setAttribute('aria-live', 'assertive');
  toastEl.setAttribute('aria-atomic', 'true');
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">
        <strong class="me-1">${title}:</strong> ${message}
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
    </div>
  `;
  container.appendChild(toastEl);
  const toast = window.bootstrap.Toast.getOrCreateInstance(toastEl, {
    autohide: autoHideMs > 0,
    delay: autoHideMs > 0 ? autoHideMs : 9999999,
  });
  toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove(), { once: true });
  toast.show();
  return toastEl;
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

function showPromptDialog(options = {}) {
  const message = options.message || 'Enter a value:';
  const defaultValue = options.defaultValue ?? '';
  if (!window.bootstrap?.Modal) {
    return Promise.resolve(window.prompt(message, defaultValue));
  }

  const modalEl = ensurePromptModal();
  const titleEl = modalEl.querySelector('#appGlobalPromptModalLabel');
  const messageEl = modalEl.querySelector('#appGlobalPromptModalMessage');
  const inputEl = modalEl.querySelector('#appGlobalPromptModalInput');
  const confirmBtn = modalEl.querySelector('[data-role="confirm"]');
  const cancelBtn = modalEl.querySelector('[data-role="cancel"]');
  const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
  const required = options.required !== false;
  const trim = options.trim !== false;

  titleEl.textContent = options.title || 'Input required';
  messageEl.textContent = message;
  confirmBtn.textContent = options.confirmText || 'Submit';
  cancelBtn.textContent = options.cancelText || 'Cancel';
  inputEl.value = String(defaultValue ?? '');
  inputEl.placeholder = options.placeholder || '';

  return new Promise((resolve) => {
    let resolved = false;
    const finish = (value) => {
      if (resolved) return;
      resolved = true;
      cleanup();
      resolve(value);
    };
    const normalizeValue = () => {
      const raw = inputEl.value;
      const normalized = trim ? raw.trim() : raw;
      if (required && !normalized) {
        showAlert('warning', options.requiredMessage || 'Please enter a value.', { autoHideMs: 3000 });
        inputEl.focus();
        return null;
      }
      return normalized;
    };
    const onConfirm = (event) => {
      event.preventDefault();
      const nextValue = normalizeValue();
      if (nextValue === null) return;
      finish(nextValue);
      modal.hide();
    };
    const onCancel = () => finish(null);
    const onHidden = () => finish(null);
    const onEnter = (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        onConfirm(event);
      }
    };
    const cleanup = () => {
      confirmBtn.removeEventListener('click', onConfirm);
      cancelBtn.removeEventListener('click', onCancel);
      inputEl.removeEventListener('keydown', onEnter);
      modalEl.removeEventListener('hidden.bs.modal', onHidden);
    };

    confirmBtn.addEventListener('click', onConfirm);
    cancelBtn.addEventListener('click', onCancel);
    inputEl.addEventListener('keydown', onEnter);
    modalEl.addEventListener('hidden.bs.modal', onHidden);
    modal.show();
    setTimeout(() => inputEl.focus(), 80);
  });
}

function buildDeclarativeConfirmOptions(element) {
  const message = element.getAttribute('data-confirm-message');
  if (!message) return null;
  return {
    message,
    title: element.getAttribute('data-confirm-title') || undefined,
    confirmText: element.getAttribute('data-confirm-ok') || undefined,
    cancelText: element.getAttribute('data-confirm-cancel') || undefined,
    confirmVariant: element.getAttribute('data-confirm-variant') || undefined,
  };
}

function bindDeclarativeConfirmations() {
  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.dataset.confirmBypassed === '1') return;
    const options = buildDeclarativeConfirmOptions(form);
    if (!options) return;
    event.preventDefault();
    const confirmed = await showConfirmDialog(options);
    if (!confirmed) return;
    form.dataset.confirmBypassed = '1';
    form.submit();
  });

  document.addEventListener('click', async (event) => {
    const trigger = event.target.closest('a[data-confirm-message]');
    if (!trigger) return;
    if (!(trigger instanceof HTMLAnchorElement)) return;
    const href = trigger.getAttribute('href');
    if (!href || href === '#') return;
    event.preventDefault();
    const confirmed = await showConfirmDialog(buildDeclarativeConfirmOptions(trigger));
    if (confirmed) {
      window.location.assign(href);
    }
  });
}

function installAlertCompatibilityShim() {
  if (window.__btAlertShimInstalled) return;
  window.__btAlertShimInstalled = true;
  const nativeAlert = window.alert ? window.alert.bind(window) : null;
  window.alert = (message) => {
    if (typeof window.showAlert === 'function') {
      window.showAlert('info', message);
      return;
    }
    nativeAlert?.(message);
  };
}

function openWindowOrNotify(url, target = '_blank', features = '', options = {}) {
  const popup = window.open(url, target, features);
  if (!popup) {
    const blockedMessage = options.blockedMessage || 'Pop-up blocked. Please allow pop-ups and try again.';
    showAlert(options.type || 'warning', blockedMessage, { autoHideMs: 6000 });
    return null;
  }
  return popup;
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
  bindDeclarativeConfirmations();
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
window.showToast = showToast;
window.showConfirmDialog = showConfirmDialog;
window.showPromptDialog = showPromptDialog;
window.openWindowOrNotify = openWindowOrNotify;
installAlertCompatibilityShim();