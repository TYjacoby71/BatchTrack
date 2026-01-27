(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { toNumber } = SoapTool.helpers;
  const { formatWeight } = SoapTool.units;
  const { computeAdditives } = SoapTool.calc;

  function attachAdditiveTypeahead(inputId, hiddenId, categorySet){
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const list = input?.parentElement?.querySelector('[data-role="suggestions"]');
    if (!input || !list || typeof window.attachMergedInventoryGlobalTypeahead !== 'function') return;
    window.attachMergedInventoryGlobalTypeahead({
      inputEl: input,
      listEl: list,
      mode: SoapTool.config.isAuthenticated ? 'recipe' : 'public',
      giHiddenEl: hidden,
      includeInventory: SoapTool.config.isAuthenticated,
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
    const percents = {
      fragrancePct: toNumber(document.getElementById('additiveFragrancePct').value),
      lactatePct: toNumber(document.getElementById('additiveLactatePct').value),
      sugarPct: toNumber(document.getElementById('additiveSugarPct').value),
      saltPct: toNumber(document.getElementById('additiveSaltPct').value),
      citricPct: toNumber(document.getElementById('additiveCitricPct').value),
    };
    const outputs = computeAdditives(totalOils || 0, lyeType, percents);
    document.getElementById('additiveFragranceOut').textContent = formatWeight(outputs.fragranceG);
    document.getElementById('additiveLactateOut').textContent = formatWeight(outputs.lactateG);
    document.getElementById('additiveSugarOut').textContent = formatWeight(outputs.sugarG);
    document.getElementById('additiveSaltOut').textContent = formatWeight(outputs.saltG);
    document.getElementById('additiveCitricOut').textContent = formatWeight(outputs.citricG);
    document.getElementById('additiveCitricLyeOut').textContent = formatWeight(outputs.citricLyeG);
    return outputs;
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
})(window);
