(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};

  function bindStageTabSizing(){
    const stageTabList = document.getElementById('soapStageTabList');
    if (!stageTabList) return;
    const updateStageTabSizing = () => {
      stageTabList.querySelectorAll('.nav-item').forEach(item => item.classList.remove('is-expanded'));
      const active = stageTabList.querySelector('.nav-link.active');
      if (active && active.closest('.nav-item')) {
        active.closest('.nav-item').classList.add('is-expanded');
      }
    };
    stageTabList.addEventListener('shown.bs.tab', () => {
      updateStageTabSizing();
      SoapTool.layout.scheduleStageHeightSync();
    });
    updateStageTabSizing();
  }

  function bindResultsToggle(){
    const resultsToggle = document.getElementById('resultsCardToggle');
    const resultsCard = document.getElementById('resultsCard');
    if (!resultsToggle || !resultsCard) return;
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

  function bindUnitInputs(){
    document.querySelectorAll('input[name="weight_unit"]').forEach(el => {
      el.addEventListener('change', function(){
        SoapTool.units.setUnit(this.value);
        SoapTool.storage.queueStateSave();
      });
    });
  }

  function bindStageOneInputs(){
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
  }

  function bindLyeWaterInputs(){
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
  }

  function bindAdditivesInputs(){
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
  }

  function bindQualityInputs(){
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
  }

  function bindStubsAndRoot(){
    document.querySelectorAll('.stub-btn').forEach(btn => {
      btn.addEventListener('click', function(){
        const kind = this.dataset.stubKind;
        const name = this.dataset.stubName;
        SoapTool.runner.addStubLine(kind, name);
        SoapTool.storage.queueStateSave();
      });
    });

    const soapRoot = document.getElementById('soapToolPage');
    if (!soapRoot) return;
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

  function bindDraftLineButtons(){
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
  }

  function bindCalcButton(){
    const calcLyeBtn = document.getElementById('calcLyeBtn');
    if (!calcLyeBtn) return;
    calcLyeBtn.addEventListener('click', async function(){
      await SoapTool.runner.calculateAll({ consumeQuota: true, showAlerts: true });
      SoapTool.storage.queueStateSave();
    });
  }

  function bind(){
    bindStageTabSizing();
    bindResultsToggle();
    bindUnitInputs();
    bindStageOneInputs();
    bindLyeWaterInputs();
    bindAdditivesInputs();
    bindQualityInputs();
    bindStubsAndRoot();
    bindDraftLineButtons();
    bindCalcButton();
  }

  SoapTool.eventsForms = {
    bind,
  };
})(window);
