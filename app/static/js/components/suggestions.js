// Shared suggestion helper for merged inventory + global item search
// Usage examples:
// attachMergedInventoryGlobalTypeahead({ inputEl, invHiddenEl, giHiddenEl, listEl, mode: 'recipe' });
// attachMergedInventoryGlobalTypeahead({ inputEl, giHiddenEl, listEl, mode: 'inventory_create' });

(function(window){
  'use strict';

  function debounce(fn, wait){
    var t;
    return function(){
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function(){ fn.apply(ctx, args); }, wait);
    };
  }

  function normalizedName(value){
    return (value || '').trim().toLowerCase();
  }

  function ensureListContainer(listEl){
    if (listEl) return listEl;
    var div = document.createElement('div');
    div.className = 'list-group position-absolute w-100 d-none';
    return div;
  }

  function renderSuggestions(listEl, groups, onPick){
    listEl.innerHTML = '';
    var hasAny = false;
    groups.forEach(function(group){
      if (!group.items || !group.items.length) return;
      hasAny = true;
      var header = document.createElement('div');
      header.className = 'list-group-item text-muted small';
      header.textContent = group.title;
      listEl.appendChild(header);

      group.items.forEach(function(r){
        var a = document.createElement('a');
        a.href = '#';
        a.className = 'list-group-item list-group-item-action';
        a.textContent = r.text;
        a.addEventListener('click', function(e){
          e.preventDefault();
          onPick(r, group.source);
          listEl.classList.add('d-none');
          listEl.innerHTML = '';
        });
        listEl.appendChild(a);
      });
    });
    listEl.classList.toggle('d-none', !hasAny);
  }

  function attachMergedInventoryGlobalTypeahead(options){
    var inputEl = options && options.inputEl;
    var invHiddenEl = options && options.invHiddenEl;
    var giHiddenEl = options && options.giHiddenEl;
    var listEl = ensureListContainer(options && options.listEl);
    var mode = (options && options.mode) || 'recipe'; // 'recipe' or 'inventory_create'
    var context = (options && options.context) || 'customer'; // 'customer' or 'public'
    var itemType = (options && options.itemType) || 'ingredient';

    if (!inputEl || (!invHiddenEl && mode === 'recipe') || !giHiddenEl) return;

    // Insert listEl if not already in DOM
    if (!listEl.parentNode && inputEl.parentNode) {
      inputEl.parentNode.appendChild(listEl);
    }

    var doSearch = debounce(function(){
      var q = (inputEl.value || '').trim();
      if (!q){
        listEl.classList.add('d-none');
        listEl.innerHTML = '';
        return;
      }
      var invPromise;
      var giPromise;
      if (context === 'public'){
        // Public context: no inventory; global-only public endpoint
        invPromise = Promise.resolve({ results: [] });
        giPromise = fetch('/api/public/global-items/search?q=' + encodeURIComponent(q) + '&type=' + encodeURIComponent(itemType))
          .then(function(r){ return r.json(); })
          .catch(function(){ return { results: [] }; });
      } else {
        invPromise = fetch('/api/ingredients/ingredients/search?q=' + encodeURIComponent(q) + '&type=' + encodeURIComponent(itemType))
          .then(function(r){ return r.json(); })
          .catch(function(){ return { results: [] }; });
        giPromise = fetch('/api/ingredients/global-items/search?q=' + encodeURIComponent(q) + '&type=' + encodeURIComponent(itemType))
          .then(function(r){ return r.json(); })
          .catch(function(){ return { results: [] }; });
      }

      Promise.all([invPromise, giPromise]).then(function(results){
        var inv = results[0] || {results: []};
        var gi = results[1] || {results: []};
        var invResults = inv.results || [];
        var giResults = gi.results || [];

        // Build maps for dedupe
        var invByGlobalId = new Map();
        var invByName = new Map();
        invResults.forEach(function(r){
          if (r.global_item_id) invByGlobalId.set(String(r.global_item_id), r);
          invByName.set(normalizedName(r.text), r);
        });

        // Filter globals not already represented in inventory
        var giFiltered = giResults.filter(function(r){
          var coveredByGlobalId = invByGlobalId.has(String(r.id));
          var coveredByName = invByName.has(normalizedName(r.text));
          return !(coveredByGlobalId || coveredByName);
        });

        // Build groups based on mode
        var groups = [];
        if (mode === 'recipe') {
          if (invResults.length) groups.push({ title: 'Your Inventory', items: invResults, source: 'inventory' });
          if (giFiltered.length) groups.push({ title: 'Global Library', items: giFiltered, source: 'global' });
        } else if (mode === 'inventory_create') {
          if (giFiltered.length) groups.push({ title: 'Global Library', items: giFiltered, source: 'global' });
        }

        renderSuggestions(listEl, groups, function(picked, source){
          inputEl.value = picked.text;
          if (source === 'inventory'){
            if (invHiddenEl) invHiddenEl.value = picked.id_numeric || picked.id || '';
            if (giHiddenEl) giHiddenEl.value = '';
          } else {
            if (giHiddenEl) giHiddenEl.value = picked.id;
            if (invHiddenEl) invHiddenEl.value = '';
          }
        });
      }).catch(function(){
        listEl.classList.add('d-none');
      });
    }, 250);

    inputEl.addEventListener('input', function(){
      // Clear selection on new typing
      if (invHiddenEl) invHiddenEl.value = '';
      if (giHiddenEl) giHiddenEl.value = '';
      doSearch();
    });

    // Public context: ensure units are from seeded global list in UIs that use it
    // Note: Unit dropdowns elsewhere already use get_global_unit_list via template context

    document.addEventListener('click', function(e){
      if (!listEl.contains(e.target) && !inputEl.contains(e.target)){
        listEl.classList.add('d-none');
      }
    });
  }

  // export
  window.attachMergedInventoryGlobalTypeahead = attachMergedInventoryGlobalTypeahead;

})(window);

