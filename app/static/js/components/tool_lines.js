(function(window){
  'use strict';

  function buildToolLineRow(kind, options){
    var context = (options && options.context) || 'public';
    var unitOptionsHtml = (options && options.unitOptionsHtml) || '';

    var row = document.createElement('div');
    row.className = 'row g-2 align-items-end mb-2';
    row.innerHTML = [
      '<div class="col-md-6">',
      '  <label class="form-label">', (kind === 'container' ? 'Container' : (kind === 'consumable' ? 'Consumable' : 'Ingredient')), '</label>',
      '  <div class="position-relative">',
      '    <input type="text" class="form-control tool-typeahead" placeholder="Search global..." autocomplete="off">',
      '    <input type="hidden" class="tool-gi-id">',
      '    <div class="list-group position-absolute w-100 d-none" data-role="suggestions"></div>',
      '  </div>',
      '</div>',
      '<div class="col-md-3 ', (kind==='container'?'d-none':''), '">',
      '  <label class="form-label">Quantity</label>',
      '  <input type="number" step="0.01" min="0" class="form-control tool-qty">',
      '</div>',
      '<div class="col-md-3 ', (kind==='container'?'d-none':''), '">',
      '  <label class="form-label">Unit</label>',
      '  <select class="form-select tool-unit">',
           unitOptionsHtml,
      '  </select>',
      '</div>',
      '<div class="col-md-3 ', (kind!=='container'?'d-none':''), '">',
      '  <label class="form-label">Count</label>',
      '  <input type="number" min="1" step="1" class="form-control tool-qty">',
      '</div>',
      '<div class="col-md-2 d-grid">',
      '  <button type="button" class="btn btn-outline-danger tool-remove">Remove</button>',
      '</div>'
    ].join('');

    var input = row.querySelector('.tool-typeahead');
    var giHidden = row.querySelector('.tool-gi-id');
    var list = row.querySelector('[data-role="suggestions"]');

    if (typeof window.attachMergedInventoryGlobalTypeahead === 'function'){
      const searchType = kind === 'container' ? 'container' : (kind === 'consumable' ? 'consumable' : 'ingredient');
      const includeInventory = context !== 'public';
      window.attachMergedInventoryGlobalTypeahead({
        inputEl: input,
        giHiddenEl: giHidden,
        listEl: list,
        mode: 'recipe',
        context: context,
        ingredientFirst: kind === 'ingredient',
        searchType,
        includeInventory,
        includeGlobal: true
      });
    }
    row.querySelector('.tool-remove').addEventListener('click', function(){ row.remove(); });
    return row;
  }

  window.buildToolLineRow = buildToolLineRow;

})(window);
