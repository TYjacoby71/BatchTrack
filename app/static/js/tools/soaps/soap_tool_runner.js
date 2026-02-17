(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const state = SoapTool.state;
  const runnerInputs = SoapTool.runnerInputs;
  const runnerQuota = SoapTool.runnerQuota;
  const runnerService = SoapTool.runnerService;
  const runnerRender = SoapTool.runnerRender;

  async function buildSoapRecipePayload(calc){
    const requestPayload = SoapTool.recipePayload.buildSoapRecipePayloadRequest(calc);
    if (!requestPayload) return null;
    return runnerService.buildRecipePayload(requestPayload);
  }

  async function calculateAll(options = {}){
    const settings = {
      consumeQuota: false,
      showAlerts: true,
      ...options
    };
    try {
      if (settings.showAlerts) {
        SoapTool.ui.clearSoapAlerts();
      }

      const validation = runnerInputs.validateCalculation();
      if (!validation.ok) {
        runnerInputs.updateStageWaterSummary(null);
        runnerInputs.updateLiveCalculationPreview(null);
        if (SoapTool.mold?.updateWetBatterWarning) {
          SoapTool.mold.updateWetBatterWarning(0);
        }
        if (settings.showAlerts) {
          SoapTool.ui.showSoapAlert(
            'warning',
            `<strong>Missing info:</strong><ul class="mb-0">${validation.errors.map(err => `<li>${err}</li>`).join('')}</ul>`,
            { dismissible: true, persist: true }
          );
        }
        return null;
      }
      if (settings.consumeQuota && !runnerQuota.canConsumeCalcQuota()) {
        return null;
      }

      const superfat = runnerInputs.readSuperfatInput();
      const selection = runnerInputs.getLyeSelection();
      const sanitized = runnerInputs.sanitizeLyeInputs();

      const requestSeq = (state.calcRequestSeq || 0) + 1;
      state.calcRequestSeq = requestSeq;
      const servicePayload = runnerService.buildServicePayload({
        oils: validation.oils,
        selection,
        superfat,
        purity: sanitized.purity,
        waterMethod: sanitized.waterMethod,
        waterPct: sanitized.waterPct,
        lyeConcentration: sanitized.lyeConcentration,
        waterRatio: sanitized.waterRatio,
        totalOils: validation.totals.totalWeight,
      });
      const serviceResult = await runnerService.calculateWithSoapService(servicePayload);
      if (requestSeq !== state.calcRequestSeq) {
        return state.lastCalc;
      }
      if (!serviceResult) {
        if (settings.showAlerts) {
          SoapTool.ui.showSoapAlert(
            'danger',
            'Soap calculator service is unavailable. Please try again.',
            { dismissible: true, timeoutMs: 6000 }
          );
        }
        return null;
      }

      const calc = runnerRender.applyServiceResult({
        serviceResult,
        validation,
        selection,
        superfat,
        purity: sanitized.purity,
        waterMethod: sanitized.waterMethod,
        waterPct: sanitized.waterPct,
        lyeConcentrationInput: sanitized.lyeConcentration,
        waterRatioInput: sanitized.waterRatio,
        showAlerts: settings.showAlerts,
      });
      if (settings.consumeQuota) {
        runnerQuota.consumeCalcQuota();
      }
      return calc;
    } catch (_) {
      if (settings.showAlerts) {
        SoapTool.ui.showSoapAlert('danger', 'Unable to run the soap calculation right now. Please try again.', { dismissible: true, timeoutMs: 6000 });
      }
      return null;
    }
  }

  SoapTool.runner = {
    getLyeSelection: (...args) => runnerInputs.getLyeSelection(...args),
    applyLyeSelection: (...args) => runnerInputs.applyLyeSelection(...args),
    setWaterMethod: (...args) => runnerInputs.setWaterMethod(...args),
    updateLiveCalculationPreview: (...args) => runnerInputs.updateLiveCalculationPreview(...args),
    calculateAll,
    buildSoapRecipePayload,
    buildLineRow: (...args) => SoapTool.recipePayload.buildLineRow(...args),
    addStubLine: (...args) => SoapTool.recipePayload.addStubLine(...args),
    maybeShowSignupModal: (...args) => runnerQuota.maybeShowSignupModal(...args),
  };
})(window);
