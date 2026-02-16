(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const state = SoapTool.state;

  function getCsrfToken(){
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  async function postJson(path, payload, timeoutMs = 2500){
    const token = getCsrfToken();
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(path, {
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
    const fragranceRows = SoapTool.fragrances.collectFragranceRows(totalOils || 0);
    const qualityFocus = Array.from(document.querySelectorAll('.quality-focus:checked'))
      .map(el => el.id);
    const qualityPreset = document.getElementById('qualityPreset')?.value || 'balanced';
    const mold = SoapTool.mold?.getMoldSettings ? SoapTool.mold.getMoldSettings() : null;
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
        global_item_id: row.globalItemId || null,
        default_unit: row.defaultUnit || null,
        ingredient_category_name: row.categoryName || null,
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
        lactate_global_item_id: additiveSettings.lactateGlobalItemId || null,
        sugar_global_item_id: additiveSettings.sugarGlobalItemId || null,
        salt_global_item_id: additiveSettings.saltGlobalItemId || null,
        citric_global_item_id: additiveSettings.citricGlobalItemId || null,
        lactate_default_unit: additiveSettings.lactateDefaultUnit || null,
        sugar_default_unit: additiveSettings.sugarDefaultUnit || null,
        salt_default_unit: additiveSettings.saltDefaultUnit || null,
        citric_default_unit: additiveSettings.citricDefaultUnit || null,
        lactate_category_name: additiveSettings.lactateCategoryName || null,
        sugar_category_name: additiveSettings.sugarCategoryName || null,
        salt_category_name: additiveSettings.saltCategoryName || null,
        citric_category_name: additiveSettings.citricCategoryName || null,
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
        quality_preset: qualityPreset,
        quality_focus: qualityFocus,
        mold,
      }
    };
  }

  async function calculateWithSoapService(payload){
    return postJson('/tools/api/soap/calculate', payload, 2500);
  }

  async function buildRecipePayload(payload){
    return postJson('/tools/api/soap/recipe-payload', payload, 3500);
  }

  SoapTool.runnerService = {
    buildServicePayload,
    calculateWithSoapService,
    buildRecipePayload,
  };
})(window);
