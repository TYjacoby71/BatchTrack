(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { formatWeight } = SoapTool.units;
  const state = SoapTool.state;
  const PRINT_CONFIRM_MIN_FILL_PCT = 90;
  const PRINT_CONFIRM_MAX_FILL_PCT = 120;
  const PRINT_CONFIRM_STRONG_LOW_FILL_PCT = 80;
  const PRINT_CONFIRM_STRONG_HIGH_FILL_PCT = 130;
  const PRINT_NORMALIZE_MIN_PCT = 50;
  const PRINT_NORMALIZE_MAX_PCT = 200;

  function hasExportPayload(calc){
    return (
      calc
      && typeof calc === 'object'
      && calc.export
      && typeof calc.export.csv_text === 'string'
      && calc.export.csv_text.trim()
      && typeof calc.export.sheet_html === 'string'
      && calc.export.sheet_html.trim()
    );
  }

  function isCalcStale(calc){
    const calcTotalOils = toNumber(calc?.totalOils);
    const currentTotalOils = SoapTool.oils?.getTotalOilsGrams ? SoapTool.oils.getTotalOilsGrams() : 0;
    if (calcTotalOils <= 0 || currentTotalOils <= 0) {
      return false;
    }
    return Math.abs(calcTotalOils - currentTotalOils) > 0.01;
  }

  async function getCalcForExport(){
    let calc = state.lastCalc;
    if (!calc || isCalcStale(calc) || !hasExportPayload(calc)) {
      calc = await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
    }
    if (!calc) {
      if (SoapTool.ui?.showSoapAlert) {
        SoapTool.ui.showSoapAlert('warning', 'Run a calculation before exporting or printing.', { dismissible: true, timeoutMs: 6000 });
      }
      return null;
    }
    if (!hasExportPayload(calc)) {
      if (SoapTool.ui?.showSoapAlert) {
        SoapTool.ui.showSoapAlert('danger', 'Export payload is missing. Please run the calculation again.', { dismissible: true, timeoutMs: 6000 });
      }
      return null;
    }
    return calc;
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

  function openPrintWindow(html){
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
    win.onload = () => win.print();
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
      return formatWeight(0);
    }
    return safe > 0 ? `+${formatWeight(safe)}` : `-${formatWeight(Math.abs(safe))}`;
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
      if (fillPctEl) {
        fillPctEl.textContent = `${round(fillSummary.fillPct, 1)}%`;
        fillPctEl.classList.remove('text-success', 'text-warning', 'text-danger');
        fillPctEl.classList.add(guidance.toneClass);
      }
      if (diffEl) diffEl.textContent = formatSignedWeight(fillSummary.differenceG);
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

  function buildScaledOilsForNormalize(calc, scaleFactor){
    const oils = Array.isArray(calc?.oils) ? calc.oils : [];
    return oils.map(oil => ({
      name: oil?.name || null,
      grams: toNumber(oil?.grams) * scaleFactor,
      sapKoh: toNumber(oil?.sapKoh ?? oil?.sap_koh),
      iodine: toNumber(oil?.iodine),
      fattyProfile: oil?.fattyProfile || oil?.fatty_profile || null,
      global_item_id: oil?.global_item_id || oil?.globalItemId || null,
      default_unit: oil?.default_unit || oil?.defaultUnit || null,
      ingredient_category_name: oil?.ingredient_category_name || oil?.ingredientCategoryName || null,
    })).filter(oil => oil.grams > 0);
  }

  function buildScaledFragranceRows(calc, scaleFactor){
    const fromCalc = Array.isArray(calc?.additives?.fragranceRows) ? calc.additives.fragranceRows : null;
    const sourceRows = fromCalc || SoapTool.fragrances.collectFragranceRows(toNumber(calc?.totalOils) || 0);
    return sourceRows.map(row => ({
      name: row?.name || 'Fragrance/Essential Oils',
      grams: toNumber(row?.grams) * scaleFactor,
      pct: toNumber(row?.pct),
      global_item_id: row?.global_item_id || row?.globalItemId || null,
      default_unit: row?.default_unit || row?.defaultUnit || null,
      ingredient_category_name: row?.ingredient_category_name || row?.categoryName || row?.ingredientCategoryName || null,
    })).filter(row => row.grams > 0 || row.pct > 0);
  }

  async function buildNormalizedPrintSheet(calc, fillSummary, targetFillPct){
    if (!fillSummary || !calc || !SoapTool.runnerService?.buildServicePayload || !SoapTool.runnerService?.calculateWithSoapService) {
      return null;
    }
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
    if (!isFinite(scaleFactor) || scaleFactor <= 0) {
      return null;
    }
    const scaledOils = buildScaledOilsForNormalize(calc, scaleFactor);
    if (!scaledOils.length) {
      return null;
    }
    const selection = SoapTool.runnerInputs?.getLyeSelection
      ? SoapTool.runnerInputs.getLyeSelection()
      : { selected: calc.lyeSelected || calc.lyeType || 'NaOH' };
    const superfat = SoapTool.runnerInputs?.readSuperfatInput
      ? SoapTool.runnerInputs.readSuperfatInput()
      : toNumber(calc.superfat);
    const sanitized = SoapTool.runnerInputs?.sanitizeLyeInputs
      ? SoapTool.runnerInputs.sanitizeLyeInputs()
      : {
          purity: toNumber(calc.purity),
          waterMethod: calc.waterMethod || 'percent',
          waterPct: toNumber(calc.waterPct),
          lyeConcentration: toNumber(calc.lyeConcentration),
          waterRatio: toNumber(calc.waterRatio),
        };
    const scaledTotalOils = (toNumber(calc.totalOils) || 0) * scaleFactor;
    const payload = SoapTool.runnerService.buildServicePayload({
      oils: scaledOils,
      selection,
      superfat,
      purity: sanitized.purity,
      waterMethod: sanitized.waterMethod,
      waterPct: sanitized.waterPct,
      lyeConcentration: sanitized.lyeConcentration,
      waterRatio: sanitized.waterRatio,
      totalOils: scaledTotalOils,
    });
    payload.fragrances = buildScaledFragranceRows(calc, scaleFactor);
    payload.meta = {
      ...(payload.meta || {}),
      normalize_print_target_fill_pct: desiredPct,
    };
    const serviceResult = await SoapTool.runnerService.calculateWithSoapService(payload);
    const html = typeof serviceResult?.export?.sheet_html === 'string'
      ? serviceResult.export.sheet_html.trim()
      : '';
    if (!html) {
      return null;
    }
    return html;
  }

  function bindSavePayloadButton(){
    const saveSoapToolBtn = document.getElementById('saveSoapTool');
    if (!saveSoapToolBtn) return;
    saveSoapToolBtn.addEventListener('click', async function(){
      try {
        const calc = state.lastCalc || await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
        if (!calc) return;
        const payload = await SoapTool.runner.buildSoapRecipePayload(calc);
        if (!payload) {
          SoapTool.ui.showSoapAlert('danger', 'Unable to prepare the recipe payload. Please try again.', { dismissible: true, persist: true });
          return;
        }
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

  function bindCsvButton(){
    const exportSoapCsvBtn = document.getElementById('exportSoapCsv');
    if (!exportSoapCsvBtn) return;
    exportSoapCsvBtn.addEventListener('click', async function(){
      const calc = await getCalcForExport();
      if (!calc) return;
      triggerCsvDownload(calc.export.csv_text, 'soap_formula.csv');
    });
  }

  function bindPrintButton(){
    const printSoapSheetBtn = document.getElementById('printSoapSheet');
    if (!printSoapSheetBtn) return;
    printSoapSheetBtn.addEventListener('click', async function(){
      const calc = await getCalcForExport();
      if (!calc) return;
      const fillSummary = getMoldFillSummary(calc);
      let html = calc.export.sheet_html;
      if (shouldShowPrintFillConfirmation(fillSummary)) {
        const choice = await showPrintFillConfirmationModal(fillSummary);
        if (!choice) return;
        if (choice.action === 'normalize') {
          const normalizedHtml = await buildNormalizedPrintSheet(calc, fillSummary, choice.targetPct);
          if (!normalizedHtml) {
            SoapTool.ui?.showSoapAlert?.(
              'warning',
              'Unable to normalize this recipe right now. Please try again or print as-is.',
              { dismissible: true, timeoutMs: 6000 }
            );
            return;
          }
          html = normalizedHtml;
        }
      }
      openPrintWindow(html);
    });
  }

  function bind(){
    bindSavePayloadButton();
    bindCsvButton();
    bindPrintButton();
  }

  SoapTool.eventsExports = {
    bind,
  };
})(window);
