(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;

  function deriveSapAverage(oils){
    let sapWeighted = 0;
    let sapWeightG = 0;
    (oils || []).forEach(oil => {
      const sapKoh = toNumber(oil?.sapKoh);
      const grams = toNumber(oil?.grams);
      if (sapKoh > 0 && grams > 0) {
        sapWeighted += sapKoh * grams;
        sapWeightG += grams;
      }
    });
    return sapWeightG > 0 ? sapWeighted / sapWeightG : 0;
  }

  function buildSoapNotesBlob(calc){
    const qualityReport = calc.qualityReport || {};
    const fattyPercent = qualityReport.fatty_acids_pct || {};
    const qualities = qualityReport.qualities || {};
    const sapAvg = (isFinite(calc.sapAvg) && calc.sapAvg > 0)
      ? calc.sapAvg
      : (toNumber(qualityReport.sap_avg_koh) || deriveSapAverage(calc.oils || []));
    const iodine = toNumber(qualityReport.iodine);
    const ins = toNumber(qualityReport.ins) || ((sapAvg && iodine) ? (sapAvg - iodine) : 0);
    const mold = SoapTool.mold.getMoldSettings();
    return {
      source: 'soap_tool',
      schema_version: 1,
      unit_display: SoapTool.state.currentUnit,
      input_mode: 'mixed',
      quality_preset: document.getElementById('qualityPreset')?.value || 'balanced',
      quality_focus: Array.from(document.querySelectorAll('.quality-focus:checked')).map(el => el.id),
      mold,
      oils: (calc.oils || []).map(oil => ({
        name: oil.name || null,
        grams: round(oil.grams || 0, 2),
        iodine: oil.iodine || null,
        sap_koh: oil.sapKoh || null,
        fatty_profile: oil.fattyProfile || null,
        global_item_id: oil.global_item_id || null,
        default_unit: oil.default_unit || null,
        ingredient_category_name: oil.ingredient_category_name || null,
      })),
      totals: {
        total_oils_g: round(calc.totalOils || 0, 2),
        batch_yield_g: round(calc.batchYield || 0, 2),
        lye_pure_g: round(calc.lyePure || 0, 2),
        lye_adjusted_g: round(calc.lyeAdjusted || 0, 2),
        water_g: round(calc.water || 0, 2),
      },
      lye: {
        lye_type: calc.lyeType,
        superfat: calc.superfat,
        purity: calc.purity,
        water_method: calc.waterMethod,
        water_pct: calc.waterPct,
        lye_concentration: calc.lyeConcentration,
        water_ratio: calc.waterRatio,
      },
      additives: {
        fragrance_pct: calc.additives?.fragrancePct || 0,
        lactate_pct: calc.additives?.lactatePct || 0,
        sugar_pct: calc.additives?.sugarPct || 0,
        salt_pct: calc.additives?.saltPct || 0,
        citric_pct: calc.additives?.citricPct || 0,
        fragrance_g: round(calc.additives?.fragranceG || 0, 2),
        lactate_g: round(calc.additives?.lactateG || 0, 2),
        sugar_g: round(calc.additives?.sugarG || 0, 2),
        salt_g: round(calc.additives?.saltG || 0, 2),
        citric_g: round(calc.additives?.citricG || 0, 2),
        citric_lye_g: round(calc.additives?.citricLyeG || 0, 2),
      },
      qualities: {
        hardness: round(qualities.hardness || 0, 1),
        cleansing: round(qualities.cleansing || 0, 1),
        conditioning: round(qualities.conditioning || 0, 1),
        bubbly: round(qualities.bubbly || 0, 1),
        creamy: round(qualities.creamy || 0, 1),
        iodine: round(iodine || 0, 1),
        ins: round(ins || 0, 1),
        sap_avg: round(sapAvg || 0, 1),
      },
      fatty_acids: fattyPercent,
      updated_at: new Date().toISOString(),
    };
  }

  function getAdditiveItem(nameId, giId, fallbackName, unitId, categoryId){
    const name = document.getElementById(nameId)?.value?.trim();
    const giRaw = document.getElementById(giId)?.value || '';
    const defaultUnit = unitId ? document.getElementById(unitId)?.value || '' : '';
    const categoryName = categoryId ? document.getElementById(categoryId)?.value || '' : '';
    return {
      name: name || fallbackName,
      globalItemId: giRaw ? parseInt(giRaw) : undefined,
      defaultUnit: defaultUnit || undefined,
      categoryName: categoryName || undefined,
    };
  }

  function collectFragranceRows(totalOils){
    const rows = [];
    const target = clamp(totalOils || SoapTool.oils.getTotalOilsGrams() || 0, 0);
    document.querySelectorAll('#fragranceRows .fragrance-row').forEach(row => {
      const name = row.querySelector('.fragrance-typeahead')?.value?.trim();
      const giRaw = row.querySelector('.fragrance-gi-id')?.value || '';
      const defaultUnit = row.querySelector('.fragrance-default-unit')?.value || '';
      const categoryName = row.querySelector('.fragrance-category')?.value || '';
      const gramsInput = row.querySelector('.fragrance-grams')?.value;
      const pctInput = row.querySelector('.fragrance-percent')?.value;
      let grams = SoapTool.units.toGrams(gramsInput);
      const pct = clamp(toNumber(pctInput), 0);
      if (grams <= 0 && pct > 0 && target > 0) {
        grams = target * (pct / 100);
      }
      if (!name && !giRaw && grams <= 0) return;
      rows.push({
        name: name || 'Fragrance/Essential Oils',
        globalItemId: giRaw ? parseInt(giRaw) : undefined,
        defaultUnit: defaultUnit || undefined,
        categoryName: categoryName || undefined,
        grams,
        pct,
      });
    });
    return rows;
  }

  function collectDraftLines(wrapperId, kind){
    const out = [];
    document.querySelectorAll(`#${wrapperId} .row`).forEach(function(row){
      const name = row.querySelector('.tool-typeahead')?.value?.trim();
      const gi = row.querySelector('.tool-gi-id')?.value || '';
      const qtyEl = row.querySelector('.tool-qty');
      const unitEl = row.querySelector('.tool-unit');
      const hasQty = qtyEl && qtyEl.value !== '';
      if (!name && !gi) return;
      if (kind === 'container'){
        out.push({ name: name || undefined, global_item_id: gi ? parseInt(gi) : undefined, quantity: hasQty ? parseFloat(qtyEl.value) : 1 });
      } else {
        out.push({ name: name || undefined, global_item_id: gi ? parseInt(gi) : undefined, quantity: hasQty ? parseFloat(qtyEl.value) : 0, unit: (unitEl?.value || '').trim() || 'gram' });
      }
    });
    return out;
  }

  function buildLineRow(kind){
    const context = SoapTool.config.isAuthenticated ? 'member' : 'public';
    const mode = SoapTool.config.isAuthenticated ? 'recipe' : 'public';
    return buildToolLineRow(kind, { context, mode, unitOptionsHtml: SoapTool.config.unitOptionsHtml });
  }

  function addStubLine(kind, name){
    const row = buildLineRow(kind);
    const input = row.querySelector('.tool-typeahead');
    const qty = row.querySelector('.tool-qty');
    if (input) {
      input.value = name;
    }
    if (qty && kind === 'container') {
      qty.value = 1;
    }
    if (kind === 'container') {
      document.getElementById('tool-containers').appendChild(row);
    } else if (kind === 'consumable') {
      document.getElementById('tool-consumables').appendChild(row);
    } else {
      document.getElementById('tool-ingredients').appendChild(row);
    }
  }

  function buildSoapRecipePayload(calc){
    const notesBlob = buildSoapNotesBlob(calc);
    const baseIngredients = (calc.oils || []).map(oil => ({
      name: oil.name || undefined,
      global_item_id: oil.global_item_id || undefined,
      quantity: oil.grams,
      unit: 'gram',
      default_unit: oil.default_unit || undefined,
      ingredient_category_name: oil.ingredient_category_name || undefined,
    }));
    const lyeName = calc.lyeType === 'KOH' ? 'Potassium Hydroxide (KOH)' : 'Sodium Hydroxide (NaOH)';
    if (calc.lyeAdjusted > 0) {
      baseIngredients.push({ name: lyeName, quantity: round(calc.lyeAdjusted, 2), unit: 'gram' });
    }
    if (calc.water > 0) {
      baseIngredients.push({ name: 'Distilled Water', quantity: round(calc.water, 2), unit: 'gram' });
    }
    const fragranceRows = collectFragranceRows(calc.totalOils || 0);
    fragranceRows.forEach(item => {
      if (item.grams > 0) {
        baseIngredients.push({
          name: item.name,
          global_item_id: item.globalItemId,
          quantity: round(item.grams, 2),
          unit: 'gram',
          default_unit: item.defaultUnit,
          ingredient_category_name: item.categoryName,
        });
      }
    });
    if (calc.additives?.lactateG > 0) {
      const item = getAdditiveItem('additiveLactateName', 'additiveLactateGi', 'Sodium Lactate', 'additiveLactateUnit', 'additiveLactateCategory');
      baseIngredients.push({
        name: item.name,
        global_item_id: item.globalItemId,
        quantity: round(calc.additives.lactateG, 2),
        unit: 'gram',
        default_unit: item.defaultUnit,
        ingredient_category_name: item.categoryName,
      });
    }
    if (calc.additives?.sugarG > 0) {
      const item = getAdditiveItem('additiveSugarName', 'additiveSugarGi', 'Sugar', 'additiveSugarUnit', 'additiveSugarCategory');
      baseIngredients.push({
        name: item.name,
        global_item_id: item.globalItemId,
        quantity: round(calc.additives.sugarG, 2),
        unit: 'gram',
        default_unit: item.defaultUnit,
        ingredient_category_name: item.categoryName,
      });
    }
    if (calc.additives?.saltG > 0) {
      const item = getAdditiveItem('additiveSaltName', 'additiveSaltGi', 'Salt', 'additiveSaltUnit', 'additiveSaltCategory');
      baseIngredients.push({
        name: item.name,
        global_item_id: item.globalItemId,
        quantity: round(calc.additives.saltG, 2),
        unit: 'gram',
        default_unit: item.defaultUnit,
        ingredient_category_name: item.categoryName,
      });
    }
    if (calc.additives?.citricG > 0) {
      const item = getAdditiveItem('additiveCitricName', 'additiveCitricGi', 'Citric Acid', 'additiveCitricUnit', 'additiveCitricCategory');
      baseIngredients.push({
        name: item.name,
        global_item_id: item.globalItemId,
        quantity: round(calc.additives.citricG, 2),
        unit: 'gram',
        default_unit: item.defaultUnit,
        ingredient_category_name: item.categoryName,
      });
      baseIngredients.push({ name: 'Extra Lye for Citric Acid', quantity: round(calc.additives.citricLyeG, 2), unit: 'gram' });
    }
    return {
      name: 'Soap (Draft)',
      instructions: 'Draft from Soap Tools',
      predicted_yield: Math.round((calc.batchYield || 0) * 100) / 100,
      predicted_yield_unit: 'gram',
      category_name: 'Soaps',
      category_data: {
        soap_superfat: calc.superfat,
        soap_lye_type: calc.lyeType,
        soap_lye_purity: calc.purity,
        soap_water_method: calc.waterMethod,
        soap_water_pct: calc.waterPct,
        soap_lye_concentration: calc.lyeConcentration,
        soap_water_ratio: calc.waterRatio,
        soap_oils_total_g: calc.totalOils,
        soap_lye_g: calc.lyeAdjusted,
        soap_water_g: calc.water,
      },
      ingredients: baseIngredients.concat(collectDraftLines('tool-ingredients', 'ingredient')),
      consumables: collectDraftLines('tool-consumables', 'consumable'),
      containers: collectDraftLines('tool-containers', 'container'),
      notes: JSON.stringify(notesBlob),
    };
  }

  SoapTool.recipePayload = {
    collectFragranceRows,
    collectDraftLines,
    buildLineRow,
    addStubLine,
    buildSoapRecipePayload,
  };
})(window);

