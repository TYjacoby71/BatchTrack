(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { toNumber, round, clamp, buildSoapcalcSearchBuilder } = SoapTool.helpers;
  const { formatWeight, toGrams, fromGrams } = SoapTool.units;
  const { FRAGRANCE_CATEGORY_SET, CITRIC_LYE_FACTORS } = SoapTool.constants;
  const state = SoapTool.state;

  function attachAdditiveTypeahead(inputId, hiddenId, categorySet, unitId, categoryId){
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const hiddenUnit = unitId ? document.getElementById(unitId) : null;
    const hiddenCategory = categoryId ? document.getElementById(categoryId) : null;
    const list = input?.parentElement?.querySelector('[data-role="suggestions"]');
    if (!input || !list || typeof window.attachMergedInventoryGlobalTypeahead !== 'function') return;
    const builder = buildSoapcalcSearchBuilder();
    window.attachMergedInventoryGlobalTypeahead({
      inputEl: input,
      listEl: list,
      mode: 'public',
      giHiddenEl: hidden,
      includeInventory: false,
      includeGlobal: true,
      ingredientFirst: false,
      globalUrlBuilder: builder,
      searchType: 'ingredient',
      resultFilter: (item, source) => {
        const category = getItemCategoryName(item);
        if (!category) return source === 'inventory';
        return categorySet.has(category);
      },
      requireHidden: false,
      onSelection: function(picked){
        if (hiddenUnit) hiddenUnit.value = picked?.default_unit || '';
        if (hiddenCategory) hiddenCategory.value = picked?.ingredient_category_name || '';
        SoapTool.storage.queueStateSave();
      }
    });
    input.addEventListener('input', function(){
      if (!this.value.trim()) {
        if (hiddenUnit) hiddenUnit.value = '';
        if (hiddenCategory) hiddenCategory.value = '';
      }
    });
  }

  function readAdditivePct({ pctId, weightId }){
    const pctInput = document.getElementById(pctId);
    const pctRaw = pctInput?.value;
    if (pctRaw !== '' && pctRaw !== null && pctRaw !== undefined) {
      return toNumber(pctRaw);
    }
    const totalOils = clamp(SoapTool.oils?.getTotalOilsGrams?.() || 0, 0);
    if (totalOils <= 0) return 0;
    const weightGrams = toGrams(document.getElementById(weightId)?.value);
    if (weightGrams <= 0) return 0;
    return (weightGrams / totalOils) * 100;
  }

  function collectAdditiveSettings(){
    const lactateGiRaw = document.getElementById('additiveLactateGi')?.value || '';
    const sugarGiRaw = document.getElementById('additiveSugarGi')?.value || '';
    const saltGiRaw = document.getElementById('additiveSaltGi')?.value || '';
    const citricGiRaw = document.getElementById('additiveCitricGi')?.value || '';
    return {
      lactatePct: readAdditivePct({ pctId: 'additiveLactatePct', weightId: 'additiveLactateWeight' }),
      sugarPct: readAdditivePct({ pctId: 'additiveSugarPct', weightId: 'additiveSugarWeight' }),
      saltPct: readAdditivePct({ pctId: 'additiveSaltPct', weightId: 'additiveSaltWeight' }),
      citricPct: readAdditivePct({ pctId: 'additiveCitricPct', weightId: 'additiveCitricWeight' }),
      lactateName: document.getElementById('additiveLactateName')?.value?.trim() || 'Sodium Lactate',
      sugarName: document.getElementById('additiveSugarName')?.value?.trim() || 'Sugar',
      saltName: document.getElementById('additiveSaltName')?.value?.trim() || 'Salt',
      citricName: document.getElementById('additiveCitricName')?.value?.trim() || 'Citric Acid',
      lactateGlobalItemId: lactateGiRaw ? parseInt(lactateGiRaw) : undefined,
      sugarGlobalItemId: sugarGiRaw ? parseInt(sugarGiRaw) : undefined,
      saltGlobalItemId: saltGiRaw ? parseInt(saltGiRaw) : undefined,
      citricGlobalItemId: citricGiRaw ? parseInt(citricGiRaw) : undefined,
      lactateDefaultUnit: document.getElementById('additiveLactateUnit')?.value || undefined,
      sugarDefaultUnit: document.getElementById('additiveSugarUnit')?.value || undefined,
      saltDefaultUnit: document.getElementById('additiveSaltUnit')?.value || undefined,
      citricDefaultUnit: document.getElementById('additiveCitricUnit')?.value || undefined,
      lactateCategoryName: document.getElementById('additiveLactateCategory')?.value || undefined,
      sugarCategoryName: document.getElementById('additiveSugarCategory')?.value || undefined,
      saltCategoryName: document.getElementById('additiveSaltCategory')?.value || undefined,
      citricCategoryName: document.getElementById('additiveCitricCategory')?.value || undefined,
    };
  }

  function getLyeTypeForCitric(){
    const selected = document.querySelector('input[name="lye_type"]:checked')?.value || 'NaOH';
    return selected === 'NaOH' ? 'NaOH' : 'KOH';
  }

  function computeAdditiveOutputs(totalOils){
    const baseOils = clamp(toNumber(totalOils), 0);
    const lactatePct = clamp(readAdditivePct({ pctId: 'additiveLactatePct', weightId: 'additiveLactateWeight' }), 0);
    const sugarPct = clamp(readAdditivePct({ pctId: 'additiveSugarPct', weightId: 'additiveSugarWeight' }), 0);
    const saltPct = clamp(readAdditivePct({ pctId: 'additiveSaltPct', weightId: 'additiveSaltWeight' }), 0);
    const citricPct = clamp(readAdditivePct({ pctId: 'additiveCitricPct', weightId: 'additiveCitricWeight' }), 0);
    const lactateG = baseOils * (lactatePct / 100);
    const sugarG = baseOils * (sugarPct / 100);
    const saltG = baseOils * (saltPct / 100);
    const citricG = baseOils * (citricPct / 100);
    const citricFactor = getLyeTypeForCitric() === 'KOH'
      ? (CITRIC_LYE_FACTORS?.KOH ?? 0.71)
      : (CITRIC_LYE_FACTORS?.NaOH ?? 0.624);
    return {
      lactatePct,
      sugarPct,
      saltPct,
      citricPct,
      lactateG,
      sugarG,
      saltG,
      citricG,
      citricLyeG: citricG * citricFactor,
    };
  }

  function syncAdditivePair({ pctId, weightId, sourceField, totalOils }){
    const pctInput = document.getElementById(pctId);
    const weightInput = document.getElementById(weightId);
    if (!pctInput || !weightInput) return;
    const target = clamp(toNumber(totalOils), 0);
    if (target <= 0) return;
    if (sourceField === 'weight') {
      const weightRaw = weightInput.value;
      if (weightRaw === '' || weightRaw === null || weightRaw === undefined) {
        pctInput.value = '';
        return;
      }
      const grams = clamp(toGrams(weightRaw), 0);
      const pct = grams > 0 ? (grams / target) * 100 : 0;
      pctInput.value = pct > 0 ? round(pct, 2) : '';
      return;
    }
    const pctRaw = pctInput.value;
    if (pctRaw === '' || pctRaw === null || pctRaw === undefined) {
      weightInput.value = '';
      return;
    }
    const pct = clamp(toNumber(pctRaw), 0);
    const grams = target * (pct / 100);
    weightInput.value = grams > 0 ? round(fromGrams(grams), 2) : '';
  }

  function applyComputedOutputs(outputs){
    const setOutput = (id, value) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (el.tagName === 'INPUT') {
        if (document.activeElement === el) return;
        el.value = value;
      } else {
        el.textContent = value;
      }
    };
    const toDisplay = (grams) => (grams > 0 ? round(fromGrams(grams), 2) : '');
    setOutput('additiveLactateWeight', toDisplay(toNumber(outputs?.lactateG)));
    setOutput('additiveSugarWeight', toDisplay(toNumber(outputs?.sugarG)));
    setOutput('additiveSaltWeight', toDisplay(toNumber(outputs?.saltG)));
    setOutput('additiveCitricWeight', toDisplay(toNumber(outputs?.citricG)));
    setOutput('additiveCitricLyeOut', formatWeight(toNumber(outputs?.citricLyeG)));
  }

  function updateAdditivesOutput(totalOils){
    const expectedOils = clamp(toNumber(totalOils), 0);
    const outputs = computeAdditiveOutputs(expectedOils);
    applyComputedOutputs(outputs);
    return outputs;
  }

  function attachFragranceTypeahead(row){
    const input = row.querySelector('.fragrance-typeahead');
    const hidden = row.querySelector('.fragrance-gi-id');
    const hiddenUnit = row.querySelector('.fragrance-default-unit');
    const hiddenCategory = row.querySelector('.fragrance-category');
    const list = row.querySelector('[data-role="suggestions"]');
    if (!input || !list || typeof window.attachMergedInventoryGlobalTypeahead !== 'function') return;
    const builder = buildSoapcalcSearchBuilder();
    window.attachMergedInventoryGlobalTypeahead({
      inputEl: input,
      listEl: list,
      mode: 'public',
      giHiddenEl: hidden,
      includeInventory: false,
      includeGlobal: true,
      ingredientFirst: false,
      globalUrlBuilder: builder,
      searchType: 'ingredient',
      resultFilter: (item, source) => {
        const category = getItemCategoryName(item);
        if (!category) return source === 'inventory';
        return FRAGRANCE_CATEGORY_SET.has(category);
      },
      requireHidden: false,
      onSelection: function(picked){
        if (hiddenUnit) hiddenUnit.value = picked?.default_unit || '';
        if (hiddenCategory) hiddenCategory.value = picked?.ingredient_category_name || '';
        SoapTool.storage.queueStateSave();
      }
    });
    input.addEventListener('input', function(){
      if (!this.value.trim()) {
        if (hiddenUnit) hiddenUnit.value = '';
        if (hiddenCategory) hiddenCategory.value = '';
      }
    });
  }

  function buildFragranceRow(){
    const template = document.getElementById('fragranceRowTemplate');
    const row = template?.content?.querySelector('.fragrance-row')?.cloneNode(true);
    if (!row) return document.createElement('div');
    row.querySelectorAll('input').forEach(input => {
      input.value = '';
    });
    attachFragranceTypeahead(row);
    row.querySelectorAll('.unit-suffix').forEach(el => {
      el.dataset.suffix = state.currentUnit;
    });
    return row;
  }

  function updateFragranceTotals(totalOils){
    const rows = Array.from(document.querySelectorAll('#fragranceRows .fragrance-row'));
    const target = clamp(totalOils || SoapTool.oils.getTotalOilsGrams() || 0, 0);
    let totalGrams = 0;
    let totalPct = 0;
    rows.forEach(row => {
      const gramsInput = row.querySelector('.fragrance-grams');
      const pctInput = row.querySelector('.fragrance-percent');
      if (!gramsInput || !pctInput) return;
      const gramsRaw = gramsInput.value;
      const pctRaw = pctInput.value;
      let effectiveGrams = toGrams(gramsRaw);
      let effectivePct = clamp(toNumber(pctRaw), 0);
      const lastEdit = SoapTool.state.lastFragranceEdit;
      const editedField = (lastEdit && lastEdit.row === row) ? lastEdit.field : null;
      if (target > 0) {
        if (editedField === 'percent') {
          effectiveGrams = target * (effectivePct / 100);
          gramsInput.value = effectiveGrams > 0 ? round(fromGrams(effectiveGrams), 2) : '';
        } else if (editedField === 'grams') {
          effectivePct = (effectiveGrams / target) * 100;
          pctInput.value = effectivePct > 0 ? round(effectivePct, 2) : '';
        } else if (effectiveGrams > 0) {
          effectivePct = (effectiveGrams / target) * 100;
          if (document.activeElement !== pctInput) {
            pctInput.value = round(effectivePct, 2);
          }
        } else if (effectivePct > 0) {
          effectiveGrams = target * (effectivePct / 100);
          if (document.activeElement !== gramsInput) {
            gramsInput.value = round(fromGrams(effectiveGrams), 2);
          }
        }
      }
      if (effectiveGrams > 0) totalGrams += effectiveGrams;
      totalPct += effectivePct;
    });
    const totalPctEl = document.getElementById('fragrancePercentTotal');
    if (totalPctEl) totalPctEl.textContent = round(totalPct, 2);
    const totalWeightEl = document.getElementById('fragranceTotalComputed');
    if (totalWeightEl) totalWeightEl.textContent = totalGrams > 0 ? formatWeight(totalGrams) : '--';
    return { totalGrams, totalPct };
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
      let grams = toGrams(gramsInput);
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

  function collectFragranceData(){
    const rows = [];
    document.querySelectorAll('#fragranceRows .fragrance-row').forEach(row => {
      const name = row.querySelector('.fragrance-typeahead')?.value?.trim() || '';
      const grams = row.querySelector('.fragrance-grams')?.value || '';
      const percent = row.querySelector('.fragrance-percent')?.value || '';
      const gi = row.querySelector('.fragrance-gi-id')?.value || '';
      const defaultUnit = row.querySelector('.fragrance-default-unit')?.value || '';
      const categoryName = row.querySelector('.fragrance-category')?.value || '';
      if (!name && !grams && !percent && !gi) return;
      rows.push({
        name,
        grams,
        percent,
        gi,
        defaultUnit,
        categoryName,
      });
    });
    return rows;
  }

  function updateVisualGuidance(data){
    const tips = Array.isArray(data?.tips) && data.tips.length
      ? data.tips
      : [];
    if (!tips.length) {
      SoapTool.guidance?.clearSection('visual-guidance');
      return;
    }
    SoapTool.guidance?.setSection('visual-guidance', {
      title: 'Visual guidance',
      tone: 'info',
      items: tips,
    });
  }

  function getItemCategoryName(item){
    if (!item || typeof item !== 'object') return null;
    return (item.ingredient && item.ingredient.ingredient_category_name)
      || item.ingredient_category_name
      || (item.ingredient_category && item.ingredient_category.name)
      || null;
  }

  SoapTool.additives = {
    attachAdditiveTypeahead,
    collectAdditiveSettings,
    syncAdditivePair,
    applyComputedOutputs,
    updateAdditivesOutput,
    updateVisualGuidance,
  };
  SoapTool.fragrances = {
    buildFragranceRow,
    updateFragranceTotals,
    collectFragranceRows,
    collectFragranceData,
  };
})(window);
