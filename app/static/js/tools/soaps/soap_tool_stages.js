(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { toNumber } = SoapTool.helpers;
  const { STAGE_CONFIGS } = SoapTool.constants;

  function injectStageActions(){
    const bodies = Array.from(document.querySelectorAll('#soapStageTabContent .soap-stage-body'));
    bodies.forEach((body, index) => {
      if (!body || body.querySelector('.soap-stage-actions')) return;
      const stageIndex = Number(body.dataset.stageIndex ?? index);
      const actions = document.createElement('div');
      actions.className = 'soap-stage-actions';
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
      body.appendChild(actions);
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
      document.getElementById('moldWaterWeight').value = '';
      document.getElementById('moldOilPct').value = '65';
      document.getElementById('oilTotalTarget').value = '';
      document.getElementById('moldShape').value = 'loaf';
      const correction = document.getElementById('moldCylinderCorrection');
      if (correction) correction.checked = false;
      document.getElementById('moldCylinderFactor').value = '0.85';
      SoapTool.mold.updateMoldSuggested();
    }
    if (stageId === 2) {
      const oilRows = document.getElementById('oilRows');
      if (oilRows) {
        oilRows.innerHTML = '';
        oilRows.appendChild(SoapTool.oils.buildOilRow());
      }
      SoapTool.oils.updateOilTotals();
    }
    if (stageId === 3) {
      document.getElementById('lyePurity').value = '100';
      document.getElementById('waterPct').value = '33';
      document.getElementById('lyeConcentration').value = '33';
      document.getElementById('waterRatio').value = '2';
    }
    if (stageId === 4) {
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
    if (stageId === 5) {
      document.getElementById('additiveFragrancePct').value = '3';
      const name = document.getElementById('additiveFragranceName');
      if (name) name.value = '';
      const gi = document.getElementById('additiveFragranceGi');
      if (gi) gi.value = '';
    }
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
    updateStageStatuses();
  }

  function getStageCompletion(stageId){
    if (stageId === 1) {
      const moldWeight = toNumber(document.getElementById('moldWaterWeight').value);
      const oilTarget = toNumber(document.getElementById('oilTotalTarget').value);
      const moldPct = toNumber(document.getElementById('moldOilPct').value);
      const complete = (moldWeight > 0 || oilTarget > 0) && moldPct > 0;
      return { state: complete ? 'complete' : 'incomplete', label: complete ? 'Complete' : 'Needs target' };
    }
    if (stageId === 2) {
      const rows = Array.from(document.querySelectorAll('#oilRows .oil-row'));
      const hasOil = rows.some(row => {
        const name = row.querySelector('.oil-typeahead')?.value?.trim();
        const grams = toNumber(row.querySelector('.oil-grams')?.value);
        const pct = toNumber(row.querySelector('.oil-percent')?.value);
        return name && (grams > 0 || pct > 0);
      });
      return { state: hasOil ? 'complete' : 'incomplete', label: hasOil ? 'Oils added' : 'Add oils' };
    }
    if (stageId === 3) {
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
    if (stageId === 4) {
      const hasAdditive = ['additiveLactatePct', 'additiveSugarPct', 'additiveSaltPct', 'additiveCitricPct']
        .some(id => toNumber(document.getElementById(id).value) > 0);
      return { state: 'optional', label: hasAdditive ? 'Added' : 'Optional' };
    }
    if (stageId === 5) {
      const pct = toNumber(document.getElementById('additiveFragrancePct').value);
      const name = document.getElementById('additiveFragranceName')?.value?.trim();
      const hasFragrance = pct > 0 || !!name;
      return { state: 'optional', label: hasFragrance ? 'Added' : 'Optional' };
    }
    return { state: 'incomplete', label: 'Incomplete' };
  }

  function updateStageStatuses(){
    STAGE_CONFIGS.forEach(stage => {
      const button = document.getElementById(stage.tabId);
      if (!button) return;
      let badge = button.querySelector('.soap-stage-status');
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'badge bg-secondary ms-2 soap-stage-status';
        button.appendChild(badge);
      }
      const status = getStageCompletion(stage.id);
      badge.textContent = status.label;
      badge.classList.remove('bg-secondary', 'bg-success', 'bg-warning', 'bg-info');
      if (status.state === 'complete') badge.classList.add('bg-success');
      if (status.state === 'incomplete') badge.classList.add('bg-warning');
      if (status.state === 'optional') badge.classList.add('bg-secondary');
      if (status.state === 'info') badge.classList.add('bg-info');
    });
    const requiredStages = STAGE_CONFIGS.filter(stage => stage.required);
    const completeCount = requiredStages.filter(stage => getStageCompletion(stage.id).state === 'complete').length;
    const progress = document.getElementById('soapStageProgress');
    if (progress) progress.textContent = `${completeCount}/${requiredStages.length} complete`;
  }

  SoapTool.stages = {
    injectStageActions,
    openStageByIndex,
    resetStage,
    updateStageStatuses,
  };
})(window);
