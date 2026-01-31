(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { toNumber, round, clamp } = SoapTool.helpers;
  const { formatWeight, toGrams, fromGrams } = SoapTool.units;
  const { computeAdditives } = SoapTool.calc;
  const { FRAGRANCE_CATEGORY_SET } = SoapTool.constants;
  const state = SoapTool.state;

  function attachAdditiveTypeahead(inputId, hiddenId, categorySet){
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const list = input?.parentElement?.querySelector('[data-role="suggestions"]');
    if (!input || !list || typeof window.attachMergedInventoryGlobalTypeahead !== 'function') return;
    window.attachMergedInventoryGlobalTypeahead({
      inputEl: input,
      listEl: list,
      mode: 'public',
      giHiddenEl: hidden,
      includeInventory: false,
      includeGlobal: true,
      ingredientFirst: false,
      searchType: 'ingredient',
      resultFilter: (item, source) => {
        const category = getItemCategoryName(item);
        if (!category) return source === 'inventory';
        return categorySet.has(category);
      },
      requireHidden: false,
      onSelection: function(){
        SoapTool.storage.queueStateSave();
      }
    });
  }

  function updateAdditivesOutput(totalOils){
    const lyeType = SoapTool.runner.getLyeSelection().lyeType || 'NaOH';
    const fragranceTotals = SoapTool.fragrances?.updateFragranceTotals
      ? SoapTool.fragrances.updateFragranceTotals(totalOils)
      : { totalPct: toNumber(document.getElementById('additiveFragrancePct')?.value), totalGrams: 0 };
    const percents = {
      fragrancePct: clamp(fragranceTotals.totalPct, 0, 100),
      lactatePct: toNumber(document.getElementById('additiveLactatePct').value),
      sugarPct: toNumber(document.getElementById('additiveSugarPct').value),
      saltPct: toNumber(document.getElementById('additiveSaltPct').value),
      citricPct: toNumber(document.getElementById('additiveCitricPct').value),
    };
    const outputs = computeAdditives(totalOils || 0, lyeType, percents);
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
    setOutput('additiveLactateWeight', toDisplay(outputs.lactateG));
    setOutput('additiveSugarWeight', toDisplay(outputs.sugarG));
    setOutput('additiveSaltWeight', toDisplay(outputs.saltG));
    setOutput('additiveCitricWeight', toDisplay(outputs.citricG));
    setOutput('additiveCitricLyeOut', formatWeight(outputs.citricLyeG));
    return outputs;
  }

  function attachFragranceTypeahead(row){
    const input = row.querySelector('.fragrance-typeahead');
    const hidden = row.querySelector('.fragrance-gi-id');
    const list = row.querySelector('[data-role="suggestions"]');
    if (!input || !list || typeof window.attachMergedInventoryGlobalTypeahead !== 'function') return;
    window.attachMergedInventoryGlobalTypeahead({
      inputEl: input,
      listEl: list,
      mode: 'public',
      giHiddenEl: hidden,
      includeInventory: false,
      includeGlobal: true,
      ingredientFirst: false,
      searchType: 'ingredient',
      resultFilter: (item, source) => {
        const category = getItemCategoryName(item);
        if (!category) return source === 'inventory';
        return FRAGRANCE_CATEGORY_SET.has(category);
      },
      requireHidden: false,
      onSelection: function(){
        SoapTool.storage.queueStateSave();
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
      let grams = toGrams(gramsInput?.value);
      let pct = clamp(toNumber(pctInput?.value), 0);
      if (target > 0) {
        if (state.lastFragranceEdit && state.lastFragranceEdit.row === row && state.lastFragranceEdit.field === 'percent') {
          grams = pct > 0 ? target * (pct / 100) : 0;
          if (gramsInput) gramsInput.value = grams > 0 ? round(fromGrams(grams), 2) : '';
        } else {
          if (grams > 0) {
            pct = (grams / target) * 100;
            if (pctInput) pctInput.value = round(pct, 2);
          } else if (pct > 0) {
            grams = target * (pct / 100);
            if (gramsInput) gramsInput.value = round(fromGrams(grams), 2);
          }
        }
        totalPct += pct;
      } else {
        totalPct += pct;
      }
      if (grams > 0) totalGrams += grams;
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
      if (!name && !grams && !percent && !gi) return;
      rows.push({ name, grams, percent, gi });
    });
    return rows;
  }

  function updateVisualGuidance(data){
    const list = document.getElementById('soapVisualGuidanceList');
    if (!list) return;
    const tips = [];
    const waterConc = data?.waterData?.lyeConcentration || 0;
    const additives = data?.additives || {};
    const fattyPercent = data?.fattyPercent || {};
    const lauricMyristic = (fattyPercent.lauric || 0) + (fattyPercent.myristic || 0);

    if (waterConc > 0 && waterConc < 28) {
      tips.push('High water can cause soda ash, warping, or glycerin rivers; keep temps even or use less water.');
    }
    if (waterConc > 40) {
      tips.push('Low water (strong lye) can overheat or crack; soap cooler and watch for volcanoing.');
    }
    if (additives.sugarPct > 1) {
      tips.push('Sugars add heat; soap cooler to avoid cracking or glycerin rivers.');
    }
    if (additives.saltPct > 1) {
      tips.push('Salt can make bars brittle; cut sooner than usual.');
    }
    if (lauricMyristic > 35) {
      tips.push('High lauric oils can crumble if cut cold; cut warm for clean edges.');
    }
    if (!tips.length) {
      tips.push('No visual flags detected for this formula.');
    }

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
    updateAdditivesOutput,
    updateVisualGuidance,
  };
  SoapTool.fragrances = {
    buildFragranceRow,
    updateFragranceTotals,
    collectFragranceData,
  };
})(window);
