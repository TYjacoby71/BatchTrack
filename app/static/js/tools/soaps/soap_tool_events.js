(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { FRAGRANCE_CATEGORY_SET, LACTATE_CATEGORY_SET, SUGAR_CATEGORY_SET, SALT_CATEGORY_SET, CITRIC_CATEGORY_SET } = SoapTool.constants;
  const state = SoapTool.state;

  function updateDownloadPreview(){
    const summary = {
      oils: document.getElementById('downloadSummaryOils'),
      lye: document.getElementById('downloadSummaryLye'),
      water: document.getElementById('downloadSummaryWater'),
      yield: document.getElementById('downloadSummaryYield'),
      superfat: document.getElementById('downloadSummarySuperfat'),
    };
    const list = document.getElementById('soapDownloadInciList');
    const empty = document.getElementById('soapDownloadPreviewEmpty');
    if (!list || !empty) return;
    const calc = state.lastCalc || SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: false });
    if (!calc) {
      empty.classList.remove('d-none');
      list.innerHTML = '';
      Object.values(summary).forEach(el => { if (el) el.textContent = '--'; });
      return;
    }
    empty.classList.add('d-none');
    const payload = SoapTool.runner.buildSoapRecipePayload(calc);
    list.innerHTML = '';
    if (!payload.ingredients.length) {
      const li = document.createElement('li');
      li.textContent = 'Add oils to build an INCI list.';
      list.appendChild(li);
    } else {
      payload.ingredients.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item.name || 'Ingredient';
        list.appendChild(li);
      });
    }
    if (summary.oils) summary.oils.textContent = SoapTool.units.formatWeight(calc.totalOils || 0);
    if (summary.lye) summary.lye.textContent = SoapTool.units.formatWeight(calc.lyeAdjusted || 0);
    if (summary.water) summary.water.textContent = SoapTool.units.formatWeight(calc.water || 0);
    if (summary.yield) summary.yield.textContent = SoapTool.units.formatWeight(calc.batchYield || 0);
    if (summary.superfat) summary.superfat.textContent = SoapTool.units.formatPercent(calc.superfat || 0);
  }

  document.getElementById('addOil').addEventListener('click', function(){
    document.getElementById('oilRows').appendChild(SoapTool.oils.buildOilRow());
    SoapTool.stages.updateStageStatuses();
    SoapTool.storage.queueStateSave();
  });

  document.getElementById('normalizeOils').addEventListener('click', function(){
    SoapTool.oils.normalizeOils();
    SoapTool.stages.updateStageStatuses();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
  });

  document.getElementById('oilRows').addEventListener('input', function(e){
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

  document.getElementById('oilRows').addEventListener('focusin', function(e){
    if (e.target.classList.contains('oil-typeahead')) {
      SoapTool.oils.setSelectedOilProfileFromRow(e.target.closest('.oil-row'));
    }
  });

  document.getElementById('oilRows').addEventListener('focusout', function(e){
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

  document.getElementById('oilRows').addEventListener('keydown', function(e){
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

  document.getElementById('oilRows').addEventListener('mouseover', function(e){
    if (!e.target.classList.contains('oil-typeahead')) return;
    const row = e.target.closest('.oil-row');
    if (!row || row === state.lastPreviewRow) return;
    state.lastPreviewRow = row;
    SoapTool.oils.setSelectedOilProfileFromRow(row);
  });

  document.getElementById('oilRows').addEventListener('mouseout', function(e){
    if (e.target.classList.contains('oil-typeahead')) {
      SoapTool.oils.clearSelectedOilProfile();
    }
  });

  document.getElementById('oilRows').addEventListener('click', function(e){
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
    if (e.target.classList.contains('remove-oil')) {
      const row = e.target.closest('.oil-row');
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

  const stageTabContent = document.getElementById('soapStageTabContent');
  if (stageTabContent) {
    stageTabContent.addEventListener('click', event => {
      const actionBtn = event.target.closest('[data-stage-action]');
      if (!actionBtn) return;
      event.preventDefault();
      event.stopPropagation();
      if (document.activeElement && typeof document.activeElement.blur === 'function') {
        document.activeElement.blur();
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
      resultsToggle.textContent = isCollapsed ? 'Expand' : 'Collapse';
    });
  }

  document.querySelectorAll('input[name="weight_unit"]').forEach(el => {
    el.addEventListener('change', function(){
      SoapTool.units.setUnit(this.value);
      SoapTool.storage.queueStateSave();
    });
  });

  document.getElementById('oilTotalTarget').addEventListener('input', function(){
    SoapTool.oils.scaleOilsToTarget();
    SoapTool.oils.updateOilTotals();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
  });

  document.getElementById('waterMethod').addEventListener('change', function(){
    SoapTool.runner.setWaterMethod();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
  });

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

  ['additiveFragrancePct', 'additiveLactatePct', 'additiveSugarPct', 'additiveSaltPct', 'additiveCitricPct']
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', () => {
        SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
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

  document.getElementById('moldWaterWeight').addEventListener('input', function(){
    SoapTool.mold.updateMoldSuggested();
    SoapTool.oils.scaleOilsToTarget();
    SoapTool.oils.updateOilTotals();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
  });
  document.getElementById('moldOilPct').addEventListener('input', function(){
    SoapTool.mold.updateMoldSuggested();
    SoapTool.oils.scaleOilsToTarget();
    SoapTool.oils.updateOilTotals();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
  });
  const moldShape = document.getElementById('moldShape');
  if (moldShape) {
    moldShape.addEventListener('change', function(){
      SoapTool.mold.updateMoldShapeUI();
      SoapTool.oils.scaleOilsToTarget();
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldCylinderCorrection = document.getElementById('moldCylinderCorrection');
  if (moldCylinderCorrection) {
    moldCylinderCorrection.addEventListener('change', function(){
      SoapTool.mold.updateMoldSuggested();
      SoapTool.oils.scaleOilsToTarget();
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }
  const moldCylinderFactor = document.getElementById('moldCylinderFactor');
  if (moldCylinderFactor) {
    moldCylinderFactor.addEventListener('input', function(){
      SoapTool.mold.updateMoldSuggested();
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

  document.getElementById('calcLyeBtn').addEventListener('click', function(){
    SoapTool.runner.calculateAll({ consumeQuota: true, showAlerts: true });
    SoapTool.storage.queueStateSave();
  });

  document.getElementById('saveSoapTool').addEventListener('click', async function(){
    try {
      const calc = state.lastCalc || SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
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

  const initialOilRow = document.querySelector('#oilRows .oil-row');
  if (initialOilRow) {
    SoapTool.oils.attachOilTypeahead(initialOilRow);
  }
  SoapTool.additives.attachAdditiveTypeahead('additiveFragranceName', 'additiveFragranceGi', FRAGRANCE_CATEGORY_SET);
  SoapTool.additives.attachAdditiveTypeahead('additiveLactateName', 'additiveLactateGi', LACTATE_CATEGORY_SET);
  SoapTool.additives.attachAdditiveTypeahead('additiveSugarName', 'additiveSugarGi', SUGAR_CATEGORY_SET);
  SoapTool.additives.attachAdditiveTypeahead('additiveSaltName', 'additiveSaltGi', SALT_CATEGORY_SET);
  SoapTool.additives.attachAdditiveTypeahead('additiveCitricName', 'additiveCitricGi', CITRIC_CATEGORY_SET);
  SoapTool.ui.applyHelperVisibility();
  SoapTool.stages.injectStageActions();
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
  SoapTool.layout.scheduleStageHeightSync();
  const downloadModal = document.getElementById('soapDownloadPreviewModal');
  if (downloadModal) {
    downloadModal.addEventListener('show.bs.modal', updateDownloadPreview);
  }
})(window);
