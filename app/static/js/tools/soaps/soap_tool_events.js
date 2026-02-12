(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { LACTATE_CATEGORY_SET, SUGAR_CATEGORY_SET, SALT_CATEGORY_SET, CITRIC_CATEGORY_SET } = SoapTool.constants;
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { formatWeight, formatPercent, toGrams } = SoapTool.units;
  const state = SoapTool.state;

  async function getCalcForExport(){
    const calc = state.lastCalc || await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
    if (!calc) {
      if (SoapTool.ui?.showSoapAlert) {
        SoapTool.ui.showSoapAlert('warning', 'Run a calculation before exporting or printing.', { dismissible: true, timeoutMs: 6000 });
      }
      return null;
    }
    return calc;
  }

  function collectFragranceExportRows(totalOils){
    const rows = [];
    document.querySelectorAll('#fragranceRows .fragrance-row').forEach(row => {
      const name = row.querySelector('.fragrance-typeahead')?.value?.trim();
      const gramsInput = row.querySelector('.fragrance-grams')?.value;
      const pctInput = row.querySelector('.fragrance-percent')?.value;
      let grams = toGrams(gramsInput);
      let pct = clamp(toNumber(pctInput), 0);
      if (grams <= 0 && pct > 0 && totalOils > 0) {
        grams = totalOils * (pct / 100);
      }
      if (grams <= 0 && pct <= 0 && !name) return;
      if (!pct && grams > 0 && totalOils > 0) {
        pct = (grams / totalOils) * 100;
      }
      rows.push({
        name: name || 'Fragrance/Essential Oils',
        grams,
        pct,
      });
    });
    return rows;
  }

  function collectAdditiveExportRows(additives){
    const rows = [];
    if (!additives) return rows;
    const lactateName = document.getElementById('additiveLactateName')?.value?.trim() || 'Sodium Lactate';
    const sugarName = document.getElementById('additiveSugarName')?.value?.trim() || 'Sugar';
    const saltName = document.getElementById('additiveSaltName')?.value?.trim() || 'Salt';
    const citricName = document.getElementById('additiveCitricName')?.value?.trim() || 'Citric Acid';
    if (additives.lactateG > 0) {
      rows.push({ name: lactateName, grams: additives.lactateG, pct: additives.lactatePct });
    }
    if (additives.sugarG > 0) {
      rows.push({ name: sugarName, grams: additives.sugarG, pct: additives.sugarPct });
    }
    if (additives.saltG > 0) {
      rows.push({ name: saltName, grams: additives.saltG, pct: additives.saltPct });
    }
    if (additives.citricG > 0) {
      rows.push({ name: citricName, grams: additives.citricG, pct: additives.citricPct });
    }
    return rows;
  }

  function buildFormulaCsv(calc){
    const totalOils = calc.totalOils || 0;
    const rows = [['section', 'name', 'quantity', 'unit', 'percent']];
    rows.push(['Summary', 'Lye Type', calc.lyeType || '', '', '']);
    rows.push(['Summary', 'Superfat', round(calc.superfat || 0, 2), '%', '']);
    rows.push(['Summary', 'Lye Purity', round(calc.purity || 0, 1), '%', '']);
    rows.push(['Summary', 'Water Method', calc.waterMethod || '', '', '']);
    rows.push(['Summary', 'Water %', round(calc.waterPct || 0, 1), '%', '']);
    rows.push(['Summary', 'Lye Concentration', round(calc.lyeConcentration || 0, 1), '%', '']);
    rows.push(['Summary', 'Water Ratio', round(calc.waterRatio || 0, 2), '', '']);
    rows.push(['Summary', 'Total Oils', round(totalOils, 2), 'gram', '']);
    rows.push(['Summary', 'Batch Yield', round(calc.batchYield || 0, 2), 'gram', '']);

    (calc.oils || []).forEach(oil => {
      const pct = totalOils > 0 ? round((oil.grams / totalOils) * 100, 2) : '';
      rows.push(['Oils', oil.name || 'Oil', round(oil.grams || 0, 2), 'gram', pct]);
    });
    if (calc.lyeAdjusted > 0) {
      rows.push(['Lye', calc.lyeType === 'KOH' ? 'Potassium Hydroxide (KOH)' : 'Sodium Hydroxide (NaOH)', round(calc.lyeAdjusted, 2), 'gram', '']);
    }
    if (calc.water > 0) {
      rows.push(['Water', 'Distilled Water', round(calc.water, 2), 'gram', '']);
    }
    const fragrances = collectFragranceExportRows(totalOils);
    fragrances.forEach(row => {
      rows.push(['Fragrance', row.name, round(row.grams || 0, 2), 'gram', round(row.pct || 0, 2)]);
    });
    const additiveRows = collectAdditiveExportRows(calc.additives);
    additiveRows.forEach(row => {
      rows.push(['Additives', row.name, round(row.grams || 0, 2), 'gram', round(row.pct || 0, 2)]);
    });
    if (calc.additives?.citricLyeG > 0) {
      rows.push(['Additives', 'Extra Lye for Citric Acid', round(calc.additives.citricLyeG, 2), 'gram', '']);
    }
    return rows;
  }

  function csvEscape(value){
    if (value === null || value === undefined) return '';
    const str = String(value);
    if (/[",\n]/.test(str)) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  }

  function buildCsvString(rows){
    return rows.map(row => row.map(csvEscape).join(',')).join('\n');
  }

  function triggerCsvDownload(csvText, filename){
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function buildPrintSheet(calc){
    const totalOils = calc.totalOils || 0;
    const oils = (calc.oils || []).map(oil => ({
      name: oil.name || 'Oil',
      grams: oil.grams || 0,
      pct: totalOils > 0 ? (oil.grams / totalOils) * 100 : 0,
    }));
    const fragrances = collectFragranceExportRows(totalOils);
    const additives = collectAdditiveExportRows(calc.additives);
    const now = new Date().toLocaleString();
    const oilRows = oils.length
      ? oils.map(oil => `
          <tr>
            <td>${oil.name}</td>
            <td class="text-end">${formatWeight(oil.grams)}</td>
            <td class="text-end">${formatPercent(oil.pct)}</td>
          </tr>`).join('')
      : '<tr><td colspan="3" class="text-muted">No oils added.</td></tr>';
    const fragranceRows = fragrances.length
      ? fragrances.map(item => `
          <tr>
            <td>${item.name}</td>
            <td class="text-end">${formatWeight(item.grams)}</td>
            <td class="text-end">${formatPercent(item.pct)}</td>
          </tr>`).join('')
      : '<tr><td colspan="3" class="text-muted">No fragrances added.</td></tr>';
    const additiveRows = additives.length
      ? additives.map(item => `
          <tr>
            <td>${item.name}</td>
            <td class="text-end">${formatWeight(item.grams)}</td>
            <td class="text-end">${formatPercent(item.pct)}</td>
          </tr>`).join('')
      : '<tr><td colspan="3" class="text-muted">No additives added.</td></tr>';
    const lyeLabel = calc.lyeType === 'KOH' ? 'Potassium Hydroxide (KOH)' : 'Sodium Hydroxide (NaOH)';
    const extraLyeRow = calc.additives?.citricLyeG > 0
      ? `<tr><td>Extra Lye for Citric Acid</td><td class="text-end">${formatWeight(calc.additives.citricLyeG)}</td></tr>`
      : '';

    return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Soap Formula Sheet</title>
    <style>
      body { font-family: Arial, sans-serif; color: #111; margin: 24px; }
      h1 { font-size: 20px; margin-bottom: 4px; }
      h2 { font-size: 16px; margin-top: 20px; }
      .meta { font-size: 12px; color: #555; margin-bottom: 12px; }
      table { width: 100%; border-collapse: collapse; margin-top: 8px; }
      th, td { border: 1px solid #ddd; padding: 6px 8px; font-size: 12px; }
      th { background: #f3f4f6; text-align: left; }
      .text-end { text-align: right; }
      .summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 16px; font-size: 12px; }
      .summary-item { display: flex; justify-content: space-between; border-bottom: 1px solid #eee; padding: 4px 0; }
      .text-muted { color: #666; }
    </style>
  </head>
  <body>
    <h1>Soap Formula Sheet</h1>
    <div class="meta">Generated ${now}</div>
    <div class="summary-grid">
      <div class="summary-item"><span>Lye type</span><span>${calc.lyeType || '--'}</span></div>
      <div class="summary-item"><span>Superfat</span><span>${formatPercent(calc.superfat || 0)}</span></div>
      <div class="summary-item"><span>Lye purity</span><span>${formatPercent(calc.purity || 0)}</span></div>
      <div class="summary-item"><span>Total oils</span><span>${formatWeight(totalOils)}</span></div>
      <div class="summary-item"><span>Water</span><span>${formatWeight(calc.water || 0)}</span></div>
      <div class="summary-item"><span>Batch yield</span><span>${formatWeight(calc.batchYield || 0)}</span></div>
      <div class="summary-item"><span>Water method</span><span>${calc.waterMethod || '--'}</span></div>
      <div class="summary-item"><span>Lye concentration</span><span>${formatPercent(calc.lyeConcentration || 0)}</span></div>
    </div>

    <h2>Oils</h2>
    <table>
      <thead>
        <tr><th>Oil</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr>
      </thead>
      <tbody>${oilRows}</tbody>
    </table>

    <h2>Lye & Water</h2>
    <table>
      <thead>
        <tr><th>Item</th><th class="text-end">Weight</th></tr>
      </thead>
      <tbody>
        <tr><td>${lyeLabel}</td><td class="text-end">${formatWeight(calc.lyeAdjusted || 0)}</td></tr>
        <tr><td>Distilled Water</td><td class="text-end">${formatWeight(calc.water || 0)}</td></tr>
        ${extraLyeRow}
      </tbody>
    </table>

    <h2>Fragrance & Essential Oils</h2>
    <table>
      <thead>
        <tr><th>Fragrance</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr>
      </thead>
      <tbody>${fragranceRows}</tbody>
    </table>

    <h2>Additives</h2>
    <table>
      <thead>
        <tr><th>Additive</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr>
      </thead>
      <tbody>${additiveRows}</tbody>
    </table>
  </body>
</html>`;
  }

  const oilRows = document.getElementById('oilRows');
  const addOilBtn = document.getElementById('addOil');
  const normalizeOilsBtn = document.getElementById('normalizeOils');
  if (addOilBtn && oilRows) {
    addOilBtn.dataset.bound = 'direct';
    addOilBtn.addEventListener('click', function(){
      oilRows.appendChild(SoapTool.oils.buildOilRow());
      SoapTool.stages.updateStageStatuses();
      SoapTool.storage.queueStateSave();
    });
  }
  if (normalizeOilsBtn) {
    normalizeOilsBtn.dataset.bound = 'direct';
    normalizeOilsBtn.addEventListener('click', function(){
      SoapTool.oils.normalizeOils();
      SoapTool.stages.updateStageStatuses();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }

  if (oilRows) oilRows.addEventListener('input', function(e){
    if (e.target.classList.contains('oil-grams')) {
      state.lastOilEdit = { row: e.target.closest('.oil-row'), field: 'grams' };
    }
    if (e.target.classList.contains('oil-percent')) {
      state.lastOilEdit = { row: e.target.closest('.oil-row'), field: 'percent' };
    }
    if (e.target.classList.contains('oil-grams')
      || e.target.classList.contains('oil-percent')
      || e.target.classList.contains('oil-typeahead')) {
      if (e.target.classList.contains('oil-typeahead')) {
        SoapTool.oils.setSelectedOilProfileFromRow(e.target.closest('.oil-row'));
      }
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    }
  });

  if (oilRows) oilRows.addEventListener('focusin', function(e){
    if (e.target.classList.contains('oil-typeahead')) {
      SoapTool.oils.setSelectedOilProfileFromRow(e.target.closest('.oil-row'));
    }
  });

  if (oilRows) oilRows.addEventListener('focusout', function(e){
    if (e.target.classList.contains('oil-typeahead')) {
      SoapTool.oils.clearSelectedOilProfile();
    }
    if (e.target.classList.contains('oil-grams')) {
      SoapTool.oils.validateOilEntry(e.target.closest('.oil-row'), 'grams');
    }
    if (e.target.classList.contains('oil-percent')) {
      SoapTool.oils.validateOilEntry(e.target.closest('.oil-row'), 'percent');
    }
  });

  if (oilRows) oilRows.addEventListener('keydown', function(e){
    if (e.key !== 'Enter') return;
    if (e.target.classList.contains('oil-grams')) {
      e.preventDefault();
      SoapTool.oils.validateOilEntry(e.target.closest('.oil-row'), 'grams');
    }
    if (e.target.classList.contains('oil-percent')) {
      e.preventDefault();
      SoapTool.oils.validateOilEntry(e.target.closest('.oil-row'), 'percent');
    }
  });

  if (oilRows) oilRows.addEventListener('mouseover', function(e){
    if (!e.target.classList.contains('oil-typeahead')) return;
    const row = e.target.closest('.oil-row');
    if (!row || row === state.lastPreviewRow) return;
    state.lastPreviewRow = row;
    SoapTool.oils.setSelectedOilProfileFromRow(row);
  });

  if (oilRows) oilRows.addEventListener('mouseout', function(e){
    if (e.target.classList.contains('oil-typeahead')) {
      SoapTool.oils.clearSelectedOilProfile();
    }
  });

  if (oilRows) oilRows.addEventListener('click', function(e){
    const profileButton = e.target.closest('.oil-profile-open');
    if (profileButton) {
      const row = profileButton.closest('.oil-row');
      if (row) {
        SoapTool.oils.setSelectedOilProfileFromRow(row);
        const modalEl = document.getElementById('oilProfileModal');
        if (modalEl && window.bootstrap) {
          const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
          modal.show();
        }
      }
      return;
    }
    const removeButton = e.target.closest('.remove-oil');
    if (removeButton) {
      const row = removeButton.closest('.oil-row');
      if (row) {
        state.lastRemovedOil = SoapTool.oils.serializeOilRow(row);
        state.lastRemovedOilIndex = Array.from(row.parentElement.children).indexOf(row);
        SoapTool.ui.showUndoToast('Oil removed.');
      }
      if (row && state.lastOilEdit && state.lastOilEdit.row === row) {
        state.lastOilEdit = null;
        SoapTool.oils.clearSelectedOilProfile();
      }
      if (row) row.remove();
      SoapTool.oils.updateOilTotals();
      SoapTool.stages.updateStageStatuses();
      SoapTool.storage.queueStateSave();
    }
  });

  const fragranceRows = document.getElementById('fragranceRows');
  const addFragranceBtn = document.getElementById('addFragrance');
  if (addFragranceBtn && fragranceRows) {
    addFragranceBtn.dataset.bound = 'direct';
    addFragranceBtn.addEventListener('click', function(){
      fragranceRows.appendChild(SoapTool.fragrances.buildFragranceRow());
      SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
      SoapTool.stages.updateStageStatuses();
      SoapTool.storage.queueStateSave();
    });
  }
  if (fragranceRows) {
    fragranceRows.addEventListener('input', function(e){
      if (e.target.classList.contains('fragrance-grams')) {
        SoapTool.state.lastFragranceEdit = { row: e.target.closest('.fragrance-row'), field: 'grams' };
      }
      if (e.target.classList.contains('fragrance-percent')) {
        SoapTool.state.lastFragranceEdit = { row: e.target.closest('.fragrance-row'), field: 'percent' };
      }
      if (e.target.classList.contains('fragrance-grams')
        || e.target.classList.contains('fragrance-percent')
        || e.target.classList.contains('fragrance-typeahead')) {
        SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      }
    });
    fragranceRows.addEventListener('click', function(e){
      const removeButton = e.target.closest('.remove-fragrance');
      if (!removeButton) return;
      const row = removeButton.closest('.fragrance-row');
      if (row) row.remove();
      SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
      SoapTool.stages.updateStageStatuses();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }

  const stageTabContent = document.getElementById('soapStageTabContent');
  if (stageTabContent) {
    stageTabContent.addEventListener('click', event => {
      const actionBtn = event.target.closest('[data-stage-action]');
      const soapActionBtn = event.target.closest('[data-soap-action]');
      if (!actionBtn && !soapActionBtn) return;
      event.preventDefault();
      event.stopPropagation();
      if (document.activeElement && typeof document.activeElement.blur === 'function') {
        document.activeElement.blur();
      }
      if (soapActionBtn) {
        if (soapActionBtn.dataset.bound === 'direct') return;
        const action = soapActionBtn.dataset.soapAction;
        if (action === 'add-oil' && oilRows) {
          oilRows.appendChild(SoapTool.oils.buildOilRow());
          SoapTool.stages.updateStageStatuses();
          SoapTool.storage.queueStateSave();
        }
        if (action === 'normalize-oils') {
          SoapTool.oils.normalizeOils();
          SoapTool.stages.updateStageStatuses();
          SoapTool.storage.queueStateSave();
          SoapTool.storage.queueAutoCalc();
        }
        if (action === 'add-fragrance' && fragranceRows) {
          fragranceRows.appendChild(SoapTool.fragrances.buildFragranceRow());
          SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
          SoapTool.stages.updateStageStatuses();
          SoapTool.storage.queueStateSave();
        }
        return;
      }
      const action = actionBtn.dataset.stageAction;
      const index = Number(actionBtn.dataset.stageIndex);
      if (Number.isNaN(index)) return;
      if (action === 'prev') SoapTool.stages.openStageByIndex(Math.max(0, index - 1));
      if (action === 'next') SoapTool.stages.openStageByIndex(Math.min(SoapTool.constants.STAGE_CONFIGS.length - 1, index + 1));
      if (action === 'reset') SoapTool.stages.resetStage(index + 1);
    });
  }
  const stageTabList = document.getElementById('soapStageTabList');
  const updateStageTabSizing = () => {
    if (!stageTabList) return;
    stageTabList.querySelectorAll('.nav-item').forEach(item => item.classList.remove('is-expanded'));
    const active = stageTabList.querySelector('.nav-link.active');
    if (active && active.closest('.nav-item')) {
      active.closest('.nav-item').classList.add('is-expanded');
    }
  };
  if (stageTabList) {
    stageTabList.addEventListener('shown.bs.tab', () => {
      updateStageTabSizing();
      SoapTool.layout.scheduleStageHeightSync();
    });
    updateStageTabSizing();
  }

  const resultsToggle = document.getElementById('resultsCardToggle');
  const resultsCard = document.getElementById('resultsCard');
  if (resultsToggle && resultsCard) {
    resultsToggle.addEventListener('click', () => {
      resultsCard.classList.toggle('is-collapsed');
      const isCollapsed = resultsCard.classList.contains('is-collapsed');
      resultsToggle.setAttribute('aria-expanded', (!isCollapsed).toString());
      const label = isCollapsed ? 'Expand formula details' : 'Collapse formula details';
      resultsToggle.setAttribute('aria-label', label);
      resultsToggle.setAttribute('title', label);
      const icon = resultsToggle.querySelector('i');
      if (icon) {
        icon.classList.toggle('fa-chevron-down', isCollapsed);
        icon.classList.toggle('fa-chevron-up', !isCollapsed);
      }
    });
  }

  document.querySelectorAll('input[name="weight_unit"]').forEach(el => {
    el.addEventListener('change', function(){
      SoapTool.units.setUnit(this.value);
      SoapTool.storage.queueStateSave();
    });
  });

  const oilTotalTarget = document.getElementById('oilTotalTarget');
  if (oilTotalTarget) {
    oilTotalTarget.addEventListener('input', function(){
      SoapTool.mold.syncMoldPctFromTarget();
      SoapTool.oils.scaleOilsToTarget();
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }

  const waterMethod = document.getElementById('waterMethod');
  if (waterMethod) {
    waterMethod.addEventListener('change', function(){
      SoapTool.runner.setWaterMethod();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }

  document.querySelectorAll('input[name="lye_type"]').forEach(el => {
    el.addEventListener('change', function(){
      SoapTool.runner.applyLyeSelection();
      SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  });

  ['lyeSuperfat', 'lyePurity', 'waterPct', 'lyeConcentration', 'waterRatio'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    ['input', 'change'].forEach(eventName => {
      el.addEventListener(eventName, () => {
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    });
  });

  ['additiveLactatePct', 'additiveSugarPct', 'additiveSaltPct', 'additiveCitricPct']
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', () => {
        SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    });
  const additiveWeights = [
    { weightId: 'additiveLactateWeight', pctId: 'additiveLactatePct' },
    { weightId: 'additiveSugarWeight', pctId: 'additiveSugarPct' },
    { weightId: 'additiveSaltWeight', pctId: 'additiveSaltPct' },
    { weightId: 'additiveCitricWeight', pctId: 'additiveCitricPct' },
  ];
  additiveWeights.forEach(({ weightId, pctId }) => {
    const weightInput = document.getElementById(weightId);
    const pctInput = document.getElementById(pctId);
    if (!weightInput || !pctInput) return;
    weightInput.addEventListener('input', () => {
      const totalOils = SoapTool.oils.getTotalOilsGrams();
      if (!totalOils) return;
      const grams = SoapTool.units.toGrams(weightInput.value);
      pctInput.value = grams > 0 ? SoapTool.helpers.round((grams / totalOils) * 100, 2) : '';
      SoapTool.additives.updateAdditivesOutput(totalOils);
      SoapTool.stages.updateStageStatuses();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  });

  document.querySelectorAll('.additive-typeahead').forEach(input => {
    input.addEventListener('input', () => {
      SoapTool.storage.queueStateSave();
    });
  });

  const qualityPreset = document.getElementById('qualityPreset');
  if (qualityPreset) {
    qualityPreset.addEventListener('change', function(){
      SoapTool.quality.updateQualityTargets();
      SoapTool.storage.queueStateSave();
    });
  }
  document.querySelectorAll('.quality-focus').forEach(el => {
    el.addEventListener('change', function(){
      SoapTool.quality.updateQualityTargets();
      SoapTool.storage.queueStateSave();
    });
  });
  const applyQualityBtn = document.getElementById('applyQualityTargets');
  if (applyQualityBtn) {
    applyQualityBtn.addEventListener('click', function(){
      SoapTool.quality.applyQualityTargets();
    });
  }
  document.querySelectorAll('.quality-target-marker').forEach(marker => {
    marker.addEventListener('click', () => SoapTool.quality.applyQualityTargets());
    marker.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        SoapTool.quality.applyQualityTargets();
      }
    });
  });

  const moldWaterWeight = document.getElementById('moldWaterWeight');
  if (moldWaterWeight) {
    moldWaterWeight.addEventListener('input', function(){
      SoapTool.mold.syncTargetFromMold();
      SoapTool.oils.scaleOilsToTarget();
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldOilPct = document.getElementById('moldOilPct');
  if (moldOilPct) {
    moldOilPct.addEventListener('input', function(){
      SoapTool.mold.syncTargetFromMold();
      SoapTool.oils.scaleOilsToTarget();
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldShape = document.getElementById('moldShape');
  if (moldShape) {
    moldShape.addEventListener('change', function(){
      SoapTool.mold.updateMoldShapeUI();
      SoapTool.mold.syncTargetFromMold();
      SoapTool.oils.scaleOilsToTarget();
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldCylinderCorrection = document.getElementById('moldCylinderCorrection');
  if (moldCylinderCorrection) {
    moldCylinderCorrection.addEventListener('change', function(){
      SoapTool.mold.syncTargetFromMold();
      SoapTool.oils.scaleOilsToTarget();
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldCylinderFactor = document.getElementById('moldCylinderFactor');
  if (moldCylinderFactor) {
    moldCylinderFactor.addEventListener('input', function(){
      SoapTool.mold.syncTargetFromMold();
      SoapTool.oils.scaleOilsToTarget();
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }

  document.querySelectorAll('.stub-btn').forEach(btn => {
    btn.addEventListener('click', function(){
      const kind = this.dataset.stubKind;
      const name = this.dataset.stubName;
      SoapTool.runner.addStubLine(kind, name);
      SoapTool.storage.queueStateSave();
    });
  });

  const soapRoot = document.getElementById('soapToolPage');
  if (soapRoot) {
    soapRoot.addEventListener('click', function(e){
      if (e.target.classList.contains('tool-remove')) {
        SoapTool.storage.queueStateSave();
      }
    });
    soapRoot.addEventListener('input', function(e){
      if (e.target.matches('input, select, textarea')) {
        SoapTool.storage.queueStateSave();
        SoapTool.ui.validateNumericField(e.target);
        SoapTool.stages.updateStageStatuses();
        SoapTool.ui.flashStage(e.target.closest('.soap-stage-card'));
      }
    });
    soapRoot.addEventListener('change', function(e){
      if (e.target.matches('input, select, textarea')) {
        SoapTool.storage.queueStateSave();
        SoapTool.ui.validateNumericField(e.target);
        SoapTool.stages.updateStageStatuses();
      }
    });
  }

  const addToolIngredient = document.getElementById('addToolIngredient');
  if (addToolIngredient) {
    addToolIngredient.addEventListener('click', function(){
      const wrapper = document.getElementById('tool-ingredients');
      if (wrapper) wrapper.appendChild(SoapTool.runner.buildLineRow('ingredient'));
      SoapTool.storage.queueStateSave();
    });
  }
  const addToolConsumable = document.getElementById('addToolConsumable');
  if (addToolConsumable) {
    addToolConsumable.addEventListener('click', function(){
      const wrapper = document.getElementById('tool-consumables');
      if (wrapper) wrapper.appendChild(SoapTool.runner.buildLineRow('consumable'));
      SoapTool.storage.queueStateSave();
    });
  }
  const addToolContainer = document.getElementById('addToolContainer');
  if (addToolContainer) {
    addToolContainer.addEventListener('click', function(){
      const wrapper = document.getElementById('tool-containers');
      if (wrapper) wrapper.appendChild(SoapTool.runner.buildLineRow('container'));
      SoapTool.storage.queueStateSave();
    });
  }

  const calcLyeBtn = document.getElementById('calcLyeBtn');
  if (calcLyeBtn) {
    calcLyeBtn.addEventListener('click', async function(){
      await SoapTool.runner.calculateAll({ consumeQuota: true, showAlerts: true });
      SoapTool.storage.queueStateSave();
    });
  }

  const saveSoapToolBtn = document.getElementById('saveSoapTool');
  if (saveSoapToolBtn) {
    saveSoapToolBtn.addEventListener('click', async function(){
      try {
        const calc = state.lastCalc || await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
        if (!calc) return;
        const payload = SoapTool.runner.buildSoapRecipePayload(calc);
        state.lastRecipePayload = payload;
        try {
          const storage = SoapTool.helpers.getStorage();
          if (storage) {
            storage.setItem('soap_recipe_payload', JSON.stringify(payload));
          }
        } catch (_) {}
        window.SOAP_RECIPE_DTO = payload;
        SoapTool.ui.showSoapAlert('info', 'Recipe payload is ready. Push is stubbed for now; no data has been sent.', { dismissible: true, timeoutMs: 7000 });
      } catch(_) {
        SoapTool.ui.showSoapAlert('danger', 'Unable to prepare the recipe payload. Please try again.', { dismissible: true, persist: true });
      }
    });
  }

  const exportSoapCsvBtn = document.getElementById('exportSoapCsv');
  if (exportSoapCsvBtn) {
    exportSoapCsvBtn.addEventListener('click', async function(){
      const calc = await getCalcForExport();
      if (!calc) return;
      const rows = buildFormulaCsv(calc);
      const csvText = buildCsvString(rows);
      triggerCsvDownload(csvText, 'soap_formula.csv');
    });
  }

  const printSoapSheetBtn = document.getElementById('printSoapSheet');
  if (printSoapSheetBtn) {
    printSoapSheetBtn.addEventListener('click', async function(){
      const calc = await getCalcForExport();
      if (!calc) return;
      const html = buildPrintSheet(calc);
      const win = window.open('', '_blank', 'width=960,height=720');
      if (!win) {
        if (SoapTool.ui?.showSoapAlert) {
          SoapTool.ui.showSoapAlert('warning', 'Pop-up blocked. Allow pop-ups to print the sheet.', { dismissible: true, timeoutMs: 6000 });
        }
        return;
      }
      win.document.open();
      win.document.write(html);
      win.document.close();
      win.focus();
      win.onload = () => {
        win.print();
      };
    });
  }

  const undoRemoveBtn = document.getElementById('soapUndoRemove');
  if (undoRemoveBtn) {
    undoRemoveBtn.addEventListener('click', () => {
      if (!state.lastRemovedOil) return;
      SoapTool.storage.restoreOilRow(state.lastRemovedOil, state.lastRemovedOilIndex || 0);
      state.lastRemovedOil = null;
      state.lastRemovedOilIndex = null;
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }

  const setupMobileDrawer = () => {
    const drawer = document.getElementById('soapMobileDrawer');
    const drawerContent = document.getElementById('soapMobileDrawerContent');
    const drawerTitle = document.getElementById('soapMobileDrawerTitle');
    const drawerEmpty = document.getElementById('soapDrawerEmpty');
    const closeBtn = document.getElementById('soapDrawerClose');
    const qualityCard = document.getElementById('soapQualityCard');
    const resultsCard = document.getElementById('resultsCard');
    if (!drawer || !drawerContent || !drawerTitle || !qualityCard || !resultsCard) return;

    const qualityHome = qualityCard.parentElement;
    const resultsHome = resultsCard.parentElement;
    const placeholders = new Map();
    let currentTarget = null;

    const isSmallScreen = () => window.matchMedia('(max-width: 767px)').matches;
    const cardForTarget = (target) => (target === 'quality' ? qualityCard : resultsCard);
    const homeForTarget = (target) => (target === 'quality' ? qualityHome : resultsHome);
    const titleForTarget = (target) => (target === 'quality' ? 'Display' : 'Results');

    const ensurePlaceholder = (card) => {
      let placeholder = placeholders.get(card);
      if (!placeholder) {
        placeholder = document.createElement('div');
        placeholder.className = 'soap-card-placeholder';
        placeholders.set(card, placeholder);
      }
      placeholder.style.height = `${card.offsetHeight}px`;
      if (card.parentElement && card.parentElement !== drawerContent && !placeholder.parentElement) {
        card.parentElement.insertBefore(placeholder, card);
      }
    };

    const moveCardToDrawer = (card) => {
      if (!card) return;
      ensurePlaceholder(card);
      drawerContent.appendChild(card);
    };

    const restoreCard = (card, home) => {
      const placeholder = placeholders.get(card);
      if (placeholder && placeholder.parentElement) {
        placeholder.replaceWith(card);
      } else if (home && card.parentElement !== home) {
        home.appendChild(card);
      }
    };

    const updateDrawerEmpty = () => {
      if (!drawerEmpty) return;
      const isResults = currentTarget === 'results';
      const resultsVisible = getComputedStyle(resultsCard).display !== 'none';
      drawerEmpty.classList.toggle('d-none', !isResults || resultsVisible);
    };

    const openDrawer = (target) => {
      if (!isSmallScreen()) return;
      if (currentTarget && currentTarget !== target) {
        restoreCard(cardForTarget(currentTarget), homeForTarget(currentTarget));
      }
      moveCardToDrawer(cardForTarget(target));
      drawerTitle.textContent = titleForTarget(target);
      currentTarget = target;
      drawer.classList.add('is-open');
      updateDrawerEmpty();
    };

    const closeDrawer = () => {
      if (!currentTarget) return;
      restoreCard(cardForTarget(currentTarget), homeForTarget(currentTarget));
      currentTarget = null;
      drawer.classList.remove('is-open');
      updateDrawerEmpty();
    };

    drawer.querySelectorAll('[data-drawer-target]').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.drawerTarget;
        if (!target) return;
        if (drawer.classList.contains('is-open') && currentTarget === target) {
          closeDrawer();
        } else {
          openDrawer(target);
        }
      });
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', closeDrawer);
    }

    window.addEventListener('resize', () => {
      if (!isSmallScreen() && currentTarget) {
        closeDrawer();
      }
    });

    const resultsObserver = new MutationObserver(() => updateDrawerEmpty());
    resultsObserver.observe(resultsCard, { attributes: true, attributeFilter: ['style', 'class'] });
  };

  setupMobileDrawer();
  window.addEventListener('resize', SoapTool.layout.scheduleStageHeightSync);
  window.addEventListener('load', SoapTool.layout.scheduleStageHeightSync);

  SoapTool.additives.attachAdditiveTypeahead('additiveLactateName', 'additiveLactateGi', LACTATE_CATEGORY_SET, 'additiveLactateUnit', 'additiveLactateCategory');
  SoapTool.additives.attachAdditiveTypeahead('additiveSugarName', 'additiveSugarGi', SUGAR_CATEGORY_SET, 'additiveSugarUnit', 'additiveSugarCategory');
  SoapTool.additives.attachAdditiveTypeahead('additiveSaltName', 'additiveSaltGi', SALT_CATEGORY_SET, 'additiveSaltUnit', 'additiveSaltCategory');
  SoapTool.additives.attachAdditiveTypeahead('additiveCitricName', 'additiveCitricGi', CITRIC_CATEGORY_SET, 'additiveCitricUnit', 'additiveCitricCategory');
  SoapTool.ui.applyHelperVisibility();
  SoapTool.quality.initQualityTooltips();
  SoapTool.runner.applyLyeSelection();
  SoapTool.runner.setWaterMethod();
  SoapTool.mold.updateMoldShapeUI();
  SoapTool.quality.setQualityRangeBars();
  SoapTool.units.updateUnitLabels();
  SoapTool.quality.updateQualityTargets();
  SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
  SoapTool.stages.updateStageStatuses();
  SoapTool.storage.restoreState();
  if (oilRows && !oilRows.querySelector('.oil-row')) {
    oilRows.appendChild(SoapTool.oils.buildOilRow());
  }
  if (fragranceRows && !fragranceRows.querySelector('.fragrance-row')) {
    if (SoapTool.fragrances?.buildFragranceRow) {
      fragranceRows.appendChild(SoapTool.fragrances.buildFragranceRow());
    }
  }
  if (SoapTool.fragrances?.updateFragranceTotals) {
    SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
  }
  SoapTool.layout.scheduleStageHeightSync();
})(window);
