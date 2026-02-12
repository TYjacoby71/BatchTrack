(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { formatWeight, formatPercent } = SoapTool.units;

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
    if (superfatRaw === '' || superfatRaw === null || superfatRaw === undefined) {
      superfat = 5;
    }
    superfat = clamp(superfat, 0, 20);
    if (superfatInput) superfatInput.value = round(superfat, 1);
    return superfat;
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
