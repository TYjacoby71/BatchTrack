(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { LACTATE_CATEGORY_SET, SUGAR_CATEGORY_SET, SALT_CATEGORY_SET, CITRIC_CATEGORY_SET } = SoapTool.constants;
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { formatWeight, fromGrams } = SoapTool.units;
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

  function getPrintPolicy(){
    const fallback = {
      confirmMinPct: 90,
      confirmMaxPct: 120,
      strongLowPct: 80,
      strongHighPct: 130,
      normalizeMinPct: 50,
      normalizeMaxPct: 200,
      guidance: {
        strong_low: {
          toneClass: 'text-danger',
          messageClass: 'alert-danger',
          message: 'This recipe is far below mold capacity and may underfill bars.',
        },
        low: {
          toneClass: 'text-warning',
          messageClass: 'alert-warning',
          message: 'This recipe is below your target range and may leave extra headspace.',
        },
        high: {
          toneClass: 'text-warning',
          messageClass: 'alert-warning',
          message: 'This recipe is above your target range and may overflow this mold.',
        },
        strong_high: {
          toneClass: 'text-danger',
          messageClass: 'alert-danger',
          message: 'This recipe is far above mold capacity and has a high overflow risk.',
        },
        ok: {
          toneClass: 'text-success',
          messageClass: 'alert-success',
          message: 'This recipe is inside your target fill range.',
        },
      },
    };
    const configured = SoapTool.config?.printPolicy;
    if (!configured || typeof configured !== 'object') return fallback;
    return {
      ...fallback,
      ...configured,
      guidance: {
        ...fallback.guidance,
        ...(configured.guidance || {}),
      },
    };
  }

  function getExportCsvText(calc){
    const csvText = calc?.export?.csv_text;
    return (typeof csvText === 'string' && csvText.trim()) ? csvText : '';
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
    const policy = getPrintPolicy();
    return fillSummary.fillPct < policy.confirmMinPct || fillSummary.fillPct > policy.confirmMaxPct;
  }

  function getPrintFillGuidance(fillPct){
    const policy = getPrintPolicy();
    const guidance = policy.guidance || {};
    if (fillPct < policy.confirmMinPct) {
      return (fillPct < policy.strongLowPct ? guidance.strong_low : guidance.low) || guidance.low || guidance.ok;
    }
    if (fillPct > policy.confirmMaxPct) {
      return (fillPct > policy.strongHighPct ? guidance.strong_high : guidance.high) || guidance.high || guidance.ok;
    }
    return guidance.ok || {
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

  async function requestNormalizedPrintSheet(calc, fillSummary, targetFillPct){
    if (!calc || !fillSummary) return null;
    if (!SoapTool.runnerService?.requestNormalizedPrintSheet) return null;
    return SoapTool.runnerService.requestNormalizedPrintSheet({
      calc,
      moldCapacityG: fillSummary.moldCapacityG,
      targetFillPct,
      unitDisplay: state.currentUnit || 'g',
    });
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
      const policy = getPrintPolicy();

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
        normalizePctInput.min = String(policy.normalizeMinPct);
        normalizePctInput.max = String(policy.normalizeMaxPct);
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
        const safeTarget = clamp(rawTarget > 0 ? rawTarget : 100, policy.normalizeMinPct, policy.normalizeMaxPct);
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
      const csvText = getExportCsvText(calc);
      if (!csvText) {
        if (SoapTool.ui?.showSoapAlert) {
          SoapTool.ui.showSoapAlert('warning', 'No CSV export is available yet. Run a fresh calculation and try again.', { dismissible: true, timeoutMs: 6000 });
        }
        return;
      }
      triggerCsvDownload(csvText, 'soap_formula.csv');
    });
  }

  const printSoapSheetBtn = document.getElementById('printSoapSheet');
  if (printSoapSheetBtn) {
    printSoapSheetBtn.addEventListener('click', async function(){
      const calc = await getCalcForExport();
      if (!calc) return;
      let html = (typeof calc?.export?.sheet_html === 'string' && calc.export.sheet_html.trim())
        ? calc.export.sheet_html
        : '';
      const fillSummary = getMoldFillSummary(calc);
      if (shouldShowPrintFillConfirmation(fillSummary)) {
        const choice = await showPrintFillConfirmationModal(fillSummary);
        if (!choice) return;
        if (choice.action === 'normalize') {
          const normalized = await requestNormalizedPrintSheet(calc, fillSummary, choice.targetPct);
          if (normalized?.sheet_html) {
            html = normalized.sheet_html;
          } else if (SoapTool.ui?.showSoapAlert) {
            SoapTool.ui.showSoapAlert('warning', 'Unable to normalize print output right now. Printing the current sheet instead.', { dismissible: true, timeoutMs: 6000 });
          }
        }
      }
      if (!html) {
        if (SoapTool.ui?.showSoapAlert) {
          SoapTool.ui.showSoapAlert('warning', 'No print sheet is available yet. Run a fresh calculation and try again.', { dismissible: true, timeoutMs: 6000 });
        }
        return;
      }
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
