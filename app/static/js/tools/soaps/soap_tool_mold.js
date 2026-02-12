(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { clamp, toNumber, round } = SoapTool.helpers;
  const { toGrams, fromGrams } = SoapTool.units;

  function updateMoldSuggested(){
    const settings = getMoldSettings();
    const targetInput = document.getElementById('oilTotalTarget');
    const targetHint = document.getElementById('oilTargetHint');
    if (targetInput && settings.effectiveCapacity > 0 && toGrams(targetInput.value) <= 0) {
      targetInput.value = settings.targetOils > 0 ? round(fromGrams(settings.targetOils), 2) : '';
    }
    if (targetHint) {
      if (settings.effectiveCapacity > 0) {
        targetHint.textContent = 'Linked to mold sizing. Edit oil % or total oils target to update the other.';
      } else {
        targetHint.textContent = 'Auto-fills when mold sizing is set.';
      }
    }
    const note = document.getElementById('moldSuggestionNote');
    if (note) {
      let message = 'Target oils are capped to the mold size above.';
      if (settings.shape === 'cylinder' && settings.waterWeight > 0) {
        if (settings.useCylinder) {
          message = `Cylinder correction applied (${round(settings.cylinderFactor * 100, 0)}% of capacity).`;
        } else {
          message = 'Cylinder mold selected. Apply a correction if you want headspace or a smaller fill.';
        }
      }
      note.textContent = message;
    }
  }

  function syncTargetFromMold(){
    const targetInput = document.getElementById('oilTotalTarget');
    const settings = getMoldSettings();
    if (!targetInput) return settings;
    if (settings.effectiveCapacity > 0) {
      targetInput.value = settings.targetOils > 0 ? round(fromGrams(settings.targetOils), 2) : '';
    }
    updateMoldSuggested();
    return settings;
  }

  function syncMoldPctFromTarget(){
    const targetInput = document.getElementById('oilTotalTarget');
    const moldOilPct = document.getElementById('moldOilPct');
    if (!targetInput || !moldOilPct) {
      const settings = getMoldSettings();
      updateMoldSuggested();
      return settings;
    }
    const settings = getMoldSettings();
    if (settings.effectiveCapacity > 0) {
      const target = toGrams(targetInput.value);
      const cappedTarget = clamp(target, 0, settings.effectiveCapacity);
      if (target > settings.effectiveCapacity + 0.01) {
        targetInput.value = round(fromGrams(cappedTarget), 2);
      }
      const nextPct = cappedTarget > 0 ? (cappedTarget / settings.effectiveCapacity) * 100 : 0;
      moldOilPct.value = cappedTarget > 0 ? round(nextPct, 2) : '';
    }
    const nextSettings = getMoldSettings();
    updateMoldSuggested();
    return nextSettings;
  }

  function getMoldSettings(){
    const waterWeight = toGrams(document.getElementById('moldWaterWeight').value);
    const oilPct = clamp(toNumber(document.getElementById('moldOilPct').value), 0, 100);
    const shape = document.getElementById('moldShape')?.value || 'loaf';
    const useCylinder = !!document.getElementById('moldCylinderCorrection')?.checked;
    const cylinderFactor = clamp(toNumber(document.getElementById('moldCylinderFactor')?.value), 0.5, 1);
    const effectiveCapacity = waterWeight > 0 ? waterWeight * (useCylinder ? cylinderFactor : 1) : 0;
    const targetOils = effectiveCapacity > 0 ? effectiveCapacity * (oilPct / 100) : 0;
    return {
      waterWeight,
      oilPct,
      shape,
      useCylinder,
      cylinderFactor,
      effectiveCapacity,
      targetOils,
    };
  }

  function updateMoldShapeUI(){
    const shape = document.getElementById('moldShape')?.value || 'loaf';
    const options = document.getElementById('moldCylinderOptions');
    if (options) {
      options.classList.toggle('d-none', shape !== 'cylinder');
    }
    updateMoldSuggested();
  }

  SoapTool.mold = {
    updateMoldSuggested,
    syncTargetFromMold,
    syncMoldPctFromTarget,
    getMoldSettings,
    updateMoldShapeUI,
  };
})(window);
