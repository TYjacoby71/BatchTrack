(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { getStorage } = SoapTool.helpers;

  function readCalcUsage(){
    if (!SoapTool.config.calcLimit) return { count: 0, date: null };
    const storage = getStorage();
    if (!storage) return { count: 0, date: null };
    try {
      const raw = storage.getItem('soap_calc_usage');
      const today = new Date().toISOString().slice(0, 10);
      if (!raw) return { count: 0, date: today };
      const data = JSON.parse(raw);
      if (!data || data.date !== today) {
        return { count: 0, date: today };
      }
      return { count: Number(data.count) || 0, date: today };
    } catch (_) {
      return { count: 0, date: null };
    }
  }

  function writeCalcUsage(count){
    if (!SoapTool.config.calcLimit) return;
    const storage = getStorage();
    if (!storage) return;
    const today = new Date().toISOString().slice(0, 10);
    try {
      storage.setItem('soap_calc_usage', JSON.stringify({ count, date: today }));
    } catch (_) {}
  }

  function canConsumeCalcQuota(){
    if (!SoapTool.config.calcLimit) return true;
    const usage = readCalcUsage();
    if (usage.count >= SoapTool.config.calcLimit) {
      const signupUrl = buildQuickSignupUrl('soap_making_rate_limit_cta');
      SoapTool.ui.showSoapAlert(
        'warning',
        `You have reached the ${SoapTool.config.calcLimit} calculation limit for ${SoapTool.config.calcTier} accounts. <a href="${signupUrl}" class="alert-link">Create a free account</a> or upgrade to keep calculating.`,
        { dismissible: true }
      );
      return false;
    }
    return true;
  }

  function consumeCalcQuota(){
    if (!SoapTool.config.calcLimit) return;
    const usage = readCalcUsage();
    const nextCount = usage.count + 1;
    writeCalcUsage(nextCount);
    const remaining = Math.max(0, SoapTool.config.calcLimit - nextCount);
    if (remaining <= 1) {
      SoapTool.ui.showSoapAlert(
        'info',
        `You have ${remaining} calculation${remaining === 1 ? '' : 's'} left on the ${SoapTool.config.calcTier} tier today.`,
        { dismissible: true, timeoutMs: 6000 }
      );
    }
  }

  function maybeShowSignupModal(remaining){
    if (!SoapTool.config.calcLimit || remaining === null || remaining > 1) return;
    const modalEl = document.getElementById('soapSignupModal');
    if (!modalEl) return;
    const signupLink = modalEl.querySelector('a.btn.btn-primary');
    if (signupLink) {
      signupLink.href = buildQuickSignupUrl('soap_making_cta');
    }
    if (window.bootstrap && window.bootstrap.Modal) {
      const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    } else {
      SoapTool.ui.showSoapAlert(
        'info',
        'You are almost at the free limit. Create a free account to keep saving your work.',
        { dismissible: true, timeoutMs: 7000 }
      );
    }
  }

  function buildQuickSignupUrl(source){
    const params = new URLSearchParams();
    params.set('source', source || 'quick_signup');
    const nextPath = `${window.location.pathname || '/tools/soap'}${window.location.search || ''}`;
    if (nextPath && nextPath.startsWith('/')) {
      params.set('next', nextPath);
    }
    return `/auth/quick-signup?${params.toString()}`;
  }

  SoapTool.runnerQuota = {
    canConsumeCalcQuota,
    consumeCalcQuota,
    maybeShowSignupModal,
  };
})(window);
