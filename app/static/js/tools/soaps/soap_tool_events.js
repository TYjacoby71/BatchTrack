(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { LACTATE_CATEGORY_SET, SUGAR_CATEGORY_SET, SALT_CATEGORY_SET, CITRIC_CATEGORY_SET } = SoapTool.constants;
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { formatWeight, formatPercent, toGrams, fromGrams } = SoapTool.units;
  const state = SoapTool.state;
  const PRINT_CONFIRM_MIN_FILL_PCT = 90;
  const PRINT_CONFIRM_MAX_FILL_PCT = 120;
  const PRINT_CONFIRM_STRONG_LOW_FILL_PCT = 80;
  const PRINT_CONFIRM_STRONG_HIGH_FILL_PCT = 130;
  const PRINT_NORMALIZE_MIN_PCT = 50;
  const PRINT_NORMALIZE_MAX_PCT = 200;

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

  function buildAssumptionNotes(calc){
    const notes = [];
    const extraLye = toNumber(calc.additives?.citricLyeG);
    const citricG = toNumber(calc.additives?.citricG);
    const lyeType = String(calc.lyeType || 'NaOH').toUpperCase();
    if (extraLye > 0 && citricG > 0) {
      if (lyeType === 'KOH') {
        notes.push('Citric-acid lye adjustment used 0.71 x citric acid because KOH was selected.');
      } else {
        notes.push('Citric-acid lye adjustment used 0.624 x citric acid because NaOH was selected.');
      }
      notes.push(`${formatWeight(extraLye)} lye added extra to accommodate the extra citrus.`);
    }
    if (calc.usedSapFallback) {
      notes.push('Average SAP fallback was used for oils missing SAP values.');
    }
    if (String(calc.lyeSelected || '').toUpperCase() === 'KOH90') {
      notes.push('KOH90 selection assumes 90% lye purity.');
    }
    const oils = Array.isArray(calc.oils) ? calc.oils : [];
    const hasDecimalSap = oils.some(oil => {
      const sap = toNumber(oil?.sapKoh);
      return sap > 0 && sap <= 1;
    });
    if (hasDecimalSap) {
      notes.push('SAP values at or below 1.0 were treated as decimal SAP and converted to mg KOH/g.');
    }
    return notes;
  }

  function buildFormulaCsv(calc){
    if (Array.isArray(calc?.export?.csv_rows) && calc.export.csv_rows.length) {
      return calc.export.csv_rows;
    }
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
    const extraLye = toNumber(calc.additives?.citricLyeG);
    const hasBaseLye = calc.lyeAdjustedBase !== null && calc.lyeAdjustedBase !== undefined && calc.lyeAdjustedBase !== '';
    const totalLye = hasBaseLye
      ? (toNumber(calc.lyeAdjustedBase) + extraLye)
      : toNumber(calc.lyeAdjusted);
    if (totalLye > 0) {
      let lyeLabel = calc.lyeType === 'KOH' ? 'Potassium Hydroxide (KOH)' : 'Sodium Hydroxide (NaOH)';
      if (extraLye > 0) {
        lyeLabel += '*';
      }
      rows.push(['Lye', lyeLabel, round(totalLye, 2), 'gram', '']);
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
    buildAssumptionNotes(calc).forEach(note => {
      rows.push(['Notes', `* ${note}`, '', '', '']);
    });
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

  function getMoldFillSummary(calc){
    const moldSettings = SoapTool.mold?.getMoldSettings ? SoapTool.mold.getMoldSettings() : null;
    const moldCapacityG = toNumber(moldSettings?.effectiveCapacity);
    const batchYieldG = toNumber(calc?.batchYield);
    if (moldCapacityG <= 0 || batchYieldG <= 0) {
      return null;
    }
    const fillPct = (batchYieldG / moldCapacityG) * 100;
    return {
      moldCapacityG,
      batchYieldG,
      fillPct,
      differenceG: batchYieldG - moldCapacityG,
    };
  }

  function shouldShowPrintFillConfirmation(fillSummary){
    if (!fillSummary) return false;
    return fillSummary.fillPct < PRINT_CONFIRM_MIN_FILL_PCT || fillSummary.fillPct > PRINT_CONFIRM_MAX_FILL_PCT;
  }

  function getPrintFillGuidance(fillPct){
    if (fillPct < PRINT_CONFIRM_MIN_FILL_PCT) {
      const isStrong = fillPct < PRINT_CONFIRM_STRONG_LOW_FILL_PCT;
      return {
        toneClass: isStrong ? 'text-danger' : 'text-warning',
        messageClass: isStrong ? 'alert-danger' : 'alert-warning',
        message: isStrong
          ? 'This recipe is far below mold capacity and may underfill bars.'
          : 'This recipe is below your target range and may leave extra headspace.',
      };
    }
    if (fillPct > PRINT_CONFIRM_MAX_FILL_PCT) {
      const isStrong = fillPct > PRINT_CONFIRM_STRONG_HIGH_FILL_PCT;
      return {
        toneClass: isStrong ? 'text-danger' : 'text-warning',
        messageClass: isStrong ? 'alert-danger' : 'alert-warning',
        message: isStrong
          ? 'This recipe is far above mold capacity and has a high overflow risk.'
          : 'This recipe is above your target range and may overflow this mold.',
      };
    }
    return {
      toneClass: 'text-success',
      messageClass: 'alert-success',
      message: 'This recipe is inside your target fill range.',
    };
  }

  function formatSignedWeight(weightG){
    const safe = toNumber(weightG);
    if (!isFinite(safe) || Math.abs(safe) < 0.01) {
      return `0 ${state.currentUnit || 'g'}`;
    }
    const sign = safe > 0 ? '+' : '-';
    return `${sign}${round(fromGrams(Math.abs(safe)), 2)} ${state.currentUnit || 'g'}`;
  }

  function scaleExportRows(rows, factor){
    const safeFactor = toNumber(factor);
    if (!Array.isArray(rows) || !isFinite(safeFactor) || safeFactor <= 0) {
      return [];
    }
    return rows.map(row => ({
      ...row,
      grams: toNumber(row?.grams) * safeFactor,
    }));
  }

  function buildScaledPrintCalc(calc, scaleFactor, targetBatchYieldG){
    const safeFactor = toNumber(scaleFactor);
    if (!isFinite(safeFactor) || safeFactor <= 0 || !calc || typeof calc !== 'object') {
      return null;
    }
    const scaledAdditives = {
      ...(calc.additives || {}),
    };
    ['lactateG', 'sugarG', 'saltG', 'citricG', 'citricLyeG', 'fragranceG'].forEach(key => {
      scaledAdditives[key] = toNumber(scaledAdditives[key]) * safeFactor;
    });
    const hasBaseLye = calc.lyeAdjustedBase !== null && calc.lyeAdjustedBase !== undefined && calc.lyeAdjustedBase !== '';
    return {
      ...calc,
      totalOils: toNumber(calc.totalOils) * safeFactor,
      oils: (calc.oils || []).map(oil => ({
        ...oil,
        grams: toNumber(oil?.grams) * safeFactor,
      })),
      lyePure: toNumber(calc.lyePure) * safeFactor,
      lyeAdjustedBase: hasBaseLye ? (toNumber(calc.lyeAdjustedBase) * safeFactor) : calc.lyeAdjustedBase,
      lyeAdjusted: toNumber(calc.lyeAdjusted) * safeFactor,
      water: toNumber(calc.water) * safeFactor,
      batchYield: toNumber(targetBatchYieldG) > 0 ? toNumber(targetBatchYieldG) : (toNumber(calc.batchYield) * safeFactor),
      additives: scaledAdditives,
      export: null,
    };
  }

  function buildNormalizedPrintPayload(calc, fillSummary, targetFillPct){
    if (!fillSummary || !calc) return null;
    const desiredPct = clamp(
      toNumber(targetFillPct) > 0 ? toNumber(targetFillPct) : 100,
      PRINT_NORMALIZE_MIN_PCT,
      PRINT_NORMALIZE_MAX_PCT
    );
    const targetBatchYieldG = fillSummary.moldCapacityG * (desiredPct / 100);
    const currentBatchYieldG = toNumber(calc.batchYield);
    if (!isFinite(targetBatchYieldG) || targetBatchYieldG <= 0 || !isFinite(currentBatchYieldG) || currentBatchYieldG <= 0) {
      return null;
    }
    const scaleFactor = targetBatchYieldG / currentBatchYieldG;
    const scaledCalc = buildScaledPrintCalc(calc, scaleFactor, targetBatchYieldG);
    if (!scaledCalc) return null;
    const fragrances = scaleExportRows(collectFragranceExportRows(toNumber(calc.totalOils)), scaleFactor);
    const additives = scaleExportRows(collectAdditiveExportRows(calc.additives), scaleFactor);
    return {
      calc: scaledCalc,
      fragrances,
      additives,
      normalizationNote: `Normalized to ${round(desiredPct, 1)}% mold fill (${formatWeight(targetBatchYieldG)} target batch).`,
    };
  }

  function showPrintFillConfirmationModal(fillSummary){
    return new Promise(resolve => {
      const modalEl = document.getElementById('soapPrintConfirmModal');
      if (!modalEl || !window.bootstrap) {
        resolve({ action: 'print-as-is' });
        return;
      }
      const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
      const batchYieldEl = document.getElementById('soapPrintConfirmBatchYield');
      const moldCapacityEl = document.getElementById('soapPrintConfirmMoldCapacity');
      const fillPctEl = document.getElementById('soapPrintConfirmFillPct');
      const diffEl = document.getElementById('soapPrintConfirmDiff');
      const messageEl = document.getElementById('soapPrintConfirmMessage');
      const normalizePctInput = document.getElementById('soapPrintNormalizePct');
      const printAsIsBtn = document.getElementById('soapPrintAsIsBtn');
      const normalizeBtn = document.getElementById('soapNormalizePrintBtn');

      if (!printAsIsBtn || !normalizeBtn) {
        resolve({ action: 'print-as-is' });
        return;
      }

      const guidance = getPrintFillGuidance(fillSummary.fillPct);
      if (batchYieldEl) batchYieldEl.textContent = formatWeight(fillSummary.batchYieldG);
      if (moldCapacityEl) moldCapacityEl.textContent = formatWeight(fillSummary.moldCapacityG);
      if (diffEl) diffEl.textContent = formatSignedWeight(fillSummary.differenceG);
      if (fillPctEl) {
        fillPctEl.textContent = `${round(fillSummary.fillPct, 1)}%`;
        fillPctEl.classList.remove('text-success', 'text-warning', 'text-danger');
        fillPctEl.classList.add(guidance.toneClass);
      }
      if (messageEl) {
        messageEl.textContent = guidance.message;
        messageEl.classList.remove('alert-success', 'alert-info', 'alert-warning', 'alert-danger');
        messageEl.classList.add(guidance.messageClass);
      }
      if (normalizePctInput) {
        normalizePctInput.value = '100';
      }

      let settled = false;
      const cleanup = () => {
        printAsIsBtn.removeEventListener('click', handleAsIsClick);
        normalizeBtn.removeEventListener('click', handleNormalizeClick);
        if (normalizePctInput) {
          normalizePctInput.removeEventListener('keydown', handleNormalizeEnter);
        }
        modalEl.removeEventListener('hidden.bs.modal', handleModalHidden);
      };
      const settle = (payload) => {
        if (settled) return;
        settled = true;
        cleanup();
        resolve(payload);
      };
      const handleAsIsClick = () => {
        settle({ action: 'print-as-is' });
        modal.hide();
      };
      const handleNormalizeClick = () => {
        const rawTarget = toNumber(normalizePctInput?.value);
        const safeTarget = clamp(rawTarget > 0 ? rawTarget : 100, PRINT_NORMALIZE_MIN_PCT, PRINT_NORMALIZE_MAX_PCT);
        if (normalizePctInput) {
          normalizePctInput.value = round(safeTarget, 2);
        }
        settle({ action: 'normalize', targetPct: safeTarget });
        modal.hide();
      };
      const handleNormalizeEnter = (event) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        handleNormalizeClick();
      };
      const handleModalHidden = () => {
        settle(null);
      };

      printAsIsBtn.addEventListener('click', handleAsIsClick);
      normalizeBtn.addEventListener('click', handleNormalizeClick);
      if (normalizePctInput) {
        normalizePctInput.addEventListener('keydown', handleNormalizeEnter);
      }
      modalEl.addEventListener('hidden.bs.modal', handleModalHidden);
      modal.show();
      if (normalizePctInput) {
        window.setTimeout(() => normalizePctInput.focus(), 120);
      }
    });
  }

  function openPrintWindow(html){
    const win = window.open('', '_blank', 'width=960,height=720');
    if (!win) {
      if (SoapTool.ui?.showSoapAlert) {
        SoapTool.ui.showSoapAlert('warning', 'Pop-up blocked. Allow pop-ups to print the sheet.', { dismissible: true, timeoutMs: 6000 });
      }
      return false;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
    win.focus();
    win.onload = () => {
      win.print();
    };
    return true;
  }

  function buildPrintSheet(calc, options = {}){
    if (typeof calc?.export?.sheet_html === 'string' && calc.export.sheet_html.trim()) {
      return calc.export.sheet_html;
    }
    const totalOils = calc.totalOils || 0;
    const oils = (calc.oils || []).map(oil => ({
      name: oil.name || 'Oil',
      grams: oil.grams || 0,
      pct: totalOils > 0 ? (oil.grams / totalOils) * 100 : 0,
    }));
    const fragrances = Array.isArray(options?.fragrances)
      ? options.fragrances
      : collectFragranceExportRows(totalOils);
    const additives = Array.isArray(options?.additives)
      ? options.additives
      : collectAdditiveExportRows(calc.additives);
    const normalizationNote = typeof options?.normalizationNote === 'string'
      ? options.normalizationNote.trim()
      : '';
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
    const extraLye = toNumber(calc.additives?.citricLyeG);
    const hasBaseLye = calc.lyeAdjustedBase !== null && calc.lyeAdjustedBase !== undefined && calc.lyeAdjustedBase !== '';
    const totalLye = hasBaseLye
      ? (toNumber(calc.lyeAdjustedBase) + extraLye)
      : toNumber(calc.lyeAdjusted);
    const lyeLabel = `${calc.lyeType === 'KOH' ? 'Potassium Hydroxide (KOH)' : 'Sodium Hydroxide (NaOH)'}${extraLye > 0 ? '*' : ''}`;
    const lyeWeightLabel = `${formatWeight(totalLye)}${extraLye > 0 ? '*' : ''}`;
    const assumptionNotes = buildAssumptionNotes(calc);
    const assumptionsHtml = assumptionNotes.map(note => `<div class="footnote">* ${note}</div>`).join('');
    const assumptionsBlockHtml = assumptionNotes.length
      ? `<div class="footnotes"><h2 class="footnotes-heading">Assumptions</h2>${assumptionsHtml}</div>`
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
      .footnotes { margin-top: 10px; }
      .footnotes-heading { font-size: 14px; margin: 12px 0 4px; }
      .footnote { font-size: 11px; color: #555; margin-top: 6px; }
    </style>
  </head>
  <body>
    <h1>Soap Formula Sheet</h1>
    <div class="meta">Generated ${now}</div>
    ${normalizationNote ? `<div class="meta">${normalizationNote}</div>` : ''}
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
        <tr><td>${lyeLabel}</td><td class="text-end">${lyeWeightLabel}</td></tr>
        <tr><td>Distilled Water</td><td class="text-end">${formatWeight(calc.water || 0)}</td></tr>
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
    ${assumptionsBlockHtml}
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
      if (row && SoapTool.state.lastFragranceEdit?.row === row) {
        SoapTool.state.lastFragranceEdit = null;
      }
      if (row) row.remove();
      SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
      SoapTool.stages.updateStageStatuses();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }

  const stageTabContent = document.getElementById('soapStageTabContent');
  const getActiveStageScrollContainer = () => {
    if (!stageTabContent) return null;
    const activePane = stageTabContent.querySelector('.tab-pane.active') || stageTabContent.querySelector('.tab-pane.show.active');
    if (!activePane) return null;
    return activePane.querySelector('.soap-stage-body') || activePane;
  };
  const bindStageWheelGuard = () => {
    if (!stageTabContent) return;
    stageTabContent.addEventListener('wheel', event => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const numberInput = target.closest('input[type="number"]');
      if (!(numberInput instanceof HTMLInputElement)) return;
      const scrollContainer = getActiveStageScrollContainer();
      if (!(scrollContainer instanceof HTMLElement)) return;
      if (scrollContainer.scrollHeight <= scrollContainer.clientHeight + 1) return;
      if (document.activeElement === numberInput && typeof numberInput.blur === 'function') {
        numberInput.blur();
      }
      const atTop = scrollContainer.scrollTop <= 0;
      const atBottom = (
        scrollContainer.scrollTop + scrollContainer.clientHeight
      ) >= (scrollContainer.scrollHeight - 1);
      if ((event.deltaY < 0 && atTop) || (event.deltaY > 0 && atBottom)) {
        return;
      }
      scrollContainer.scrollTop += event.deltaY;
      event.preventDefault();
    }, { passive: false });
  };
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
    bindStageWheelGuard();
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

  const rescaleOilsFromStageOne = () => {
    SoapTool.oils.scaleOilsToTarget(undefined, { force: true });
    SoapTool.oils.updateOilTotals();
    if (SoapTool.mold?.updateWetBatterWarning) {
      SoapTool.mold.updateWetBatterWarning(null);
    }
  };

  const oilTotalTarget = document.getElementById('oilTotalTarget');
  if (oilTotalTarget) {
    oilTotalTarget.addEventListener('input', function(){
      SoapTool.mold.syncMoldPctFromTarget();
      rescaleOilsFromStageOne();
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

  const additivePairs = [
    { pctId: 'additiveLactatePct', weightId: 'additiveLactateWeight' },
    { pctId: 'additiveSugarPct', weightId: 'additiveSugarWeight' },
    { pctId: 'additiveSaltPct', weightId: 'additiveSaltWeight' },
    { pctId: 'additiveCitricPct', weightId: 'additiveCitricWeight' },
  ];
  additivePairs.forEach(({ pctId, weightId }) => {
    const pctInput = document.getElementById(pctId);
    const weightInput = document.getElementById(weightId);
    if (pctInput) {
      pctInput.addEventListener('input', () => {
        const totalOils = SoapTool.oils.getTotalOilsGrams();
        SoapTool.additives.syncAdditivePair({ pctId, weightId, sourceField: 'pct', totalOils });
        SoapTool.additives.updateAdditivesOutput(totalOils);
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    if (weightInput) {
      weightInput.addEventListener('input', () => {
        const totalOils = SoapTool.oils.getTotalOilsGrams();
        SoapTool.additives.syncAdditivePair({ pctId, weightId, sourceField: 'weight', totalOils });
        SoapTool.additives.updateAdditivesOutput(totalOils);
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
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
      rescaleOilsFromStageOne();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldOilPct = document.getElementById('moldOilPct');
  if (moldOilPct) {
    moldOilPct.addEventListener('input', function(){
      SoapTool.mold.syncTargetFromMold();
      rescaleOilsFromStageOne();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldShape = document.getElementById('moldShape');
  if (moldShape) {
    moldShape.addEventListener('change', function(){
      SoapTool.mold.updateMoldShapeUI();
      SoapTool.mold.syncTargetFromMold();
      rescaleOilsFromStageOne();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldCylinderCorrection = document.getElementById('moldCylinderCorrection');
  if (moldCylinderCorrection) {
    moldCylinderCorrection.addEventListener('change', function(){
      SoapTool.mold.syncTargetFromMold();
      rescaleOilsFromStageOne();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldCylinderFactor = document.getElementById('moldCylinderFactor');
  if (moldCylinderFactor) {
    moldCylinderFactor.addEventListener('input', function(){
      SoapTool.mold.syncTargetFromMold();
      rescaleOilsFromStageOne();
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
      const csvText = (typeof calc?.export?.csv_text === 'string' && calc.export.csv_text)
        ? calc.export.csv_text
        : buildCsvString(rows);
      triggerCsvDownload(csvText, 'soap_formula.csv');
    });
  }

  const printSoapSheetBtn = document.getElementById('printSoapSheet');
  if (printSoapSheetBtn) {
    printSoapSheetBtn.addEventListener('click', async function(){
      const calc = await getCalcForExport();
      if (!calc) return;
      const fillSummary = getMoldFillSummary(calc);
      let sheetCalc = calc;
      let sheetOptions = {};
      if (shouldShowPrintFillConfirmation(fillSummary)) {
        const choice = await showPrintFillConfirmationModal(fillSummary);
        if (!choice) return;
        if (choice.action === 'normalize') {
          const normalized = buildNormalizedPrintPayload(calc, fillSummary, choice.targetPct);
          if (normalized?.calc) {
            sheetCalc = normalized.calc;
            sheetOptions = {
              fragrances: normalized.fragrances,
              additives: normalized.additives,
              normalizationNote: normalized.normalizationNote,
            };
          }
        }
      }
      const html = buildPrintSheet(sheetCalc, sheetOptions);
      openPrintWindow(html);
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
