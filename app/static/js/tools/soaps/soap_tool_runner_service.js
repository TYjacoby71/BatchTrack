(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const state = SoapTool.state;

  function buildServicePayload({
    oils,
    selection,
    superfat,
    purity,
    waterMethod,
    waterPct,
    lyeConcentration,
    waterRatio,
    totalOils,
  }){
    const additiveSettings = SoapTool.additives.collectAdditiveSettings();
    const fragranceRows = SoapTool.recipePayload.collectFragranceRows(totalOils || 0);
    return {
      oils: (oils || []).map(oil => ({
        name: oil.name || null,
        grams: oil.grams || 0,
        sap_koh: oil.sapKoh || 0,
        iodine: oil.iodine || 0,
        fatty_profile: oil.fattyProfile || null,
        global_item_id: oil.global_item_id || null,
        default_unit: oil.default_unit || null,
        ingredient_category_name: oil.ingredient_category_name || null,
      })),
      fragrances: fragranceRows.map(row => ({
        name: row.name || 'Fragrance/Essential Oils',
        grams: row.grams || 0,
        pct: row.pct || 0,
      })),
      additives: {
        lactate_pct: additiveSettings.lactatePct || 0,
        sugar_pct: additiveSettings.sugarPct || 0,
        salt_pct: additiveSettings.saltPct || 0,
        citric_pct: additiveSettings.citricPct || 0,
        lactate_name: additiveSettings.lactateName || 'Sodium Lactate',
        sugar_name: additiveSettings.sugarName || 'Sugar',
        salt_name: additiveSettings.saltName || 'Salt',
        citric_name: additiveSettings.citricName || 'Citric Acid',
      },
      lye: {
        selected: selection?.selected || 'NaOH',
        superfat,
        purity,
      },
      water: {
        method: waterMethod,
        water_pct: waterPct,
        lye_concentration: lyeConcentration,
        water_ratio: waterRatio,
      },
      meta: {
        unit_display: state.currentUnit || 'g',
      }
    };
  }

  async function calculateWithSoapService(payload){
    const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 2500);
    try {
      const response = await fetch('/tools/api/soap/calculate', {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-CSRFToken': token } : {}),
        },
        body: JSON.stringify(payload || {}),
      });
      if (!response.ok) return null;
      const data = await response.json();
      if (!data || data.success !== true || typeof data.result !== 'object') return null;
      return data.result;
    } catch (_) {
      return null;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  SoapTool.runnerService = {
    buildServicePayload,
    calculateWithSoapService,
  };
})(window);
