(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const {
    LACTATE_CATEGORY_SET,
    SUGAR_CATEGORY_SET,
    SALT_CATEGORY_SET,
    CITRIC_CATEGORY_SET,
  } = SoapTool.constants;

  function bind({ oilRows, fragranceRows } = {}){
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
  }

  SoapTool.eventsInit = {
    bind,
  };
})(window);
