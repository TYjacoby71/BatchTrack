// Shared suggestion helper for merged inventory + global item search
// Updated to support scoped item types, compact rendering, and reusable modules across the app.

(function(window){
  'use strict';

  const SOURCE_LABELS = {
    inventory: 'Inventory',
    global: 'Global Library',
  };

  const SOURCE_BADGE_CLASS = {
    inventory: 'bg-primary',
    global: 'bg-info text-dark',
  };

  const DEFAULT_OPTIONS = {
    mode: 'recipe',
    searchType: 'ingredient',
    includeInventory: true,
    includeGlobal: true,
    ingredientFirst: false,
    displayVariant: null,
    showSourceBadge: true,
    globalUrlBuilder: null,
    globalFallbackUrlBuilder: null,
    globalFallbackMode: 'fallback',
    resultFilter: null,
  };

  function debounce(fn, wait){
    let timeout;
    return function(){
      const args = arguments;
      clearTimeout(timeout);
      timeout = setTimeout(() => fn.apply(null, args), wait);
    };
  }

  function normalizedName(value){
    return (value || '').trim().toLowerCase();
  }

  function ensureListContainer(listEl){
    if (listEl) return listEl;
    const div = document.createElement('div');
    div.className = 'list-group position-absolute w-100 d-none inventory-suggestions';
    div.style.zIndex = '1050';
    div.style.maxHeight = '300px';
    div.style.overflowY = 'auto';
    return div;
  }

  function resolveOption(value){
    return typeof value === 'function' ? value() : value;
  }

  function buildGlobalIdSet(items){
    const set = new Set();
    (items || []).forEach(item => {
      const gid = item && (item.global_item_id || item.id);
      if (gid) set.add(String(gid));
    });
    return set;
  }

  function createSourceBadge(source){
    if (!source) return '';
    const label = SOURCE_LABELS[source] || source;
    const badgeClass = SOURCE_BADGE_CLASS[source] || 'bg-secondary';
    return `<span class="badge ${badgeClass} ms-2">${label}</span>`;
  }

  function renderFlatList(listEl, groups, onPick, opts){
    opts = opts || {};
    listEl.innerHTML = '';
    let hasAny = false;
    groups.forEach(group => {
      if (!group.items || !group.items.length) return;
      hasAny = true;
      group.items.forEach(item => {
        const entry = document.createElement('a');
        entry.href = '#';
        entry.className = 'list-group-item list-group-item-action suggestion-item';
        const subtitle = opts.showSubtitle && item.subtitle
          ? `<div class="small text-muted mt-1">${item.subtitle}</div>`
          : '';
        entry.innerHTML = `<div class="d-flex justify-content-between align-items-center gap-2">
          <span class="fw-semibold text-truncate">${item.text || item.display_name || item.name || ''}</span>
          ${opts.showSourceBadge ? createSourceBadge(group.source || item.source) : ''}
        </div>${subtitle}`;
        entry.addEventListener('click', function(e){
          e.preventDefault();
          onPick(item, group.source || item.source);
          listEl.classList.add('d-none');
        });
        listEl.appendChild(entry);
      });
    });
    listEl.classList.toggle('d-none', !hasAny);
    if (!hasAny && listEl.dataset.emptyMessage) {
      const empty = document.createElement('div');
      empty.className = 'list-group-item text-muted small';
      empty.textContent = listEl.dataset.emptyMessage;
      listEl.appendChild(empty);
      listEl.classList.remove('d-none');
    }
  }

  function renderIngredientFirst(listEl, groups, onPick){
    listEl.innerHTML = '';
    let hasAny = false;

    groups.forEach(group => {
      if (!group.ingredients || !group.ingredients.length) return;
      hasAny = true;
      const header = document.createElement('div');
      header.className = 'list-group-item text-muted small fw-semibold';
      header.textContent = group.title;
      listEl.appendChild(header);

      group.ingredients.forEach(ingredient => {
        const itemEl = document.createElement('div');
        itemEl.className = 'list-group-item ingredient-result';

        const summary = document.createElement('div');
        summary.className = 'd-flex justify-content-between align-items-center ingredient-summary';
        summary.setAttribute('role', 'button');
        summary.setAttribute('tabindex', '0');
        summary.innerHTML = `<span class="fw-semibold">${ingredient.name || 'Ingredient'}</span>
          <span class="badge bg-light text-dark">${ingredient.forms.length} option${ingredient.forms.length === 1 ? '' : 's'}</span>`;

        const formsContainer = document.createElement('div');
        formsContainer.className = 'ingredient-form-options d-none mt-2 ps-3 border-start border-2';
        ingredient.forms.forEach(form => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'btn btn-sm btn-outline-primary w-100 text-start mb-2 ingredient-form-option suggestion-item';
          btn.innerHTML = `<div class="fw-semibold">${form.text || form.display_name || form.name || 'Form'}</div>`;
          btn.addEventListener('click', function(){
            onPick(form, form.source || group.source);
            listEl.classList.add('d-none');
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

  function renderDefinitionResults(listEl, items, onPick){
    listEl.innerHTML = '';
    let hasAny = false;
    (items || []).forEach(item => {
      hasAny = true;
      const entry = document.createElement('a');
      entry.href = '#';
      entry.className = 'list-group-item list-group-item-action suggestion-item';
      const meta = item.inci_name ? `<div class="small text-muted">${item.inci_name}</div>` : '';
      entry.innerHTML = `<div class="fw-semibold">${item.text || item.name}</div>${meta}`;
      entry.addEventListener('click', function(e){
        e.preventDefault();
        onPick(item, 'definition');
        listEl.classList.add('d-none');
      });
      listEl.appendChild(entry);
    });
    listEl.classList.toggle('d-none', !hasAny);
    if (!hasAny && listEl.dataset.emptyMessage) {
      const empty = document.createElement('div');
      empty.className = 'list-group-item text-muted small';
      empty.textContent = listEl.dataset.emptyMessage;
      listEl.appendChild(empty);
      listEl.classList.remove('d-none');
    }
  }

  function expandGlobalItems(items){
    const expanded = [];
    (items || []).forEach(item => {
      if (item && Array.isArray(item.forms) && item.forms.length){
        const baseIngredientName = (item.ingredient && item.ingredient.name) || item.ingredient_name || null;
        const categoryName = (item.ingredient && item.ingredient.ingredient_category_name)
          || item.ingredient_category_name
          || (item.ingredient_category && item.ingredient_category.name)
          || null;
        const categoryTags = item.category_tags || [];
        item.forms.forEach(form => {
          const physical = form.physical_form || {};
          const display = form.display_name || form.text || form.name || (baseIngredientName && form.physical_form_name ? `${baseIngredientName}, ${form.physical_form_name}` : (item.display_name || item.text || item.name || ''));
          expanded.push({
            id: form.id,
            text: display,
            item_type: form.item_type || item.item_type,
            default_unit: form.default_unit || form.unit || item.default_unit || item.unit || null,
            source: 'global',
            global_item_id: form.id,
            ingredient_id: form.ingredient_id || (item.ingredient && item.ingredient.id) || item.ingredient_id || null,
            ingredient_name: form.ingredient_name || baseIngredientName,
            physical_form_id: form.physical_form_id || (physical && physical.id) || null,
            physical_form_name: form.physical_form_name || (physical && physical.name) || null,
            ingredient_category_name: categoryName,
            category_tags: categoryTags,
            density: form.density || item.density || null,
            capacity: form.capacity || item.capacity || null,
            capacity_unit: form.capacity_unit || item.capacity_unit || null,
            container_material: form.container_material || item.container_material || null,
            container_type: form.container_type || item.container_type || null,
            container_style: form.container_style || item.container_style || null,
            container_color: form.container_color || item.container_color || null,
            default_is_perishable: form.default_is_perishable ?? item.default_is_perishable,
            recommended_shelf_life_days: form.recommended_shelf_life_days ?? item.recommended_shelf_life_days,
            saponification_value: form.saponification_value ?? item.saponification_value ?? null,
            iodine_value: form.iodine_value ?? item.iodine_value ?? null,
            fatty_acid_profile: form.fatty_acid_profile ?? item.fatty_acid_profile ?? null,
            melting_point_c: form.melting_point_c ?? item.melting_point_c ?? null,
          });
        });
      } else if (item) {
        const displayName = item.display_name || item.text || item.name || '';
        const categoryName = (item.ingredient && item.ingredient.ingredient_category_name)
          || item.ingredient_category_name
          || (item.ingredient_category && item.ingredient_category.name)
          || null;
        expanded.push({
          id: item.id,
          text: displayName,
          source: 'global',
          item_type: item.item_type,
          global_item_id: item.id,
          ingredient_name: (item.ingredient && item.ingredient.name) || item.ingredient_name || item.name,
          ingredient_category_name: categoryName,
          category_tags: item.category_tags || [],
          physical_form_name: (item.physical_form && item.physical_form.name) || item.physical_form_name || null,
          default_unit: item.default_unit || item.unit || null,
          density: item.density || null,
          capacity: item.capacity || null,
          capacity_unit: item.capacity_unit || null,
          container_material: item.container_material || null,
          container_type: item.container_type || null,
          container_style: item.container_style || null,
          container_color: item.container_color || null,
          default_is_perishable: item.default_is_perishable,
          recommended_shelf_life_days: item.recommended_shelf_life_days,
          saponification_value: item.saponification_value || null,
          iodine_value: item.iodine_value || null,
          fatty_acid_profile: item.fatty_acid_profile || null,
          melting_point_c: item.melting_point_c || null,
        });
      }
    });
    return expanded;
  }

  function groupInventoryByIngredient(items){
    const map = new Map();
    (items || []).forEach(item => {
      const baseName = item.ingredient_name || item.text || item.name || '';
      const key = item.ingredient_id ? `id:${item.ingredient_id}` : `name:${normalizedName(baseName)}`;
      const entry = map.get(key) || {
        ingredient_id: item.ingredient_id || null,
        name: baseName,
        forms: [],
      };
      entry.forms.push({
        id: item.id,
        text: item.text || baseName,
        ingredient_name: baseName,
        physical_form_name: item.physical_form_name || null,
        default_unit: item.default_unit || item.unit || null,
        source: 'inventory',
        global_item_id: item.global_item_id || null,
      });
      map.set(key, entry);
    });
    return Array.from(map.values());
  }

  function groupGlobalByIngredient(rawGroups, dedupeIds){
    const groups = [];
    (rawGroups || []).forEach(group => {
      const forms = (group.forms || []).map(form => ({
        id: form.id,
        text: form.name || form.display_name || form.text,
        ingredient_name: form.ingredient_name || group.name || (group.ingredient && group.ingredient.name) || 'Ingredient',
        physical_form_name: form.physical_form_name || null,
        default_unit: form.default_unit || form.unit || null,
        source: 'global',
        global_item_id: form.id,
        density: form.density || null,
        capacity: form.capacity || null,
        capacity_unit: form.capacity_unit || null,
        container_material: form.container_material || null,
        container_type: form.container_type || null,
        container_style: form.container_style || null,
        container_color: form.container_color || null,
        saponification_value: form.saponification_value || null,
        iodine_value: form.iodine_value || null,
        fatty_acid_profile: form.fatty_acid_profile || null,
        melting_point_c: form.melting_point_c || null,
      }));
      const filteredForms = dedupeIds
        ? forms.filter(form => !form.global_item_id || !dedupeIds.has(String(form.global_item_id)))
        : forms;
      if (filteredForms.length){
        groups.push({
          ingredient_id: group.ingredient_id || group.id || null,
          name: group.name || (group.ingredient && group.ingredient.name) || (forms[0] && forms[0].ingredient_name) || 'Ingredient',
          forms: filteredForms,
        });
      }
    });
    return groups;
  }

  function fetchIngredientDefinitions(q){
    const params = new URLSearchParams({ q });
    return fetch(`/api/ingredients/definitions/search?${params.toString()}`)
      .then(r => r.json())
      .catch(() => ({ results: [] }));
  }

  function attachMergedInventoryGlobalTypeahead(options){
    const opts = { ...DEFAULT_OPTIONS, ...options };
    const inputEl = opts.inputEl;
    const invHiddenEl = opts.invHiddenEl;
    const giHiddenEl = opts.giHiddenEl;
    const listEl = ensureListContainer(opts.listEl);
    const mode = opts.mode || 'recipe';
    const searchTypeOption = opts.searchType || 'ingredient';
    const includeInventoryOption = opts.includeInventory;
    const includeGlobalOption = opts.includeGlobal;
    const ingredientFirstOption = opts.ingredientFirst;
    const displayVariant = opts.displayVariant;
    const resultFilter = typeof opts.resultFilter === 'function' ? opts.resultFilter : null;
    const onSelection = typeof opts.onSelection === 'function' ? opts.onSelection : null;
    const globalUrlBuilder = opts.globalUrlBuilder;
    const globalFallbackUrlBuilder = opts.globalFallbackUrlBuilder;
    const globalFallbackMode = opts.globalFallbackMode || 'fallback';

    if (!inputEl || (!invHiddenEl && mode === 'recipe') || (!giHiddenEl && opts.requireHidden !== false)) return;

    if (listEl && !listEl.classList.contains('list-group')) {
      listEl.classList.add('list-group');
    }
    if (!listEl.parentNode && inputEl.parentNode) {
      inputEl.parentNode.appendChild(listEl);
    }

    function buildInventoryUrl(q, effectiveSearchType){
      const params = new URLSearchParams({ q });
      if (effectiveSearchType && effectiveSearchType !== 'all') params.set('type', effectiveSearchType);
      return `/inventory/api/search?${params.toString()}`;
    }

    function buildGlobalUrl(q, effectiveSearchType, useIngredientFirst){
      if (typeof globalUrlBuilder === 'function') {
        return globalUrlBuilder(q, effectiveSearchType, useIngredientFirst);
      }
      const params = new URLSearchParams({ q });
      if (effectiveSearchType && effectiveSearchType !== 'all') params.set('type', effectiveSearchType);
      if (effectiveSearchType === 'ingredient' && useIngredientFirst) params.set('group', 'ingredient');
      const base = mode === 'public' ? '/api/public/global-items/search' : '/api/ingredients/global-items/search';
      return `${base}?${params.toString()}`;
    }

    const doSearch = debounce(function(){
      const q = (inputEl.value || '').trim();
      if (!q){
        listEl.classList.add('d-none');
        listEl.innerHTML = '';
        if (invHiddenEl) invHiddenEl.value = '';
        if (giHiddenEl) giHiddenEl.value = '';
        return;
      }

      const effectiveSearchType = (resolveOption(searchTypeOption) || 'ingredient').toLowerCase();
      const includeInventory = resolveOption(includeInventoryOption);
      const includeGlobal = resolveOption(includeGlobalOption);
      const ingredientFirst = effectiveSearchType === 'ingredient' && !!resolveOption(ingredientFirstOption);
      const variant = displayVariant || (ingredientFirst ? 'grouped' : 'compact');

      if (effectiveSearchType === 'ingredient_definition' || effectiveSearchType === 'definition') {
        fetchIngredientDefinitions(q).then(results => {
          const items = (results && results.results) || [];
          renderDefinitionResults(listEl, items.map(item => ({
            id: item.id,
            text: item.name,
            name: item.name,
            inci_name: item.inci_name,
            slug: item.slug,
            ingredient_category_id: item.ingredient_category_id,
            ingredient_category_name: item.ingredient_category_name,
          })), handleSelection);
        }).catch(() => listEl.classList.add('d-none'));
        return;
      }

      const inventoryPromise = includeInventory !== false
        ? fetch(buildInventoryUrl(q, effectiveSearchType)).then(r => r.json()).catch(() => ({ results: [] }))
        : Promise.resolve({ results: [] });
      const globalPromise = includeGlobal !== false
        ? fetch(buildGlobalUrl(q, effectiveSearchType, ingredientFirst)).then(r => r.json()).catch(() => ({ results: [] }))
        : Promise.resolve({ results: [] });
      const fallbackPromise = (includeGlobal !== false && typeof globalFallbackUrlBuilder === 'function')
        ? fetch(globalFallbackUrlBuilder(q, effectiveSearchType, ingredientFirst)).then(r => r.json()).catch(() => ({ results: [] }))
        : Promise.resolve({ results: [] });

      Promise.all([inventoryPromise, globalPromise, fallbackPromise]).then(results => {
        const inventoryRaw = (results[0] && results[0].results) || [];
        const primaryGlobalRaw = (results[1] && results[1].results) || [];
        const fallbackGlobalRaw = (results[2] && results[2].results) || [];
        let globalRaw = primaryGlobalRaw;
        if (typeof globalFallbackUrlBuilder === 'function') {
          if (globalFallbackMode === 'append') {
            globalRaw = primaryGlobalRaw.concat(fallbackGlobalRaw);
          } else if (!primaryGlobalRaw.length) {
            globalRaw = fallbackGlobalRaw;
          }
        }
        const inventory = resultFilter
          ? inventoryRaw.filter(item => resultFilter(item, 'inventory'))
          : inventoryRaw;
        const filteredGlobalRaw = resultFilter
          ? globalRaw.filter(item => resultFilter(item, 'global'))
          : globalRaw;
        const seenGlobalIds = buildGlobalIdSet(inventory);
        const globalExpanded = expandGlobalItems(filteredGlobalRaw)
          .filter(item => !item.global_item_id || !seenGlobalIds.has(String(item.global_item_id)))
          .filter(item => (resultFilter ? resultFilter(item, 'global') : true));

        if (ingredientFirst) {
          const inventoryGroups = groupInventoryByIngredient(inventory);
          const globalGroups = groupGlobalByIngredient(filteredGlobalRaw, seenGlobalIds);
          const ingredientGroups = [];
          if (inventoryGroups.length) {
            ingredientGroups.push({ title: 'Your Inventory', source: 'inventory', ingredients: inventoryGroups });
          }
          if (globalGroups.length) {
            ingredientGroups.push({ title: 'Global Library', source: 'global', ingredients: globalGroups });
          }
          renderIngredientFirst(listEl, ingredientGroups, handleSelection);
          return;
        }

        const mergedGroups = [];
        if (inventory.length) {
          mergedGroups.push({ title: 'Your Inventory', source: 'inventory', items: inventory });
        }
        if (globalExpanded.length) {
          mergedGroups.push({ title: 'Global Library', source: 'global', items: globalExpanded });
        }
        renderFlatList(listEl, mergedGroups, handleSelection, {
          showSourceBadge: opts.showSourceBadge !== false,
          showSubtitle: variant === 'detailed'
        });
      }).catch(() => {
        listEl.classList.add('d-none');
      });
    }, 200);

    function handleSelection(picked, source){
      inputEl.value = picked.text || picked.display_name || picked.name || '';
      if (source === 'inventory') {
        if (invHiddenEl) invHiddenEl.value = picked.id_numeric || picked.id || '';
        if (giHiddenEl) giHiddenEl.value = picked.global_item_id || '';
      } else {
        if (giHiddenEl) giHiddenEl.value = picked.global_item_id || picked.id || '';
        if (invHiddenEl) invHiddenEl.value = '';
      }
      if (typeof onSelection === 'function') {
        onSelection(picked, source);
      }
    }

    inputEl.addEventListener('input', function(){
      if (invHiddenEl) invHiddenEl.value = '';
      if (giHiddenEl) giHiddenEl.value = '';
      doSearch();
    });

    document.addEventListener('click', function(e){
      if (!listEl.contains(e.target) && !inputEl.contains(e.target)) {
        listEl.classList.add('d-none');
      }
    });
  }

  window.attachMergedInventoryGlobalTypeahead = attachMergedInventoryGlobalTypeahead;
  window.renderInventoryTypeaheadList = renderFlatList;
})(window);
