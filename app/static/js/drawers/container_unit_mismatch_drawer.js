
(function() {
  'use strict';
  
  console.log('🔧 CONTAINER DRAWER JS: Script is loading');

  function isYieldForm(target) {
    return target && target.matches('#yieldFixForm');
  }

  function findModal(element) {
    return element ? element.closest('#containerUnitMismatchDrawer') : null;
  }

  function toggleAlert(alertEl, show, message) {
    if (!alertEl) return;
    if (show) {
      if (message) {
        alertEl.textContent = message;
      }
      alertEl.classList.remove('d-none');
    } else {
      alertEl.classList.add('d-none');
    }
  }

  async function handleYieldSubmit(event) {
    if (!isYieldForm(event.target)) {
      return;
    }

    event.preventDefault();
    const form = event.target;
    const modal = findModal(form);
    const recipeId = form.dataset.recipeId;
    const submitBtn = form.querySelector('button[type="submit"]');
    const successAlert = modal?.querySelector('#yieldFixSuccess');
    const errorAlert = modal?.querySelector('#yieldFixError');
    const updateUrl = form.dataset.updateUrl;

    if (!updateUrl) {
      console.warn('Container drawer missing update URL');
      return;
    }

    toggleAlert(successAlert, false);
    toggleAlert(errorAlert, false);

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.dataset.originalLabel = submitBtn.innerHTML;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Saving';
    }

    try {
      const response = await fetch(updateUrl, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: new FormData(form)
      });
      const payload = await response.json();

      if (!response.ok || !payload.success) {
        throw new Error(payload.error || 'Failed to update recipe yield');
      }

      toggleAlert(successAlert, true, 'Yield updated. Refreshing plan…');
      window.dispatchEvent(
        new CustomEvent('recipe.yield.updated', {
          detail: {
            recipe_id: Number(recipeId),
            yield_amount: payload.yield_amount,
            yield_unit: payload.yield_unit,
            source: 'container_unit_mismatch',
            refresh_plan: true
          }
        })
      );

      setTimeout(() => {
        if (!modal) return;
        const instance = bootstrap.Modal.getInstance(modal);
        if (instance) {
          instance.hide();
        }
      }, 600);
    } catch (err) {
      console.error('Container drawer: yield update failed', err);
      toggleAlert(errorAlert, true, err.message);
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = submitBtn.dataset.originalLabel || '<i class="fas fa-sync-alt me-1"></i> Save & Refresh';
      }
    }
  }

  function handleDisableClick(event) {
    const btn = event.target.closest('#disableContainersBtn');
    if (!btn) {
      return;
    }

    console.log('🔧 CONTAINER DRAWER: Disable button clicked');
    const modal = findModal(btn);
    const recipeId = Number(btn.dataset.recipeId);
    
    window.dispatchEvent(
      new CustomEvent('container.requirements.disable', {
        detail: { recipe_id: recipeId }
      })
    );
    
    if (modal) {
      const instance = bootstrap.Modal.getInstance(modal);
      if (instance) {
        instance.hide();
      }
    }
  }

  function initializeModal() {
    console.log('🔧 CONTAINER DRAWER: initializeModal called');
    // This function is called by DrawerProtocol after modal is rendered
  }

  function init() {
    console.log('🔧 CONTAINER DRAWER JS: Initializing event listeners');
    document.body.addEventListener('submit', handleYieldSubmit);
    document.body.addEventListener('click', handleDisableClick);
  }

  // Expose functions globally for DrawerProtocol - assign after function declarations
  window.containerUnitMismatchDrawer = window.containerUnitMismatchDrawer || {};
  window.containerUnitMismatchDrawer.initializeModal = initializeModal;
  
  console.log('🔧 CONTAINER DRAWER JS: Functions exposed to window.containerUnitMismatchDrawer', window.containerUnitMismatchDrawer);
  console.log('🔧 CONTAINER DRAWER JS: initializeModal type:', typeof window.containerUnitMismatchDrawer.initializeModal);

  console.log('🔧 CONTAINER DRAWER JS: Setting up initialization, readyState:', document.readyState);
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  
  console.log('🔧 CONTAINER DRAWER JS: Script fully loaded');
})();
