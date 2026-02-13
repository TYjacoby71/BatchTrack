(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { toNumber, round, clamp, buildSoapcalcSearchBuilder } = SoapTool.helpers;
  const { formatWeight, toGrams, fromGrams } = SoapTool.units;
  const { FRAGRANCE_CATEGORY_SET } = SoapTool.constants;
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
    return {
      lactatePct: readAdditivePct({ pctId: 'additiveLactatePct', weightId: 'additiveLactateWeight' }),
      sugarPct: readAdditivePct({ pctId: 'additiveSugarPct', weightId: 'additiveSugarWeight' }),
      saltPct: readAdditivePct({ pctId: 'additiveSaltPct', weightId: 'additiveSaltWeight' }),
      citricPct: readAdditivePct({ pctId: 'additiveCitricPct', weightId: 'additiveCitricWeight' }),
      lactateName: document.getElementById('additiveLactateName')?.value?.trim() || 'Sodium Lactate',
      sugarName: document.getElementById('additiveSugarName')?.value?.trim() || 'Sugar',
      saltName: document.getElementById('additiveSaltName')?.value?.trim() || 'Salt',
      citricName: document.getElementById('additiveCitricName')?.value?.trim() || 'Citric Acid',
    };
  }

  function applyComputedOutputs(outputs){
    const setOutput = (id, value) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (el.tagName === 'INPUT') {
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
    const calc = SoapTool.state?.lastCalc;
    const calcOils = clamp(toNumber(calc?.totalOils), 0);
    const oilsMatch = Math.abs(calcOils - expectedOils) < 0.01;
    const outputs = (calc?.additives && oilsMatch)
      ? calc.additives
      : { lactateG: 0, sugarG: 0, saltG: 0, citricG: 0, citricLyeG: 0 };
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
      const grams = toGrams(gramsInput?.value);
      const pct = clamp(toNumber(pctInput?.value), 0);
      let effectiveGrams = grams;
      let effectivePct = pct;
      if (target > 0) {
        if (effectiveGrams <= 0 && effectivePct > 0) {
          effectiveGrams = target * (effectivePct / 100);
        } else if (effectivePct <= 0 && effectiveGrams > 0) {
          effectivePct = (effectiveGrams / target) * 100;
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
    const list = document.getElementById('soapVisualGuidanceList');
    if (!list) return;
    const tips = Array.isArray(data?.tips) && data.tips.length
      ? data.tips
      : ['No visual flags detected for this formula.'];
    list.innerHTML = tips.map(tip => `<li>${tip}</li>`).join('');
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
    applyComputedOutputs,
    updateAdditivesOutput,
    updateVisualGuidance,
  };
  SoapTool.fragrances = {
    buildFragranceRow,
    updateFragranceTotals,
    collectFragranceData,
  };
})(window);
