(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber } = SoapTool.helpers;
  const { formatWeight, formatPercent } = SoapTool.units;
  const state = SoapTool.state;

  const DEFAULT_ADDITIVES = {
    lactateG: 0,
    sugarG: 0,
    saltG: 0,
    citricG: 0,
    citricLyeG: 0,
    fragranceG: 0,
    fragrancePct: 0,
  };

  function mapOilsForState(rows){
    return (rows || []).map(oil => ({
      name: oil.name || null,
      grams: toNumber(oil.grams),
      sapKoh: toNumber(oil.sap_koh ?? oil.sapKoh),
      iodine: toNumber(oil.iodine),
      fattyProfile: oil.fatty_profile || oil.fattyProfile || null,
      global_item_id: oil.global_item_id || null,
      default_unit: oil.default_unit || null,
      ingredient_category_name: oil.ingredient_category_name || null,
    }));
  }

  function setText(id, value){
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
  }

  function renderResultsCard({
    resultsCard,
    lyeAdjusted,
    waterData,
    batchYield,
    totalOils,
    superfat,
  }){
    const card = document.getElementById('resultsCard');
    if (card) card.style.display = 'block';

    const ratioValue = toNumber(resultsCard.water_lye_ratio) || waterData.waterRatio;
    setText('lyeAdjustedOutput', formatWeight(toNumber(resultsCard.lye_adjusted_g) || lyeAdjusted));
    setText('waterOutput', formatWeight(toNumber(resultsCard.water_g) || waterData.waterG));
    setText('batchYieldOutput', formatWeight(batchYield));
    setText(
      'lyeConcentrationOutput',
      formatPercent(toNumber(resultsCard.lye_concentration_pct) || waterData.lyeConcentration)
    );
    setText(
      'waterRatioOutput',
      (isFinite(ratioValue) && ratioValue > 0) ? round(ratioValue, 2).toString() : '--'
    );
    setText('totalOilsOutput', formatWeight(totalOils));
    setText('superfatOutput', formatPercent(superfat));

    [
      'lyeAdjustedOutput',
      'waterOutput',
      'batchYieldOutput',
      'lyeConcentrationOutput',
      'waterRatioOutput',
      'totalOilsOutput',
      'superfatOutput',
    ].forEach(id => SoapTool.ui.pulseValue(document.getElementById(id)));
  }

  function maybeShowGuidanceAlerts({ showAlerts, lyeTotals, purity, waterData }){
    if (!showAlerts) return;
    if (lyeTotals.usedFallback) {
      SoapTool.ui.showSoapAlert(
        'info',
        'Some oils are missing SAP values, so an average SAP was used. Select oils with SAP data for the most accurate lye calculation.',
        { dismissible: true, timeoutMs: 7000 }
      );
    }
    if (purity < 100) {
      SoapTool.ui.showSoapAlert(
        'info',
        `Lye purity is set to ${round(purity, 1)}%. Adjusting lye to match your real-world purity.`,
        { dismissible: true, timeoutMs: 6000 }
      );
    }
    if (waterData.lyeConcentration < 25 || waterData.lyeConcentration > 45) {
      SoapTool.ui.showSoapAlert(
        'warning',
        'Your lye concentration is outside the common 25-45% range. Expect slower or faster trace.',
        { dismissible: true, timeoutMs: 7000 }
      );
    }
    const mold = SoapTool.mold.getMoldSettings();
    if (mold.shape === 'cylinder' && mold.waterWeight > 0 && !mold.useCylinder) {
      SoapTool.ui.showSoapAlert(
        'info',
        'Cylinder mold selected. Enable the cylinder correction if you want to leave headspace or reduce spill risk.',
        { dismissible: true, timeoutMs: 7000 }
      );
    }
  }

  function applyServiceResult({
    serviceResult,
    validation,
    selection,
    superfat,
    purity,
    waterMethod,
    waterPct,
    lyeConcentrationInput,
    waterRatioInput,
    showAlerts,
  }){
    const lyeType = serviceResult.lye_type || selection.lyeType || 'NaOH';
    const lyeSelected = serviceResult.lye_selected || selection.selected || null;
    const totalOils = toNumber(serviceResult.total_oils_g) || validation.totals.totalWeight;
    const resolvedSuperfat = toNumber(serviceResult.superfat_pct);
    const superfatValue = isFinite(resolvedSuperfat) ? resolvedSuperfat : superfat;
    const lyeTotals = {
      sapAvg: toNumber(serviceResult.sap_avg_koh),
      usedFallback: !!serviceResult.used_sap_fallback,
    };
    const lyePure = toNumber(serviceResult.lye_pure_g);
    const hasLyeAdjustedBase = Object.prototype.hasOwnProperty.call(serviceResult, 'lye_adjusted_base_g');
    const lyeAdjustedBase = hasLyeAdjustedBase ? toNumber(serviceResult.lye_adjusted_base_g) : null;
    const lyeAdjusted = toNumber(serviceResult.lye_adjusted_g);
    const resolvedPurity = toNumber(serviceResult.lye_purity_pct) || purity;
    const resolvedWaterMethod = serviceResult.water_method || waterMethod;
    const resolvedWaterPct = toNumber(serviceResult.water_pct) || waterPct;
    const resolvedLyeConcentrationInput = toNumber(serviceResult.lye_concentration_input_pct) || lyeConcentrationInput;
    const resolvedWaterRatioInput = toNumber(serviceResult.water_ratio_input) || waterRatioInput;
    const waterData = {
      waterG: toNumber(serviceResult.water_g),
      lyeConcentration: toNumber(serviceResult.lye_concentration_pct),
      waterRatio: toNumber(serviceResult.water_lye_ratio),
    };
    const resultsCard = serviceResult.results_card || {};
    const qualityReport = serviceResult.quality_report || {};
    const oilsForState = mapOilsForState(serviceResult.oils || validation.oils);
    const liveSummary = {
      waterG: waterData.waterG,
      lyeAdjusted,
      totalOils,
      waterMethod: resolvedWaterMethod,
      waterPct: resolvedWaterPct,
      lyeConcentrationInput: resolvedLyeConcentrationInput,
      waterRatioInput: resolvedWaterRatioInput,
      lyeConcentration: waterData.lyeConcentration,
      waterRatio: waterData.waterRatio,
    };
    SoapTool.runnerInputs.updateStageWaterSummary(liveSummary);
    SoapTool.runnerInputs.updateLiveCalculationPreview(liveSummary);

    const additives = serviceResult.additives || DEFAULT_ADDITIVES;
    if (SoapTool.additives.applyComputedOutputs) {
      SoapTool.additives.applyComputedOutputs(additives);
    }
    const batchYield = toNumber(resultsCard.batch_yield_g) || (
      totalOils
      + lyeAdjusted
      + waterData.waterG
      + additives.fragranceG
      + additives.lactateG
      + additives.sugarG
      + additives.saltG
      + additives.citricG
    );
    if (SoapTool.mold?.updateWetBatterWarning) {
      SoapTool.mold.updateWetBatterWarning(batchYield);
    }

    renderResultsCard({
      resultsCard,
      lyeAdjusted,
      waterData,
      batchYield,
      totalOils,
      superfat: superfatValue,
    });
    SoapTool.ui.updateResultsWarnings(waterData);
    SoapTool.ui.updateResultsMeta();

    SoapTool.quality.updateQualitiesDisplay({
      qualities: qualityReport.qualities || {},
      fattyPercent: qualityReport.fatty_acids_pct || {},
      coveragePct: toNumber(qualityReport.coverage_pct),
      iodine: toNumber(qualityReport.iodine),
      ins: toNumber(qualityReport.ins),
      sapAvg: lyeTotals.sapAvg,
      superfat: superfatValue,
      waterData,
      additives,
      oils: oilsForState,
      totalOils,
      warnings: qualityReport.warnings || [],
    });
    if (SoapTool.oils?.renderOilTips) {
      SoapTool.oils.renderOilTips(qualityReport.blend_tips || []);
    }
    SoapTool.additives.updateVisualGuidance({
      tips: qualityReport.visual_guidance || [],
    });
    SoapTool.stages.updateStageStatuses();
    maybeShowGuidanceAlerts({
      showAlerts,
      lyeTotals,
      purity: resolvedPurity,
      waterData,
    });

    state.lastCalc = {
      totalOils,
      oils: oilsForState,
      lyeType,
      lyeSelected,
      superfat: superfatValue,
      purity: resolvedPurity,
      lyePure,
      lyeAdjustedBase,
      lyeAdjusted,
      water: waterData.waterG,
      waterMethod: resolvedWaterMethod,
      waterPct: resolvedWaterPct,
      lyeConcentration: waterData.lyeConcentration,
      waterRatio: waterData.waterRatio,
      sapAvg: lyeTotals.sapAvg,
      usedSapFallback: lyeTotals.usedFallback,
      additives,
      batchYield,
      qualityReport,
      export: serviceResult.export || null,
    };
    return state.lastCalc;
  }

  SoapTool.runnerRender = {
    applyServiceResult,
  };
})(window);
