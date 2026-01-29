(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp, getStorage } = SoapTool.helpers;
  const { formatWeight, formatPercent } = SoapTool.units;
  const { computeLyeTotals, computeWater, computeIodine, computeFattyAcids, computeQualities } = SoapTool.calc;
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
      waterPct = clamp(waterPct, 20, 50);
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

  function calculateAll(options = {}){
    const settings = {
      consumeQuota: false,
      showAlerts: true,
      ...options
    };
    if (settings.showAlerts) {
      SoapTool.ui.clearSoapAlerts();
    }
    const validation = validateCalculation();
    if (!validation.ok) {
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
    const lyeType = selection.lyeType || 'NaOH';
    const sanitized = sanitizeLyeInputs();
    const purity = sanitized.purity;
    const waterMethod = sanitized.waterMethod;
    const waterPct = sanitized.waterPct;
    const lyeConcentration = sanitized.lyeConcentration;
    const waterRatio = sanitized.waterRatio;

    let oils = validation.oils;
    let totalOils = validation.totals.totalWeight;
    const lyeTotals = computeLyeTotals(oils, lyeType);
    const lyePure = lyeTotals.lyeTotal * (1 - superfat / 100);
    const lyeAdjusted = purity > 0 ? lyePure / (purity / 100) : lyePure;
    const waterData = computeWater(lyeAdjusted, totalOils, waterMethod, waterPct, lyeConcentration, waterRatio);
    const additives = SoapTool.additives.updateAdditivesOutput(totalOils);
    const batchYield = totalOils + lyeAdjusted + waterData.waterG + additives.fragranceG + additives.lactateG + additives.sugarG + additives.saltG + additives.citricG;

    document.getElementById('resultsCard').style.display = 'block';
    document.getElementById('lyeAdjustedOutput').textContent = formatWeight(lyeAdjusted);
    document.getElementById('waterOutput').textContent = formatWeight(waterData.waterG);
    document.getElementById('batchYieldOutput').textContent = formatWeight(batchYield);
    document.getElementById('lyeConcentrationOutput').textContent = formatPercent(waterData.lyeConcentration);
    document.getElementById('waterRatioOutput').textContent = isFinite(waterData.waterRatio) && waterData.waterRatio > 0
      ? round(waterData.waterRatio, 2).toString()
      : '--';
    document.getElementById('totalOilsOutput').textContent = formatWeight(totalOils);
    document.getElementById('superfatOutput').textContent = formatPercent(superfat);

    ['lyeAdjustedOutput', 'waterOutput', 'batchYieldOutput', 'lyeConcentrationOutput', 'waterRatioOutput', 'totalOilsOutput', 'superfatOutput']
      .forEach(id => SoapTool.ui.pulseValue(document.getElementById(id)));
    SoapTool.ui.updateResultsWarnings(waterData);
    SoapTool.ui.updateResultsMeta();

    const iodineData = computeIodine(oils);
    const fatty = computeFattyAcids(oils);
    const qualities = computeQualities(fatty.percent);
    const ins = (lyeTotals.sapAvg && iodineData.iodine) ? (lyeTotals.sapAvg - iodineData.iodine) : 0;
    const coveragePct = totalOils > 0 ? (fatty.coveredWeight / totalOils) * 100 : 0;
    SoapTool.quality.updateQualitiesDisplay({
      qualities,
      fattyPercent: fatty.percent,
      coveragePct,
      iodine: iodineData.iodine,
      ins,
      sapAvg: lyeTotals.sapAvg,
      superfat,
      waterData,
      additives,
      oils,
      totalOils,
    });
    SoapTool.additives.updateVisualGuidance({
      fattyPercent: fatty.percent,
      waterData,
      additives,
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
      oils,
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
      additives,
      batchYield,
    };
    if (settings.consumeQuota) {
      consumeCalcQuota();
    }
    return state.lastCalc;
  }

  function buildSoapNotesBlob(calc){
    const iodineData = computeIodine(calc.oils || []);
    const fatty = computeFattyAcids(calc.oils || []);
    const qualities = computeQualities(fatty.percent || {});
    const lyeTotals = computeLyeTotals(calc.oils || [], calc.lyeType);
    const ins = (lyeTotals.sapAvg && iodineData.iodine) ? (lyeTotals.sapAvg - iodineData.iodine) : 0;
    const mold = SoapTool.mold.getMoldSettings();
    return {
      source: 'soap_tool',
      schema_version: 1,
      unit_display: SoapTool.state.currentUnit,
      input_mode: 'mixed',
      quality_preset: document.getElementById('qualityPreset')?.value || 'balanced',
      quality_focus: Array.from(document.querySelectorAll('.quality-focus:checked')).map(el => el.id),
      mold,
      oils: (calc.oils || []).map(oil => ({
        name: oil.name || null,
        grams: round(oil.grams || 0, 2),
        iodine: oil.iodine || null,
        sap_koh: oil.sapKoh || null,
        fatty_profile: oil.fattyProfile || null,
        global_item_id: oil.global_item_id || null,
      })),
      totals: {
        total_oils_g: round(calc.totalOils || 0, 2),
        batch_yield_g: round(calc.batchYield || 0, 2),
        lye_pure_g: round(calc.lyePure || 0, 2),
        lye_adjusted_g: round(calc.lyeAdjusted || 0, 2),
        water_g: round(calc.water || 0, 2),
      },
      lye: {
        lye_type: calc.lyeType,
        superfat: calc.superfat,
        purity: calc.purity,
        water_method: calc.waterMethod,
        water_pct: calc.waterPct,
        lye_concentration: calc.lyeConcentration,
        water_ratio: calc.waterRatio,
      },
      additives: {
        fragrance_pct: calc.additives?.fragrancePct || 0,
        lactate_pct: calc.additives?.lactatePct || 0,
        sugar_pct: calc.additives?.sugarPct || 0,
        salt_pct: calc.additives?.saltPct || 0,
        citric_pct: calc.additives?.citricPct || 0,
        fragrance_g: round(calc.additives?.fragranceG || 0, 2),
        lactate_g: round(calc.additives?.lactateG || 0, 2),
        sugar_g: round(calc.additives?.sugarG || 0, 2),
        salt_g: round(calc.additives?.saltG || 0, 2),
        citric_g: round(calc.additives?.citricG || 0, 2),
        citric_lye_g: round(calc.additives?.citricLyeG || 0, 2),
      },
      qualities: {
        hardness: round(qualities.hardness || 0, 1),
        cleansing: round(qualities.cleansing || 0, 1),
        conditioning: round(qualities.conditioning || 0, 1),
        bubbly: round(qualities.bubbly || 0, 1),
        creamy: round(qualities.creamy || 0, 1),
        iodine: round(iodineData.iodine || 0, 1),
        ins: round(ins || 0, 1),
        sap_avg: round(lyeTotals.sapAvg || 0, 1),
      },
      fatty_acids: fatty.percent || {},
      updated_at: new Date().toISOString(),
    };
  }

  function getAdditiveItem(nameId, giId, fallbackName){
    const name = document.getElementById(nameId)?.value?.trim();
    const giRaw = document.getElementById(giId)?.value || '';
    return {
      name: name || fallbackName,
      globalItemId: giRaw ? parseInt(giRaw) : undefined,
    };
  }

  function collectFragranceRows(totalOils){
    const rows = [];
    const target = clamp(totalOils || SoapTool.oils.getTotalOilsGrams() || 0, 0);
    document.querySelectorAll('#fragranceRows .fragrance-row').forEach(row => {
      const name = row.querySelector('.fragrance-typeahead')?.value?.trim();
      const giRaw = row.querySelector('.fragrance-gi-id')?.value || '';
      const gramsInput = row.querySelector('.fragrance-grams')?.value;
      const pctInput = row.querySelector('.fragrance-percent')?.value;
      let grams = SoapTool.units.toGrams(gramsInput);
      const pct = clamp(toNumber(pctInput), 0);
      if (grams <= 0 && pct > 0 && target > 0) {
        grams = target * (pct / 100);
      }
      if (!name && !giRaw && grams <= 0) return;
      rows.push({
        name: name || 'Fragrance/Essential Oils',
        globalItemId: giRaw ? parseInt(giRaw) : undefined,
        grams,
      });
    });
    return rows;
  }

  function buildSoapRecipePayload(calc){
    const notesBlob = buildSoapNotesBlob(calc);
    const baseIngredients = (calc.oils || []).map(oil => ({
      name: oil.name || undefined,
      global_item_id: oil.global_item_id || undefined,
      quantity: oil.grams,
      unit: 'gram',
    }));
    const lyeName = calc.lyeType === 'KOH' ? 'Potassium Hydroxide (KOH)' : 'Sodium Hydroxide (NaOH)';
    if (calc.lyeAdjusted > 0) {
      baseIngredients.push({ name: lyeName, quantity: round(calc.lyeAdjusted, 2), unit: 'gram' });
    }
    if (calc.water > 0) {
      baseIngredients.push({ name: 'Distilled Water', quantity: round(calc.water, 2), unit: 'gram' });
    }
    const fragranceRows = collectFragranceRows(calc.totalOils || 0);
    fragranceRows.forEach(item => {
      if (item.grams > 0) {
        baseIngredients.push({ name: item.name, global_item_id: item.globalItemId, quantity: round(item.grams, 2), unit: 'gram' });
      }
    });
    if (calc.additives?.lactateG > 0) {
      const item = getAdditiveItem('additiveLactateName', 'additiveLactateGi', 'Sodium Lactate');
      baseIngredients.push({ name: item.name, global_item_id: item.globalItemId, quantity: round(calc.additives.lactateG, 2), unit: 'gram' });
    }
    if (calc.additives?.sugarG > 0) {
      const item = getAdditiveItem('additiveSugarName', 'additiveSugarGi', 'Sugar');
      baseIngredients.push({ name: item.name, global_item_id: item.globalItemId, quantity: round(calc.additives.sugarG, 2), unit: 'gram' });
    }
    if (calc.additives?.saltG > 0) {
      const item = getAdditiveItem('additiveSaltName', 'additiveSaltGi', 'Salt');
      baseIngredients.push({ name: item.name, global_item_id: item.globalItemId, quantity: round(calc.additives.saltG, 2), unit: 'gram' });
    }
    if (calc.additives?.citricG > 0) {
      const item = getAdditiveItem('additiveCitricName', 'additiveCitricGi', 'Citric Acid');
      baseIngredients.push({ name: item.name, global_item_id: item.globalItemId, quantity: round(calc.additives.citricG, 2), unit: 'gram' });
      baseIngredients.push({ name: 'Extra Lye for Citric Acid', quantity: round(calc.additives.citricLyeG, 2), unit: 'gram' });
    }
    return {
      name: 'Soap (Draft)',
      instructions: 'Draft from Soap Tools',
      predicted_yield: Math.round((calc.batchYield || 0) * 100) / 100,
      predicted_yield_unit: 'gram',
      category_name: 'Soaps',
      category_data: {
        soap_superfat: calc.superfat,
        soap_lye_type: calc.lyeType,
        soap_lye_purity: calc.purity,
        soap_water_method: calc.waterMethod,
        soap_water_pct: calc.waterPct,
        soap_lye_concentration: calc.lyeConcentration,
        soap_water_ratio: calc.waterRatio,
        soap_oils_total_g: calc.totalOils,
        soap_lye_g: calc.lyeAdjusted,
        soap_water_g: calc.water,
      },
      ingredients: baseIngredients.concat(collectDraftLines('tool-ingredients', 'ingredient')),
      consumables: collectDraftLines('tool-consumables', 'consumable'),
      containers: collectDraftLines('tool-containers', 'container'),
      notes: JSON.stringify(notesBlob),
    };
  }

  function collectDraftLines(wrapperId, kind){
    const out = [];
    document.querySelectorAll(`#${wrapperId} .row`).forEach(function(row){
      const name = row.querySelector('.tool-typeahead')?.value?.trim();
      const gi = row.querySelector('.tool-gi-id')?.value || '';
      const qtyEl = row.querySelector('.tool-qty');
      const unitEl = row.querySelector('.tool-unit');
      const hasQty = qtyEl && qtyEl.value !== '';
      if (!name && !gi) return;
      if (kind === 'container'){
        out.push({ name: name || undefined, global_item_id: gi ? parseInt(gi) : undefined, quantity: hasQty ? parseFloat(qtyEl.value) : 1 });
      } else {
        out.push({ name: name || undefined, global_item_id: gi ? parseInt(gi) : undefined, quantity: hasQty ? parseFloat(qtyEl.value) : 0, unit: (unitEl?.value || '').trim() || 'gram' });
      }
    });
    return out;
  }

  function buildLineRow(kind){
    const context = SoapTool.config.isAuthenticated ? 'member' : 'public';
    const mode = SoapTool.config.isAuthenticated ? 'recipe' : 'public';
    return buildToolLineRow(kind, { context, mode, unitOptionsHtml: SoapTool.config.unitOptionsHtml });
  }

  function addStubLine(kind, name){
    const row = buildLineRow(kind);
    const input = row.querySelector('.tool-typeahead');
    const qty = row.querySelector('.tool-qty');
    if (input) {
      input.value = name;
    }
    if (qty && kind === 'container') {
      qty.value = 1;
    }
    if (kind === 'container') {
      document.getElementById('tool-containers').appendChild(row);
    } else if (kind === 'consumable') {
      document.getElementById('tool-consumables').appendChild(row);
    } else {
      document.getElementById('tool-ingredients').appendChild(row);
    }
  }

  SoapTool.runner = {
    getLyeSelection,
    applyLyeSelection,
    setWaterMethod,
    calculateAll,
    buildSoapRecipePayload,
    buildLineRow,
    addStubLine,
    maybeShowSignupModal,
  };
})(window);
