(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { UNIT_FACTORS } = SoapTool.constants;
  const state = SoapTool.state;

  function toGrams(value){
    return clamp(toNumber(value), 0) * (UNIT_FACTORS[state.currentUnit] || 1);
  }

  function fromGrams(value){
    const grams = clamp(value, 0);
    return grams / (UNIT_FACTORS[state.currentUnit] || 1);
  }

  function formatWeight(value){
    if (!isFinite(value) || value <= 0) return '--';
    return `${round(fromGrams(value), 2)} ${state.currentUnit}`;
  }

  function formatPercent(value){
    if (!isFinite(value)) return '--';
    return `${round(value, 1)}%`;
  }

  function updateUnitLabels(){
    document.querySelectorAll('.unit-label').forEach(el => {
      el.textContent = state.currentUnit;
    });
  }

  function setUnit(unit, options = {}){
    if (!unit) return;
    if (unit === state.currentUnit) {
      updateUnitLabels();
      return;
    }
    const prevUnit = state.currentUnit;
    state.currentUnit = unit;
    updateUnitLabels();
    if (options.skipConvert) return;
    const ratio = (UNIT_FACTORS[prevUnit] || 1) / (UNIT_FACTORS[unit] || 1);
    document.querySelectorAll('.oil-grams').forEach(input => {
      const value = toNumber(input.value);
      if (value > 0) input.value = round(value * ratio, 2);
    });
    const oilTarget = document.getElementById('oilTotalTarget');
    if (oilTarget && oilTarget.value) {
      const value = toNumber(oilTarget.value);
      if (value > 0) oilTarget.value = round(value * ratio, 2);
    }
    const moldWater = document.getElementById('moldWaterWeight');
    if (moldWater && moldWater.value) {
      const value = toNumber(moldWater.value);
      if (value > 0) moldWater.value = round(value * ratio, 2);
    }
    SoapTool.oils.updateOilTotals();
    SoapTool.mold.updateMoldSuggested();
    SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
    if (!options.skipAutoCalc) {
      SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: false });
    }
  }

  SoapTool.units = {
    toGrams,
    fromGrams,
    formatWeight,
    formatPercent,
    updateUnitLabels,
    setUnit,
  };
})(window);
