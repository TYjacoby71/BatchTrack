(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { formatWeight, formatPercent } = SoapTool.units;

  function getLyeSelection(){
    const selected = document.querySelector('input[name="lye_type"]:checked')?.value || 'NaOH';
    const purityInput = document.getElementById('lyePurity');
    const purityRaw = purityInput?.value;
    let purity = toNumber(purityInput?.value);
    const lyeType = selected === 'NaOH' ? 'NaOH' : 'KOH';
    if (purityRaw === '' || purityRaw === null || purityRaw === undefined || !isFinite(purity)) {
      purity = 100;
    }
    return { selected, lyeType, purity };
  }

  function applyLyeSelection(){
    const purityInput = document.getElementById('lyePurity');
    const selection = getLyeSelection();
    if (!purityInput) return;
    purityInput.removeAttribute('readonly');
    if (selection.selected === 'KOH90') {
      const hint = document.getElementById('lyePurityHint');
      if (hint) hint.textContent = '90% KOH selected. Safe default purity is 90%.';
    } else {
      const hint = document.getElementById('lyePurityHint');
      if (hint) hint.textContent = 'Safe default is 100%.';
    }
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

  function setWaterMethod(){
    const method = document.getElementById('waterMethod')?.value || 'percent';
    document.querySelectorAll('.water-input').forEach(el => {
      el.classList.toggle('d-none', el.dataset.method !== method);
    });
    updateStageWaterSummary(null, method);
    updateLiveCalculationPreview(null, method);
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

  function readSuperfatInput(){
    const superfatInput = document.getElementById('lyeSuperfat');
    const superfatRaw = superfatInput?.value;
    let superfat = toNumber(superfatRaw);
    if (superfatRaw === '' || superfatRaw === null || superfatRaw === undefined || !isFinite(superfat)) {
      superfat = 5;
    }
    return superfat;
  }

  function sanitizeLyeInputs(){
    const selection = getLyeSelection();
    let purity = selection.purity;
    if (!isFinite(purity)) {
      purity = 100;
    }

    const waterMethod = document.getElementById('waterMethod')?.value || 'percent';
    // Do not force defaults or clamp user typing for water inputs.
    // Backend calculation logic owns method defaults/ranges.
    const waterPct = toNumber(document.getElementById('waterPct')?.value);
    const lyeConcentration = toNumber(document.getElementById('lyeConcentration')?.value);
    const waterRatio = toNumber(document.getElementById('waterRatio')?.value);

    return { purity, waterMethod, waterPct, lyeConcentration, waterRatio };
  }

  SoapTool.runnerInputs = {
    getLyeSelection,
    applyLyeSelection,
    setWaterMethod,
    updateStageWaterSummary,
    updateLiveCalculationPreview,
    validateCalculation,
    readSuperfatInput,
    sanitizeLyeInputs,
  };
})(window);
