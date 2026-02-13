(function(window){
  'use strict';

  const STEP_SORT = 'sort';
  const STEP_DETAILS = 'details';
  const STEP_SUCCESS = 'success';

  const FLOW_LABELS = {
    question: 'Question',
    missing_feature: 'Missing feature',
    glitch: 'Glitch',
    bad_preset_data: 'Bad preset data',
  };

  function getCsrfToken(){
    const tokenEl = document.querySelector('meta[name="csrf-token"]');
    return tokenEl ? tokenEl.getAttribute('content') : '';
  }

  function cleanText(value){
    if (value === null || value === undefined) return '';
    return String(value).trim();
  }

  function showStep(widget, stepName){
    widget.querySelectorAll('[data-feedback-step]').forEach(section => {
      const isActive = section.getAttribute('data-feedback-step') === stepName;
      section.classList.toggle('d-none', !isActive);
    });
    widget.setAttribute('data-feedback-current-step', stepName);
  }

  function setError(widget, message){
    const errorEl = widget.querySelector('[data-feedback-error]');
    if (!errorEl) return;
    const safeMessage = cleanText(message);
    if (!safeMessage) {
      errorEl.classList.add('d-none');
      errorEl.textContent = '';
      return;
    }
    errorEl.textContent = safeMessage;
    errorEl.classList.remove('d-none');
  }

  function selectedFlowValue(widget){
    const flowInput = widget.querySelector('input[name="flow"]:checked');
    return flowInput ? cleanText(flowInput.value) : '';
  }

  function selectedSourceLabel(widget){
    const sourceSelect = widget.querySelector('select[name="source"]');
    if (!sourceSelect) return '';
    const option = sourceSelect.options[sourceSelect.selectedIndex];
    return option ? cleanText(option.textContent) : cleanText(sourceSelect.value);
  }

  function updateFlowSelectionStyles(widget){
    const currentFlow = selectedFlowValue(widget);
    widget.querySelectorAll('.feedback-note-flow-option').forEach(option => {
      const input = option.querySelector('input[name="flow"]');
      const isSelected = !!(input && cleanText(input.value) === currentFlow);
      option.classList.toggle('is-selected', isSelected);
    });
  }

  function updateSortSummary(widget){
    const summaryEl = widget.querySelector('[data-feedback-sort-summary]');
    if (!summaryEl) return;
    const sourceText = selectedSourceLabel(widget) || 'Unknown source';
    const flowValue = selectedFlowValue(widget);
    const flowLabel = FLOW_LABELS[flowValue] || 'Not selected';
    summaryEl.textContent = `Will save to: ${sourceText} / ${flowLabel}.`;
  }

  function validateSortStep(widget){
    const sourceSelect = widget.querySelector('select[name="source"]');
    const sourceValue = sourceSelect ? cleanText(sourceSelect.value) : '';
    const flowValue = selectedFlowValue(widget);
    if (!sourceValue) {
      setError(widget, 'Pick a source before continuing.');
      return false;
    }
    if (!flowValue) {
      setError(widget, 'Pick one type: question, missing feature, glitch, or bad preset data.');
      return false;
    }
    return true;
  }

  function validateDetailsStep(widget){
    const messageInput = widget.querySelector('textarea[name="message"]');
    const message = messageInput ? cleanText(messageInput.value) : '';
    if (!message) {
      setError(widget, 'Please share details before submitting.');
      return false;
    }
    return true;
  }

  function setSubmitting(widget, isSubmitting){
    const submitBtn = widget.querySelector('[data-feedback-submit]');
    const nextBtn = widget.querySelector('[data-feedback-next]');
    if (submitBtn) submitBtn.disabled = !!isSubmitting;
    if (nextBtn) nextBtn.disabled = !!isSubmitting;

    const submitDefault = widget.querySelector('[data-feedback-submit-default]');
    const submitLoading = widget.querySelector('[data-feedback-submit-loading]');
    if (submitDefault && submitLoading) {
      submitDefault.classList.toggle('d-none', !!isSubmitting);
      submitLoading.classList.toggle('d-none', !isSubmitting);
    }
  }

  function buildPayload(widget){
    const form = widget.querySelector('[data-feedback-note-form]');
    const sourceSelect = form ? form.querySelector('select[name="source"]') : null;
    const titleInput = form ? form.querySelector('input[name="title"]') : null;
    const messageInput = form ? form.querySelector('textarea[name="message"]') : null;
    const emailInput = form ? form.querySelector('input[name="contact_email"]') : null;

    const source = sourceSelect ? cleanText(sourceSelect.value) : cleanText(widget.dataset.defaultSource);
    const flow = selectedFlowValue(widget) || cleanText(widget.dataset.defaultFlow);
    const title = titleInput ? cleanText(titleInput.value) : '';
    const message = messageInput ? cleanText(messageInput.value) : '';
    const contactEmail = emailInput ? cleanText(emailInput.value) : '';
    const context = cleanText(widget.dataset.context);

    return {
      source,
      flow,
      title,
      message,
      contact_email: contactEmail,
      context,
      page_path: window.location.pathname,
      page_url: window.location.href,
      metadata: {
        viewport: `${window.innerWidth}x${window.innerHeight}`,
      },
    };
  }

  function restoreDefaults(widget){
    const form = widget.querySelector('[data-feedback-note-form]');
    if (!form) return;
    form.reset();

    const defaultSource = cleanText(widget.dataset.defaultSource);
    const sourceSelect = form.querySelector('select[name="source"]');
    if (sourceSelect && defaultSource) {
      sourceSelect.value = defaultSource;
    }

    const defaultFlow = cleanText(widget.dataset.defaultFlow || 'question');
    if (defaultFlow) {
      const defaultRadio = form.querySelector(`input[name="flow"][value="${defaultFlow}"]`);
      if (defaultRadio) {
        defaultRadio.checked = true;
      }
    }

    const savedPath = widget.querySelector('[data-feedback-saved-path]');
    if (savedPath) {
      savedPath.textContent = '';
    }

    setError(widget, '');
    setSubmitting(widget, false);
    updateFlowSelectionStyles(widget);
    updateSortSummary(widget);
    showStep(widget, STEP_SORT);
  }

  async function submitFeedback(widget){
    setError(widget, '');
    if (!validateSortStep(widget)) {
      showStep(widget, STEP_SORT);
      return;
    }
    if (!validateDetailsStep(widget)) {
      showStep(widget, STEP_DETAILS);
      return;
    }

    const endpoint = cleanText(widget.dataset.endpoint) || '/tools/api/feedback-notes';
    const payload = buildPayload(widget);
    const csrfToken = getCsrfToken();

    setSubmitting(widget, true);
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.success !== true) {
        throw new Error(data.error || 'Unable to save your note right now.');
      }

      const result = data.result || {};
      const pathLabel = widget.querySelector('[data-feedback-saved-path]');
      if (pathLabel) {
        const bucketPath = cleanText(result.bucket_path);
        pathLabel.textContent = bucketPath ? `Saved in ${bucketPath}` : 'Saved.';
      }
      showStep(widget, STEP_SUCCESS);
    } catch (error) {
      setError(widget, error && error.message ? error.message : 'Unable to save your note right now.');
      showStep(widget, STEP_DETAILS);
    } finally {
      setSubmitting(widget, false);
    }
  }

  function initFeedbackNoteWidget(widget){
    if (!widget || widget.dataset.feedbackReady === '1') {
      return;
    }
    widget.dataset.feedbackReady = '1';

    const modal = widget.querySelector('.feedback-note-modal');
    const form = widget.querySelector('[data-feedback-note-form]');
    const nextBtn = widget.querySelector('[data-feedback-next]');
    const backBtn = widget.querySelector('[data-feedback-back]');
    const submitAnotherBtn = widget.querySelector('[data-feedback-submit-another]');

    if (!modal || !form) {
      return;
    }

    restoreDefaults(widget);

    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        setError(widget, '');
        if (!validateSortStep(widget)) {
          return;
        }
        showStep(widget, STEP_DETAILS);
        const messageInput = widget.querySelector('textarea[name="message"]');
        if (messageInput && typeof messageInput.focus === 'function') {
          messageInput.focus();
        }
      });
    }

    if (backBtn) {
      backBtn.addEventListener('click', () => {
        setError(widget, '');
        showStep(widget, STEP_SORT);
      });
    }

    if (submitAnotherBtn) {
      submitAnotherBtn.addEventListener('click', () => {
        restoreDefaults(widget);
        showStep(widget, STEP_DETAILS);
        const messageInput = widget.querySelector('textarea[name="message"]');
        if (messageInput && typeof messageInput.focus === 'function') {
          messageInput.focus();
        }
      });
    }

    form.addEventListener('submit', event => {
      event.preventDefault();
      submitFeedback(widget);
    });

    const sourceSelect = widget.querySelector('select[name="source"]');
    if (sourceSelect) {
      sourceSelect.addEventListener('change', () => {
        updateSortSummary(widget);
      });
    }

    widget.querySelectorAll('input[name="flow"]').forEach(input => {
      input.addEventListener('change', () => {
        updateFlowSelectionStyles(widget);
        updateSortSummary(widget);
      });
    });

    modal.addEventListener('show.bs.modal', () => {
      setError(widget, '');
      updateFlowSelectionStyles(widget);
      updateSortSummary(widget);
    });

    modal.addEventListener('hidden.bs.modal', () => {
      restoreDefaults(widget);
    });
  }

  function initAllFeedbackNoteWidgets(){
    document.querySelectorAll('[data-feedback-note-widget]').forEach(initFeedbackNoteWidget);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAllFeedbackNoteWidgets);
  } else {
    initAllFeedbackNoteWidgets();
  }

  window.BatchTrackFeedbackNote = {
    init: initFeedbackNoteWidget,
    initAll: initAllFeedbackNoteWidgets,
  };
})(window);
