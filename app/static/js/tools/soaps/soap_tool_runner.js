(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp, getStorage } = SoapTool.helpers;
  const { formatWeight, formatPercent } = SoapTool.units;
  const state = SoapTool.state;

  function getLyeSelection(){
    const selected = document.querySelector('input[name="lye_type"]:checked')?.value || 'NaOH';
    const purityInput = document.getElementById('lyePurity');
    let purity = toNumber(purityInput?.value);
    const lyeType = selected === 'NaOH' ? 'NaOH' : 'KOH';
    if (selected === 'KOH90') {
      purity = 90;
    }
    return { selected, lyeType, purity };
  }

  function applyLyeSelection(){
    const purityInput = document.getElementById('lyePurity');
    if (!purityInput) return;
    const selection = getLyeSelection();
    if (selection.selected === 'KOH90') {
      purityInput.value = '90';
      purityInput.setAttribute('readonly', 'readonly');
      const hint = document.getElementById('lyePurityHint');
      if (hint) hint.textContent = '90% KOH selected (purity locked).';
    } else {
      purityInput.removeAttribute('readonly');
      const hint = document.getElementById('lyePurityHint');
      if (hint) hint.textContent = 'Most calculators assume 100%.';
    }
  }

  function setWaterMethod(){
    const method = document.getElementById('waterMethod').value;
    document.querySelectorAll('.water-input').forEach(el => {
      el.classList.toggle('d-none', el.dataset.method !== method);
    });
    updateStageWaterSummary(null, method);
    updateLiveCalculationPreview(null, method);
  }

  function getWaterMethodHelp(method){
    if (method === 'concentration') {
      return 'Concentration mode uses lye amount, so superfat and purity change water.';
    }
    if (method === 'ratio') {
      return 'Ratio mode uses lye amount, so superfat and purity change water.';
    }
    return 'Percent mode uses oils total, so superfat changes lye but not water.';
  }

  function updateStageWaterSummary(summary = null, explicitMethod = null){
    const waterOutput = document.getElementById('stageWaterOutput');
    const hintOutput = document.getElementById('stageWaterComputedHint');
    const method = explicitMethod || summary?.waterMethod || document.getElementById('waterMethod')?.value || 'percent';

    if (waterOutput) {
      const hasWater = summary && isFinite(summary.waterG) && summary.waterG > 0;
      waterOutput.textContent = hasWater ? formatWeight(summary.waterG) : '--';
    }
    if (!hintOutput) return;

    if (!summary || !isFinite(summary.totalOils) || summary.totalOils <= 0) {
      hintOutput.textContent = `Set oils in Stage 2 to calculate water. ${getWaterMethodHelp(method)}`;
      return;
    }

    if (method === 'concentration') {
      const concentration = summary.lyeConcentrationInput || summary.lyeConcentration || 0;
      hintOutput.textContent = `Using ${round(concentration, 1)}% lye concentration from ${formatWeight(summary.lyeAdjusted || 0)} lye.`;
      return;
    }
    if (method === 'ratio') {
      const ratio = summary.waterRatioInput || summary.waterRatio || 0;
      hintOutput.textContent = `Using ${round(ratio, 2)} : 1 water-to-lye ratio from ${formatWeight(summary.lyeAdjusted || 0)} lye.`;
      return;
    }
    hintOutput.textContent = `Using ${round(summary.waterPct || 0, 1)}% of total oils (${formatWeight(summary.totalOils)}).`;
  }

  function updateLiveCalculationPreview(summary = null, explicitMethod = null){
    const anchorEl = document.getElementById('lyeWaterPreviewAnchor');
    const lyeEl = document.getElementById('lyePreview');
    const waterEl = document.getElementById('waterPreview');
    const concEl = document.getElementById('concPreview');
    const ratioEl = document.getElementById('ratioPreview');
    if (!anchorEl && !lyeEl && !waterEl && !concEl && !ratioEl) return;

    const setText = (el, value) => {
      if (el) el.textContent = value;
    };
    const method = explicitMethod || summary?.waterMethod || document.getElementById('waterMethod')?.value || 'percent';
    const totalOils = toNumber(summary?.totalOils);
    const lye = toNumber(summary?.lyeAdjusted);
    const water = toNumber(summary?.waterG);
    if (totalOils <= 0 || lye <= 0) {
      setText(anchorEl, 'Based on -- oils. All values update live as you change inputs.');
      setText(lyeEl, '--');
      setText(waterEl, '--');
      setText(concEl, '--');
      setText(ratioEl, '--');
      return;
    }

    const concentration = toNumber(summary?.lyeConcentration) > 0
      ? toNumber(summary?.lyeConcentration)
      : ((lye + water) > 0 ? (lye / (lye + water)) * 100 : 0);
    const ratio = toNumber(summary?.waterRatio) > 0
      ? toNumber(summary?.waterRatio)
      : (lye > 0 ? water / lye : 0);
    setText(anchorEl, `Based on ${formatWeight(totalOils)} oils. All values update live as you change inputs.`);
    setText(lyeEl, formatWeight(lye));
    setText(waterEl, formatWeight(water));
    setText(concEl, concentration > 0 ? formatPercent(concentration) : '--');
    setText(ratioEl, ratio > 0 ? `${round(ratio, 2)} : 1` : '--');

    if (method === 'concentration') {
      const concentrationInput = toNumber(summary?.lyeConcentrationInput);
      if (concentrationInput > 0) {
        setText(concEl, formatPercent(concentrationInput));
      }
    }
    if (method === 'ratio') {
      const ratioInput = toNumber(summary?.waterRatioInput);
      if (ratioInput > 0) {
        setText(ratioEl, `${round(ratioInput, 2)} : 1`);
      }
    }
  }

  function validateCalculation(){
    const totals = SoapTool.oils.updateOilTotals();
    const totalOils = totals.totalWeight;
    const totalPct = totals.totalPct;
    const errors = [];
    const oils = SoapTool.oils.collectOilData();
    const target = SoapTool.oils.getOilTargetGrams();
    const percentInputs = Array.from(document.querySelectorAll('#oilRows .oil-percent'))
      .map(input => clamp(toNumber(input.value), 0));
    const hasPercent = percentInputs.some(value => value > 0);

    if (!oils.length || totalOils <= 0) {
      errors.push('Add at least one oil with a weight or percent.');
    }
    if (!target && totalOils <= 0 && hasPercent) {
      errors.push('Enter a total oils target or weights to convert percentages.');
    }
    if (target > 0 && totalPct > 0 && Math.abs(totalPct - 100) > 0.5) {
      errors.push('Oil percentages should total 100% (use Normalize to fix).');
    }
    if (target > 0 && totalOils > target + 0.01) {
      errors.push('Oil weights exceed the mold target.');
    } else if (!target && totalPct > 100.01) {
      errors.push('Oil percentages exceed 100%.');
    }
    return { ok: errors.length === 0, errors, totals, oils };
  }

  function sanitizeLyeInputs(){
    const selection = getLyeSelection();
    const purityInput = document.getElementById('lyePurity');
    let purity = selection.purity;
    if (!purity || purity <= 0) {
      purity = 100;
    }
    purity = Math.min(100, Math.max(90, purity));
    if (selection.selected === 'KOH90') {
      purity = 90;
    }
    if (purityInput) {
      purityInput.value = round(purity, 1);
    }

    const waterMethod = document.getElementById('waterMethod')?.value || 'percent';
    let waterPct = toNumber(document.getElementById('waterPct')?.value);
    let lyeConcentration = toNumber(document.getElementById('lyeConcentration')?.value);
    let waterRatio = toNumber(document.getElementById('waterRatio')?.value);

    if (waterMethod === 'percent') {
      if (!waterPct || waterPct <= 0) {
        waterPct = 33;
      }
      const input = document.getElementById('waterPct');
      if (input) input.value = round(waterPct, 1);
    }
    if (waterMethod === 'concentration') {
      if (!lyeConcentration || lyeConcentration <= 0) {
        lyeConcentration = 33;
      }
      lyeConcentration = clamp(lyeConcentration, 20, 50);
      const input = document.getElementById('lyeConcentration');
      if (input) input.value = round(lyeConcentration, 1);
    }
    if (waterMethod === 'ratio') {
      if (!waterRatio || waterRatio <= 0) {
        waterRatio = 2;
      }
      waterRatio = clamp(waterRatio, 1, 4);
      const input = document.getElementById('waterRatio');
      if (input) input.value = round(waterRatio, 2);
    }

    return { purity, waterMethod, waterPct, lyeConcentration, waterRatio };
  }

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
      SoapTool.ui.showSoapAlert('warning', `You have reached the ${SoapTool.config.calcLimit} calculation limit for ${SoapTool.config.calcTier} accounts. Create a free account or upgrade to keep calculating.`, { dismissible: true });
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
      SoapTool.ui.showSoapAlert('info', `You have ${remaining} calculation${remaining === 1 ? '' : 's'} left on the ${SoapTool.config.calcTier} tier today.`, { dismissible: true, timeoutMs: 6000 });
    }
  }

  function maybeShowSignupModal(remaining){
    if (!SoapTool.config.calcLimit || remaining === null || remaining > 1) return;
    const modalEl = document.getElementById('soapSignupModal');
    if (!modalEl) return;
    if (window.bootstrap && window.bootstrap.Modal) {
      const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    } else {
      SoapTool.ui.showSoapAlert('info', 'You are almost at the free limit. Create a free account to keep saving your work.', { dismissible: true, timeoutMs: 7000 });
    }
  }

  function buildServicePayload({ oils, selection, superfat, purity, waterMethod, waterPct, lyeConcentration, waterRatio, totalOils }){
    const additiveSettings = SoapTool.additives.collectAdditiveSettings
      ? SoapTool.additives.collectAdditiveSettings()
      : {
        lactatePct: toNumber(document.getElementById('additiveLactatePct')?.value),
        sugarPct: toNumber(document.getElementById('additiveSugarPct')?.value),
        saltPct: toNumber(document.getElementById('additiveSaltPct')?.value),
        citricPct: toNumber(document.getElementById('additiveCitricPct')?.value),
        lactateName: document.getElementById('additiveLactateName')?.value?.trim() || 'Sodium Lactate',
        sugarName: document.getElementById('additiveSugarName')?.value?.trim() || 'Sugar',
        saltName: document.getElementById('additiveSaltName')?.value?.trim() || 'Salt',
        citricName: document.getElementById('additiveCitricName')?.value?.trim() || 'Citric Acid',
      };
    const fragranceRows = SoapTool.recipePayload?.collectFragranceRows
      ? SoapTool.recipePayload.collectFragranceRows(totalOils || 0)
      : [];
    return {
      oils: (oils || []).map(oil => ({
        name: oil.name || null,
        grams: oil.grams || 0,
        sap_koh: oil.sapKoh || 0,
        iodine: oil.iodine || 0,
        fatty_profile: oil.fattyProfile || null,
        global_item_id: oil.global_item_id || null,
        default_unit: oil.default_unit || null,
        ingredient_category_name: oil.ingredient_category_name || null,
      })),
      fragrances: fragranceRows.map(row => ({
        name: row.name || 'Fragrance/Essential Oils',
        grams: row.grams || 0,
        pct: row.pct || 0,
      })),
      additives: {
        lactate_pct: additiveSettings.lactatePct || 0,
        sugar_pct: additiveSettings.sugarPct || 0,
        salt_pct: additiveSettings.saltPct || 0,
        citric_pct: additiveSettings.citricPct || 0,
        lactate_name: additiveSettings.lactateName || 'Sodium Lactate',
        sugar_name: additiveSettings.sugarName || 'Sugar',
        salt_name: additiveSettings.saltName || 'Salt',
        citric_name: additiveSettings.citricName || 'Citric Acid',
      },
      lye: {
        selected: selection?.selected || 'NaOH',
        superfat,
        purity,
      },
      water: {
        method: waterMethod,
        water_pct: waterPct,
        lye_concentration: lyeConcentration,
        water_ratio: waterRatio,
      },
      meta: {
        unit_display: state.currentUnit || 'g',
      }
    };
  }

  async function calculateWithSoapService(payload){
    const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 2500);
    try {
      const response = await fetch('/tools/api/soap/calculate', {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-CSRFToken': token } : {}),
        },
        body: JSON.stringify(payload || {}),
      });
      if (!response.ok) return null;
      const data = await response.json();
      if (!data || data.success !== true || typeof data.result !== 'object') return null;
      return data.result;
    } catch (_) {
      return null;
    } finally {
      window.clearTimeout(timeoutId);
    }
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
    const validation = validateCalculation();
    if (!validation.ok) {
      updateStageWaterSummary(null);
      updateLiveCalculationPreview(null);
      if (settings.showAlerts) {
        SoapTool.ui.showSoapAlert('warning', `<strong>Missing info:</strong><ul class="mb-0">${validation.errors.map(err => `<li>${err}</li>`).join('')}</ul>`, { dismissible: true, persist: true });
      }
      return null;
    }
    if (settings.consumeQuota && !canConsumeCalcQuota()) {
      return null;
    }
    const superfatInput = document.getElementById('lyeSuperfat');
    const superfatRaw = superfatInput?.value;
    let superfat = toNumber(superfatRaw);
    if (superfatRaw === '' || superfatRaw === null || superfatRaw === undefined) {
      superfat = 5;
    }
    superfat = clamp(superfat, 0, 20);
    if (superfatInput) superfatInput.value = round(superfat, 1);
    const selection = getLyeSelection();
    const sanitized = sanitizeLyeInputs();
    let purity = sanitized.purity;
    let waterMethod = sanitized.waterMethod;
    let waterPct = sanitized.waterPct;
    let lyeConcentration = sanitized.lyeConcentration;
    let waterRatio = sanitized.waterRatio;

    const oils = validation.oils;
    const requestSeq = (state.calcRequestSeq || 0) + 1;
    state.calcRequestSeq = requestSeq;
    const servicePayload = buildServicePayload({
      oils,
      selection,
      superfat,
      purity,
      waterMethod,
      waterPct,
      lyeConcentration,
      waterRatio,
      totalOils: validation.totals.totalWeight,
    });
    const serviceResult = await calculateWithSoapService(servicePayload);
    if (requestSeq !== state.calcRequestSeq) {
      return state.lastCalc;
    }
    if (!serviceResult) {
      if (settings.showAlerts) {
        SoapTool.ui.showSoapAlert('danger', 'Soap calculator service is unavailable. Please try again.', { dismissible: true, timeoutMs: 6000 });
      }
      return null;
    }

    const lyeType = serviceResult.lye_type || selection.lyeType || 'NaOH';
    const totalOils = toNumber(serviceResult.total_oils_g) || validation.totals.totalWeight;
    const lyeTotals = {
      lyeTotal: toNumber(serviceResult.lye_total_g),
      sapAvg: toNumber(serviceResult.sap_avg_koh),
      usedFallback: !!serviceResult.used_sap_fallback,
    };
    const lyePure = toNumber(serviceResult.lye_pure_g);
    const lyeAdjusted = toNumber(serviceResult.lye_adjusted_g);
    purity = toNumber(serviceResult.lye_purity_pct) || purity;
    waterMethod = serviceResult.water_method || waterMethod;
    waterPct = toNumber(serviceResult.water_pct) || waterPct;
    lyeConcentration = toNumber(serviceResult.lye_concentration_input_pct) || lyeConcentration;
    waterRatio = toNumber(serviceResult.water_ratio_input) || waterRatio;
    const waterData = {
      waterG: toNumber(serviceResult.water_g),
      lyeConcentration: toNumber(serviceResult.lye_concentration_pct),
      waterRatio: toNumber(serviceResult.water_lye_ratio),
    };
    const resultsCard = serviceResult.results_card || {};
    const qualityReport = serviceResult.quality_report || {};
    const oilsForState = (serviceResult.oils || oils).map(oil => ({
      name: oil.name || null,
      grams: toNumber(oil.grams),
      sapKoh: toNumber(oil.sap_koh ?? oil.sapKoh),
      iodine: toNumber(oil.iodine),
      fattyProfile: oil.fatty_profile || oil.fattyProfile || null,
      global_item_id: oil.global_item_id || null,
      default_unit: oil.default_unit || null,
      ingredient_category_name: oil.ingredient_category_name || null,
    }));
    const liveSummary = {
      waterG: waterData.waterG,
      lyeAdjusted,
      totalOils,
      waterMethod,
      waterPct,
      lyeConcentrationInput: lyeConcentration,
      waterRatioInput: waterRatio,
      lyeConcentration: waterData.lyeConcentration,
      waterRatio: waterData.waterRatio,
    };
    updateStageWaterSummary(liveSummary);
    updateLiveCalculationPreview(liveSummary);
    const additives = serviceResult.additives || { lactateG: 0, sugarG: 0, saltG: 0, citricG: 0, citricLyeG: 0, fragranceG: 0, fragrancePct: 0 };
    if (SoapTool.additives.applyComputedOutputs) {
      SoapTool.additives.applyComputedOutputs(additives);
    }
    const batchYield = toNumber(resultsCard.batch_yield_g) || (
      totalOils + lyeAdjusted + waterData.waterG + additives.fragranceG + additives.lactateG + additives.sugarG + additives.saltG + additives.citricG
    );

    document.getElementById('resultsCard').style.display = 'block';
    document.getElementById('lyeAdjustedOutput').textContent = formatWeight(toNumber(resultsCard.lye_adjusted_g) || lyeAdjusted);
    document.getElementById('waterOutput').textContent = formatWeight(toNumber(resultsCard.water_g) || waterData.waterG);
    document.getElementById('batchYieldOutput').textContent = formatWeight(batchYield);
    document.getElementById('lyeConcentrationOutput').textContent = formatPercent(
      toNumber(resultsCard.lye_concentration_pct) || waterData.lyeConcentration
    );
    document.getElementById('waterRatioOutput').textContent = isFinite(toNumber(resultsCard.water_lye_ratio) || waterData.waterRatio) && (toNumber(resultsCard.water_lye_ratio) || waterData.waterRatio) > 0
      ? round(toNumber(resultsCard.water_lye_ratio) || waterData.waterRatio, 2).toString()
      : '--';
    document.getElementById('totalOilsOutput').textContent = formatWeight(totalOils);
    document.getElementById('superfatOutput').textContent = formatPercent(superfat);

    ['lyeAdjustedOutput', 'waterOutput', 'batchYieldOutput', 'lyeConcentrationOutput', 'waterRatioOutput', 'totalOilsOutput', 'superfatOutput']
      .forEach(id => SoapTool.ui.pulseValue(document.getElementById(id)));
    SoapTool.ui.updateResultsWarnings(waterData);
    SoapTool.ui.updateResultsMeta();

    SoapTool.quality.updateQualitiesDisplay({
      qualities: qualityReport.qualities || {},
      fattyPercent: qualityReport.fatty_acids_pct || {},
      coveragePct: toNumber(qualityReport.coverage_pct),
      iodine: toNumber(qualityReport.iodine),
      ins: toNumber(qualityReport.ins),
      sapAvg: lyeTotals.sapAvg,
      superfat,
      waterData,
      additives,
      oils: oilsForState,
      totalOils,
      warnings: qualityReport.warnings || [],
    });
    SoapTool.additives.updateVisualGuidance({
      tips: qualityReport.visual_guidance || [],
    });
    SoapTool.stages.updateStageStatuses();

    if (settings.showAlerts) {
      if (lyeTotals.usedFallback) {
        SoapTool.ui.showSoapAlert('info', 'Some oils are missing SAP values, so an average SAP was used. Select oils with SAP data for the most accurate lye calculation.', { dismissible: true, timeoutMs: 7000 });
      }
      if (purity < 100) {
        SoapTool.ui.showSoapAlert('info', `Lye purity is set to ${round(purity, 1)}%. Adjusting lye to match your real-world purity.`, { dismissible: true, timeoutMs: 6000 });
      }
      if (waterData.lyeConcentration < 25 || waterData.lyeConcentration > 45) {
        SoapTool.ui.showSoapAlert('warning', 'Your lye concentration is outside the common 25-45% range. Expect slower or faster trace.', { dismissible: true, timeoutMs: 7000 });
      }
      const mold = SoapTool.mold.getMoldSettings();
      if (mold.shape === 'cylinder' && mold.waterWeight > 0 && !mold.useCylinder) {
        SoapTool.ui.showSoapAlert('info', 'Cylinder mold selected. Enable the cylinder correction if you want to leave headspace or reduce spill risk.', { dismissible: true, timeoutMs: 7000 });
      }
    }

    state.lastCalc = {
      totalOils,
      oils: oilsForState,
      lyeType,
      superfat,
      purity,
      lyePure,
      lyeAdjusted,
      water: waterData.waterG,
      waterMethod,
      waterPct,
      lyeConcentration: waterData.lyeConcentration,
      waterRatio: waterData.waterRatio,
      sapAvg: lyeTotals.sapAvg,
      usedSapFallback: lyeTotals.usedFallback,
      additives,
      batchYield,
      qualityReport,
      export: serviceResult.export || null,
    };
    if (settings.consumeQuota) {
      consumeCalcQuota();
    }
    return state.lastCalc;
    } catch (_) {
      if (settings.showAlerts) {
        SoapTool.ui.showSoapAlert('danger', 'Unable to run the soap calculation right now. Please try again.', { dismissible: true, timeoutMs: 6000 });
      }
      return null;
    }
  }

  SoapTool.runner = {
    getLyeSelection,
    applyLyeSelection,
    setWaterMethod,
    updateLiveCalculationPreview,
    calculateAll,
    buildSoapRecipePayload: (...args) => SoapTool.recipePayload.buildSoapRecipePayload(...args),
    buildLineRow: (...args) => SoapTool.recipePayload.buildLineRow(...args),
    addStubLine: (...args) => SoapTool.recipePayload.addStubLine(...args),
    maybeShowSignupModal,
  };
})(window);
