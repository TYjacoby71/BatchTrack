(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { toNumber } = SoapTool.helpers;
  const { STAGE_CONFIGS } = SoapTool.constants;

  function injectStageActions(){
    const bodies = Array.from(document.querySelectorAll('#soapStageTabContent .soap-stage-body'));
    bodies.forEach((body, index) => {
      if (!body) return;
      const existing = body.querySelector('.soap-stage-actions');
      if (existing) return;
      const stageIndex = Number(body.dataset.stageIndex ?? index);
      const target = body.querySelector('[data-stage-actions]');
      const actions = target || document.createElement('div');
      actions.classList.add('soap-stage-actions');
      actions.innerHTML = `
        <button class="btn btn-sm btn-outline-secondary" type="button" data-stage-action="prev" data-stage-index="${stageIndex}">
          <i class="fas fa-arrow-left me-1"></i>Back
        </button>
        <button class="btn btn-sm btn-outline-danger" type="button" data-stage-action="reset" data-stage-index="${stageIndex}">
          Reset stage
        </button>
        <button class="btn btn-sm btn-outline-secondary" type="button" data-stage-action="next" data-stage-index="${stageIndex}">
          Next<i class="fas fa-arrow-right ms-1"></i>
        </button>
      `;
      if (!target) {
        body.appendChild(actions);
      }
    });
  }

  function openStageByIndex(index){
    const stage = STAGE_CONFIGS[index];
    if (!stage) return;
    const tabButton = document.getElementById(stage.tabId);
    if (!tabButton) return;
    if (window.bootstrap?.Tab) {
      bootstrap.Tab.getOrCreateInstance(tabButton).show();
    } else {
      document.querySelectorAll('#soapStageTabList .nav-link').forEach(btn => {
        btn.classList.remove('active');
        btn.setAttribute('aria-selected', 'false');
      });
      document.querySelectorAll('#soapStageTabContent .tab-pane').forEach(pane => {
        pane.classList.remove('show', 'active');
      });
      tabButton.classList.add('active');
      tabButton.setAttribute('aria-selected', 'true');
      const pane = document.getElementById(stage.paneId);
      if (pane) pane.classList.add('show', 'active');
    }
    SoapTool.layout.scheduleStageHeightSync();
    tabButton.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  }

  function resetStage(stageId){
    if (stageId === 1) {
      const lyeNaoh = document.getElementById('lyeTypeNaoh');
      if (lyeNaoh) lyeNaoh.checked = true;
      const unitGrams = document.getElementById('unitGrams');
      if (unitGrams) unitGrams.checked = true;
      const waterMethod = document.getElementById('waterMethod');
      if (waterMethod) waterMethod.value = 'percent';
      const superfat = document.getElementById('lyeSuperfat');
      if (superfat) superfat.value = '5';
      const purity = document.getElementById('lyePurity');
      if (purity) purity.value = '100';
      const waterPct = document.getElementById('waterPct');
      if (waterPct) waterPct.value = '33';
      const lyeConcentration = document.getElementById('lyeConcentration');
      if (lyeConcentration) lyeConcentration.value = '33';
      const waterRatio = document.getElementById('waterRatio');
      if (waterRatio) waterRatio.value = '2';
      SoapTool.units.setUnit('g', { skipAutoCalc: true });
      SoapTool.runner.applyLyeSelection();
      SoapTool.runner.setWaterMethod();
      SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
    }
    if (stageId === 2) {
      document.getElementById('moldWaterWeight').value = '';
      document.getElementById('moldOilPct').value = '65';
      document.getElementById('oilTotalTarget').value = '';
      document.getElementById('moldShape').value = 'loaf';
      const correction = document.getElementById('moldCylinderCorrection');
      if (correction) correction.checked = false;
      document.getElementById('moldCylinderFactor').value = '0.85';
      SoapTool.mold.updateMoldSuggested();
    }
    if (stageId === 3) {
      const oilRows = document.getElementById('oilRows');
      if (oilRows) {
        oilRows.innerHTML = '';
        oilRows.appendChild(SoapTool.oils.buildOilRow());
      }
      SoapTool.oils.updateOilTotals();
    }
    if (stageId === 4) {
      const purity = document.getElementById('lyePurity');
      if (purity) purity.value = '100';
      const waterMethod = document.getElementById('waterMethod');
      if (waterMethod) waterMethod.value = 'percent';
      const waterPct = document.getElementById('waterPct');
      if (waterPct) waterPct.value = '33';
      const lyeConcentration = document.getElementById('lyeConcentration');
      if (lyeConcentration) lyeConcentration.value = '33';
      const waterRatio = document.getElementById('waterRatio');
      if (waterRatio) waterRatio.value = '2';
      SoapTool.runner.setWaterMethod();
    }
    if (stageId === 5) {
      document.getElementById('additiveLactatePct').value = '1';
      document.getElementById('additiveSugarPct').value = '1';
      document.getElementById('additiveSaltPct').value = '0.5';
      document.getElementById('additiveCitricPct').value = '0';
      ['additiveLactateName', 'additiveSugarName', 'additiveSaltName', 'additiveCitricName']
        .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
      ['additiveLactateGi', 'additiveSugarGi', 'additiveSaltGi', 'additiveCitricGi']
        .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
      SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
    }
    if (stageId === 6) {
      const fragranceRows = document.getElementById('fragranceRows');
      if (fragranceRows) {
        fragranceRows.innerHTML = '';
        if (SoapTool.fragrances?.buildFragranceRow) {
          fragranceRows.appendChild(SoapTool.fragrances.buildFragranceRow());
        }
      }
      const totalPct = document.getElementById('fragrancePercentTotal');
      if (totalPct) totalPct.textContent = '0';
      const totalWeight = document.getElementById('fragranceTotalComputed');
      if (totalWeight) totalWeight.textContent = '--';
    }
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
    updateStageStatuses();
  }

  function getStageCompletion(stageId){
    if (stageId === 1) {
      const superfat = toNumber(document.getElementById('lyeSuperfat').value);
      const method = document.getElementById('waterMethod')?.value;
      const hasLye = !!document.querySelector('input[name="lye_type"]:checked');
      const hasUnit = !!document.querySelector('input[name="weight_unit"]:checked');
      const complete = hasLye && hasUnit && !!method && superfat >= 0;
      return { state: complete ? 'complete' : 'incomplete', label: complete ? 'Configured' : 'Set basics' };
    }
    if (stageId === 2) {
      const moldWeight = toNumber(document.getElementById('moldWaterWeight').value);
      const oilTarget = toNumber(document.getElementById('oilTotalTarget').value);
      const moldPct = toNumber(document.getElementById('moldOilPct').value);
      const complete = (moldWeight > 0 || oilTarget > 0) && moldPct > 0;
      return { state: complete ? 'complete' : 'incomplete', label: complete ? 'Complete' : 'Needs target' };
    }
    if (stageId === 3) {
      const rows = Array.from(document.querySelectorAll('#oilRows .oil-row'));
      const hasOil = rows.some(row => {
        const name = row.querySelector('.oil-typeahead')?.value?.trim();
        const grams = toNumber(row.querySelector('.oil-grams')?.value);
        const pct = toNumber(row.querySelector('.oil-percent')?.value);
        return name && (grams > 0 || pct > 0);
      });
      return { state: hasOil ? 'complete' : 'incomplete', label: hasOil ? 'Oils added' : 'Add oils' };
    }
    if (stageId === 4) {
      const purity = toNumber(document.getElementById('lyePurity').value);
      const method = document.getElementById('waterMethod')?.value || 'percent';
      const waterValue = method === 'percent'
        ? toNumber(document.getElementById('waterPct').value)
        : method === 'concentration'
          ? toNumber(document.getElementById('lyeConcentration').value)
          : toNumber(document.getElementById('waterRatio').value);
      const complete = purity > 0 && waterValue > 0;
      return { state: complete ? 'complete' : 'incomplete', label: complete ? 'Configured' : 'Set water' };
    }
    if (stageId === 5) {
      const hasAdditive = ['additiveLactatePct', 'additiveSugarPct', 'additiveSaltPct', 'additiveCitricPct']
        .some(id => toNumber(document.getElementById(id).value) > 0);
      return { state: 'optional', label: hasAdditive ? 'Added' : 'Optional' };
    }
    if (stageId === 6) {
      const rows = Array.from(document.querySelectorAll('#fragranceRows .fragrance-row'));
      const hasFragrance = rows.some(row => {
        const name = row.querySelector('.fragrance-typeahead')?.value?.trim();
        const grams = toNumber(row.querySelector('.fragrance-grams')?.value);
        const pct = toNumber(row.querySelector('.fragrance-percent')?.value);
        return name || grams > 0 || pct > 0;
      });
      return { state: 'optional', label: hasFragrance ? 'Added' : 'Optional' };
    }
    return { state: 'incomplete', label: 'Incomplete' };
  }

  function updateStageStatuses(){
    const tabList = document.getElementById('soapStageTabList');
    if (tabList) {
      tabList.querySelectorAll('.soap-stage-status').forEach(el => el.remove());
    }
    const progress = document.getElementById('soapStageProgress');
    if (progress) progress.textContent = '';
  }

  SoapTool.stages = {
    injectStageActions,
    openStageByIndex,
    resetStage,
    updateStageStatuses,
  };
})(window);
