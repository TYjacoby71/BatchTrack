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

    function renderSuggestions(listEl, groups, onPick, opts){
    opts = opts || {};
    if (opts.ingredientFirst){
      renderIngredientFirst(listEl, groups, onPick);
      return;
    }

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
          var primaryLabel = r.text || '';
          var metaBits = [];
          if (r.ingredient_name && r.ingredient_name !== primaryLabel) {
            metaBits.push(r.ingredient_name);
          }
          if (r.physical_form_name) {
            metaBits.push(r.physical_form_name);
          }
          if (r.default_unit) {
            metaBits.push('Unit: ' + r.default_unit);
          }
          if (typeof r.density === 'number') {
            metaBits.push('Density: ' + r.density.toFixed(3) + ' g/ml');
          }
          a.innerHTML = '<div class="fw-semibold">' + primaryLabel + '</div>' +
            (metaBits.length ? '<div class="small text-muted">' + metaBits.join(' • ') + '</div>' : '');
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

  function buildFormMeta(form){
    var meta = [];
    if (typeof form.cost_per_unit === 'number'){
      var unitLabel = form.default_unit || 'unit';
      meta.push('$' + form.cost_per_unit.toFixed(2) + '/' + unitLabel);
    }
    if (form.default_unit){
      meta.push('Unit: ' + form.default_unit);
    }
    if (typeof form.density === 'number'){
      meta.push('Density: ' + form.density.toFixed(3) + ' g/ml');
    }
    if (typeof form.recommended_shelf_life_days === 'number'){
      meta.push('Shelf life: ' + form.recommended_shelf_life_days + ' days');
    }
    return meta.join(' • ');
  }

  function renderIngredientFirst(listEl, groups, onPick){
    listEl.innerHTML = '';
    var hasAny = false;

    groups.forEach(function(group){
      if (!group.ingredients || !group.ingredients.length) return;
      hasAny = true;

      var header = document.createElement('div');
      header.className = 'list-group-item text-muted small fw-semibold';
      header.textContent = group.title;
      listEl.appendChild(header);

      group.ingredients.forEach(function(ingredient){
        var itemEl = document.createElement('div');
        itemEl.className = 'list-group-item ingredient-result';

        var summary = document.createElement('div');
        summary.className = 'd-flex justify-content-between align-items-center ingredient-summary py-1';
        summary.setAttribute('role', 'button');
        summary.setAttribute('tabindex', '0');
        summary.innerHTML = '<span class="fw-semibold">' + (ingredient.name || 'Ingredient') + '</span>' +
          '<span class="badge bg-light text-dark">' + ingredient.forms.length + ' form' + (ingredient.forms.length === 1 ? '' : 's') + '</span>';
        summary.style.cursor = 'pointer';

        var formsContainer = document.createElement('div');
        formsContainer.className = 'ingredient-form-options d-none mt-2 ps-3 border-start border-2';
        ingredient.forms.forEach(function(form){
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'btn btn-sm btn-outline-primary w-100 text-start mb-2 ingredient-form-option';
          var primaryLabel = form.ingredient_name || ingredient.name || form.text || 'Ingredient';
          if (form.physical_form_name){
            primaryLabel += ' — ' + form.physical_form_name;
          }
          var meta = buildFormMeta(form);
          btn.innerHTML = '<div class="fw-semibold">' + primaryLabel + '</div>' +
            (meta ? '<div class="small text-muted">' + meta + '</div>' : '');
          btn.addEventListener('click', function(){
            onPick(form, form.source || group.source);
            listEl.classList.add('d-none');
            listEl.innerHTML = '';
          });
          formsContainer.appendChild(btn);
        });

        function toggleForms(e){
          if (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ') return;
          e.preventDefault();
          formsContainer.classList.toggle('d-none');
        }

        summary.addEventListener('click', toggleForms);
        summary.addEventListener('keydown', toggleForms);

        itemEl.appendChild(summary);
        itemEl.appendChild(formsContainer);
        listEl.appendChild(itemEl);

        if (ingredient.forms.length === 1){
          formsContainer.classList.remove('d-none');
        }
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
    var ingredientFirst = !!(options && options.ingredientFirst);
    var onSelection = options && options.onSelection;

    if (!inputEl || (!invHiddenEl && mode === 'recipe') || !giHiddenEl) return;

    // Insert listEl if not already in DOM
    if (!listEl.parentNode && inputEl.parentNode) {
      inputEl.parentNode.appendChild(listEl);
    }

    function expandGlobalItems(items){
        var expanded = [];
        (items || []).forEach(function(item){
        if (item && Array.isArray(item.forms) && item.forms.length){
          var baseIngredientName = (item.ingredient && item.ingredient.name) || item.ingredient_name || null;
          item.forms.forEach(function(form){
            var physical = form.physical_form || {};
            var display = form.display_name || form.text || form.name || (baseIngredientName && (physical && physical.name) ? (baseIngredientName + ' (' + physical.name + ')') : (item.display_name || item.text || item.name || ''));
              expanded.push({
              id: form.id,
              text: display,
              item_type: form.item_type || item.item_type,
              default_unit: form.default_unit || form.unit || item.default_unit || item.unit || null,
              density: typeof form.density === 'number' ? form.density : item.density,
                global_item_id: form.id,
              ingredient_id: form.ingredient_id || (item.ingredient && item.ingredient.id) || item.ingredient_id || null,
              ingredient_name: form.ingredient_name || baseIngredientName,
              physical_form_id: form.physical_form_id || (physical && physical.id) || null,
              physical_form_name: form.physical_form_name || (physical && physical.name) || null,
              physical_form_slug: physical.slug || null,
              aliases: form.aliases || item.aliases || [],
              certifications: form.certifications || item.certifications || [],
              default_is_perishable: form.default_is_perishable,
              recommended_shelf_life_days: form.recommended_shelf_life_days,
              recommended_usage_rate: form.recommended_usage_rate || item.recommended_usage_rate,
              recommended_fragrance_load_pct: form.recommended_fragrance_load_pct || item.recommended_fragrance_load_pct,
              functions: form.functions || item.functions || [],
              applications: form.applications || item.applications || [],
            });
          });
        } else if (item) {
          var displayName = item.display_name || item.text || item.name || '';
          var clone = Object.assign({}, item);
          clone.text = displayName;
          if (!clone.ingredient_name && item.ingredient && item.ingredient.name) {
            clone.ingredient_name = item.ingredient.name;
          }
          if (!clone.physical_form_name && item.physical_form && item.physical_form.name) {
            clone.physical_form_name = item.physical_form.name;
          }
          if (!clone.default_unit && item.unit) {
            clone.default_unit = item.unit;
          }
            clone.global_item_id = item.id;
            expanded.push(clone);
        }
        });
        return expanded;
      }

  function groupInventoryByIngredient(items){
    var map = new Map();
    (items || []).forEach(function(item){
      var baseName = item.ingredient_name || item.text || item.name || '';
      var key = item.ingredient_id ? ('id:' + item.ingredient_id) : ('name:' + normalizedName(baseName));
      var entry = map.get(key);
      if (!entry){
        entry = {
          ingredient_id: item.ingredient_id || null,
          name: baseName,
          forms: [],
        };
        map.set(key, entry);
      }
      entry.forms.push({
        id: item.id_numeric || item.id,
        id_numeric: item.id_numeric || item.id,
        text: baseName + (item.physical_form_name ? ' (' + item.physical_form_name + ')' : ''),
        ingredient_name: baseName,
        physical_form_name: item.physical_form_name || null,
        default_unit: item.unit || item.default_unit || null,
        density: item.density,
        cost_per_unit: item.cost_per_unit,
        source: 'inventory',
        global_item_id: item.global_item_id || null,
        item_type: item.type,
      });
    });
    return Array.from(map.values());
  }

  function groupGlobalByIngredient(rawGroups, allowedIds){
    var groups = [];
    (rawGroups || []).forEach(function(group){
      var forms = (group.forms || []).filter(function(form){
        if (!allowedIds) return true;
        return allowedIds.has(String(form.id));
      }).map(function(form){
        var ingredientName = group.name || (group.ingredient && group.ingredient.name) || form.ingredient_name || form.name;
        return {
          id: form.id,
          text: ingredientName + (form.physical_form_name ? ' (' + form.physical_form_name + ')' : ''),
          ingredient_name: ingredientName,
          physical_form_name: form.physical_form_name || null,
          default_unit: form.default_unit || form.unit || null,
          density: form.density,
          default_is_perishable: form.default_is_perishable,
          recommended_shelf_life_days: form.recommended_shelf_life_days,
          source: 'global',
          global_item_id: form.id,
        };
      });
      if (forms.length){
        groups.push({
          ingredient_id: group.ingredient_id || group.id || null,
          name: group.name || (group.ingredient && group.ingredient.name) || (forms[0] && forms[0].ingredient_name) || 'Ingredient',
          forms: forms,
        });
      }
    });
    return groups;
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
          giPromise = fetch('/api/public/global-items/search?q=' + encodeURIComponent(q) + '&type=ingredient&group=ingredient')
          .then(function(r){ return r.json(); })
          .catch(function(){ return { results: [] }; });
      } else {
        invPromise = fetch('/api/ingredients/ingredients/search?q=' + encodeURIComponent(q))
          .then(function(r){ return r.json(); })
          .catch(function(){ return { results: [] }; });
          giPromise = fetch('/api/ingredients/global-items/search?q=' + encodeURIComponent(q) + '&type=ingredient&group=ingredient')
          .then(function(r){ return r.json(); })
          .catch(function(){ return { results: [] }; });
      }

      Promise.all([invPromise, giPromise]).then(function(results){
        var inv = results[0] || {results: []};
        var gi = results[1] || {results: []};
        var invResults = inv.results || [];
          var giResults = expandGlobalItems(gi.results || []);

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

        if (ingredientFirst){
          var allowedGlobalIds = new Set(giFiltered.map(function(r){ return String(r.id); }));
          var inventoryGroups = mode === 'recipe' ? groupInventoryByIngredient(invResults) : [];
          var globalGroups = groupGlobalByIngredient(gi.results || [], allowedGlobalIds);
          var ingredientGroups = [];
          if (inventoryGroups.length && mode === 'recipe'){
            ingredientGroups.push({ title: 'Your Inventory', source: 'inventory', ingredients: inventoryGroups });
          }
          if (globalGroups.length){
            ingredientGroups.push({ title: 'Global Library', source: 'global', ingredients: globalGroups });
          }
          renderSuggestions(listEl, ingredientGroups, function(picked, source){
            inputEl.value = picked.text;
            if (source === 'inventory'){
              if (invHiddenEl) invHiddenEl.value = picked.id_numeric || picked.id || '';
              if (giHiddenEl) giHiddenEl.value = '';
            } else {
              if (giHiddenEl) giHiddenEl.value = picked.id;
              if (invHiddenEl) invHiddenEl.value = '';
            }
            if (typeof onSelection === 'function'){
              onSelection(picked, source);
            }
          }, { ingredientFirst: true });
          return;
        }

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
          if (typeof onSelection === 'function'){
            onSelection(picked, source);
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

