(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};

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

  function cloneCalcWithoutExport(calc){
    if (!calc || typeof calc !== 'object') return null;
    try {
      const cloned = JSON.parse(JSON.stringify(calc));
      if (cloned && typeof cloned === 'object') {
        delete cloned.export;
      }
      return cloned;
    } catch (_) {
      return null;
    }
  }

  function buildSoapRecipePayloadRequest(calc){
    const calcSnapshot = cloneCalcWithoutExport(calc);
    if (!calcSnapshot) return null;
    const qualityPreset = document.getElementById('qualityPreset')?.value || 'balanced';
    const qualityFocus = Array.from(document.querySelectorAll('.quality-focus:checked'))
      .map(el => el.id);
    const mold = SoapTool.mold?.getMoldSettings ? SoapTool.mold.getMoldSettings() : null;
    return {
      calc: calcSnapshot,
      draft_lines: {
        ingredients: collectDraftLines('tool-ingredients', 'ingredient'),
        consumables: collectDraftLines('tool-consumables', 'consumable'),
        containers: collectDraftLines('tool-containers', 'container'),
      },
      context: {
        source: 'soap_tool',
        schema_version: 1,
        unit_display: SoapTool.state.currentUnit || 'g',
        input_mode: 'mixed',
        quality_preset: qualityPreset,
        quality_focus: qualityFocus,
        mold,
      },
    };
  }

  SoapTool.recipePayload = {
    collectDraftLines,
    buildLineRow,
    addStubLine,
    buildSoapRecipePayloadRequest,
  };
})(window);

