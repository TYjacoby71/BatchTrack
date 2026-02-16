(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const state = SoapTool.state;

  const ALERT_ICONS = {
    info: 'fa-info-circle',
    warning: 'fa-exclamation-triangle',
    danger: 'fa-times-circle',
    success: 'fa-check-circle'
  };

  function pulseValue(el){
    if (!el) return;
    el.classList.remove('soap-number-pulse');
    void el.offsetWidth;
    el.classList.add('soap-number-pulse');
  }

  function getToastInstance(id){
    const el = document.getElementById(id);
    if (!el || !window.bootstrap?.Toast) return null;
    return bootstrap.Toast.getOrCreateInstance(el);
  }

  function showAutosaveToast(){
    const now = Date.now();
    if (now - state.lastSaveToastAt < 3500) return;
    state.lastSaveToastAt = now;
    const toast = getToastInstance('soapAutosaveToast');
    if (toast) toast.show();
  }

  function showUndoToast(message){
    const toastEl = document.getElementById('soapUndoToast');
    if (!toastEl) return;
    const body = toastEl.querySelector('.toast-body');
    if (body) body.textContent = message || 'Oil removed.';
    const toast = getToastInstance('soapUndoToast');
    if (toast) toast.show();
  }

  function updateResultsMeta(){
    const badge = document.getElementById('resultsReadyBadge');
    const updatedAt = document.getElementById('resultsUpdatedAt');
    if (badge) badge.classList.remove('d-none');
    if (updatedAt) {
      updatedAt.textContent = `Updated ${new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
    }
  }

  function updateResultsWarnings(waterData){
    const concentrationEl = document.getElementById('lyeConcentrationWarning');
    const ratioEl = document.getElementById('waterRatioWarning');
    const guidanceWarnings = [];
    if (concentrationEl) {
      const concentration = waterData?.lyeConcentration || 0;
      let message = '';
      if (concentration > 40) message = 'High concentration';
      if (concentration > 0 && concentration < 25) message = 'Low concentration';
      concentrationEl.textContent = message;
      concentrationEl.classList.toggle('d-none', !message);
      if (message) {
        guidanceWarnings.push(`Lye concentration: ${message.toLowerCase()}.`);
      }
    }
    if (ratioEl) {
      const ratio = waterData?.waterRatio || 0;
      let message = '';
      if (ratio > 0 && ratio < 1.8) message = 'Low water';
      if (ratio > 2.7) message = 'High water';
      ratioEl.textContent = message;
      ratioEl.classList.toggle('d-none', !message);
      if (message) {
        guidanceWarnings.push(`Water to lye ratio: ${message.toLowerCase()}.`);
      }
    }
    if (guidanceWarnings.length) {
      SoapTool.guidance?.setSection('results-water-warnings', {
        title: 'Process warnings',
        tone: 'warning',
        items: guidanceWarnings,
      });
    } else {
      SoapTool.guidance?.clearSection('results-water-warnings');
    }
  }

  function applyHelperVisibility(){
    document.querySelectorAll('#soapToolPage .form-text').forEach(text => {
      const wrapper = text.closest('.col-md-2, .col-md-3, .col-md-4, .col-md-6, .col-md-8, .col-lg-6, .col-lg-4, .col-12');
      if (wrapper) wrapper.classList.add('soap-field');
    });
  }

  function validateNumericField(input){
    if (!input || input.type !== 'number') return;
    const raw = input.value;
    if (raw === '') {
      input.classList.remove('is-invalid');
      return;
    }
    const value = parseFloat(raw);
    const min = input.getAttribute('min');
    const max = input.getAttribute('max');
    const tooLow = min !== null && min !== '' && value < parseFloat(min);
    const tooHigh = max !== null && max !== '' && value > parseFloat(max);
    input.classList.toggle('is-invalid', !isFinite(value) || tooLow || tooHigh);
  }

  function flashStage(stageItem){
    if (!stageItem) return;
    const target = stageItem.querySelector?.('.soap-stage-card') || stageItem;
    target.classList.add('soap-stage-highlight');
    setTimeout(() => target.classList.remove('soap-stage-highlight'), 900);
  }

  function getTemplateClone(id){
    const template = document.getElementById(id);
    const fragment = template?.content?.cloneNode?.(true);
    if (!fragment) return null;
    const firstElement = fragment.firstElementChild || fragment.querySelector('*');
    return { fragment, root: firstElement };
  }

  function renderTitledList(container, title, items){
    if (!container) return;
    const values = Array.isArray(items) ? items.filter(item => typeof item === 'string' && item.trim()) : [];
    if (!values.length) {
      container.textContent = '';
      return;
    }
    const cloned = getTemplateClone('soapTitledListTemplate');
    if (cloned?.root) {
      const titleEl = cloned.root.querySelector('[data-role="title"]');
      const listEl = cloned.root.querySelector('[data-role="list"]');
      if (titleEl) titleEl.textContent = title || '';
      if (listEl) {
        listEl.innerHTML = '';
        values.forEach(value => {
          const item = document.createElement('li');
          item.textContent = value;
          listEl.appendChild(item);
        });
      }
      container.replaceChildren(cloned.fragment);
      return;
    }
    container.innerHTML = '';
    const strong = document.createElement('strong');
    strong.textContent = title || '';
    const list = document.createElement('ul');
    list.className = 'mb-0';
    values.forEach(value => {
      const item = document.createElement('li');
      item.textContent = value;
      list.appendChild(item);
    });
    container.appendChild(strong);
    container.appendChild(list);
  }

  function showSoapAlert(type, message, options = {}){
    const alertStack = document.getElementById('soapAlertStack');
    if (!alertStack) return;
    const icon = ALERT_ICONS[type] || ALERT_ICONS.info;
    const cloned = getTemplateClone('soapAlertTemplate');
    const alert = cloned?.root || document.createElement('div');
    if (!cloned) {
      alert.className = 'alert d-flex align-items-start gap-2';
      const iconEl = document.createElement('i');
      iconEl.className = `fas ${icon} mt-1`;
      const messageEl = document.createElement('div');
      messageEl.className = 'flex-grow-1';
      messageEl.innerHTML = message;
      alert.appendChild(iconEl);
      alert.appendChild(messageEl);
      if (options.dismissible) {
        const dismissBtn = document.createElement('button');
        dismissBtn.type = 'button';
        dismissBtn.className = 'btn-close';
        dismissBtn.dataset.role = 'dismiss';
        alert.appendChild(dismissBtn);
      }
    } else {
      alert.classList.add(`alert-${type}`);
      const iconEl = alert.querySelector('[data-role="icon"]');
      if (iconEl) {
        iconEl.classList.add(icon);
      }
      const messageEl = alert.querySelector('[data-role="message"]');
      if (messageEl) {
        messageEl.innerHTML = message;
      }
      const dismissBtn = alert.querySelector('[data-role="dismiss"]');
      if (dismissBtn) {
        dismissBtn.classList.toggle('d-none', !options.dismissible);
      }
    }
    alert.classList.add(`alert-${type}`, 'd-flex', 'align-items-start', 'gap-2');
    if (options.dismissible) {
      alert.querySelector('[data-role="dismiss"]')?.addEventListener('click', () => alert.remove());
    }
    alertStack.prepend(alert);
    if (!options.persist) {
      setTimeout(() => {
        if (alert.parentNode) alert.remove();
      }, options.timeoutMs || 4500);
    }
  }

  function clearSoapAlerts(){
    const alertStack = document.getElementById('soapAlertStack');
    if (!alertStack) return;
    alertStack.querySelectorAll('.alert').forEach(el => el.remove());
  }

  SoapTool.ui = {
    pulseValue,
    getToastInstance,
    showAutosaveToast,
    showUndoToast,
    updateResultsMeta,
    updateResultsWarnings,
    applyHelperVisibility,
    validateNumericField,
    flashStage,
    renderTitledList,
    showSoapAlert,
    clearSoapAlerts,
  };
})(window);
