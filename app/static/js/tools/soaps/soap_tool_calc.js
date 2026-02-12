(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { clamp, toNumber } = SoapTool.helpers;

  function computeLyeTotals(oils, lyeType){
    let lyeTotal = 0;
    let sapWeighted = 0;
    let sapWeightG = 0;
    let totalWeight = 0;
    oils.forEach(oil => {
      totalWeight += oil.grams;
      if (oil.sapKoh > 0) {
        const perG = lyeType === 'KOH'
          ? (oil.sapKoh / 1000)
          : (oil.sapKoh * 0.713 / 1000);
        lyeTotal += oil.grams * perG;
        sapWeighted += oil.sapKoh * oil.grams;
        sapWeightG += oil.grams;
      }
    });
    const sapAvg = sapWeightG > 0 ? sapWeighted / sapWeightG : 0;
    const usedFallback = lyeTotal <= 0 && totalWeight > 0;
    if (usedFallback) {
      const fallbackPerG = lyeType === 'KOH' ? 0.194 : 0.138;
      lyeTotal = totalWeight * fallbackPerG;
    }
    return { lyeTotal, sapAvg, usedFallback };
  }

  function computeWater(lyeAdjusted, totalOils, method, waterPct, lyeConcentration, waterRatio){
    let waterG = 0;
    if (method === 'concentration') {
      if (lyeAdjusted <= 0) {
        return { waterG: 0, lyeConcentration: 0, waterRatio: 0 };
      }
      const conc = lyeConcentration > 0 ? lyeConcentration : 33;
      waterG = lyeAdjusted * ((100 - conc) / conc);
    } else if (method === 'ratio') {
      if (lyeAdjusted <= 0) {
        return { waterG: 0, lyeConcentration: 0, waterRatio: 0 };
      }
      const ratio = waterRatio > 0 ? waterRatio : 2;
      waterG = lyeAdjusted * ratio;
    } else {
      const pct = waterPct > 0 ? waterPct : 33;
      waterG = totalOils * (pct / 100);
    }
    const lyeConc = waterG + lyeAdjusted > 0 ? (lyeAdjusted / (lyeAdjusted + waterG)) * 100 : 0;
    const ratio = lyeAdjusted > 0 ? (waterG / lyeAdjusted) : 0;
    return { waterG, lyeConcentration: lyeConc, waterRatio: ratio };
  }

  function computeIodine(oils){
    let totalWeight = 0;
    let weighted = 0;
    oils.forEach(oil => {
      if (oil.iodine > 0) {
        totalWeight += oil.grams;
        weighted += oil.iodine * oil.grams;
      }
    });
    return {
      iodine: totalWeight > 0 ? weighted / totalWeight : 0,
      coverageWeight: totalWeight,
    };
  }

  function computeFattyAcids(oils){
    const totals = {};
    let coveredWeight = 0;
    oils.forEach(oil => {
      if (!oil.fattyProfile || typeof oil.fattyProfile !== 'object') {
        return;
      }
      coveredWeight += oil.grams;
      Object.entries(oil.fattyProfile).forEach(([key, pct]) => {
        const value = toNumber(pct);
        if (value > 0) {
          totals[key] = (totals[key] || 0) + oil.grams * (value / 100);
        }
      });
    });
    const percent = {};
    if (coveredWeight > 0) {
      Object.entries(totals).forEach(([key, grams]) => {
        percent[key] = (grams / coveredWeight) * 100;
      });
    }
    return { percent, coveredWeight };
  }

  function computeQualities(fattyPercent){
    const get = key => fattyPercent[key] || 0;
    return {
      hardness: get('lauric') + get('myristic') + get('palmitic') + get('stearic'),
      cleansing: get('lauric') + get('myristic'),
      conditioning: get('oleic') + get('linoleic') + get('linolenic') + get('ricinoleic'),
      bubbly: get('lauric') + get('myristic') + get('ricinoleic'),
      creamy: get('palmitic') + get('stearic') + get('ricinoleic'),
    };
  }

  function computeOilQualityScores(fattyProfile){
    if (!fattyProfile || typeof fattyProfile !== 'object') {
      return {
        hardness: 0,
        cleansing: 0,
        conditioning: 0,
        bubbly: 0,
        creamy: 0,
      };
    }
    const profile = {
      lauric: toNumber(fattyProfile.lauric),
      myristic: toNumber(fattyProfile.myristic),
      palmitic: toNumber(fattyProfile.palmitic),
      stearic: toNumber(fattyProfile.stearic),
      ricinoleic: toNumber(fattyProfile.ricinoleic),
      oleic: toNumber(fattyProfile.oleic),
      linoleic: toNumber(fattyProfile.linoleic),
      linolenic: toNumber(fattyProfile.linolenic),
    };
    const qualities = computeQualities(profile);
    return {
      hardness: (qualities.hardness || 0) / 100,
      cleansing: (qualities.cleansing || 0) / 100,
      conditioning: (qualities.conditioning || 0) / 100,
      bubbly: (qualities.bubbly || 0) / 100,
      creamy: (qualities.creamy || 0) / 100,
    };
  }

  function computeAdditives(totalOils, lyeType, percents){
    const inputs = percents || {};
    const baseOils = clamp(totalOils, 0);
    const fragrancePct = clamp(toNumber(inputs.fragrancePct), 0, 100);
    const lactatePct = clamp(toNumber(inputs.lactatePct), 0, 100);
    const sugarPct = clamp(toNumber(inputs.sugarPct), 0, 100);
    const saltPct = clamp(toNumber(inputs.saltPct), 0, 100);
    const citricPct = clamp(toNumber(inputs.citricPct), 0, 100);
    const fragranceG = baseOils * (fragrancePct / 100);
    const lactateG = baseOils * (lactatePct / 100);
    const sugarG = baseOils * (sugarPct / 100);
    const saltG = baseOils * (saltPct / 100);
    const citricG = baseOils * (citricPct / 100);
    const citricLyeFactor = lyeType === 'KOH' ? 0.719 : 0.624;
    const citricLyeG = citricG * citricLyeFactor;
    return {
      fragrancePct,
      lactatePct,
      sugarPct,
      saltPct,
      citricPct,
      fragranceG,
      lactateG,
      sugarG,
      saltG,
      citricG,
      citricLyeG,
    };
  }

  SoapTool.calc = {
    computeLyeTotals,
    computeWater,
    computeIodine,
    computeFattyAcids,
    computeQualities,
    computeOilQualityScores,
    computeAdditives,
  };

  window.SoapCalcService = SoapTool.calc;
})(window);
