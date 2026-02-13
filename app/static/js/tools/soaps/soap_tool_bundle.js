(() => {
  // app/static/js/components/suggestions.js
  (function(window2) {
    "use strict";
    const SOURCE_LABELS = {
      inventory: "Inventory",
      global: "Global Library"
    };
    const SOURCE_BADGE_CLASS = {
      inventory: "bg-primary",
      global: "bg-info text-dark"
    };
    const DEFAULT_OPTIONS = {
      mode: "recipe",
      searchType: "ingredient",
      includeInventory: true,
      includeGlobal: true,
      ingredientFirst: false,
      displayVariant: null,
      showSourceBadge: true,
      globalUrlBuilder: null,
      resultFilter: null
    };
    function debounce(fn, wait) {
      let timeout;
      return function() {
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(null, args), wait);
      };
    }
    function normalizedName(value) {
      return (value || "").trim().toLowerCase();
    }
    function ensureListContainer(listEl) {
      if (listEl) return listEl;
      const div = document.createElement("div");
      div.className = "list-group position-absolute w-100 d-none inventory-suggestions";
      div.style.zIndex = "1050";
      div.style.maxHeight = "300px";
      div.style.overflowY = "auto";
      return div;
    }
    function resolveOption(value) {
      return typeof value === "function" ? value() : value;
    }
    function buildGlobalIdSet(items) {
      const set = /* @__PURE__ */ new Set();
      (items || []).forEach((item) => {
        const gid = item && (item.global_item_id || item.id);
        if (gid) set.add(String(gid));
      });
      return set;
    }
    function createSourceBadge(source) {
      if (!source) return "";
      const label = SOURCE_LABELS[source] || source;
      const badgeClass = SOURCE_BADGE_CLASS[source] || "bg-secondary";
      return `<span class="badge ${badgeClass} ms-2">${label}</span>`;
    }
    function renderFlatList(listEl, groups, onPick, opts) {
      opts = opts || {};
      listEl.innerHTML = "";
      let hasAny = false;
      groups.forEach((group) => {
        if (!group.items || !group.items.length) return;
        hasAny = true;
        group.items.forEach((item) => {
          const entry = document.createElement("a");
          entry.href = "#";
          entry.className = "list-group-item list-group-item-action suggestion-item";
          const subtitle = opts.showSubtitle && item.subtitle ? `<div class="small text-muted mt-1">${item.subtitle}</div>` : "";
          entry.innerHTML = `<div class="d-flex justify-content-between align-items-center gap-2">
          <span class="fw-semibold text-truncate">${item.text || item.display_name || item.name || ""}</span>
          ${opts.showSourceBadge ? createSourceBadge(group.source || item.source) : ""}
        </div>${subtitle}`;
          entry.addEventListener("click", function(e) {
            e.preventDefault();
            onPick(item, group.source || item.source);
            listEl.classList.add("d-none");
          });
          listEl.appendChild(entry);
        });
      });
      listEl.classList.toggle("d-none", !hasAny);
      if (!hasAny && listEl.dataset.emptyMessage) {
        const empty = document.createElement("div");
        empty.className = "list-group-item text-muted small";
        empty.textContent = listEl.dataset.emptyMessage;
        listEl.appendChild(empty);
        listEl.classList.remove("d-none");
      }
    }
    function renderIngredientFirst(listEl, groups, onPick) {
      listEl.innerHTML = "";
      let hasAny = false;
      groups.forEach((group) => {
        if (!group.ingredients || !group.ingredients.length) return;
        hasAny = true;
        const header = document.createElement("div");
        header.className = "list-group-item text-muted small fw-semibold";
        header.textContent = group.title;
        listEl.appendChild(header);
        group.ingredients.forEach((ingredient) => {
          const itemEl = document.createElement("div");
          itemEl.className = "list-group-item ingredient-result";
          const summary = document.createElement("div");
          summary.className = "d-flex justify-content-between align-items-center ingredient-summary";
          summary.setAttribute("role", "button");
          summary.setAttribute("tabindex", "0");
          summary.innerHTML = `<span class="fw-semibold">${ingredient.name || "Ingredient"}</span>
          <span class="badge bg-light text-dark">${ingredient.forms.length} option${ingredient.forms.length === 1 ? "" : "s"}</span>`;
          const formsContainer = document.createElement("div");
          formsContainer.className = "ingredient-form-options d-none mt-2 ps-3 border-start border-2";
          ingredient.forms.forEach((form) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn btn-sm btn-outline-primary w-100 text-start mb-2 ingredient-form-option suggestion-item";
            btn.innerHTML = `<div class="fw-semibold">${form.text || form.display_name || form.name || "Form"}</div>`;
            btn.addEventListener("click", function() {
              onPick(form, form.source || group.source);
              listEl.classList.add("d-none");
            });
            formsContainer.appendChild(btn);
          });
          function toggleForms(e) {
            if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
            e.preventDefault();
            formsContainer.classList.toggle("d-none");
          }
          summary.addEventListener("click", toggleForms);
          summary.addEventListener("keydown", toggleForms);
          itemEl.appendChild(summary);
          itemEl.appendChild(formsContainer);
          listEl.appendChild(itemEl);
          if (ingredient.forms.length === 1) {
            formsContainer.classList.remove("d-none");
          }
        });
      });
      listEl.classList.toggle("d-none", !hasAny);
    }
    function renderDefinitionResults(listEl, items, onPick) {
      listEl.innerHTML = "";
      let hasAny = false;
      (items || []).forEach((item) => {
        hasAny = true;
        const entry = document.createElement("a");
        entry.href = "#";
        entry.className = "list-group-item list-group-item-action suggestion-item";
        const meta = item.inci_name ? `<div class="small text-muted">${item.inci_name}</div>` : "";
        entry.innerHTML = `<div class="fw-semibold">${item.text || item.name}</div>${meta}`;
        entry.addEventListener("click", function(e) {
          e.preventDefault();
          onPick(item, "definition");
          listEl.classList.add("d-none");
        });
        listEl.appendChild(entry);
      });
      listEl.classList.toggle("d-none", !hasAny);
      if (!hasAny && listEl.dataset.emptyMessage) {
        const empty = document.createElement("div");
        empty.className = "list-group-item text-muted small";
        empty.textContent = listEl.dataset.emptyMessage;
        listEl.appendChild(empty);
        listEl.classList.remove("d-none");
      }
    }
    function expandGlobalItems(items) {
      const expanded = [];
      (items || []).forEach((item) => {
        if (item && Array.isArray(item.forms) && item.forms.length) {
          const baseIngredientName = item.ingredient && item.ingredient.name || item.ingredient_name || null;
          const categoryName = item.ingredient && item.ingredient.ingredient_category_name || item.ingredient_category_name || item.ingredient_category && item.ingredient_category.name || null;
          const categoryTags = item.category_tags || [];
          item.forms.forEach((form) => {
            var _a, _b, _c, _d, _e, _f, _g, _h, _i, _j;
            const physical = form.physical_form || {};
            const display = form.display_name || form.text || form.name || (baseIngredientName && form.physical_form_name ? `${baseIngredientName}, ${form.physical_form_name}` : item.display_name || item.text || item.name || "");
            expanded.push({
              id: form.id,
              text: display,
              item_type: form.item_type || item.item_type,
              default_unit: form.default_unit || form.unit || item.default_unit || item.unit || null,
              source: "global",
              global_item_id: form.id,
              ingredient_id: form.ingredient_id || item.ingredient && item.ingredient.id || item.ingredient_id || null,
              ingredient_name: form.ingredient_name || baseIngredientName,
              physical_form_id: form.physical_form_id || physical && physical.id || null,
              physical_form_name: form.physical_form_name || physical && physical.name || null,
              ingredient_category_name: categoryName,
              category_tags: categoryTags,
              density: form.density || item.density || null,
              capacity: form.capacity || item.capacity || null,
              capacity_unit: form.capacity_unit || item.capacity_unit || null,
              container_material: form.container_material || item.container_material || null,
              container_type: form.container_type || item.container_type || null,
              container_style: form.container_style || item.container_style || null,
              container_color: form.container_color || item.container_color || null,
              default_is_perishable: (_a = form.default_is_perishable) != null ? _a : item.default_is_perishable,
              recommended_shelf_life_days: (_b = form.recommended_shelf_life_days) != null ? _b : item.recommended_shelf_life_days,
              saponification_value: (_d = (_c = form.saponification_value) != null ? _c : item.saponification_value) != null ? _d : null,
              iodine_value: (_f = (_e = form.iodine_value) != null ? _e : item.iodine_value) != null ? _f : null,
              fatty_acid_profile: (_h = (_g = form.fatty_acid_profile) != null ? _g : item.fatty_acid_profile) != null ? _h : null,
              melting_point_c: (_j = (_i = form.melting_point_c) != null ? _i : item.melting_point_c) != null ? _j : null
            });
          });
        } else if (item) {
          const displayName = item.display_name || item.text || item.name || "";
          const categoryName = item.ingredient && item.ingredient.ingredient_category_name || item.ingredient_category_name || item.ingredient_category && item.ingredient_category.name || null;
          expanded.push({
            id: item.id,
            text: displayName,
            source: "global",
            item_type: item.item_type,
            global_item_id: item.id,
            ingredient_name: item.ingredient && item.ingredient.name || item.ingredient_name || item.name,
            ingredient_category_name: categoryName,
            category_tags: item.category_tags || [],
            physical_form_name: item.physical_form && item.physical_form.name || item.physical_form_name || null,
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
            melting_point_c: item.melting_point_c || null
          });
        }
      });
      return expanded;
    }
    function groupInventoryByIngredient(items) {
      const map = /* @__PURE__ */ new Map();
      (items || []).forEach((item) => {
        const baseName = item.ingredient_name || item.text || item.name || "";
        const key = item.ingredient_id ? `id:${item.ingredient_id}` : `name:${normalizedName(baseName)}`;
        const entry = map.get(key) || {
          ingredient_id: item.ingredient_id || null,
          name: baseName,
          forms: []
        };
        entry.forms.push({
          id: item.id,
          text: item.text || baseName,
          ingredient_name: baseName,
          physical_form_name: item.physical_form_name || null,
          default_unit: item.default_unit || item.unit || null,
          source: "inventory",
          global_item_id: item.global_item_id || null
        });
        map.set(key, entry);
      });
      return Array.from(map.values());
    }
    function groupGlobalByIngredient(rawGroups, dedupeIds) {
      const groups = [];
      (rawGroups || []).forEach((group) => {
        const forms = (group.forms || []).map((form) => ({
          id: form.id,
          text: form.name || form.display_name || form.text,
          ingredient_name: form.ingredient_name || group.name || group.ingredient && group.ingredient.name || "Ingredient",
          physical_form_name: form.physical_form_name || null,
          default_unit: form.default_unit || form.unit || null,
          source: "global",
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
          melting_point_c: form.melting_point_c || null
        }));
        const filteredForms = dedupeIds ? forms.filter((form) => !form.global_item_id || !dedupeIds.has(String(form.global_item_id))) : forms;
        if (filteredForms.length) {
          groups.push({
            ingredient_id: group.ingredient_id || group.id || null,
            name: group.name || group.ingredient && group.ingredient.name || forms[0] && forms[0].ingredient_name || "Ingredient",
            forms: filteredForms
          });
        }
      });
      return groups;
    }
    function fetchIngredientDefinitions(q) {
      const params = new URLSearchParams({ q });
      return fetch(`/api/ingredients/definitions/search?${params.toString()}`).then((r) => r.json()).catch(() => ({ results: [] }));
    }
    function attachMergedInventoryGlobalTypeahead(options) {
      const opts = { ...DEFAULT_OPTIONS, ...options };
      const inputEl = opts.inputEl;
      const invHiddenEl = opts.invHiddenEl;
      const giHiddenEl = opts.giHiddenEl;
      const listEl = ensureListContainer(opts.listEl);
      const mode = opts.mode || "recipe";
      const searchTypeOption = opts.searchType || "ingredient";
      const includeInventoryOption = opts.includeInventory;
      const includeGlobalOption = opts.includeGlobal;
      const ingredientFirstOption = opts.ingredientFirst;
      const displayVariant = opts.displayVariant;
      const resultFilter = typeof opts.resultFilter === "function" ? opts.resultFilter : null;
      const onSelection = typeof opts.onSelection === "function" ? opts.onSelection : null;
      const globalUrlBuilder = opts.globalUrlBuilder;
      if (!inputEl || !invHiddenEl && mode === "recipe" || !giHiddenEl && opts.requireHidden !== false) return;
      if (listEl && !listEl.classList.contains("list-group")) {
        listEl.classList.add("list-group");
      }
      if (!listEl.parentNode && inputEl.parentNode) {
        inputEl.parentNode.appendChild(listEl);
      }
      function buildInventoryUrl(q, effectiveSearchType) {
        const params = new URLSearchParams({ q });
        if (effectiveSearchType && effectiveSearchType !== "all") params.set("type", effectiveSearchType);
        return `/inventory/api/search?${params.toString()}`;
      }
      function buildGlobalUrl(q, effectiveSearchType, useIngredientFirst) {
        if (typeof globalUrlBuilder === "function") {
          return globalUrlBuilder(q, effectiveSearchType, useIngredientFirst);
        }
        const params = new URLSearchParams({ q });
        if (effectiveSearchType && effectiveSearchType !== "all") params.set("type", effectiveSearchType);
        if (effectiveSearchType === "ingredient" && useIngredientFirst) params.set("group", "ingredient");
        const base = mode === "public" ? "/api/public/global-items/search" : "/api/ingredients/global-items/search";
        return `${base}?${params.toString()}`;
      }
      const doSearch = debounce(function() {
        const q = (inputEl.value || "").trim();
        if (!q) {
          listEl.classList.add("d-none");
          listEl.innerHTML = "";
          if (invHiddenEl) invHiddenEl.value = "";
          if (giHiddenEl) giHiddenEl.value = "";
          return;
        }
        const effectiveSearchType = (resolveOption(searchTypeOption) || "ingredient").toLowerCase();
        const includeInventory = resolveOption(includeInventoryOption);
        const includeGlobal = resolveOption(includeGlobalOption);
        const ingredientFirst = effectiveSearchType === "ingredient" && !!resolveOption(ingredientFirstOption);
        const variant = displayVariant || (ingredientFirst ? "grouped" : "compact");
        if (effectiveSearchType === "ingredient_definition" || effectiveSearchType === "definition") {
          fetchIngredientDefinitions(q).then((results) => {
            const items = results && results.results || [];
            renderDefinitionResults(listEl, items.map((item) => ({
              id: item.id,
              text: item.name,
              name: item.name,
              inci_name: item.inci_name,
              slug: item.slug,
              ingredient_category_id: item.ingredient_category_id,
              ingredient_category_name: item.ingredient_category_name
            })), handleSelection);
          }).catch(() => listEl.classList.add("d-none"));
          return;
        }
        const inventoryPromise = includeInventory !== false ? fetch(buildInventoryUrl(q, effectiveSearchType)).then((r) => r.json()).catch(() => ({ results: [] })) : Promise.resolve({ results: [] });
        const globalPromise = includeGlobal !== false ? fetch(buildGlobalUrl(q, effectiveSearchType, ingredientFirst)).then((r) => r.json()).catch(() => ({ results: [] })) : Promise.resolve({ results: [] });
        Promise.all([inventoryPromise, globalPromise]).then((results) => {
          const inventoryRaw = results[0] && results[0].results || [];
          const globalRaw = results[1] && results[1].results || [];
          const inventory = resultFilter ? inventoryRaw.filter((item) => resultFilter(item, "inventory")) : inventoryRaw;
          const filteredGlobalRaw = resultFilter ? globalRaw.filter((item) => resultFilter(item, "global")) : globalRaw;
          const seenGlobalIds = buildGlobalIdSet(inventory);
          const globalExpanded = expandGlobalItems(filteredGlobalRaw).filter((item) => !item.global_item_id || !seenGlobalIds.has(String(item.global_item_id))).filter((item) => resultFilter ? resultFilter(item, "global") : true);
          if (ingredientFirst) {
            const inventoryGroups = groupInventoryByIngredient(inventory);
            const globalGroups = groupGlobalByIngredient(filteredGlobalRaw, seenGlobalIds);
            const ingredientGroups = [];
            if (inventoryGroups.length) {
              ingredientGroups.push({ title: "Your Inventory", source: "inventory", ingredients: inventoryGroups });
            }
            if (globalGroups.length) {
              ingredientGroups.push({ title: "Global Library", source: "global", ingredients: globalGroups });
            }
            renderIngredientFirst(listEl, ingredientGroups, handleSelection);
            return;
          }
          const mergedGroups = [];
          if (inventory.length) {
            mergedGroups.push({ title: "Your Inventory", source: "inventory", items: inventory });
          }
          if (globalExpanded.length) {
            mergedGroups.push({ title: "Global Library", source: "global", items: globalExpanded });
          }
          renderFlatList(listEl, mergedGroups, handleSelection, {
            showSourceBadge: opts.showSourceBadge !== false,
            showSubtitle: variant === "detailed"
          });
        }).catch(() => {
          listEl.classList.add("d-none");
        });
      }, 200);
      function handleSelection(picked, source) {
        inputEl.value = picked.text || picked.display_name || picked.name || "";
        if (source === "inventory") {
          if (invHiddenEl) invHiddenEl.value = picked.id_numeric || picked.id || "";
          if (giHiddenEl) giHiddenEl.value = picked.global_item_id || "";
        } else {
          if (giHiddenEl) giHiddenEl.value = picked.global_item_id || picked.id || "";
          if (invHiddenEl) invHiddenEl.value = "";
        }
        if (typeof onSelection === "function") {
          onSelection(picked, source);
        }
      }
      inputEl.addEventListener("input", function() {
        if (invHiddenEl) invHiddenEl.value = "";
        if (giHiddenEl) giHiddenEl.value = "";
        doSearch();
      });
      document.addEventListener("click", function(e) {
        if (!listEl.contains(e.target) && !inputEl.contains(e.target)) {
          listEl.classList.add("d-none");
        }
      });
    }
    window2.attachMergedInventoryGlobalTypeahead = attachMergedInventoryGlobalTypeahead;
    window2.renderInventoryTypeaheadList = renderFlatList;
  })(window);

  // app/static/js/components/tool_lines.js
  (function(window2) {
    "use strict";
    function buildToolLineRow2(kind, options) {
      var context = options && options.context || "public";
      var unitOptionsHtml = options && options.unitOptionsHtml || "";
      var mode = options && options.mode || (context === "public" ? "public" : "recipe");
      var row = document.createElement("div");
      row.className = "row g-2 align-items-end mb-2";
      row.innerHTML = [
        '<div class="col-md-6">',
        '  <label class="form-label">',
        kind === "container" ? "Container" : kind === "consumable" ? "Consumable" : "Ingredient",
        "</label>",
        '  <div class="position-relative">',
        '    <input type="text" class="form-control tool-typeahead" placeholder="Search global..." autocomplete="off">',
        '    <input type="hidden" class="tool-gi-id">',
        '    <div class="list-group position-absolute w-100 d-none" data-role="suggestions"></div>',
        "  </div>",
        "</div>",
        '<div class="col-md-3 ',
        kind === "container" ? "d-none" : "",
        '">',
        '  <label class="form-label">Quantity</label>',
        '  <input type="number" step="0.01" min="0" class="form-control tool-qty">',
        "</div>",
        '<div class="col-md-3 ',
        kind === "container" ? "d-none" : "",
        '">',
        '  <label class="form-label">Unit</label>',
        '  <select class="form-select tool-unit">',
        unitOptionsHtml,
        "  </select>",
        "</div>",
        '<div class="col-md-3 ',
        kind !== "container" ? "d-none" : "",
        '">',
        '  <label class="form-label">Count</label>',
        '  <input type="number" min="1" step="1" class="form-control tool-qty">',
        "</div>",
        '<div class="col-md-2 d-grid">',
        '  <button type="button" class="btn btn-outline-danger tool-remove">Remove</button>',
        "</div>"
      ].join("");
      var input = row.querySelector(".tool-typeahead");
      var giHidden = row.querySelector(".tool-gi-id");
      var list = row.querySelector('[data-role="suggestions"]');
      if (typeof window2.attachMergedInventoryGlobalTypeahead === "function") {
        const searchType = kind === "container" ? "container" : kind === "consumable" ? "consumable" : "ingredient";
        const includeInventory = context !== "public";
        window2.attachMergedInventoryGlobalTypeahead({
          inputEl: input,
          giHiddenEl: giHidden,
          listEl: list,
          mode,
          context,
          ingredientFirst: kind === "ingredient",
          searchType,
          includeInventory,
          includeGlobal: true
        });
      }
      row.querySelector(".tool-remove").addEventListener("click", function() {
        row.remove();
      });
      return row;
    }
    window2.buildToolLineRow = buildToolLineRow2;
  })(window);

  // app/static/js/tools/soaps/soap_tool_core.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    SoapTool.config = {
      unitOptionsHtml: window2.soapToolConfig && window2.soapToolConfig.unitOptionsHtml || "",
      calcLimit: Number.isFinite(window2.SOAP_CALC_LIMIT) ? window2.SOAP_CALC_LIMIT : null,
      calcTier: window2.SOAP_CALC_TIER || "guest",
      useCsvPrimary: !!(window2.soapToolConfig && window2.soapToolConfig.useCsvPrimary),
      isAuthenticated: window2.__IS_AUTHENTICATED__ === true
    };
    SoapTool.state = {
      lastCalc: null,
      calcRequestSeq: 0,
      lastOilEdit: null,
      lastFragranceEdit: null,
      selectedOilProfile: null,
      wasCapped: false,
      lastPreviewRow: null,
      lastRemovedOil: null,
      lastRemovedOilIndex: null,
      lastSaveToastAt: 0,
      lastRecipePayload: null,
      totalOilsGrams: 0,
      currentUnit: "g"
    };
    SoapTool.helpers = {
      round,
      toNumber,
      clamp,
      formatTime,
      getStorage,
      buildSoapcalcSearchBuilder
    };
    function round(value, decimals = 3) {
      if (!isFinite(value)) return 0;
      const factor = Math.pow(10, decimals);
      return Math.round(value * factor) / factor;
    }
    function toNumber(value) {
      let cleaned = value;
      if (typeof cleaned === "string") {
        cleaned = cleaned.replace(/,/g, "").trim();
      }
      const num = parseFloat(cleaned);
      return isFinite(num) ? num : 0;
    }
    function clamp(value, min, max) {
      if (!isFinite(value)) return min;
      if (value < min) return min;
      if (max !== void 0 && max !== null && value > max) return max;
      return value;
    }
    function formatTime(ts) {
      if (!ts) return "Not saved yet";
      const date = new Date(ts);
      return `Saved ${date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
    }
    function getStorage() {
      try {
        return window2.localStorage;
      } catch (_) {
        return null;
      }
    }
    function buildSoapcalcSearchBuilder() {
      const buildGilUrl = (q, effectiveSearchType, useIngredientFirst) => {
        const params = new URLSearchParams({ q });
        if (effectiveSearchType && effectiveSearchType !== "all") params.set("type", effectiveSearchType);
        if (effectiveSearchType === "ingredient" && useIngredientFirst) params.set("group", "ingredient");
        return `/api/public/global-items/search?${params.toString()}`;
      };
      const buildCsvUrl = (q, _searchType, useIngredientFirst) => {
        const params = new URLSearchParams({ q });
        if (useIngredientFirst) params.set("group", "ingredient");
        return `/api/public/soapcalc-items/search?${params.toString()}`;
      };
      return SoapTool.config.useCsvPrimary === true ? buildCsvUrl : buildGilUrl;
    }
  })(window);

  // app/static/js/tools/soaps/soap_tool_constants.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const QUALITY_RANGES = {
      hardness: [29, 54],
      cleansing: [12, 22],
      conditioning: [44, 69],
      bubbly: [14, 46],
      creamy: [16, 48]
    };
    const QUALITY_HINTS = {
      hardness: "Durable bar that resists mush.",
      cleansing: "Higher values feel more stripping.",
      conditioning: "Silky, moisturizing feel.",
      bubbly: "Fluffy lather and big bubbles.",
      creamy: "Stable, creamy lather."
    };
    const QUALITY_FEEL_HINTS = {
      hardness: {
        low: "Soft bar, slower unmold.",
        ok: "Balanced hardness for daily use.",
        high: "Very hard bar, can feel brittle."
      },
      cleansing: {
        low: "Very mild cleansing.",
        ok: "Balanced cleansing.",
        high: "Strong cleansing, can be drying."
      },
      conditioning: {
        low: "Less conditioning feel.",
        ok: "Smooth and conditioning.",
        high: "Very conditioning, may feel oily."
      },
      bubbly: {
        low: "Low bubbly lather.",
        ok: "Balanced bubbly lather.",
        high: "Very bubbly, big foam."
      },
      creamy: {
        low: "Light creamy lather.",
        ok: "Creamy and stable.",
        high: "Dense creamy lather."
      }
    };
    const IODINE_RANGE = [41, 70];
    const IODINE_SCALE_MAX = 100;
    const INS_RANGE = [136, 170];
    const INS_SCALE_MAX = 250;
    const QUALITY_BASE = {
      hardness: (QUALITY_RANGES.hardness[0] + QUALITY_RANGES.hardness[1]) / 2,
      cleansing: (QUALITY_RANGES.cleansing[0] + QUALITY_RANGES.cleansing[1]) / 2,
      conditioning: (QUALITY_RANGES.conditioning[0] + QUALITY_RANGES.conditioning[1]) / 2,
      bubbly: (QUALITY_RANGES.bubbly[0] + QUALITY_RANGES.bubbly[1]) / 2,
      creamy: (QUALITY_RANGES.creamy[0] + QUALITY_RANGES.creamy[1]) / 2
    };
    const QUALITY_PRESETS = {
      balanced: {
        hardness: 40,
        cleansing: 15,
        conditioning: 55,
        bubbly: 25,
        creamy: 25,
        iodine: 55,
        ins: 160
      },
      bubbly: {
        hardness: 35,
        cleansing: 20,
        conditioning: 50,
        bubbly: 35,
        creamy: 25,
        iodine: 60,
        ins: 150
      },
      creamy: {
        hardness: 45,
        cleansing: 12,
        conditioning: 60,
        bubbly: 20,
        creamy: 35,
        iodine: 50,
        ins: 155
      },
      hard: {
        hardness: 50,
        cleansing: 18,
        conditioning: 48,
        bubbly: 22,
        creamy: 28,
        iodine: 45,
        ins: 165
      },
      gentle: {
        hardness: 35,
        cleansing: 10,
        conditioning: 65,
        bubbly: 15,
        creamy: 20,
        iodine: 65,
        ins: 140
      },
      castile: {
        hardness: 20,
        cleansing: 5,
        conditioning: 75,
        bubbly: 10,
        creamy: 15,
        iodine: 80,
        ins: 110
      },
      shampoo: {
        hardness: 30,
        cleansing: 22,
        conditioning: 50,
        bubbly: 30,
        creamy: 25,
        iodine: 60,
        ins: 145
      },
      utility: {
        hardness: 70,
        cleansing: 50,
        conditioning: 20,
        bubbly: 50,
        creamy: 20,
        iodine: 10,
        ins: 250
      },
      luxury: {
        hardness: 55,
        cleansing: 10,
        conditioning: 55,
        bubbly: 15,
        creamy: 40,
        iodine: 50,
        ins: 150
      },
      palmFree: {
        hardness: 42,
        cleansing: 16,
        conditioning: 58,
        bubbly: 22,
        creamy: 28,
        iodine: 55,
        ins: 155
      }
    };
    const FATTY_BAR_COLORS = {
      lauric: "var(--color-primary)",
      myristic: "var(--color-info)",
      palmitic: "var(--color-warning)",
      stearic: "var(--color-muted)",
      ricinoleic: "var(--color-info-hover)",
      oleic: "var(--color-success)",
      linoleic: "var(--color-primary-hover)",
      linolenic: "var(--color-danger)"
    };
    const FATTY_DISPLAY_KEYS = [
      "lauric",
      "myristic",
      "palmitic",
      "stearic",
      "ricinoleic",
      "oleic",
      "linoleic",
      "linolenic"
    ];
    const OIL_TIP_RULES = [
      { match: /coconut|palm kernel|babassu|murumuru/i, tip: "High lauric oils trace fast and feel cleansing; keep superfat >= 5%." },
      { match: /olive|avocado|rice bran|canola|sunflower|safflower|almond|apricot|macadamia|camellia|grapeseed|hazelnut/i, tip: "High-oleic liquid oils trace slowly and stay softer early on; allow a longer cure." },
      { match: /castor/i, tip: "Castor boosts lather but can feel sticky above 10-15%." },
      { match: /cocoa|shea|mango|kokum|sal|illipe|tallow|lard|palm|stearic/i, tip: "Hard fats/butters set up quickly; melt fully and keep batter warm for a smooth pour." },
      { match: /beeswax|candelilla|carnauba|wax/i, tip: "Waxes harden fast and can seize; keep usage low and add hot." },
      { match: /hemp|flax|linseed|evening primrose|borage|rosehip|black currant|chia|pomegranate/i, tip: "High-PUFA oils shorten shelf life; keep low and add antioxidant." }
    ];
    const UNIT_FACTORS = { g: 1, oz: 28.3495, lb: 453.592 };
    const STAGE_CONFIGS = [
      { id: 1, tabId: "soapStage1Tab", paneId: "soapStage1Pane", required: true },
      { id: 2, tabId: "soapStage2Tab", paneId: "soapStage2Pane", required: true },
      { id: 3, tabId: "soapStage3Tab", paneId: "soapStage3Pane", required: true },
      { id: 4, tabId: "soapStage4Tab", paneId: "soapStage4Pane", required: false },
      { id: 5, tabId: "soapStage5Tab", paneId: "soapStage5Pane", required: false }
    ];
    const OIL_CATEGORY_SET = /* @__PURE__ */ new Set(["Oils (Carrier & Fixed)", "Butters & Solid Fats", "Waxes"]);
    const FRAGRANCE_CATEGORY_SET = /* @__PURE__ */ new Set(["Essential Oils", "Fragrance Oils"]);
    const LACTATE_CATEGORY_SET = /* @__PURE__ */ new Set(["Aqueous Solutions & Blends", "Preservatives & Additives"]);
    const SUGAR_CATEGORY_SET = /* @__PURE__ */ new Set(["Sugars & Syrups"]);
    const SALT_CATEGORY_SET = /* @__PURE__ */ new Set(["Salts & Minerals"]);
    const CITRIC_CATEGORY_SET = /* @__PURE__ */ new Set(["Preservatives & Additives", "Salts & Minerals", "Aqueous Solutions & Blends"]);
    SoapTool.constants = {
      QUALITY_RANGES,
      QUALITY_HINTS,
      QUALITY_FEEL_HINTS,
      IODINE_RANGE,
      IODINE_SCALE_MAX,
      INS_RANGE,
      INS_SCALE_MAX,
      QUALITY_BASE,
      QUALITY_PRESETS,
      FATTY_BAR_COLORS,
      FATTY_DISPLAY_KEYS,
      OIL_TIP_RULES,
      UNIT_FACTORS,
      STAGE_CONFIGS,
      OIL_CATEGORY_SET,
      FRAGRANCE_CATEGORY_SET,
      LACTATE_CATEGORY_SET,
      SUGAR_CATEGORY_SET,
      SALT_CATEGORY_SET,
      CITRIC_CATEGORY_SET
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_calc.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { toNumber } = SoapTool.helpers;
    function computeIodine(oils) {
      let totalWeight = 0;
      let weighted = 0;
      oils.forEach((oil) => {
        if (oil.iodine > 0) {
          totalWeight += oil.grams;
          weighted += oil.iodine * oil.grams;
        }
      });
      return {
        iodine: totalWeight > 0 ? weighted / totalWeight : 0,
        coverageWeight: totalWeight
      };
    }
    function computeFattyAcids(oils) {
      const totals = {};
      let coveredWeight = 0;
      oils.forEach((oil) => {
        if (!oil.fattyProfile || typeof oil.fattyProfile !== "object") {
          return;
        }
        coveredWeight += oil.grams;
        Object.entries(oil.fattyProfile).forEach(([key, pct]) => {
          const value = toNumber(pct);
          if (value > 0) {
            totals[key] = (totals[key] || 0) + oil.grams * (value / 100);
          }
        });
      });
      const percent = {};
      if (coveredWeight > 0) {
        Object.entries(totals).forEach(([key, grams]) => {
          percent[key] = grams / coveredWeight * 100;
        });
      }
      return { percent, coveredWeight };
    }
    function computeQualities(fattyPercent) {
      const get = (key) => fattyPercent[key] || 0;
      return {
        hardness: get("lauric") + get("myristic") + get("palmitic") + get("stearic"),
        cleansing: get("lauric") + get("myristic"),
        conditioning: get("oleic") + get("linoleic") + get("linolenic") + get("ricinoleic"),
        bubbly: get("lauric") + get("myristic") + get("ricinoleic"),
        creamy: get("palmitic") + get("stearic") + get("ricinoleic")
      };
    }
    function computeOilQualityScores(fattyProfile) {
      if (!fattyProfile || typeof fattyProfile !== "object") {
        return {
          hardness: 0,
          cleansing: 0,
          conditioning: 0,
          bubbly: 0,
          creamy: 0
        };
      }
      const profile = {
        lauric: toNumber(fattyProfile.lauric),
        myristic: toNumber(fattyProfile.myristic),
        palmitic: toNumber(fattyProfile.palmitic),
        stearic: toNumber(fattyProfile.stearic),
        ricinoleic: toNumber(fattyProfile.ricinoleic),
        oleic: toNumber(fattyProfile.oleic),
        linoleic: toNumber(fattyProfile.linoleic),
        linolenic: toNumber(fattyProfile.linolenic)
      };
      const qualities = computeQualities(profile);
      return {
        hardness: (qualities.hardness || 0) / 100,
        cleansing: (qualities.cleansing || 0) / 100,
        conditioning: (qualities.conditioning || 0) / 100,
        bubbly: (qualities.bubbly || 0) / 100,
        creamy: (qualities.creamy || 0) / 100
      };
    }
    SoapTool.calc = {
      computeIodine,
      computeFattyAcids,
      computeQualities,
      computeOilQualityScores
    };
    window2.SoapCalcService = SoapTool.calc;
  })(window);

  // app/static/js/tools/soaps/soap_tool_units.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { round, toNumber, clamp } = SoapTool.helpers;
    const { UNIT_FACTORS } = SoapTool.constants;
    const state = SoapTool.state;
    function toGrams(value) {
      return clamp(toNumber(value), 0) * (UNIT_FACTORS[state.currentUnit] || 1);
    }
    function fromGrams(value) {
      const grams = clamp(value, 0);
      return grams / (UNIT_FACTORS[state.currentUnit] || 1);
    }
    function formatWeight(value) {
      if (!isFinite(value) || value <= 0) return "--";
      return `${round(fromGrams(value), 2)} ${state.currentUnit}`;
    }
    function formatPercent(value) {
      if (!isFinite(value)) return "--";
      return `${round(value, 1)}%`;
    }
    function updateUnitLabels() {
      document.querySelectorAll(".unit-label").forEach((el) => {
        el.textContent = state.currentUnit;
      });
      document.querySelectorAll(".unit-suffix").forEach((el) => {
        el.dataset.suffix = state.currentUnit;
      });
    }
    function setUnit(unit, options = {}) {
      if (!unit) return;
      if (unit === state.currentUnit) {
        updateUnitLabels();
        return;
      }
      const prevUnit = state.currentUnit;
      state.currentUnit = unit;
      updateUnitLabels();
      if (options.skipConvert) return;
      const ratio = (UNIT_FACTORS[prevUnit] || 1) / (UNIT_FACTORS[unit] || 1);
      document.querySelectorAll(".oil-grams").forEach((input) => {
        const value = toNumber(input.value);
        if (value > 0) input.value = round(value * ratio, 2);
      });
      document.querySelectorAll(".fragrance-grams").forEach((input) => {
        const value = toNumber(input.value);
        if (value > 0) input.value = round(value * ratio, 2);
      });
      const oilTarget = document.getElementById("oilTotalTarget");
      if (oilTarget && oilTarget.value) {
        const value = toNumber(oilTarget.value);
        if (value > 0) oilTarget.value = round(value * ratio, 2);
      }
      const moldWater = document.getElementById("moldWaterWeight");
      if (moldWater && moldWater.value) {
        const value = toNumber(moldWater.value);
        if (value > 0) moldWater.value = round(value * ratio, 2);
      }
      SoapTool.oils.updateOilTotals();
      SoapTool.mold.updateMoldSuggested();
      SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
      if (SoapTool.bulkOilsModal && typeof SoapTool.bulkOilsModal.onUnitChanged === "function") {
        SoapTool.bulkOilsModal.onUnitChanged();
      }
      if (!options.skipAutoCalc) {
        SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: false });
      }
    }
    SoapTool.units = {
      toGrams,
      fromGrams,
      formatWeight,
      formatPercent,
      updateUnitLabels,
      setUnit
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_ui.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const state = SoapTool.state;
    const ALERT_ICONS = {
      info: "fa-info-circle",
      warning: "fa-exclamation-triangle",
      danger: "fa-times-circle",
      success: "fa-check-circle"
    };
    function pulseValue(el) {
      if (!el) return;
      el.classList.remove("soap-number-pulse");
      void el.offsetWidth;
      el.classList.add("soap-number-pulse");
    }
    function getToastInstance(id) {
      var _a;
      const el = document.getElementById(id);
      if (!el || !((_a = window2.bootstrap) == null ? void 0 : _a.Toast)) return null;
      return bootstrap.Toast.getOrCreateInstance(el);
    }
    function showAutosaveToast() {
      const now = Date.now();
      if (now - state.lastSaveToastAt < 3500) return;
      state.lastSaveToastAt = now;
      const toast = getToastInstance("soapAutosaveToast");
      if (toast) toast.show();
    }
    function showUndoToast(message) {
      const toastEl = document.getElementById("soapUndoToast");
      if (!toastEl) return;
      const body = toastEl.querySelector(".toast-body");
      if (body) body.textContent = message || "Oil removed.";
      const toast = getToastInstance("soapUndoToast");
      if (toast) toast.show();
    }
    function updateResultsMeta() {
      const badge = document.getElementById("resultsReadyBadge");
      const updatedAt = document.getElementById("resultsUpdatedAt");
      if (badge) badge.classList.remove("d-none");
      if (updatedAt) {
        updatedAt.textContent = `Updated ${(/* @__PURE__ */ new Date()).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
      }
    }
    function updateResultsWarnings(waterData) {
      const concentrationEl = document.getElementById("lyeConcentrationWarning");
      const ratioEl = document.getElementById("waterRatioWarning");
      if (concentrationEl) {
        const concentration = (waterData == null ? void 0 : waterData.lyeConcentration) || 0;
        let message = "";
        if (concentration > 40) message = "High concentration";
        if (concentration > 0 && concentration < 25) message = "Low concentration";
        concentrationEl.textContent = message;
        concentrationEl.classList.toggle("d-none", !message);
      }
      if (ratioEl) {
        const ratio = (waterData == null ? void 0 : waterData.waterRatio) || 0;
        let message = "";
        if (ratio > 0 && ratio < 1.8) message = "Low water";
        if (ratio > 2.7) message = "High water";
        ratioEl.textContent = message;
        ratioEl.classList.toggle("d-none", !message);
      }
    }
    function applyHelperVisibility() {
      document.querySelectorAll("#soapToolPage .form-text").forEach((text) => {
        const wrapper = text.closest(".col-md-2, .col-md-3, .col-md-4, .col-md-6, .col-md-8, .col-lg-6, .col-lg-4, .col-12");
        if (wrapper) wrapper.classList.add("soap-field");
      });
    }
    function validateNumericField(input) {
      if (!input || input.type !== "number") return;
      const raw = input.value;
      if (raw === "") {
        input.classList.remove("is-invalid");
        return;
      }
      const value = parseFloat(raw);
      const min = input.getAttribute("min");
      const max = input.getAttribute("max");
      const tooLow = min !== null && min !== "" && value < parseFloat(min);
      const tooHigh = max !== null && max !== "" && value > parseFloat(max);
      input.classList.toggle("is-invalid", !isFinite(value) || tooLow || tooHigh);
    }
    function flashStage(stageItem) {
      var _a;
      if (!stageItem) return;
      const target = ((_a = stageItem.querySelector) == null ? void 0 : _a.call(stageItem, ".soap-stage-card")) || stageItem;
      target.classList.add("soap-stage-highlight");
      setTimeout(() => target.classList.remove("soap-stage-highlight"), 900);
    }
    function showSoapAlert(type, message, options = {}) {
      var _a;
      const alertStack = document.getElementById("soapAlertStack");
      if (!alertStack) return;
      const icon = ALERT_ICONS[type] || ALERT_ICONS.info;
      const alert = document.createElement("div");
      alert.className = `alert alert-${type} d-flex align-items-start gap-2`;
      alert.innerHTML = `
      <i class="fas ${icon} mt-1"></i>
      <div class="flex-grow-1">${message}</div>
      ${options.dismissible ? '<button type="button" class="btn-close" data-role="dismiss"></button>' : ""}
    `;
      if (options.dismissible) {
        (_a = alert.querySelector('[data-role="dismiss"]')) == null ? void 0 : _a.addEventListener("click", () => alert.remove());
      }
      alertStack.prepend(alert);
      if (!options.persist) {
        setTimeout(() => {
          if (alert.parentNode) alert.remove();
        }, options.timeoutMs || 4500);
      }
    }
    function clearSoapAlerts() {
      const alertStack = document.getElementById("soapAlertStack");
      if (!alertStack) return;
      alertStack.querySelectorAll(".alert").forEach((el) => el.remove());
    }
    SoapTool.ui = {
      pulseValue,
      getToastInstance,
      showAutosaveToast,
      showUndoToast,
      updateResultsMeta,
      updateResultsWarnings,
      applyHelperVisibility,
      validateNumericField,
      flashStage,
      showSoapAlert,
      clearSoapAlerts
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_layout.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    function syncStageHeight() {
      const stagePane = document.getElementById("soapStagePane");
      const qualityCard = document.getElementById("soapQualityCard");
      if (!stagePane || !qualityCard) return;
      const shouldSync = window2.matchMedia("(min-width: 768px)").matches;
      if (!shouldSync) {
        stagePane.classList.remove("is-height-synced");
        stagePane.style.removeProperty("--soap-stage-height");
        return;
      }
      const qualityHeight = qualityCard.offsetHeight;
      if (!qualityHeight) {
        stagePane.classList.remove("is-height-synced");
        stagePane.style.removeProperty("--soap-stage-height");
        return;
      }
      stagePane.style.setProperty("--soap-stage-height", `${qualityHeight}px`);
      stagePane.classList.add("is-height-synced");
    }
    const scheduleStageHeightSync = () => {
      window2.requestAnimationFrame(syncStageHeight);
    };
    SoapTool.layout = {
      syncStageHeight,
      scheduleStageHeightSync
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_mold.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { clamp, toNumber, round } = SoapTool.helpers;
    const { toGrams, fromGrams } = SoapTool.units;
    function updateMoldSuggested() {
      const settings = getMoldSettings();
      const targetInput = document.getElementById("oilTotalTarget");
      const targetHint = document.getElementById("oilTargetHint");
      if (targetInput && settings.effectiveCapacity > 0 && toGrams(targetInput.value) <= 0) {
        targetInput.value = settings.targetOils > 0 ? round(fromGrams(settings.targetOils), 2) : "";
      }
      if (targetHint) {
        if (settings.effectiveCapacity > 0) {
          targetHint.textContent = "Linked to mold sizing. Edit oil % or total oils target to update the other.";
        } else {
          targetHint.textContent = "Auto-fills when mold sizing is set.";
        }
      }
      const note = document.getElementById("moldSuggestionNote");
      if (note) {
        let message = "Target oils are capped to the mold size above.";
        if (settings.shape === "cylinder" && settings.waterWeight > 0) {
          if (settings.useCylinder) {
            message = `Cylinder correction applied (${round(settings.cylinderFactor * 100, 0)}% of capacity).`;
          } else {
            message = "Cylinder mold selected. Apply a correction if you want headspace or a smaller fill.";
          }
        }
        note.textContent = message;
      }
      updateWetBatterWarning();
    }
    function updateWetBatterWarning(batchYieldG = null) {
      var _a;
      const warning = document.getElementById("moldWetBatterWarning");
      if (!warning) return;
      const hide = () => {
        warning.classList.add("d-none");
        warning.textContent = "";
      };
      const settings = getMoldSettings();
      const state = SoapTool.state || {};
      const lastCalc = state.lastCalc || null;
      const currentTotalOils = ((_a = SoapTool.oils) == null ? void 0 : _a.getTotalOilsGrams) ? SoapTool.oils.getTotalOilsGrams() : 0;
      const calcTotalOils = toNumber(lastCalc == null ? void 0 : lastCalc.totalOils);
      let batchYield = toNumber(batchYieldG);
      if (!isFinite(batchYield) || batchYield <= 0) {
        batchYield = toNumber(lastCalc == null ? void 0 : lastCalc.batchYield);
      }
      if ((batchYieldG === null || batchYieldG === void 0) && calcTotalOils > 0 && currentTotalOils > 0 && Math.abs(calcTotalOils - currentTotalOils) > 0.01) {
        hide();
        return;
      }
      if (!isFinite(batchYield) || batchYield <= 0 || settings.effectiveCapacity <= 0) {
        hide();
        return;
      }
      const overBy = batchYield - settings.effectiveCapacity;
      if (overBy <= 0.01) {
        hide();
        return;
      }
      const unit = state.currentUnit || "g";
      warning.textContent = `Full wet batter is ${round(fromGrams(batchYield), 2)} ${unit}, exceeding mold capacity ${round(fromGrams(settings.effectiveCapacity), 2)} ${unit} by ${round(fromGrams(overBy), 2)} ${unit}. Reduce oils target/% of mold or lower water/additives.`;
      warning.classList.remove("d-none");
    }
    function syncTargetFromMold() {
      const targetInput = document.getElementById("oilTotalTarget");
      const settings = getMoldSettings();
      if (!targetInput) return settings;
      if (settings.effectiveCapacity > 0) {
        targetInput.value = settings.targetOils > 0 ? round(fromGrams(settings.targetOils), 2) : "";
      }
      updateMoldSuggested();
      return settings;
    }
    function syncMoldPctFromTarget() {
      const targetInput = document.getElementById("oilTotalTarget");
      const moldOilPct = document.getElementById("moldOilPct");
      if (!targetInput || !moldOilPct) {
        const settings2 = getMoldSettings();
        updateMoldSuggested();
        return settings2;
      }
      const settings = getMoldSettings();
      if (settings.effectiveCapacity > 0) {
        const target = toGrams(targetInput.value);
        const cappedTarget = clamp(target, 0, settings.effectiveCapacity);
        if (target > settings.effectiveCapacity + 0.01) {
          targetInput.value = round(fromGrams(cappedTarget), 2);
        }
        const nextPct = cappedTarget > 0 ? cappedTarget / settings.effectiveCapacity * 100 : 0;
        moldOilPct.value = cappedTarget > 0 ? round(nextPct, 2) : "";
      }
      const nextSettings = getMoldSettings();
      updateMoldSuggested();
      return nextSettings;
    }
    function getMoldSettings() {
      var _a, _b, _c;
      const waterWeight = toGrams(document.getElementById("moldWaterWeight").value);
      const oilPct = clamp(toNumber(document.getElementById("moldOilPct").value), 0, 100);
      const shape = ((_a = document.getElementById("moldShape")) == null ? void 0 : _a.value) || "loaf";
      const useCylinder = !!((_b = document.getElementById("moldCylinderCorrection")) == null ? void 0 : _b.checked);
      const cylinderFactor = clamp(toNumber((_c = document.getElementById("moldCylinderFactor")) == null ? void 0 : _c.value), 0.5, 1);
      const effectiveCapacity = waterWeight > 0 ? waterWeight * (useCylinder ? cylinderFactor : 1) : 0;
      const targetOils = effectiveCapacity > 0 ? effectiveCapacity * (oilPct / 100) : 0;
      return {
        waterWeight,
        oilPct,
        shape,
        useCylinder,
        cylinderFactor,
        effectiveCapacity,
        targetOils
      };
    }
    function updateMoldShapeUI() {
      var _a;
      const shape = ((_a = document.getElementById("moldShape")) == null ? void 0 : _a.value) || "loaf";
      const options = document.getElementById("moldCylinderOptions");
      if (options) {
        options.classList.toggle("d-none", shape !== "cylinder");
      }
      updateMoldSuggested();
    }
    SoapTool.mold = {
      updateMoldSuggested,
      updateWetBatterWarning,
      syncTargetFromMold,
      syncMoldPctFromTarget,
      getMoldSettings,
      updateMoldShapeUI
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_oils.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { round, toNumber, clamp, buildSoapcalcSearchBuilder } = SoapTool.helpers;
    const { toGrams, fromGrams } = SoapTool.units;
    const { OIL_CATEGORY_SET, OIL_TIP_RULES } = SoapTool.constants;
    const { computeQualities } = SoapTool.calc;
    const state = SoapTool.state;
    function attachOilTypeahead(row) {
      const input = row.querySelector(".oil-typeahead");
      const hiddenSap = row.querySelector(".oil-sap-koh");
      const hiddenIodine = row.querySelector(".oil-iodine");
      const hiddenFatty = row.querySelector(".oil-fatty");
      const hiddenGi = row.querySelector(".oil-gi-id");
      const hiddenUnit = row.querySelector(".oil-default-unit");
      const hiddenCategory = row.querySelector(".oil-category");
      const list = row.querySelector('[data-role="suggestions"]');
      if (!input || !list || typeof window2.attachMergedInventoryGlobalTypeahead !== "function") {
        return;
      }
      const builder = buildSoapcalcSearchBuilder();
      window2.attachMergedInventoryGlobalTypeahead({
        inputEl: input,
        listEl: list,
        mode: "public",
        giHiddenEl: hiddenGi,
        includeInventory: false,
        includeGlobal: true,
        ingredientFirst: true,
        globalUrlBuilder: builder,
        searchType: "ingredient",
        resultFilter: (item, source) => matchesCategory(item, OIL_CATEGORY_SET, source),
        requireHidden: false,
        onSelection: function(picked) {
          if (hiddenSap) {
            hiddenSap.value = (picked == null ? void 0 : picked.saponification_value) || "";
          }
          if (hiddenIodine) {
            hiddenIodine.value = (picked == null ? void 0 : picked.iodine_value) || "";
          }
          if (hiddenFatty) {
            hiddenFatty.value = (picked == null ? void 0 : picked.fatty_acid_profile) ? JSON.stringify(picked.fatty_acid_profile) : "";
          }
          if (hiddenUnit) {
            hiddenUnit.value = (picked == null ? void 0 : picked.default_unit) || "";
          }
          if (hiddenCategory) {
            hiddenCategory.value = (picked == null ? void 0 : picked.ingredient_category_name) || "";
          }
          setSelectedOilProfile(picked);
          updateOilTotals();
          SoapTool.storage.queueStateSave();
          SoapTool.storage.queueAutoCalc();
        }
      });
      input.addEventListener("input", function() {
        if (!this.value.trim()) {
          if (hiddenSap) hiddenSap.value = "";
          if (hiddenIodine) hiddenIodine.value = "";
          if (hiddenFatty) hiddenFatty.value = "";
          if (hiddenGi) hiddenGi.value = "";
          if (hiddenUnit) hiddenUnit.value = "";
          if (hiddenCategory) hiddenCategory.value = "";
          clearSelectedOilProfile();
        }
      });
    }
    function buildOilRow() {
      var _a, _b;
      const template = document.getElementById("oilRowTemplate");
      const row = (_b = (_a = template == null ? void 0 : template.content) == null ? void 0 : _a.querySelector(".oil-row")) == null ? void 0 : _b.cloneNode(true);
      if (!row) {
        return document.createElement("div");
      }
      row.querySelectorAll("input").forEach((input) => {
        input.value = "";
      });
      row.querySelectorAll(".form-text").forEach((text) => {
        const wrapper = text.closest('.soap-field-stack, [class*="col-"]');
        if (wrapper) wrapper.classList.add("soap-field");
      });
      attachOilTypeahead(row);
      row.querySelectorAll(".unit-suffix").forEach((el) => {
        el.dataset.suffix = state.currentUnit;
      });
      return row;
    }
    function getOilTargetGrams() {
      const targetInput = document.getElementById("oilTotalTarget");
      const manualTarget = toGrams(targetInput == null ? void 0 : targetInput.value);
      if (manualTarget > 0) return manualTarget;
      const mold = SoapTool.mold.getMoldSettings();
      if (mold.targetOils > 0) return mold.targetOils;
      return 0;
    }
    function deriveTargetFromRows(rows) {
      const derived = [];
      rows.forEach((row) => {
        var _a, _b;
        const grams = toGrams((_a = row.querySelector(".oil-grams")) == null ? void 0 : _a.value);
        const pct = clamp(toNumber((_b = row.querySelector(".oil-percent")) == null ? void 0 : _b.value), 0);
        if (grams > 0 && pct > 0) {
          derived.push(grams / (pct / 100));
        }
      });
      if (!derived.length) return 0;
      const sum = derived.reduce((acc, value) => acc + value, 0);
      return sum / derived.length;
    }
    function getRowLimits(row, target) {
      if (!row || !target || target <= 0) {
        return { allowedGrams: null, allowedPct: null };
      }
      const rows = Array.from(document.querySelectorAll("#oilRows .oil-row"));
      const otherTotal = rows.reduce((acc, current) => {
        var _a;
        if (current === row) return acc;
        return acc + toGrams((_a = current.querySelector(".oil-grams")) == null ? void 0 : _a.value);
      }, 0);
      const otherPct = rows.reduce((acc, current) => {
        var _a;
        if (current === row) return acc;
        return acc + clamp(toNumber((_a = current.querySelector(".oil-percent")) == null ? void 0 : _a.value), 0);
      }, 0);
      const allowedPct = Math.max(0, 100 - otherPct);
      const allowedByTotal = Math.max(0, target - otherTotal);
      const allowedByPct = target * allowedPct / 100;
      const allowedGrams = Math.max(0, Math.min(allowedByTotal, allowedByPct));
      return { allowedGrams, allowedPct };
    }
    function setOilHint(row, field, message) {
      if (!row) return;
      const hint = row.querySelector(`[data-role="oil-${field}-hint"]`);
      if (!hint) return;
      if (message) {
        hint.textContent = message;
        hint.classList.add("is-visible");
      } else {
        hint.textContent = "";
        hint.classList.remove("is-visible");
      }
    }
    function bounceInput(input) {
      if (!input) return;
      input.classList.remove("oil-input-bounce");
      void input.offsetWidth;
      input.classList.add("oil-input-bounce");
    }
    function validateOilEntry(row, field, options = {}) {
      const target = getOilTargetGrams();
      if (!row || !target || target <= 0) {
        setOilHint(row, field, "");
        return;
      }
      const gramsInput = row.querySelector(".oil-grams");
      const pctInput = row.querySelector(".oil-percent");
      const limits = getRowLimits(row, target);
      if (field === "grams" && gramsInput) {
        const grams = toGrams(gramsInput.value);
        let message = "";
        if (grams > target + 0.01) {
          message = "Entry exceeds the max oils allowed in stage 2.";
        } else if (limits.allowedGrams !== null && grams > limits.allowedGrams + 0.01) {
          message = `Must be under ${round(fromGrams(limits.allowedGrams), 2)} ${state.currentUnit} to stay within the stage 2 oil limit.`;
        }
        if (message) {
          const nextValue = limits.allowedGrams !== null ? round(fromGrams(limits.allowedGrams), 2) : round(fromGrams(target), 2);
          gramsInput.value = nextValue > 0 ? nextValue : "";
          setOilHint(row, field, message);
          gramsInput.classList.add("oil-input-warning");
          bounceInput(gramsInput);
          updateOilTotals();
        } else {
          gramsInput.classList.remove("oil-input-warning");
          setOilHint(row, field, "");
        }
      }
      if (field === "percent" && pctInput) {
        const pct = clamp(toNumber(pctInput.value), 0);
        let message = "";
        if (pct > 100.01) {
          message = "Entry exceeds the max oils allowed in stage 2.";
        } else if (limits.allowedPct !== null && pct > limits.allowedPct + 0.01) {
          message = `Must be under ${round(limits.allowedPct, 2)}% to stay within the stage 2 oil limit.`;
        }
        if (message) {
          const nextPct = limits.allowedPct !== null ? round(limits.allowedPct, 2) : 100;
          pctInput.value = nextPct > 0 ? nextPct : "";
          setOilHint(row, field, message);
          pctInput.classList.add("oil-input-warning");
          bounceInput(pctInput);
          updateOilTotals();
        } else {
          pctInput.classList.remove("oil-input-warning");
          setOilHint(row, field, "");
        }
      }
    }
    function scaleOilsToTarget(target, options = {}) {
      const rows = Array.from(document.querySelectorAll("#oilRows .oil-row"));
      const nextTarget = target != null ? target : getOilTargetGrams();
      const force = !!options.force;
      if (!nextTarget || nextTarget <= 0 || !rows.length) {
        state.lastOilTarget = nextTarget;
        return;
      }
      const totalPct = rows.reduce((sum, row) => {
        var _a;
        return sum + clamp(toNumber((_a = row.querySelector(".oil-percent")) == null ? void 0 : _a.value), 0);
      }, 0);
      const totalWeight = rows.reduce((sum, row) => {
        var _a;
        return sum + toGrams((_a = row.querySelector(".oil-grams")) == null ? void 0 : _a.value);
      }, 0);
      if (totalPct <= 0 && totalWeight <= 0) {
        state.lastOilTarget = nextTarget;
        return;
      }
      if (!force && state.lastOilTarget && Math.abs(state.lastOilTarget - nextTarget) < 0.01) {
        return;
      }
      if (totalPct > 0) {
        rows.forEach((row) => {
          const pctInput = row.querySelector(".oil-percent");
          const gramsInput = row.querySelector(".oil-grams");
          const pct = clamp(toNumber(pctInput == null ? void 0 : pctInput.value), 0);
          const share = totalPct > 0 ? pct / totalPct : 0;
          if (gramsInput) {
            gramsInput.value = share > 0 ? round(fromGrams(nextTarget * share), 2) : "";
          }
          if (pctInput) {
            pctInput.value = share > 0 ? round(share * 100, 2) : "";
          }
        });
      } else if (totalWeight > 0) {
        const ratio = nextTarget / totalWeight;
        rows.forEach((row) => {
          const gramsInput = row.querySelector(".oil-grams");
          const pctInput = row.querySelector(".oil-percent");
          const grams = toGrams(gramsInput == null ? void 0 : gramsInput.value);
          if (gramsInput) {
            const nextGrams = grams > 0 ? grams * ratio : 0;
            gramsInput.value = nextGrams > 0 ? round(fromGrams(nextGrams), 2) : "";
          }
          if (pctInput) {
            const nextGrams = toGrams(gramsInput == null ? void 0 : gramsInput.value);
            pctInput.value = nextGrams > 0 ? round(nextGrams / nextTarget * 100, 2) : "";
          }
        });
      }
      state.lastOilTarget = nextTarget;
      updateOilTotals({ skipEnforce: true });
    }
    function enforceOilTargetCap(rows, target) {
      if (!state.lastOilEdit || !state.lastOilEdit.row) return false;
      const lastRow = state.lastOilEdit.row;
      const otherTotal = rows.reduce((acc, row) => {
        var _a;
        if (row === lastRow) return acc;
        return acc + toGrams((_a = row.querySelector(".oil-grams")) == null ? void 0 : _a.value);
      }, 0);
      const allowed = Math.max(0, target - otherTotal);
      const gramsInput = lastRow.querySelector(".oil-grams");
      const pctInput = lastRow.querySelector(".oil-percent");
      if (!gramsInput || !pctInput) return false;
      gramsInput.value = allowed > 0 ? round(fromGrams(allowed), 2) : "";
      pctInput.value = allowed > 0 ? round(allowed / target * 100, 2) : "";
      state.wasCapped = true;
      return true;
    }
    function updateOilLimitWarning({ totalWeight, totalPct, target, capped }) {
      const warning = document.getElementById("oilLimitWarning");
      if (!warning) return;
      const messages = [];
      if (capped) {
        messages.push("Oil total hit the mold cap and was adjusted.");
      }
      if (target > 0 && totalWeight > target + 0.01) {
        const over = totalWeight - target;
        messages.push(`Oil weights exceed the target by ${round(fromGrams(over), 2)} ${state.currentUnit}.`);
      }
      if (totalPct > 100.01) {
        messages.push(`Oil percentages are over 100% by ${round(totalPct - 100, 2)}%.`);
      }
      if (messages.length) {
        warning.classList.remove("d-none");
        warning.innerHTML = `${messages.join(" ")} Adjust oils or mold % to continue.`;
      } else {
        warning.classList.add("d-none");
        warning.textContent = "";
      }
    }
    function updateOilTotals(options = {}) {
      if (!options.skipEnforce) {
        state.wasCapped = false;
      }
      const rows = Array.from(document.querySelectorAll("#oilRows .oil-row"));
      const mold = SoapTool.mold.getMoldSettings();
      let target = getOilTargetGrams();
      if (!target && !mold.targetOils) {
        const derived = deriveTargetFromRows(rows);
        if (derived > 0) {
          target = derived;
          const targetInput = document.getElementById("oilTotalTarget");
          if (targetInput && !targetInput.value) {
            targetInput.value = round(fromGrams(derived), 2);
          }
        }
      }
      let totalWeight = 0;
      let totalPct = 0;
      rows.forEach((row) => {
        const gramsInput = row.querySelector(".oil-grams");
        const pctInput = row.querySelector(".oil-percent");
        let grams = toGrams(gramsInput == null ? void 0 : gramsInput.value);
        let pct = clamp(toNumber(pctInput == null ? void 0 : pctInput.value), 0);
        if (target > 0) {
          if (state.lastOilEdit && state.lastOilEdit.row === row && state.lastOilEdit.field === "percent") {
            grams = pct > 0 ? target * (pct / 100) : 0;
            gramsInput.value = pct > 0 ? round(fromGrams(grams), 2) : "";
          } else {
            if (grams > 0) {
              pct = grams / target * 100;
              pctInput.value = round(pct, 2);
            } else if (pct > 0) {
              grams = target * (pct / 100);
              gramsInput.value = round(fromGrams(grams), 2);
            }
          }
          totalPct += pct;
        }
        if (grams > 0) totalWeight += grams;
      });
      if (target <= 0) {
        if (totalWeight > 0) {
          totalPct = 0;
          rows.forEach((row) => {
            const gramsInput = row.querySelector(".oil-grams");
            const pctInput = row.querySelector(".oil-percent");
            const grams = toGrams(gramsInput == null ? void 0 : gramsInput.value);
            if (grams > 0) {
              const pct = grams / totalWeight * 100;
              pctInput.value = round(pct, 2);
              totalPct += pct;
            }
          });
        } else {
          totalPct = rows.reduce((sum, row) => {
            var _a;
            return sum + clamp(toNumber((_a = row.querySelector(".oil-percent")) == null ? void 0 : _a.value), 0);
          }, 0);
        }
      }
      if (!options.skipEnforce && mold.targetOils > 0 && totalWeight > mold.targetOils + 0.01) {
        if (enforceOilTargetCap(rows, mold.targetOils)) {
          return updateOilTotals({ skipEnforce: true });
        }
      }
      state.totalOilsGrams = totalWeight;
      const totalLabel = document.getElementById("oilTotalComputed");
      if (totalLabel) {
        totalLabel.textContent = totalWeight > 0 ? `${round(fromGrams(totalWeight), 2)} ${state.currentUnit}` : "--";
      }
      document.getElementById("oilPercentTotal").textContent = round(totalPct, 2);
      updateOilLimitWarning({ totalWeight, totalPct, target, capped: state.wasCapped });
      SoapTool.additives.updateAdditivesOutput(totalWeight);
      SoapTool.mold.updateMoldSuggested();
      updateOilTips();
      return { totalWeight, totalPct, target };
    }
    function normalizeOils() {
      const rows = Array.from(document.querySelectorAll("#oilRows .oil-row"));
      if (!rows.length) return;
      const target = getOilTargetGrams();
      let totalPct = rows.reduce((sum, row) => {
        var _a;
        return sum + clamp(toNumber((_a = row.querySelector(".oil-percent")) == null ? void 0 : _a.value), 0);
      }, 0);
      if (!totalPct && target > 0) {
        totalPct = rows.reduce((sum, row) => {
          var _a;
          const grams = toGrams((_a = row.querySelector(".oil-grams")) == null ? void 0 : _a.value);
          return sum + (grams > 0 ? grams / target * 100 : 0);
        }, 0);
      }
      if (totalPct <= 0) return;
      rows.forEach((row) => {
        const pctInput = row.querySelector(".oil-percent");
        const gramsInput = row.querySelector(".oil-grams");
        const pct = clamp(toNumber(pctInput.value), 0);
        const nextPct = pct / totalPct * 100;
        pctInput.value = round(nextPct, 2);
        if (target > 0) {
          gramsInput.value = nextPct > 0 ? round(fromGrams(target * (nextPct / 100)), 2) : "";
        }
      });
      updateOilTotals();
    }
    function collectOilData() {
      const oils = [];
      document.querySelectorAll("#oilRows .oil-row").forEach((row) => {
        var _a, _b, _c, _d, _e, _f, _g, _h, _i;
        const name = (_b = (_a = row.querySelector(".oil-typeahead")) == null ? void 0 : _a.value) == null ? void 0 : _b.trim();
        const grams = toGrams((_c = row.querySelector(".oil-grams")) == null ? void 0 : _c.value);
        const sapKoh = toNumber((_d = row.querySelector(".oil-sap-koh")) == null ? void 0 : _d.value);
        const iodine = toNumber((_e = row.querySelector(".oil-iodine")) == null ? void 0 : _e.value);
        const fattyRaw = ((_f = row.querySelector(".oil-fatty")) == null ? void 0 : _f.value) || "";
        const gi = ((_g = row.querySelector(".oil-gi-id")) == null ? void 0 : _g.value) || "";
        const defaultUnit = ((_h = row.querySelector(".oil-default-unit")) == null ? void 0 : _h.value) || "";
        const categoryName = ((_i = row.querySelector(".oil-category")) == null ? void 0 : _i.value) || "";
        let fattyProfile = null;
        if (fattyRaw) {
          try {
            fattyProfile = JSON.parse(fattyRaw);
          } catch (_) {
            fattyProfile = null;
          }
        }
        if (grams <= 0) return;
        oils.push({
          name: name || null,
          grams,
          sapKoh,
          iodine,
          fattyProfile,
          global_item_id: gi ? parseInt(gi) : null,
          default_unit: defaultUnit || null,
          ingredient_category_name: categoryName || null
        });
      });
      return oils;
    }
    function updateSelectedOilProfileDisplay({ name, sapKoh, iodine, fattyProfile } = {}) {
      const floatCard = document.getElementById("oilProfileFloat");
      const setText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
      };
      const nameLabel = name || "Pick an oil to preview";
      setText("selectedOilName", nameLabel);
      setText("selectedOilModalName", nameLabel);
      if (floatCard) {
        floatCard.classList.toggle("d-none", !name);
      }
      const sapValue = sapKoh > 0 ? round(sapKoh, 1) : "--";
      const iodineValue = iodine > 0 ? round(iodine, 1) : "--";
      setText("selectedOilSap", sapValue);
      setText("selectedOilModalSap", sapValue);
      setText("selectedOilIodine", iodineValue);
      setText("selectedOilModalIodine", iodineValue);
      const qualities = fattyProfile ? computeQualities(fattyProfile) : {};
      const setValue = (id, value) => {
        const safe = isFinite(value) && value > 0 ? round(value, 1) : "--";
        setText(id, safe);
      };
      setValue("selectedOilHardness", qualities.hardness);
      setValue("selectedOilModalHardness", qualities.hardness);
      setValue("selectedOilCleansing", qualities.cleansing);
      setValue("selectedOilModalCleansing", qualities.cleansing);
      setValue("selectedOilConditioning", qualities.conditioning);
      setValue("selectedOilModalConditioning", qualities.conditioning);
      setValue("selectedOilBubbly", qualities.bubbly);
      setValue("selectedOilModalBubbly", qualities.bubbly);
      setValue("selectedOilCreamy", qualities.creamy);
      setValue("selectedOilModalCreamy", qualities.creamy);
      const fattyKeys = ["lauric", "myristic", "palmitic", "stearic", "ricinoleic", "oleic", "linoleic", "linolenic"];
      fattyKeys.forEach((key) => {
        const baseId = `selectedOil${key.charAt(0).toUpperCase()}${key.slice(1)}`;
        const modalId = `selectedOilModal${key.charAt(0).toUpperCase()}${key.slice(1)}`;
        const value = fattyProfile ? toNumber(fattyProfile[key]) : 0;
        const safe = value > 0 ? round(value, 1) : "--";
        setText(baseId, safe);
        setText(modalId, safe);
      });
    }
    function setSelectedOilProfile(picked) {
      if (!picked) {
        clearSelectedOilProfile();
        return;
      }
      state.selectedOilProfile = picked;
      let fattyProfile = picked.fatty_acid_profile || null;
      if (typeof fattyProfile === "string") {
        try {
          fattyProfile = JSON.parse(fattyProfile);
        } catch (_) {
          fattyProfile = null;
        }
      }
      updateSelectedOilProfileDisplay({
        name: picked.text || picked.display_name || picked.name,
        sapKoh: toNumber(picked.saponification_value),
        iodine: toNumber(picked.iodine_value),
        fattyProfile
      });
    }
    function setSelectedOilProfileFromRow(row) {
      var _a, _b, _c, _d, _e;
      if (!row) return;
      const name = (_b = (_a = row.querySelector(".oil-typeahead")) == null ? void 0 : _a.value) == null ? void 0 : _b.trim();
      const sapKoh = toNumber((_c = row.querySelector(".oil-sap-koh")) == null ? void 0 : _c.value);
      const iodine = toNumber((_d = row.querySelector(".oil-iodine")) == null ? void 0 : _d.value);
      const fattyRaw = ((_e = row.querySelector(".oil-fatty")) == null ? void 0 : _e.value) || "";
      let fattyProfile = null;
      if (fattyRaw) {
        try {
          fattyProfile = JSON.parse(fattyRaw);
        } catch (_) {
          fattyProfile = null;
        }
      }
      updateSelectedOilProfileDisplay({
        name,
        sapKoh,
        iodine,
        fattyProfile
      });
    }
    function clearSelectedOilProfile() {
      state.selectedOilProfile = null;
      state.lastPreviewRow = null;
      updateSelectedOilProfileDisplay();
    }
    function updateOilTips() {
      const tipBox = document.getElementById("oilBlendTips");
      if (!tipBox) return;
      const oils = collectOilData().filter((oil) => oil.grams > 0 || oil.percent > 0);
      if (!oils.length) {
        tipBox.classList.add("d-none");
        tipBox.textContent = "";
        return;
      }
      const tips = /* @__PURE__ */ new Set();
      oils.forEach((oil) => {
        const name = (oil.name || "").toLowerCase();
        if (name) {
          OIL_TIP_RULES.forEach((rule) => {
            if (rule.match.test(name)) tips.add(rule.tip);
          });
        }
        if (oil.fattyProfile && typeof oil.fattyProfile === "object") {
          const lauric = toNumber(oil.fattyProfile.lauric);
          const myristic = toNumber(oil.fattyProfile.myristic);
          const palmitic = toNumber(oil.fattyProfile.palmitic);
          const stearic = toNumber(oil.fattyProfile.stearic);
          const ricinoleic = toNumber(oil.fattyProfile.ricinoleic);
          const oleic = toNumber(oil.fattyProfile.oleic);
          const linoleic = toNumber(oil.fattyProfile.linoleic);
          const linolenic = toNumber(oil.fattyProfile.linolenic);
          if (lauric + myristic >= 30) {
            tips.add(`${oil.name || "This oil"} is high in lauric/myristic; expect faster trace and stronger cleansing.`);
          }
          if (palmitic + stearic >= 40) {
            tips.add(`${oil.name || "This oil"} is high in palmitic/stearic; expect a harder bar and quicker set-up.`);
          }
          if (oleic >= 60) {
            tips.add(`${oil.name || "This oil"} is high oleic; trace may be slow and bars may start softer.`);
          }
          if (linoleic + linolenic >= 20) {
            tips.add(`${oil.name || "This oil"} is high in PUFAs; keep the % lower to reduce DOS risk.`);
          }
          if (ricinoleic >= 60) {
            tips.add(`${oil.name || "This oil"} boosts lather but can feel tacky; keep under 10-15%.`);
          }
        }
      });
      const tipList = Array.from(tips).slice(0, 6);
      if (!tipList.length) {
        tipBox.classList.add("d-none");
        tipBox.textContent = "";
        return;
      }
      tipBox.classList.remove("d-none");
      tipBox.innerHTML = `<strong>Blend behavior tips:</strong><ul class="mb-0">${tipList.map((tip) => `<li>${tip}</li>`).join("")}</ul>`;
    }
    function getTotalOilsGrams() {
      return state.totalOilsGrams || 0;
    }
    function serializeOilRow(row) {
      var _a, _b, _c, _d, _e, _f, _g, _h, _i;
      if (!row) return null;
      return {
        name: ((_a = row.querySelector(".oil-typeahead")) == null ? void 0 : _a.value) || "",
        grams: ((_b = row.querySelector(".oil-grams")) == null ? void 0 : _b.value) || "",
        percent: ((_c = row.querySelector(".oil-percent")) == null ? void 0 : _c.value) || "",
        sap: ((_d = row.querySelector(".oil-sap-koh")) == null ? void 0 : _d.value) || "",
        iodine: ((_e = row.querySelector(".oil-iodine")) == null ? void 0 : _e.value) || "",
        fattyRaw: ((_f = row.querySelector(".oil-fatty")) == null ? void 0 : _f.value) || "",
        gi: ((_g = row.querySelector(".oil-gi-id")) == null ? void 0 : _g.value) || "",
        defaultUnit: ((_h = row.querySelector(".oil-default-unit")) == null ? void 0 : _h.value) || "",
        categoryName: ((_i = row.querySelector(".oil-category")) == null ? void 0 : _i.value) || ""
      };
    }
    function matchesCategory(item, allowedSet, source) {
      const category = getItemCategoryName(item);
      if (!category) {
        return source === "inventory";
      }
      return allowedSet.has(category);
    }
    function getItemCategoryName(item) {
      if (!item || typeof item !== "object") return null;
      return item.ingredient && item.ingredient.ingredient_category_name || item.ingredient_category_name || item.ingredient_category && item.ingredient_category.name || null;
    }
    SoapTool.oils = {
      attachOilTypeahead,
      buildOilRow,
      getOilTargetGrams,
      updateOilTotals,
      normalizeOils,
      collectOilData,
      setSelectedOilProfileFromRow,
      clearSelectedOilProfile,
      updateOilTips,
      getTotalOilsGrams,
      serializeOilRow,
      validateOilEntry,
      scaleOilsToTarget
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_bulk_oils_shared.js
  (function(window2) {
    "use strict";
    var _a;
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const bulk = SoapTool.bulkOils = SoapTool.bulkOils || {};
    const { toNumber, clamp } = SoapTool.helpers;
    const state = SoapTool.state;
    const FATTY_KEYS = Array.isArray((_a = SoapTool.constants) == null ? void 0 : _a.FATTY_DISPLAY_KEYS) ? SoapTool.constants.FATTY_DISPLAY_KEYS.slice() : ["lauric", "myristic", "palmitic", "stearic", "ricinoleic", "oleic", "linoleic", "linolenic"];
    const LOCAL_SORT_KEYS = /* @__PURE__ */ new Set(["selected_pct", "selected_weight_g"]);
    const PAGE_SIZE = 25;
    const SCROLL_FETCH_THRESHOLD = 140;
    const SEARCH_DEBOUNCE_MS = 260;
    const DEFAULT_MODAL_STATE = {
      mode: "basics",
      viewSelected: false,
      query: "",
      sortKey: "name",
      sortDir: "asc",
      selection: {},
      recordByKey: {},
      visibleRecords: [],
      offset: 0,
      totalCount: 0,
      hasMore: true,
      loading: false,
      requestToken: 0
    };
    function queueStateSave() {
      var _a2, _b;
      (_b = (_a2 = SoapTool.storage) == null ? void 0 : _a2.queueStateSave) == null ? void 0 : _b.call(_a2);
    }
    function showAlert(level, message) {
      var _a2, _b;
      (_b = (_a2 = SoapTool.ui) == null ? void 0 : _a2.showSoapAlert) == null ? void 0 : _b.call(_a2, level, message, { dismissible: true, timeoutMs: 6e3 });
    }
    function getRefs() {
      return {
        modalEl: document.getElementById("bulkOilModal"),
        openBtn: document.getElementById("openBulkOilModal"),
        searchInput: document.getElementById("bulkOilSearchInput"),
        modeToggle: document.getElementById("bulkOilDisplayAllToggle"),
        viewSelectedToggle: document.getElementById("bulkOilViewSelectedToggle"),
        statusEl: document.getElementById("bulkOilCatalogStatus"),
        summaryEl: document.getElementById("bulkOilSelectedSummary"),
        stageCountEl: document.getElementById("bulkOilSelectionCount"),
        bodyEl: document.getElementById("bulkOilCatalogBody"),
        scrollEl: document.getElementById("bulkOilCatalogScroll"),
        importBtn: document.getElementById("bulkOilImportBtn"),
        clearBtn: document.getElementById("bulkOilClearSelectionBtn"),
        unitLabelEl: document.getElementById("bulkOilWeightUnitLabel")
      };
    }
    function isSupportedSortKey(sortKey) {
      if (!sortKey) return false;
      if (sortKey === "name") return true;
      if (LOCAL_SORT_KEYS.has(sortKey)) return true;
      return FATTY_KEYS.includes(sortKey);
    }
    function ensureModalState() {
      if (!state.bulkOilModal || typeof state.bulkOilModal !== "object") {
        state.bulkOilModal = JSON.parse(JSON.stringify(DEFAULT_MODAL_STATE));
      }
      const modalState = state.bulkOilModal;
      modalState.mode = modalState.mode === "all" ? "all" : "basics";
      modalState.viewSelected = !!modalState.viewSelected;
      modalState.query = typeof modalState.query === "string" ? modalState.query : "";
      modalState.sortKey = isSupportedSortKey(modalState.sortKey) ? modalState.sortKey : "name";
      modalState.sortDir = modalState.sortDir === "desc" ? "desc" : "asc";
      modalState.selection = modalState.selection && typeof modalState.selection === "object" ? modalState.selection : {};
      modalState.recordByKey = modalState.recordByKey && typeof modalState.recordByKey === "object" ? modalState.recordByKey : {};
      modalState.visibleRecords = Array.isArray(modalState.visibleRecords) ? modalState.visibleRecords : [];
      modalState.offset = Math.max(0, parseInt(modalState.offset, 10) || 0);
      modalState.totalCount = Math.max(0, parseInt(modalState.totalCount, 10) || 0);
      modalState.hasMore = modalState.hasMore !== false;
      modalState.loading = !!modalState.loading;
      modalState.requestToken = Math.max(0, parseInt(modalState.requestToken, 10) || 0);
      return modalState;
    }
    function normalizeFattyProfile(rawProfile) {
      const profile = {};
      const input = rawProfile && typeof rawProfile === "object" ? rawProfile : {};
      FATTY_KEYS.forEach((key) => {
        const value = toNumber(input[key]);
        if (value > 0) {
          profile[key] = value;
        }
      });
      return profile;
    }
    function normalizeCatalogRecord(raw) {
      const fattyProfile = normalizeFattyProfile(raw == null ? void 0 : raw.fatty_profile);
      const name = String((raw == null ? void 0 : raw.name) || "").trim();
      const source = String((raw == null ? void 0 : raw.source) || "soapcalc").trim().toLowerCase() || "soapcalc";
      const globalItemId = Number.isInteger(raw == null ? void 0 : raw.global_item_id) ? raw.global_item_id : toNumber(raw == null ? void 0 : raw.global_item_id) > 0 ? parseInt(raw.global_item_id, 10) : null;
      const key = String((raw == null ? void 0 : raw.key) || (globalItemId ? `global:${globalItemId}` : `${source}:${name.toLowerCase()}`));
      return {
        key,
        name,
        sap_koh: toNumber(raw == null ? void 0 : raw.sap_koh),
        iodine: toNumber(raw == null ? void 0 : raw.iodine),
        fatty_profile: fattyProfile,
        default_unit: String((raw == null ? void 0 : raw.default_unit) || "gram"),
        ingredient_category_name: String((raw == null ? void 0 : raw.ingredient_category_name) || "Oils (Carrier & Fixed)"),
        global_item_id: globalItemId,
        source,
        is_basic: !!(raw == null ? void 0 : raw.is_basic)
      };
    }
    function updateSelectionCounters() {
      const refs = getRefs();
      const modalState = ensureModalState();
      const count = Object.keys(modalState.selection || {}).length;
      const summary = `Selected: ${count}`;
      if (refs.summaryEl) refs.summaryEl.textContent = summary;
      if (refs.stageCountEl) refs.stageCountEl.textContent = String(count);
    }
    function selectionForRecordKey(recordKey) {
      var _a2;
      const modalState = ensureModalState();
      return ((_a2 = modalState.selection) == null ? void 0 : _a2[recordKey]) || null;
    }
    function setSelection(record, values = {}) {
      var _a2, _b;
      const modalState = ensureModalState();
      if (!record || !record.key) return null;
      const existing = modalState.selection[record.key] || {};
      const next = {
        key: record.key,
        name: record.name,
        sap_koh: record.sap_koh,
        iodine: record.iodine,
        fatty_profile: record.fatty_profile || {},
        default_unit: record.default_unit || "gram",
        ingredient_category_name: record.ingredient_category_name || "",
        global_item_id: record.global_item_id || null,
        source: record.source || "soapcalc",
        is_basic: !!record.is_basic,
        selected_pct: clamp(toNumber((_a2 = values.selected_pct) != null ? _a2 : existing.selected_pct), 0, 100),
        selected_weight_g: clamp(toNumber((_b = values.selected_weight_g) != null ? _b : existing.selected_weight_g), 0)
      };
      modalState.selection[record.key] = next;
      return next;
    }
    function removeSelection(recordKey) {
      var _a2;
      const modalState = ensureModalState();
      if ((_a2 = modalState.selection) == null ? void 0 : _a2[recordKey]) {
        delete modalState.selection[recordKey];
      }
    }
    function getRecordByKey(recordKey) {
      var _a2;
      const modalState = ensureModalState();
      return ((_a2 = modalState.recordByKey) == null ? void 0 : _a2[recordKey]) || null;
    }
    function serializeSelection() {
      const modalState = ensureModalState();
      return {
        mode: modalState.mode,
        view_selected: !!modalState.viewSelected,
        query: modalState.query,
        sort_key: modalState.sortKey,
        sort_dir: modalState.sortDir,
        selections: Object.values(modalState.selection || {}).map((item) => ({
          key: item.key,
          name: item.name,
          sap_koh: item.sap_koh,
          iodine: item.iodine,
          fatty_profile: item.fatty_profile || {},
          default_unit: item.default_unit,
          ingredient_category_name: item.ingredient_category_name,
          global_item_id: item.global_item_id,
          source: item.source,
          is_basic: !!item.is_basic,
          selected_pct: clamp(toNumber(item.selected_pct), 0, 100),
          selected_weight_g: clamp(toNumber(item.selected_weight_g), 0)
        }))
      };
    }
    function restoreState(savedState) {
      const modalState = ensureModalState();
      modalState.mode = (savedState == null ? void 0 : savedState.mode) === "all" ? "all" : "basics";
      modalState.viewSelected = !!(savedState == null ? void 0 : savedState.view_selected);
      modalState.query = typeof (savedState == null ? void 0 : savedState.query) === "string" ? savedState.query : "";
      modalState.sortKey = isSupportedSortKey(savedState == null ? void 0 : savedState.sort_key) ? savedState.sort_key : "name";
      modalState.sortDir = (savedState == null ? void 0 : savedState.sort_dir) === "desc" ? "desc" : "asc";
      const selection = {};
      const rows = Array.isArray(savedState == null ? void 0 : savedState.selections) ? savedState.selections : [];
      rows.forEach((raw) => {
        const key = String((raw == null ? void 0 : raw.key) || "").trim();
        const name = String((raw == null ? void 0 : raw.name) || "").trim();
        if (!key || !name) return;
        selection[key] = {
          key,
          name,
          sap_koh: toNumber(raw == null ? void 0 : raw.sap_koh),
          iodine: toNumber(raw == null ? void 0 : raw.iodine),
          fatty_profile: normalizeFattyProfile(raw == null ? void 0 : raw.fatty_profile),
          default_unit: String((raw == null ? void 0 : raw.default_unit) || "gram"),
          ingredient_category_name: String((raw == null ? void 0 : raw.ingredient_category_name) || ""),
          global_item_id: toNumber(raw == null ? void 0 : raw.global_item_id) > 0 ? parseInt(raw.global_item_id, 10) : null,
          source: String((raw == null ? void 0 : raw.source) || "soapcalc"),
          is_basic: !!(raw == null ? void 0 : raw.is_basic),
          selected_pct: clamp(toNumber(raw == null ? void 0 : raw.selected_pct), 0, 100),
          selected_weight_g: clamp(toNumber(raw == null ? void 0 : raw.selected_weight_g), 0)
        };
      });
      modalState.selection = selection;
      modalState.visibleRecords = [];
      modalState.offset = 0;
      modalState.totalCount = 0;
      modalState.hasMore = true;
      modalState.loading = false;
      updateSelectionCounters();
    }
    bulk.shared = {
      FATTY_KEYS,
      LOCAL_SORT_KEYS,
      PAGE_SIZE,
      SCROLL_FETCH_THRESHOLD,
      SEARCH_DEBOUNCE_MS,
      queueStateSave,
      showAlert,
      getRefs,
      ensureModalState,
      normalizeFattyProfile,
      normalizeCatalogRecord,
      updateSelectionCounters,
      selectionForRecordKey,
      setSelection,
      removeSelection,
      getRecordByKey,
      serializeSelection,
      restoreState
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_bulk_oils_render.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const bulk = SoapTool.bulkOils = SoapTool.bulkOils || {};
    const shared = bulk.shared;
    if (!shared) return;
    const { round, toNumber } = SoapTool.helpers;
    const { fromGrams } = SoapTool.units;
    const {
      FATTY_KEYS,
      LOCAL_SORT_KEYS,
      getRefs,
      ensureModalState,
      selectionForRecordKey,
      updateSelectionCounters
    } = shared;
    function updateStatusText(text) {
      const refs = getRefs();
      if (refs.statusEl) refs.statusEl.textContent = text;
    }
    function refreshCatalogStatus() {
      const modalState = ensureModalState();
      const modeLabel = modalState.mode === "all" ? "all oils" : "SoapCalc basics";
      if (modalState.loading && !modalState.visibleRecords.length) {
        updateStatusText("Loading oils...");
        return;
      }
      if (!modalState.visibleRecords.length) {
        const noMatchLabel = modalState.query ? "No oils match that search." : "No oils available.";
        updateStatusText(noMatchLabel);
        return;
      }
      const loaded = modalState.visibleRecords.length;
      const total = modalState.totalCount;
      const moreHint = modalState.hasMore ? " \u2022 scroll for more" : "";
      const queryHint = modalState.query ? ` \u2022 search: "${modalState.query}"` : "";
      updateStatusText(`Loaded ${loaded}/${total} in ${modeLabel}${queryHint}${moreHint}`);
    }
    function compareValues(aValue, bValue, dir) {
      if (typeof aValue === "string" || typeof bValue === "string") {
        const left = String(aValue || "").toLowerCase();
        const right = String(bValue || "").toLowerCase();
        if (left < right) return dir === "asc" ? -1 : 1;
        if (left > right) return dir === "asc" ? 1 : -1;
        return 0;
      }
      const aNum = toNumber(aValue);
      const bNum = toNumber(bValue);
      if (aNum < bNum) return dir === "asc" ? -1 : 1;
      if (aNum > bNum) return dir === "asc" ? 1 : -1;
      return 0;
    }
    function localSortValue(record, sortKey) {
      var _a, _b;
      if (sortKey === "selected_pct") return ((_a = selectionForRecordKey(record.key)) == null ? void 0 : _a.selected_pct) || 0;
      if (sortKey === "selected_weight_g") return ((_b = selectionForRecordKey(record.key)) == null ? void 0 : _b.selected_weight_g) || 0;
      return "";
    }
    function applyLocalSelectionSortIfNeeded() {
      const modalState = ensureModalState();
      if (!LOCAL_SORT_KEYS.has(modalState.sortKey)) return;
      modalState.visibleRecords.sort((left, right) => {
        const primary = compareValues(
          localSortValue(left, modalState.sortKey),
          localSortValue(right, modalState.sortKey),
          modalState.sortDir
        );
        if (primary !== 0) return primary;
        return compareValues(left.name || "", right.name || "", "asc");
      });
    }
    function applyViewSelectedOrderingIfNeeded() {
      const modalState = ensureModalState();
      if (!modalState.viewSelected) return;
      const selected = [];
      const others = [];
      modalState.visibleRecords.forEach((record) => {
        if (selectionForRecordKey(record.key)) {
          selected.push(record);
        } else {
          others.push(record);
        }
      });
      modalState.visibleRecords = selected.concat(others);
    }
    function applyClientOrdering() {
      applyLocalSelectionSortIfNeeded();
      applyViewSelectedOrderingIfNeeded();
    }
    function normalizeServerSortKey(sortKey) {
      const key = String(sortKey || "").trim().toLowerCase();
      if (key === "name") return key;
      if (FATTY_KEYS.includes(key)) return key;
      return "name";
    }
    function sortButtonsLabel() {
      const modalState = ensureModalState();
      document.querySelectorAll(".bulk-oil-sort").forEach((button) => {
        if (!button.dataset.label) {
          button.dataset.label = String(button.textContent || "").replace(/[▲▼]\s*$/, "").trim();
        }
        const label = button.dataset.label || "";
        const key = button.dataset.sortKey || "";
        if (modalState.sortKey === key) {
          button.textContent = `${label} ${modalState.sortDir === "asc" ? "\u25B2" : "\u25BC"}`;
        } else {
          button.textContent = label;
        }
      });
    }
    function updateRowFromSelection(row, record) {
      const selection = selectionForRecordKey(record.key);
      const checkbox = row.querySelector(".bulk-oil-check");
      const pctInput = row.querySelector(".bulk-oil-pct");
      const weightInput = row.querySelector(".bulk-oil-weight");
      if (checkbox) checkbox.checked = !!selection;
      if (pctInput) pctInput.value = selection && selection.selected_pct > 0 ? round(selection.selected_pct, 2) : "";
      if (weightInput) {
        weightInput.value = selection && selection.selected_weight_g > 0 ? round(fromGrams(selection.selected_weight_g), 2) : "";
      }
    }
    function createFattyCell(value) {
      const cell = document.createElement("td");
      cell.className = "bulk-oil-acid";
      const numeric = toNumber(value);
      cell.textContent = numeric > 0 ? round(numeric, 1).toString() : "--";
      return cell;
    }
    function createRow(record) {
      const row = document.createElement("tr");
      row.dataset.recordKey = record.key;
      const pickCell = document.createElement("td");
      pickCell.className = "text-center";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "form-check-input bulk-oil-check";
      pickCell.appendChild(checkbox);
      row.appendChild(pickCell);
      const nameCell = document.createElement("td");
      nameCell.className = "bulk-oil-name";
      const title = document.createElement("div");
      title.className = "fw-semibold small";
      title.textContent = record.name;
      const detail = document.createElement("div");
      detail.className = "text-muted small";
      const category = record.ingredient_category_name ? ` \xB7 ${record.ingredient_category_name}` : "";
      detail.textContent = `${record.source}${category}`;
      nameCell.appendChild(title);
      nameCell.appendChild(detail);
      row.appendChild(nameCell);
      FATTY_KEYS.forEach((key) => {
        var _a;
        row.appendChild(createFattyCell((_a = record.fatty_profile) == null ? void 0 : _a[key]));
      });
      const pctCell = document.createElement("td");
      const pctInput = document.createElement("input");
      pctInput.type = "number";
      pctInput.min = "0";
      pctInput.max = "100";
      pctInput.step = "0.1";
      pctInput.className = "form-control form-control-sm bulk-oil-input bulk-oil-pct";
      pctCell.appendChild(pctInput);
      row.appendChild(pctCell);
      const weightCell = document.createElement("td");
      const weightInput = document.createElement("input");
      weightInput.type = "number";
      weightInput.min = "0";
      weightInput.step = "0.1";
      weightInput.className = "form-control form-control-sm bulk-oil-input bulk-oil-weight";
      weightCell.appendChild(weightInput);
      row.appendChild(weightCell);
      updateRowFromSelection(row, record);
      return row;
    }
    function renderVisibleRecords() {
      const refs = getRefs();
      const modalState = ensureModalState();
      if (!refs.bodyEl) return;
      refs.bodyEl.innerHTML = "";
      const fragment = document.createDocumentFragment();
      modalState.visibleRecords.forEach((record) => {
        fragment.appendChild(createRow(record));
      });
      refs.bodyEl.appendChild(fragment);
      sortButtonsLabel();
      updateSelectionCounters();
      refreshCatalogStatus();
    }
    bulk.render = {
      updateStatusText,
      refreshCatalogStatus,
      applyLocalSelectionSortIfNeeded,
      applyViewSelectedOrderingIfNeeded,
      applyClientOrdering,
      normalizeServerSortKey,
      sortButtonsLabel,
      renderVisibleRecords
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_bulk_oils_api.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const bulk = SoapTool.bulkOils = SoapTool.bulkOils || {};
    const shared = bulk.shared;
    const render = bulk.render;
    if (!shared || !render) return;
    const {
      PAGE_SIZE,
      getRefs,
      ensureModalState,
      normalizeCatalogRecord
    } = shared;
    const {
      refreshCatalogStatus,
      normalizeServerSortKey,
      applyClientOrdering,
      renderVisibleRecords,
      updateStatusText
    } = render;
    function resetVisibleCatalogForFetch() {
      const modalState = ensureModalState();
      const refs = getRefs();
      modalState.visibleRecords = [];
      modalState.offset = 0;
      modalState.totalCount = 0;
      modalState.hasMore = true;
      if (refs.bodyEl) refs.bodyEl.innerHTML = "";
      if (refs.scrollEl) refs.scrollEl.scrollTop = 0;
    }
    async function fetchCatalogPage({ reset = false } = {}) {
      const modalState = ensureModalState();
      const refs = getRefs();
      if (!refs.modalEl) return;
      if (modalState.loading && !reset) return;
      if (!modalState.hasMore && !reset) return;
      if (reset) {
        resetVisibleCatalogForFetch();
      }
      const requestToken = modalState.requestToken + 1;
      modalState.requestToken = requestToken;
      modalState.loading = true;
      refreshCatalogStatus();
      const params = new URLSearchParams();
      params.set("mode", modalState.mode);
      params.set("offset", String(modalState.offset));
      params.set("limit", String(PAGE_SIZE));
      params.set("q", modalState.query || "");
      params.set("sort_key", normalizeServerSortKey(modalState.sortKey));
      params.set("sort_dir", modalState.sortDir === "desc" ? "desc" : "asc");
      try {
        const response = await fetch(`/tools/api/soap/oils-catalog?${params.toString()}`);
        if (!response.ok) {
          throw new Error("Unable to load oils catalog");
        }
        const payload = await response.json();
        if (!payload || payload.success !== true || !payload.result || !Array.isArray(payload.result.records)) {
          throw new Error("Invalid oils catalog response");
        }
        if (requestToken !== modalState.requestToken) {
          return;
        }
        const records = payload.result.records.map(normalizeCatalogRecord);
        const nextOffset = Math.max(0, parseInt(payload.result.next_offset, 10) || modalState.offset + records.length);
        const totalCount = Math.max(records.length, parseInt(payload.result.count, 10) || 0);
        const hasMore = !!payload.result.has_more;
        records.forEach((record) => {
          modalState.recordByKey[record.key] = record;
        });
        modalState.visibleRecords = reset ? records.slice() : modalState.visibleRecords.concat(records);
        modalState.offset = nextOffset;
        modalState.totalCount = totalCount;
        modalState.hasMore = hasMore;
        applyClientOrdering();
        renderVisibleRecords();
      } catch (_) {
        if (requestToken === modalState.requestToken) {
          updateStatusText("Unable to load oils catalog.");
        }
        throw _;
      } finally {
        if (requestToken === modalState.requestToken) {
          modalState.loading = false;
          refreshCatalogStatus();
        }
      }
    }
    bulk.api = {
      fetchCatalogPage
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_bulk_oils_modal.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const bulk = SoapTool.bulkOils = SoapTool.bulkOils || {};
    const shared = bulk.shared;
    const render = bulk.render;
    const api = bulk.api;
    if (!shared || !render || !api) return;
    const { round, toNumber, clamp } = SoapTool.helpers;
    const { toGrams, fromGrams } = SoapTool.units;
    const state = SoapTool.state;
    const {
      LOCAL_SORT_KEYS,
      SCROLL_FETCH_THRESHOLD,
      SEARCH_DEBOUNCE_MS,
      queueStateSave,
      showAlert,
      getRefs,
      ensureModalState,
      updateSelectionCounters,
      setSelection,
      removeSelection,
      getRecordByKey,
      serializeSelection,
      restoreState
    } = shared;
    const {
      applyClientOrdering,
      sortButtonsLabel,
      renderVisibleRecords
    } = render;
    const { fetchCatalogPage } = api;
    let modalInstance = null;
    let searchDebounceTimer = null;
    function closeModal() {
      var _a;
      const refs = getRefs();
      if (!refs.modalEl) return;
      if (!modalInstance && ((_a = window2.bootstrap) == null ? void 0 : _a.Modal)) {
        modalInstance = window2.bootstrap.Modal.getOrCreateInstance(refs.modalEl);
      }
      if (modalInstance) modalInstance.hide();
    }
    function getStageRowsContainer() {
      return document.getElementById("oilRows");
    }
    function getStageRows() {
      return Array.from(document.querySelectorAll("#oilRows .oil-row"));
    }
    function normalizeName(value) {
      return String(value || "").trim().toLowerCase();
    }
    function stageRowName(row) {
      var _a;
      return normalizeName((_a = row == null ? void 0 : row.querySelector(".oil-typeahead")) == null ? void 0 : _a.value);
    }
    function stageRowGi(row) {
      var _a;
      const raw = String(((_a = row == null ? void 0 : row.querySelector(".oil-gi-id")) == null ? void 0 : _a.value) || "").trim();
      return raw ? raw : "";
    }
    function stageRowByKey(recordKey, fallbackRecord) {
      const normalizedKey = String(recordKey || "").trim();
      if (!normalizedKey) return null;
      const rows = getStageRows();
      let row = rows.find((entry) => String(entry.dataset.bulkOilKey || "") === normalizedKey);
      if (row) return row;
      const gi = String((fallbackRecord == null ? void 0 : fallbackRecord.global_item_id) || "").trim();
      if (gi) {
        row = rows.find((entry) => stageRowGi(entry) === gi);
        if (row) return row;
      }
      const name = normalizeName(fallbackRecord == null ? void 0 : fallbackRecord.name);
      if (name) {
        row = rows.find((entry) => stageRowName(entry) === name);
        if (row) return row;
      }
      return null;
    }
    function applySelectionToStageRow(row, item) {
      if (!row || !item) return;
      row.dataset.bulkOilKey = item.key || "";
      const nameInput = row.querySelector(".oil-typeahead");
      const sapInput = row.querySelector(".oil-sap-koh");
      const iodineInput = row.querySelector(".oil-iodine");
      const fattyInput = row.querySelector(".oil-fatty");
      const giInput = row.querySelector(".oil-gi-id");
      const unitInput = row.querySelector(".oil-default-unit");
      const categoryInput = row.querySelector(".oil-category");
      const gramsInput = row.querySelector(".oil-grams");
      const percentInput = row.querySelector(".oil-percent");
      if (nameInput) nameInput.value = item.name || "";
      if (sapInput) sapInput.value = item.sap_koh > 0 ? round(item.sap_koh, 3) : "";
      if (iodineInput) iodineInput.value = item.iodine > 0 ? round(item.iodine, 3) : "";
      if (fattyInput) fattyInput.value = item.fatty_profile && Object.keys(item.fatty_profile).length ? JSON.stringify(item.fatty_profile) : "";
      if (giInput) giInput.value = item.global_item_id || "";
      if (unitInput) unitInput.value = item.default_unit || "";
      if (categoryInput) categoryInput.value = item.ingredient_category_name || "";
      if (percentInput) percentInput.value = item.selected_pct > 0 ? round(item.selected_pct, 2) : "";
      if (gramsInput) gramsInput.value = item.selected_weight_g > 0 ? round(fromGrams(item.selected_weight_g), 2) : "";
    }
    function upsertStageRowForSelection(item) {
      if (!item || !item.key) return null;
      let row = stageRowByKey(item.key, item);
      const oilRows = getStageRowsContainer();
      if (!row && oilRows) {
        row = SoapTool.oils.buildOilRow();
        if (row) {
          oilRows.appendChild(row);
        }
      }
      applySelectionToStageRow(row, item);
      return row;
    }
    function removeStageRowForSelection(recordKey, fallbackRecord) {
      const row = stageRowByKey(recordKey, fallbackRecord);
      if (!row) return;
      if (state.lastOilEdit && state.lastOilEdit.row === row) {
        state.lastOilEdit = null;
        SoapTool.oils.clearSelectedOilProfile();
      }
      row.remove();
    }
    function clearStageRows() {
      const rows = getStageRows();
      rows.forEach((row) => {
        if (state.lastOilEdit && state.lastOilEdit.row === row) {
          state.lastOilEdit = null;
        }
        row.remove();
      });
      SoapTool.oils.clearSelectedOilProfile();
    }
    function notifyStageOilChanged() {
      SoapTool.oils.updateOilTotals();
      SoapTool.stages.updateStageStatuses();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    }
    function normalizeSelectionKey(rawName, rawGi, rawKey) {
      const explicit = String(rawKey || "").trim();
      if (explicit) return explicit;
      const gi = String(rawGi || "").trim();
      if (gi) return `global:${gi}`;
      const name = normalizeName(rawName);
      if (name) return `soapcalc:${name}`;
      return "";
    }
    function buildSelectionFromStage() {
      const selection = {};
      getStageRows().forEach((row) => {
        var _a, _b, _c, _d, _e, _f, _g, _h, _i;
        const name = String(((_a = row.querySelector(".oil-typeahead")) == null ? void 0 : _a.value) || "").trim();
        const sap = toNumber((_b = row.querySelector(".oil-sap-koh")) == null ? void 0 : _b.value);
        const iodine = toNumber((_c = row.querySelector(".oil-iodine")) == null ? void 0 : _c.value);
        const giRaw = String(((_d = row.querySelector(".oil-gi-id")) == null ? void 0 : _d.value) || "").trim();
        const unit = String(((_e = row.querySelector(".oil-default-unit")) == null ? void 0 : _e.value) || "gram");
        const categoryName = String(((_f = row.querySelector(".oil-category")) == null ? void 0 : _f.value) || "");
        const selectedPct = clamp(toNumber((_g = row.querySelector(".oil-percent")) == null ? void 0 : _g.value), 0, 100);
        const selectedWeightG = clamp(toGrams((_h = row.querySelector(".oil-grams")) == null ? void 0 : _h.value), 0);
        const fattyRaw = String(((_i = row.querySelector(".oil-fatty")) == null ? void 0 : _i.value) || "");
        let fattyProfile = {};
        if (fattyRaw) {
          try {
            const parsed = JSON.parse(fattyRaw);
            fattyProfile = shared.normalizeFattyProfile(parsed);
          } catch (_) {
            fattyProfile = {};
          }
        }
        const key = normalizeSelectionKey(name, giRaw, row.dataset.bulkOilKey);
        if (!key) return;
        const hasMaterial = name || selectedPct > 0 || selectedWeightG > 0 || sap > 0 || iodine > 0 || Object.keys(fattyProfile).length > 0;
        if (!hasMaterial) return;
        row.dataset.bulkOilKey = key;
        selection[key] = {
          key,
          name: name || "Unnamed oil",
          sap_koh: sap,
          iodine,
          fatty_profile: fattyProfile,
          default_unit: unit || "gram",
          ingredient_category_name: categoryName,
          global_item_id: giRaw ? parseInt(giRaw, 10) : null,
          source: giRaw ? "global" : "soapcalc",
          is_basic: !giRaw,
          selected_pct: selectedPct,
          selected_weight_g: selectedWeightG
        };
      });
      return selection;
    }
    function hydrateSelectionFromStage() {
      const modalState = ensureModalState();
      modalState.selection = buildSelectionFromStage();
      updateSelectionCounters();
    }
    function syncAllSelectionsToStage() {
      const modalState = ensureModalState();
      const selectedItems = Object.values(modalState.selection || {});
      const expectedKeys = new Set(selectedItems.map((item) => item.key));
      getStageRows().forEach((row) => {
        const key = String(row.dataset.bulkOilKey || "").trim();
        if (!key || !expectedKeys.has(key)) {
          row.remove();
        }
      });
      selectedItems.slice().sort((left, right) => String(left.name || "").localeCompare(String(right.name || ""))).forEach((item) => {
        upsertStageRowForSelection(item);
      });
      notifyStageOilChanged();
    }
    async function openModal() {
      var _a;
      const refs = getRefs();
      const modalState = ensureModalState();
      if (!refs.modalEl) return;
      hydrateSelectionFromStage();
      if (!modalInstance && ((_a = window2.bootstrap) == null ? void 0 : _a.Modal)) {
        modalInstance = window2.bootstrap.Modal.getOrCreateInstance(refs.modalEl);
      }
      if (refs.searchInput) refs.searchInput.value = modalState.query || "";
      if (refs.modeToggle) refs.modeToggle.checked = modalState.mode === "all";
      if (refs.viewSelectedToggle) refs.viewSelectedToggle.checked = !!modalState.viewSelected;
      if (refs.unitLabelEl) refs.unitLabelEl.textContent = state.currentUnit || "g";
      if (modalInstance) modalInstance.show();
      sortButtonsLabel();
      updateSelectionCounters();
      try {
        await fetchCatalogPage({ reset: true });
      } catch (_) {
        showAlert("danger", "Unable to load bulk oils catalog right now.");
      }
    }
    function handleBodyInput(event) {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const row = target.closest("tr[data-record-key]");
      if (!row) return;
      const recordKey = row.dataset.recordKey || "";
      const record = getRecordByKey(recordKey);
      if (!record) return;
      const checkbox = row.querySelector(".bulk-oil-check");
      const pctInput = row.querySelector(".bulk-oil-pct");
      const weightInput = row.querySelector(".bulk-oil-weight");
      const pct = clamp(toNumber(pctInput == null ? void 0 : pctInput.value), 0, 100);
      const selectedWeightG = clamp(toGrams(weightInput == null ? void 0 : weightInput.value), 0);
      const hasValues = pct > 0 || selectedWeightG > 0;
      const isChecked = !!(checkbox == null ? void 0 : checkbox.checked);
      if (isChecked || hasValues) {
        if (checkbox) checkbox.checked = true;
        const selected = setSelection(record, {
          selected_pct: pct,
          selected_weight_g: selectedWeightG
        });
        upsertStageRowForSelection(selected);
      } else {
        removeSelection(recordKey);
        removeStageRowForSelection(recordKey, record);
      }
      const modalState = ensureModalState();
      const shouldReorder = LOCAL_SORT_KEYS.has(modalState.sortKey) || modalState.viewSelected;
      if (shouldReorder) {
        applyClientOrdering();
        renderVisibleRecords();
      } else {
        updateSelectionCounters();
      }
      notifyStageOilChanged();
      queueStateSave();
    }
    async function handleModeToggle(checked) {
      const modalState = ensureModalState();
      modalState.mode = checked ? "all" : "basics";
      queueStateSave();
      try {
        await fetchCatalogPage({ reset: true });
      } catch (_) {
        showAlert("danger", "Unable to load bulk oils catalog right now.");
      }
    }
    function handleViewSelectedToggle(checked) {
      const modalState = ensureModalState();
      modalState.viewSelected = !!checked;
      applyClientOrdering();
      renderVisibleRecords();
      queueStateSave();
    }
    async function handleSortClick(event) {
      const button = event.target instanceof HTMLElement ? event.target.closest(".bulk-oil-sort") : null;
      if (!button) return;
      const sortKey = button.getAttribute("data-sort-key") || "name";
      const modalState = ensureModalState();
      if (modalState.sortKey === sortKey) {
        modalState.sortDir = modalState.sortDir === "asc" ? "desc" : "asc";
      } else {
        modalState.sortKey = sortKey;
        modalState.sortDir = sortKey === "name" ? "asc" : "desc";
      }
      queueStateSave();
      if (LOCAL_SORT_KEYS.has(modalState.sortKey)) {
        applyClientOrdering();
        renderVisibleRecords();
        return;
      }
      try {
        await fetchCatalogPage({ reset: true });
      } catch (_) {
        showAlert("danger", "Unable to load oils in that sort order.");
      }
    }
    function clearSelection() {
      const modalState = ensureModalState();
      modalState.selection = {};
      clearStageRows();
      if (LOCAL_SORT_KEYS.has(modalState.sortKey) || modalState.viewSelected) {
        applyClientOrdering();
      }
      renderVisibleRecords();
      notifyStageOilChanged();
      queueStateSave();
    }
    async function handleScroll() {
      const refs = getRefs();
      const modalState = ensureModalState();
      if (!refs.scrollEl) return;
      if (modalState.loading || !modalState.hasMore) return;
      const isNearBottom = refs.scrollEl.scrollTop + refs.scrollEl.clientHeight >= refs.scrollEl.scrollHeight - SCROLL_FETCH_THRESHOLD;
      if (!isNearBottom) return;
      try {
        await fetchCatalogPage({ reset: false });
      } catch (_) {
        showAlert("danger", "Unable to load more oils right now.");
      }
    }
    function scheduleSearchReload() {
      if (searchDebounceTimer) window2.clearTimeout(searchDebounceTimer);
      searchDebounceTimer = window2.setTimeout(async () => {
        try {
          await fetchCatalogPage({ reset: true });
        } catch (_) {
          showAlert("danger", "Unable to search oils right now.");
        }
      }, SEARCH_DEBOUNCE_MS);
    }
    function saveAndClose() {
      syncAllSelectionsToStage();
      queueStateSave();
      closeModal();
    }
    function onUnitChanged() {
      var _a;
      const refs = getRefs();
      if (refs.unitLabelEl) refs.unitLabelEl.textContent = state.currentUnit || "g";
      if ((_a = refs.modalEl) == null ? void 0 : _a.classList.contains("show")) {
        renderVisibleRecords();
      }
    }
    function bindEvents() {
      const refs = getRefs();
      if (!refs.modalEl) return;
      if (refs.openBtn) {
        refs.openBtn.addEventListener("click", () => {
          openModal();
        });
      }
      if (refs.searchInput) {
        refs.searchInput.addEventListener("input", () => {
          const modalState = ensureModalState();
          modalState.query = refs.searchInput.value || "";
          queueStateSave();
          scheduleSearchReload();
        });
      }
      if (refs.modeToggle) {
        refs.modeToggle.addEventListener("change", async () => {
          await handleModeToggle(!!refs.modeToggle.checked);
        });
      }
      if (refs.viewSelectedToggle) {
        refs.viewSelectedToggle.addEventListener("change", () => {
          handleViewSelectedToggle(!!refs.viewSelectedToggle.checked);
        });
      }
      if (refs.scrollEl) {
        refs.scrollEl.addEventListener("scroll", handleScroll);
      }
      if (refs.bodyEl) {
        refs.bodyEl.addEventListener("input", handleBodyInput);
        refs.bodyEl.addEventListener("change", handleBodyInput);
      }
      refs.modalEl.querySelectorAll(".bulk-oil-sort").forEach((button) => {
        button.addEventListener("click", handleSortClick);
      });
      if (refs.importBtn) {
        refs.importBtn.addEventListener("click", () => {
          saveAndClose();
        });
      }
      if (refs.clearBtn) {
        refs.clearBtn.addEventListener("click", () => {
          clearSelection();
        });
      }
      refs.modalEl.addEventListener("shown.bs.modal", () => {
        const localRefs = getRefs();
        if (localRefs.searchInput) localRefs.searchInput.focus();
      });
    }
    bindEvents();
    updateSelectionCounters();
    sortButtonsLabel();
    SoapTool.bulkOilsModal = {
      openModal,
      serializeSelection,
      restoreState,
      onUnitChanged
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_additives.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { toNumber, round, clamp, buildSoapcalcSearchBuilder } = SoapTool.helpers;
    const { formatWeight, toGrams, fromGrams } = SoapTool.units;
    const { FRAGRANCE_CATEGORY_SET } = SoapTool.constants;
    const state = SoapTool.state;
    function attachAdditiveTypeahead(inputId, hiddenId, categorySet, unitId, categoryId) {
      var _a;
      const input = document.getElementById(inputId);
      const hidden = document.getElementById(hiddenId);
      const hiddenUnit = unitId ? document.getElementById(unitId) : null;
      const hiddenCategory = categoryId ? document.getElementById(categoryId) : null;
      const list = (_a = input == null ? void 0 : input.parentElement) == null ? void 0 : _a.querySelector('[data-role="suggestions"]');
      if (!input || !list || typeof window2.attachMergedInventoryGlobalTypeahead !== "function") return;
      const builder = buildSoapcalcSearchBuilder();
      window2.attachMergedInventoryGlobalTypeahead({
        inputEl: input,
        listEl: list,
        mode: "public",
        giHiddenEl: hidden,
        includeInventory: false,
        includeGlobal: true,
        ingredientFirst: false,
        globalUrlBuilder: builder,
        searchType: "ingredient",
        resultFilter: (item, source) => {
          const category = getItemCategoryName(item);
          if (!category) return source === "inventory";
          return categorySet.has(category);
        },
        requireHidden: false,
        onSelection: function(picked) {
          if (hiddenUnit) hiddenUnit.value = (picked == null ? void 0 : picked.default_unit) || "";
          if (hiddenCategory) hiddenCategory.value = (picked == null ? void 0 : picked.ingredient_category_name) || "";
          SoapTool.storage.queueStateSave();
        }
      });
      input.addEventListener("input", function() {
        if (!this.value.trim()) {
          if (hiddenUnit) hiddenUnit.value = "";
          if (hiddenCategory) hiddenCategory.value = "";
        }
      });
    }
    function readAdditivePct({ pctId, weightId }) {
      var _a, _b, _c;
      const pctInput = document.getElementById(pctId);
      const pctRaw = pctInput == null ? void 0 : pctInput.value;
      if (pctRaw !== "" && pctRaw !== null && pctRaw !== void 0) {
        return toNumber(pctRaw);
      }
      const totalOils = clamp(((_b = (_a = SoapTool.oils) == null ? void 0 : _a.getTotalOilsGrams) == null ? void 0 : _b.call(_a)) || 0, 0);
      if (totalOils <= 0) return 0;
      const weightGrams = toGrams((_c = document.getElementById(weightId)) == null ? void 0 : _c.value);
      if (weightGrams <= 0) return 0;
      return weightGrams / totalOils * 100;
    }
    function collectAdditiveSettings() {
      var _a, _b, _c, _d, _e, _f, _g, _h;
      return {
        lactatePct: readAdditivePct({ pctId: "additiveLactatePct", weightId: "additiveLactateWeight" }),
        sugarPct: readAdditivePct({ pctId: "additiveSugarPct", weightId: "additiveSugarWeight" }),
        saltPct: readAdditivePct({ pctId: "additiveSaltPct", weightId: "additiveSaltWeight" }),
        citricPct: readAdditivePct({ pctId: "additiveCitricPct", weightId: "additiveCitricWeight" }),
        lactateName: ((_b = (_a = document.getElementById("additiveLactateName")) == null ? void 0 : _a.value) == null ? void 0 : _b.trim()) || "Sodium Lactate",
        sugarName: ((_d = (_c = document.getElementById("additiveSugarName")) == null ? void 0 : _c.value) == null ? void 0 : _d.trim()) || "Sugar",
        saltName: ((_f = (_e = document.getElementById("additiveSaltName")) == null ? void 0 : _e.value) == null ? void 0 : _f.trim()) || "Salt",
        citricName: ((_h = (_g = document.getElementById("additiveCitricName")) == null ? void 0 : _g.value) == null ? void 0 : _h.trim()) || "Citric Acid"
      };
    }
    function applyComputedOutputs(outputs) {
      const setOutput = (id, value) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (el.tagName === "INPUT") {
          el.value = value;
        } else {
          el.textContent = value;
        }
      };
      const toDisplay = (grams) => grams > 0 ? round(fromGrams(grams), 2) : "";
      setOutput("additiveLactateWeight", toDisplay(toNumber(outputs == null ? void 0 : outputs.lactateG)));
      setOutput("additiveSugarWeight", toDisplay(toNumber(outputs == null ? void 0 : outputs.sugarG)));
      setOutput("additiveSaltWeight", toDisplay(toNumber(outputs == null ? void 0 : outputs.saltG)));
      setOutput("additiveCitricWeight", toDisplay(toNumber(outputs == null ? void 0 : outputs.citricG)));
      setOutput("additiveCitricLyeOut", formatWeight(toNumber(outputs == null ? void 0 : outputs.citricLyeG)));
    }
    function updateAdditivesOutput(totalOils) {
      var _a;
      const expectedOils = clamp(toNumber(totalOils), 0);
      const calc = (_a = SoapTool.state) == null ? void 0 : _a.lastCalc;
      const calcOils = clamp(toNumber(calc == null ? void 0 : calc.totalOils), 0);
      const oilsMatch = Math.abs(calcOils - expectedOils) < 0.01;
      const outputs = (calc == null ? void 0 : calc.additives) && oilsMatch ? calc.additives : { lactateG: 0, sugarG: 0, saltG: 0, citricG: 0, citricLyeG: 0 };
      applyComputedOutputs(outputs);
      return outputs;
    }
    function attachFragranceTypeahead(row) {
      const input = row.querySelector(".fragrance-typeahead");
      const hidden = row.querySelector(".fragrance-gi-id");
      const hiddenUnit = row.querySelector(".fragrance-default-unit");
      const hiddenCategory = row.querySelector(".fragrance-category");
      const list = row.querySelector('[data-role="suggestions"]');
      if (!input || !list || typeof window2.attachMergedInventoryGlobalTypeahead !== "function") return;
      const builder = buildSoapcalcSearchBuilder();
      window2.attachMergedInventoryGlobalTypeahead({
        inputEl: input,
        listEl: list,
        mode: "public",
        giHiddenEl: hidden,
        includeInventory: false,
        includeGlobal: true,
        ingredientFirst: false,
        globalUrlBuilder: builder,
        searchType: "ingredient",
        resultFilter: (item, source) => {
          const category = getItemCategoryName(item);
          if (!category) return source === "inventory";
          return FRAGRANCE_CATEGORY_SET.has(category);
        },
        requireHidden: false,
        onSelection: function(picked) {
          if (hiddenUnit) hiddenUnit.value = (picked == null ? void 0 : picked.default_unit) || "";
          if (hiddenCategory) hiddenCategory.value = (picked == null ? void 0 : picked.ingredient_category_name) || "";
          SoapTool.storage.queueStateSave();
        }
      });
      input.addEventListener("input", function() {
        if (!this.value.trim()) {
          if (hiddenUnit) hiddenUnit.value = "";
          if (hiddenCategory) hiddenCategory.value = "";
        }
      });
    }
    function buildFragranceRow() {
      var _a, _b;
      const template = document.getElementById("fragranceRowTemplate");
      const row = (_b = (_a = template == null ? void 0 : template.content) == null ? void 0 : _a.querySelector(".fragrance-row")) == null ? void 0 : _b.cloneNode(true);
      if (!row) return document.createElement("div");
      row.querySelectorAll("input").forEach((input) => {
        input.value = "";
      });
      attachFragranceTypeahead(row);
      row.querySelectorAll(".unit-suffix").forEach((el) => {
        el.dataset.suffix = state.currentUnit;
      });
      return row;
    }
    function updateFragranceTotals(totalOils) {
      const rows = Array.from(document.querySelectorAll("#fragranceRows .fragrance-row"));
      const target = clamp(totalOils || SoapTool.oils.getTotalOilsGrams() || 0, 0);
      let totalGrams = 0;
      let totalPct = 0;
      rows.forEach((row) => {
        const gramsInput = row.querySelector(".fragrance-grams");
        const pctInput = row.querySelector(".fragrance-percent");
        const grams = toGrams(gramsInput == null ? void 0 : gramsInput.value);
        const pct = clamp(toNumber(pctInput == null ? void 0 : pctInput.value), 0);
        let effectiveGrams = grams;
        let effectivePct = pct;
        if (target > 0) {
          if (effectiveGrams <= 0 && effectivePct > 0) {
            effectiveGrams = target * (effectivePct / 100);
          } else if (effectivePct <= 0 && effectiveGrams > 0) {
            effectivePct = effectiveGrams / target * 100;
          }
        }
        if (effectiveGrams > 0) totalGrams += effectiveGrams;
        totalPct += effectivePct;
      });
      const totalPctEl = document.getElementById("fragrancePercentTotal");
      if (totalPctEl) totalPctEl.textContent = round(totalPct, 2);
      const totalWeightEl = document.getElementById("fragranceTotalComputed");
      if (totalWeightEl) totalWeightEl.textContent = totalGrams > 0 ? formatWeight(totalGrams) : "--";
      return { totalGrams, totalPct };
    }
    function collectFragranceData() {
      const rows = [];
      document.querySelectorAll("#fragranceRows .fragrance-row").forEach((row) => {
        var _a, _b, _c, _d, _e, _f, _g;
        const name = ((_b = (_a = row.querySelector(".fragrance-typeahead")) == null ? void 0 : _a.value) == null ? void 0 : _b.trim()) || "";
        const grams = ((_c = row.querySelector(".fragrance-grams")) == null ? void 0 : _c.value) || "";
        const percent = ((_d = row.querySelector(".fragrance-percent")) == null ? void 0 : _d.value) || "";
        const gi = ((_e = row.querySelector(".fragrance-gi-id")) == null ? void 0 : _e.value) || "";
        const defaultUnit = ((_f = row.querySelector(".fragrance-default-unit")) == null ? void 0 : _f.value) || "";
        const categoryName = ((_g = row.querySelector(".fragrance-category")) == null ? void 0 : _g.value) || "";
        if (!name && !grams && !percent && !gi) return;
        rows.push({
          name,
          grams,
          percent,
          gi,
          defaultUnit,
          categoryName
        });
      });
      return rows;
    }
    function updateVisualGuidance(data) {
      const list = document.getElementById("soapVisualGuidanceList");
      if (!list) return;
      const tips = Array.isArray(data == null ? void 0 : data.tips) && data.tips.length ? data.tips : ["No visual flags detected for this formula."];
      list.innerHTML = tips.map((tip) => `<li>${tip}</li>`).join("");
    }
    function getItemCategoryName(item) {
      if (!item || typeof item !== "object") return null;
      return item.ingredient && item.ingredient.ingredient_category_name || item.ingredient_category_name || item.ingredient_category && item.ingredient_category.name || null;
    }
    SoapTool.additives = {
      attachAdditiveTypeahead,
      collectAdditiveSettings,
      applyComputedOutputs,
      updateAdditivesOutput,
      updateVisualGuidance
    };
    SoapTool.fragrances = {
      buildFragranceRow,
      updateFragranceTotals,
      collectFragranceData
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_stages.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { toNumber } = SoapTool.helpers;
    const { STAGE_CONFIGS } = SoapTool.constants;
    function openStageByIndex(index) {
      var _a;
      const stage = STAGE_CONFIGS[index];
      if (!stage) return;
      const tabButton = document.getElementById(stage.tabId);
      if (!tabButton) return;
      if ((_a = window2.bootstrap) == null ? void 0 : _a.Tab) {
        bootstrap.Tab.getOrCreateInstance(tabButton).show();
      } else {
        document.querySelectorAll("#soapStageTabList .nav-link").forEach((btn) => {
          btn.classList.remove("active");
          btn.setAttribute("aria-selected", "false");
        });
        document.querySelectorAll("#soapStageTabContent .tab-pane").forEach((pane2) => {
          pane2.classList.remove("show", "active");
        });
        tabButton.classList.add("active");
        tabButton.setAttribute("aria-selected", "true");
        const pane = document.getElementById(stage.paneId);
        if (pane) pane.classList.add("show", "active");
      }
      SoapTool.layout.scheduleStageHeightSync();
      tabButton.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
    }
    function resetStage(stageId) {
      var _a, _b;
      if (stageId === 1) {
        const unitGrams = document.getElementById("unitGrams");
        if (unitGrams) unitGrams.checked = true;
        SoapTool.units.setUnit("g", { skipAutoCalc: true });
        document.getElementById("moldWaterWeight").value = "";
        document.getElementById("moldOilPct").value = "65";
        document.getElementById("oilTotalTarget").value = "";
        document.getElementById("moldShape").value = "loaf";
        const correction = document.getElementById("moldCylinderCorrection");
        if (correction) correction.checked = false;
        document.getElementById("moldCylinderFactor").value = "0.85";
        SoapTool.mold.updateMoldShapeUI();
        if ((_a = SoapTool.mold) == null ? void 0 : _a.updateWetBatterWarning) {
          SoapTool.mold.updateWetBatterWarning(0);
        }
      }
      if (stageId === 2) {
        const oilRows = document.getElementById("oilRows");
        if (oilRows) {
          oilRows.innerHTML = "";
          oilRows.appendChild(SoapTool.oils.buildOilRow());
        }
        SoapTool.oils.updateOilTotals();
      }
      if (stageId === 3) {
        const lyeNaoh = document.getElementById("lyeTypeNaoh");
        if (lyeNaoh) lyeNaoh.checked = true;
        const waterMethod = document.getElementById("waterMethod");
        if (waterMethod) waterMethod.value = "percent";
        const superfat = document.getElementById("lyeSuperfat");
        if (superfat) superfat.value = "5";
        const purity = document.getElementById("lyePurity");
        if (purity) purity.value = "100";
        const waterPct = document.getElementById("waterPct");
        if (waterPct) waterPct.value = "33";
        const lyeConcentration = document.getElementById("lyeConcentration");
        if (lyeConcentration) lyeConcentration.value = "33";
        const waterRatio = document.getElementById("waterRatio");
        if (waterRatio) waterRatio.value = "2";
        SoapTool.runner.applyLyeSelection();
        SoapTool.runner.setWaterMethod();
        SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
      }
      if (stageId === 4) {
        document.getElementById("additiveLactatePct").value = "1";
        document.getElementById("additiveSugarPct").value = "1";
        document.getElementById("additiveSaltPct").value = "0.5";
        document.getElementById("additiveCitricPct").value = "0";
        ["additiveLactateName", "additiveSugarName", "additiveSaltName", "additiveCitricName"].forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.value = "";
        });
        ["additiveLactateGi", "additiveSugarGi", "additiveSaltGi", "additiveCitricGi"].forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.value = "";
        });
        SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
      }
      if (stageId === 5) {
        const fragranceRows = document.getElementById("fragranceRows");
        if (fragranceRows) {
          fragranceRows.innerHTML = "";
          if ((_b = SoapTool.fragrances) == null ? void 0 : _b.buildFragranceRow) {
            fragranceRows.appendChild(SoapTool.fragrances.buildFragranceRow());
          }
        }
        const totalPct = document.getElementById("fragrancePercentTotal");
        if (totalPct) totalPct.textContent = "0";
        const totalWeight = document.getElementById("fragranceTotalComputed");
        if (totalWeight) totalWeight.textContent = "--";
      }
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
      updateStageStatuses();
    }
    function getStageCompletion(stageId) {
      var _a;
      if (stageId === 1) {
        const moldWeight = toNumber(document.getElementById("moldWaterWeight").value);
        const oilTarget = toNumber(document.getElementById("oilTotalTarget").value);
        const moldPct = toNumber(document.getElementById("moldOilPct").value);
        const hasUnit = !!document.querySelector('input[name="weight_unit"]:checked');
        const complete = hasUnit && (moldWeight > 0 || oilTarget > 0) && moldPct > 0;
        return { state: complete ? "complete" : "incomplete", label: complete ? "Sized" : "Needs target" };
      }
      if (stageId === 2) {
        const rows = Array.from(document.querySelectorAll("#oilRows .oil-row"));
        const hasOil = rows.some((row) => {
          var _a2, _b, _c, _d;
          const name = (_b = (_a2 = row.querySelector(".oil-typeahead")) == null ? void 0 : _a2.value) == null ? void 0 : _b.trim();
          const grams = toNumber((_c = row.querySelector(".oil-grams")) == null ? void 0 : _c.value);
          const pct = toNumber((_d = row.querySelector(".oil-percent")) == null ? void 0 : _d.value);
          return name && (grams > 0 || pct > 0);
        });
        return { state: hasOil ? "complete" : "incomplete", label: hasOil ? "Oils added" : "Add oils" };
      }
      if (stageId === 3) {
        const superfat = toNumber(document.getElementById("lyeSuperfat").value);
        const method = (_a = document.getElementById("waterMethod")) == null ? void 0 : _a.value;
        const hasLye = !!document.querySelector('input[name="lye_type"]:checked');
        const complete = hasLye && !!method && superfat >= 0;
        return { state: complete ? "complete" : "incomplete", label: complete ? "Configured" : "Set lye" };
      }
      if (stageId === 4) {
        const hasAdditive = ["additiveLactatePct", "additiveSugarPct", "additiveSaltPct", "additiveCitricPct"].some((id) => toNumber(document.getElementById(id).value) > 0);
        return { state: "optional", label: hasAdditive ? "Added" : "Optional" };
      }
      if (stageId === 5) {
        const rows = Array.from(document.querySelectorAll("#fragranceRows .fragrance-row"));
        const hasFragrance = rows.some((row) => {
          var _a2, _b, _c, _d;
          const name = (_b = (_a2 = row.querySelector(".fragrance-typeahead")) == null ? void 0 : _a2.value) == null ? void 0 : _b.trim();
          const grams = toNumber((_c = row.querySelector(".fragrance-grams")) == null ? void 0 : _c.value);
          const pct = toNumber((_d = row.querySelector(".fragrance-percent")) == null ? void 0 : _d.value);
          return name || grams > 0 || pct > 0;
        });
        return { state: "optional", label: hasFragrance ? "Added" : "Optional" };
      }
      return { state: "incomplete", label: "Incomplete" };
    }
    function updateStageStatuses() {
      const tabList = document.getElementById("soapStageTabList");
      if (tabList) {
        tabList.querySelectorAll(".soap-stage-status").forEach((el) => el.remove());
      }
      const progress = document.getElementById("soapStageProgress");
      if (progress) progress.textContent = "";
    }
    SoapTool.stages = {
      openStageByIndex,
      resetStage,
      updateStageStatuses
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_quality.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { round, toNumber, clamp } = SoapTool.helpers;
    const { computeFattyAcids, computeQualities, computeOilQualityScores } = SoapTool.calc;
    const {
      QUALITY_RANGES,
      QUALITY_HINTS,
      QUALITY_FEEL_HINTS,
      IODINE_RANGE,
      IODINE_SCALE_MAX,
      INS_RANGE,
      INS_SCALE_MAX,
      QUALITY_BASE,
      QUALITY_PRESETS,
      FATTY_BAR_COLORS,
      FATTY_DISPLAY_KEYS
    } = SoapTool.constants;
    const { pulseValue, showSoapAlert } = SoapTool.ui;
    function setBarFill({ barId, fillId, value, max, label }) {
      const bar = document.getElementById(barId);
      const fill = document.getElementById(fillId);
      if (!bar || !fill) return null;
      const safeValue = isFinite(value) ? value : 0;
      const clamped = Math.max(0, Math.min(max, safeValue));
      const width = max > 0 ? clamped / max * 100 : 0;
      fill.style.width = `${width}%`;
      bar.setAttribute("aria-valuemin", "0");
      bar.setAttribute("aria-valuemax", String(max));
      bar.setAttribute("aria-valuenow", clamped.toFixed(1));
      if (label) {
        bar.setAttribute("aria-label", label);
      }
      return { bar, fill, value: safeValue };
    }
    function setQualityBarColor(fill, value, range) {
      if (!fill || !range) return;
      fill.classList.remove("bg-success", "bg-warning", "bg-danger", "bg-secondary");
      if (!isFinite(value)) {
        fill.classList.add("bg-secondary");
        return;
      }
      if (value < range[0]) {
        fill.classList.add("bg-warning");
      } else if (value > range[1]) {
        fill.classList.add("bg-danger");
      } else {
        fill.classList.add("bg-success");
      }
    }
    function setScaledBar(barId, fillId, value, range, max, label) {
      const result = setBarFill({ barId, fillId, value, max, label });
      if (!result) return;
      setQualityBarColor(result.fill, value, range);
    }
    function setQualityRangeBars() {
      const rangeConfig = {
        hardness: { range: QUALITY_RANGES.hardness, scale: 100 },
        cleansing: { range: QUALITY_RANGES.cleansing, scale: 100 },
        conditioning: { range: QUALITY_RANGES.conditioning, scale: 100 },
        bubbly: { range: QUALITY_RANGES.bubbly, scale: 100 },
        creamy: { range: QUALITY_RANGES.creamy, scale: 100 },
        iodine: { range: IODINE_RANGE, scale: IODINE_SCALE_MAX },
        ins: { range: INS_RANGE, scale: INS_SCALE_MAX }
      };
      Object.entries(rangeConfig).forEach(([key, config]) => {
        const [min, max] = config.range;
        const scale = config.scale;
        const name = key.charAt(0).toUpperCase() + key.slice(1);
        const barId = key === "iodine" ? "iodineBar" : key === "ins" ? "insBar" : `quality${name}Bar`;
        const safe = document.getElementById(`quality${name}Safe`);
        if (safe) {
          const startPct = Math.max(0, Math.min(100, min / scale * 100));
          const widthPct = Math.max(0, Math.min(100, (max - min) / scale * 100));
          safe.style.left = `${startPct}%`;
          safe.style.width = `${widthPct}%`;
          safe.title = `Safe range ${round(min, 0)}-${round(max, 0)}`;
        }
        const bar = document.getElementById(barId);
        if (bar) {
          bar.dataset.safeRange = `${round(min, 0)}-${round(max, 0)}`;
        }
        const minLabel = document.getElementById(`quality${name}RangeMin`);
        const maxLabel = document.getElementById(`quality${name}RangeMax`);
        if (minLabel) minLabel.textContent = round(min, 0);
        if (maxLabel) maxLabel.textContent = round(max, 0);
      });
    }
    function updateQualitySliders(qualities, superfat) {
      const hardness = clamp(qualities.hardness || 0, 0, 100);
      const bubbly = clamp(qualities.bubbly || 0, 0, 100);
      const conditioning = clamp(qualities.conditioning || 0, 0, 100);
      const greasyScore = clamp(conditioning + (superfat || 0) * 3, 0, 100);
      const hardEl = document.getElementById("feelHardness");
      const bubblyEl = document.getElementById("feelBubbly");
      const conditioningEl = document.getElementById("feelConditioning");
      const greasyEl = document.getElementById("feelGreasy");
      if (hardEl) hardEl.value = round(hardness, 1);
      if (bubblyEl) bubblyEl.value = round(bubbly, 1);
      if (conditioningEl) conditioningEl.value = round(conditioning, 1);
      if (greasyEl) greasyEl.value = round(greasyScore, 1);
    }
    function updateFattyBar(fattyPercent) {
      FATTY_DISPLAY_KEYS.forEach((key) => {
        const el = document.getElementById(`fattyBar${key.charAt(0).toUpperCase()}${key.slice(1)}`);
        if (!el) return;
        const value = clamp(toNumber(fattyPercent[key]), 0, 100);
        const width = value;
        el.style.width = `${width}%`;
        el.style.backgroundColor = FATTY_BAR_COLORS[key] || "var(--color-muted)";
        el.title = `${key.charAt(0).toUpperCase()}${key.slice(1)}: ${round(value, 1)}%`;
      });
    }
    function getQualityTargets() {
      var _a;
      const preset = ((_a = document.getElementById("qualityPreset")) == null ? void 0 : _a.value) || "balanced";
      const focusEls = Array.from(document.querySelectorAll(".quality-focus:checked"));
      if (preset === "none" && !focusEls.length) return null;
      const base = preset === "none" ? { ...QUALITY_BASE } : QUALITY_PRESETS[preset] ? { ...QUALITY_PRESETS[preset] } : { ...QUALITY_BASE };
      focusEls.forEach((el) => {
        const attr = el.dataset.attr;
        const direction = el.dataset.direction;
        const range = QUALITY_RANGES[attr];
        if (!range) return;
        base[attr] = direction === "low" ? range[0] : range[1];
      });
      return base;
    }
    function updateQualityTargets() {
      const targets = getQualityTargets();
      const markers = {
        hardness: document.getElementById("qualityHardnessTarget"),
        cleansing: document.getElementById("qualityCleansingTarget"),
        conditioning: document.getElementById("qualityConditioningTarget"),
        bubbly: document.getElementById("qualityBubblyTarget"),
        creamy: document.getElementById("qualityCreamyTarget"),
        iodine: document.getElementById("iodineTarget"),
        ins: document.getElementById("insTarget")
      };
      Object.entries(markers).forEach(([key, marker]) => {
        if (!marker) return;
        const labelEl = document.getElementById(`${marker.id}Label`);
        if (!targets) {
          marker.classList.add("d-none");
          if (labelEl) labelEl.textContent = "";
          return;
        }
        const value = toNumber(targets[key]);
        if (!isFinite(value)) {
          marker.classList.add("d-none");
          if (labelEl) labelEl.textContent = "";
          return;
        }
        const scaleMax = key === "iodine" ? IODINE_SCALE_MAX : key === "ins" ? INS_SCALE_MAX : 100;
        const clamped = clamp(value, 0, scaleMax);
        marker.classList.remove("d-none");
        marker.style.left = `${clamped / scaleMax * 100}%`;
        marker.setAttribute("aria-label", `Apply ${key} target`);
        marker.setAttribute("role", "button");
        marker.setAttribute("tabindex", "0");
        marker.title = `Target ${key}: ${round(value, 1)}`;
        if (labelEl) {
          labelEl.textContent = round(value, 1);
        }
      });
    }
    function applyQualityTargets() {
      const targets = getQualityTargets();
      if (!targets) {
        showSoapAlert("info", "Select a quality target to nudge the blend.", { dismissible: true, timeoutMs: 5e3 });
        return;
      }
      const rows = Array.from(document.querySelectorAll("#oilRows .oil-row"));
      const oils = rows.map((row) => {
        var _a, _b;
        const grams = SoapTool.units.toGrams((_a = row.querySelector(".oil-grams")) == null ? void 0 : _a.value);
        const fattyRaw = ((_b = row.querySelector(".oil-fatty")) == null ? void 0 : _b.value) || "";
        let fattyProfile = null;
        if (fattyRaw) {
          try {
            fattyProfile = JSON.parse(fattyRaw);
          } catch (_) {
            fattyProfile = null;
          }
        }
        return { row, grams, fattyProfile };
      }).filter((item) => item.grams > 0);
      if (!oils.length) {
        showSoapAlert("warning", "Add oils before nudging toward a target.", { dismissible: true, timeoutMs: 5e3 });
        return;
      }
      const fatty = computeFattyAcids(oils.map((oil) => ({
        grams: oil.grams,
        fattyProfile: oil.fattyProfile
      })));
      const currentQualities = computeQualities(fatty.percent);
      const deltas = {
        hardness: clamp((targets.hardness - currentQualities.hardness) / 100, -1, 1),
        cleansing: clamp((targets.cleansing - currentQualities.cleansing) / 100, -1, 1),
        conditioning: clamp((targets.conditioning - currentQualities.conditioning) / 100, -1, 1),
        bubbly: clamp((targets.bubbly - currentQualities.bubbly) / 100, -1, 1),
        creamy: clamp((targets.creamy - currentQualities.creamy) / 100, -1, 1)
      };
      const totalOils = oils.reduce((sum, oil) => sum + oil.grams, 0);
      const adjusted = [];
      let totalAdjusted = 0;
      const strength = 0.8;
      const missingFatty = oils.filter((oil) => !oil.fattyProfile || typeof oil.fattyProfile !== "object").length;
      if (missingFatty === oils.length) {
        showSoapAlert("warning", "None of the selected oils have fatty acid data, so targets cannot be applied.", { dismissible: true, timeoutMs: 6e3 });
        return;
      }
      if (missingFatty) {
        showSoapAlert("info", "Some oils are missing fatty acid data. The nudge will only use oils with profiles.", { dismissible: true, timeoutMs: 5e3 });
      }
      oils.forEach((oil) => {
        const scores = computeOilQualityScores(oil.fattyProfile);
        const adjustment = deltas.hardness * scores.hardness + deltas.cleansing * scores.cleansing + deltas.conditioning * scores.conditioning + deltas.bubbly * scores.bubbly + deltas.creamy * scores.creamy;
        const factor = clamp(1 + adjustment * strength, 0.2, 1.8);
        const next = oil.grams * factor;
        adjusted.push({ row: oil.row, grams: next });
        totalAdjusted += next;
      });
      if (totalAdjusted <= 0) {
        showSoapAlert("warning", "Unable to adjust blend with current data.", { dismissible: true, timeoutMs: 5e3 });
        return;
      }
      const scale = totalOils / totalAdjusted;
      const target = SoapTool.oils.getOilTargetGrams() || totalOils;
      adjusted.forEach((item) => {
        const grams = item.grams * scale;
        const gramsInput = item.row.querySelector(".oil-grams");
        const pctInput = item.row.querySelector(".oil-percent");
        if (gramsInput) gramsInput.value = grams > 0 ? round(SoapTool.units.fromGrams(grams), 2) : "";
        if (pctInput && target > 0) {
          const percent = grams / target * 100;
          pctInput.value = percent > 0 ? round(percent, 2) : "";
        }
      });
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
      showSoapAlert("info", "Blend nudged toward selected targets. Re-check results and adjust as needed.", { dismissible: true, timeoutMs: 6e3 });
    }
    function updateQualitiesDisplay(data) {
      const {
        qualities,
        fattyPercent,
        coveragePct,
        iodine,
        ins,
        sapAvg,
        superfat,
        warnings: serviceWarnings
      } = data;
      const hasCoverage = coveragePct > 0;
      function setQuality(name, value) {
        var _a, _b;
        const label = document.getElementById(`quality${name}Value`);
        const hintEl = document.getElementById(`quality${name}Hint`);
        if (!label) return;
        label.textContent = hasCoverage && isFinite(value) ? round(value, 1) : "--";
        pulseValue(label);
        const rangeKey = name.toLowerCase();
        const range = QUALITY_RANGES[rangeKey];
        const fillResult = setBarFill({
          barId: `quality${name}Bar`,
          fillId: `quality${name}Fill`,
          value: hasCoverage ? value : 0,
          max: 100,
          label: name
        });
        if (fillResult && range) {
          setQualityBarColor(fillResult.fill, value, range);
          if (hasCoverage && isFinite(value)) {
            fillResult.bar.title = `${name}: ${round(value, 1)} (safe ${range[0]}-${range[1]}). ${QUALITY_HINTS[rangeKey] || ""}`.trim();
          } else {
            fillResult.bar.title = `${name}: -- (safe ${range[0]}-${range[1]}). ${QUALITY_HINTS[rangeKey] || ""}`.trim();
          }
        }
        if (hintEl && range) {
          if (!hasCoverage || !isFinite(value)) {
            hintEl.textContent = "";
          } else if (value < range[0]) {
            hintEl.textContent = ((_a = QUALITY_FEEL_HINTS[rangeKey]) == null ? void 0 : _a.low) || "";
          } else if (value > range[1]) {
            hintEl.textContent = ((_b = QUALITY_FEEL_HINTS[rangeKey]) == null ? void 0 : _b.high) || "";
          } else {
            hintEl.textContent = "";
          }
        }
      }
      setQuality("Hardness", qualities.hardness);
      setQuality("Cleansing", qualities.cleansing);
      setQuality("Conditioning", qualities.conditioning);
      setQuality("Bubbly", qualities.bubbly);
      setQuality("Creamy", qualities.creamy);
      const coverageNote = document.getElementById("fattyCoverageNote");
      if (coverageNote) {
        coverageNote.textContent = coveragePct > 0 ? `Fatty acid coverage: ${round(coveragePct, 1)}% of oils` : "Fatty acid coverage: not enough data yet";
      }
      const iodineEl = document.getElementById("iodineValue");
      const insEl = document.getElementById("insValue");
      const sapEl = document.getElementById("sapAvgValue");
      if (iodineEl) {
        iodineEl.textContent = iodine > 0 ? round(iodine, 1) : "--";
        pulseValue(iodineEl);
      }
      if (insEl) {
        insEl.textContent = ins > 0 ? round(ins, 1) : "--";
        pulseValue(insEl);
      }
      if (sapEl) {
        sapEl.textContent = sapAvg > 0 ? round(sapAvg, 1) : "--";
        pulseValue(sapEl);
      }
      setScaledBar("iodineBar", "iodineFill", iodine, IODINE_RANGE, IODINE_SCALE_MAX, "Iodine");
      setScaledBar("insBar", "insFill", ins, INS_RANGE, INS_SCALE_MAX, "INS");
      const sat = (fattyPercent.lauric || 0) + (fattyPercent.myristic || 0) + (fattyPercent.palmitic || 0) + (fattyPercent.stearic || 0);
      const unsat = (fattyPercent.ricinoleic || 0) + (fattyPercent.oleic || 0) + (fattyPercent.linoleic || 0) + (fattyPercent.linolenic || 0);
      const ratioEl = document.getElementById("fattySatRatioResult");
      if (ratioEl) {
        ratioEl.textContent = sat + unsat > 0 ? `${round(sat, 0)}:${round(unsat, 0)}` : "--";
        pulseValue(ratioEl);
      }
      FATTY_DISPLAY_KEYS.forEach((key) => {
        const id = `fatty${key.charAt(0).toUpperCase()}${key.slice(1)}`;
        const value = fattyPercent[key];
        document.getElementById(id).textContent = hasCoverage && value ? `${round(value, 1)}%` : "--";
      });
      updateQualitySliders(qualities, superfat || 0);
      updateFattyBar(fattyPercent);
      updateQualityTargets();
      const warnings = Array.isArray(serviceWarnings) ? serviceWarnings.slice() : [];
      const warningBox = document.getElementById("soapQualityWarnings");
      if (warnings.length) {
        warningBox.classList.remove("d-none");
        warningBox.innerHTML = `<strong>Guidance & flags:</strong><ul class="mb-0">${warnings.map((w) => `<li>${w}</li>`).join("")}</ul>`;
      } else {
        warningBox.classList.add("d-none");
        warningBox.textContent = "";
      }
      SoapTool.layout.scheduleStageHeightSync();
    }
    function initQualityTooltips() {
      var _a;
      document.querySelectorAll(".soap-quality-help").forEach((btn) => {
        const key = btn.dataset.quality;
        if (QUALITY_HINTS[key]) {
          btn.setAttribute("title", QUALITY_HINTS[key]);
        }
      });
      if ((_a = window2.bootstrap) == null ? void 0 : _a.Tooltip) {
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
          bootstrap.Tooltip.getOrCreateInstance(el);
        });
      }
    }
    SoapTool.quality = {
      setQualityRangeBars,
      updateQualityTargets,
      applyQualityTargets,
      updateQualitiesDisplay,
      initQualityTooltips
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_recipe_payload.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { round, toNumber, clamp } = SoapTool.helpers;
    function deriveSapAverage(oils) {
      let sapWeighted = 0;
      let sapWeightG = 0;
      (oils || []).forEach((oil) => {
        const sapKoh = toNumber(oil == null ? void 0 : oil.sapKoh);
        const grams = toNumber(oil == null ? void 0 : oil.grams);
        if (sapKoh > 0 && grams > 0) {
          sapWeighted += sapKoh * grams;
          sapWeightG += grams;
        }
      });
      return sapWeightG > 0 ? sapWeighted / sapWeightG : 0;
    }
    function buildSoapNotesBlob(calc) {
      var _a, _b, _c, _d, _e, _f, _g, _h, _i, _j, _k, _l;
      const qualityReport = calc.qualityReport || {};
      const fattyPercent = qualityReport.fatty_acids_pct || {};
      const qualities = qualityReport.qualities || {};
      const sapAvg = isFinite(calc.sapAvg) && calc.sapAvg > 0 ? calc.sapAvg : toNumber(qualityReport.sap_avg_koh) || deriveSapAverage(calc.oils || []);
      const iodine = toNumber(qualityReport.iodine);
      const ins = toNumber(qualityReport.ins) || (sapAvg && iodine ? sapAvg - iodine : 0);
      const mold = SoapTool.mold.getMoldSettings();
      return {
        source: "soap_tool",
        schema_version: 1,
        unit_display: SoapTool.state.currentUnit,
        input_mode: "mixed",
        quality_preset: ((_a = document.getElementById("qualityPreset")) == null ? void 0 : _a.value) || "balanced",
        quality_focus: Array.from(document.querySelectorAll(".quality-focus:checked")).map((el) => el.id),
        mold,
        oils: (calc.oils || []).map((oil) => ({
          name: oil.name || null,
          grams: round(oil.grams || 0, 2),
          iodine: oil.iodine || null,
          sap_koh: oil.sapKoh || null,
          fatty_profile: oil.fattyProfile || null,
          global_item_id: oil.global_item_id || null,
          default_unit: oil.default_unit || null,
          ingredient_category_name: oil.ingredient_category_name || null
        })),
        totals: {
          total_oils_g: round(calc.totalOils || 0, 2),
          batch_yield_g: round(calc.batchYield || 0, 2),
          lye_pure_g: round(calc.lyePure || 0, 2),
          lye_adjusted_g: round(calc.lyeAdjusted || 0, 2),
          water_g: round(calc.water || 0, 2)
        },
        lye: {
          lye_type: calc.lyeType,
          superfat: calc.superfat,
          purity: calc.purity,
          water_method: calc.waterMethod,
          water_pct: calc.waterPct,
          lye_concentration: calc.lyeConcentration,
          water_ratio: calc.waterRatio
        },
        additives: {
          fragrance_pct: ((_b = calc.additives) == null ? void 0 : _b.fragrancePct) || 0,
          lactate_pct: ((_c = calc.additives) == null ? void 0 : _c.lactatePct) || 0,
          sugar_pct: ((_d = calc.additives) == null ? void 0 : _d.sugarPct) || 0,
          salt_pct: ((_e = calc.additives) == null ? void 0 : _e.saltPct) || 0,
          citric_pct: ((_f = calc.additives) == null ? void 0 : _f.citricPct) || 0,
          fragrance_g: round(((_g = calc.additives) == null ? void 0 : _g.fragranceG) || 0, 2),
          lactate_g: round(((_h = calc.additives) == null ? void 0 : _h.lactateG) || 0, 2),
          sugar_g: round(((_i = calc.additives) == null ? void 0 : _i.sugarG) || 0, 2),
          salt_g: round(((_j = calc.additives) == null ? void 0 : _j.saltG) || 0, 2),
          citric_g: round(((_k = calc.additives) == null ? void 0 : _k.citricG) || 0, 2),
          citric_lye_g: round(((_l = calc.additives) == null ? void 0 : _l.citricLyeG) || 0, 2)
        },
        qualities: {
          hardness: round(qualities.hardness || 0, 1),
          cleansing: round(qualities.cleansing || 0, 1),
          conditioning: round(qualities.conditioning || 0, 1),
          bubbly: round(qualities.bubbly || 0, 1),
          creamy: round(qualities.creamy || 0, 1),
          iodine: round(iodine || 0, 1),
          ins: round(ins || 0, 1),
          sap_avg: round(sapAvg || 0, 1)
        },
        fatty_acids: fattyPercent,
        updated_at: (/* @__PURE__ */ new Date()).toISOString()
      };
    }
    function getAdditiveItem(nameId, giId, fallbackName, unitId, categoryId) {
      var _a, _b, _c, _d, _e;
      const name = (_b = (_a = document.getElementById(nameId)) == null ? void 0 : _a.value) == null ? void 0 : _b.trim();
      const giRaw = ((_c = document.getElementById(giId)) == null ? void 0 : _c.value) || "";
      const defaultUnit = unitId ? ((_d = document.getElementById(unitId)) == null ? void 0 : _d.value) || "" : "";
      const categoryName = categoryId ? ((_e = document.getElementById(categoryId)) == null ? void 0 : _e.value) || "" : "";
      return {
        name: name || fallbackName,
        globalItemId: giRaw ? parseInt(giRaw) : void 0,
        defaultUnit: defaultUnit || void 0,
        categoryName: categoryName || void 0
      };
    }
    function collectFragranceRows(totalOils) {
      const rows = [];
      const target = clamp(totalOils || SoapTool.oils.getTotalOilsGrams() || 0, 0);
      document.querySelectorAll("#fragranceRows .fragrance-row").forEach((row) => {
        var _a, _b, _c, _d, _e, _f, _g;
        const name = (_b = (_a = row.querySelector(".fragrance-typeahead")) == null ? void 0 : _a.value) == null ? void 0 : _b.trim();
        const giRaw = ((_c = row.querySelector(".fragrance-gi-id")) == null ? void 0 : _c.value) || "";
        const defaultUnit = ((_d = row.querySelector(".fragrance-default-unit")) == null ? void 0 : _d.value) || "";
        const categoryName = ((_e = row.querySelector(".fragrance-category")) == null ? void 0 : _e.value) || "";
        const gramsInput = (_f = row.querySelector(".fragrance-grams")) == null ? void 0 : _f.value;
        const pctInput = (_g = row.querySelector(".fragrance-percent")) == null ? void 0 : _g.value;
        let grams = SoapTool.units.toGrams(gramsInput);
        const pct = clamp(toNumber(pctInput), 0);
        if (grams <= 0 && pct > 0 && target > 0) {
          grams = target * (pct / 100);
        }
        if (!name && !giRaw && grams <= 0) return;
        rows.push({
          name: name || "Fragrance/Essential Oils",
          globalItemId: giRaw ? parseInt(giRaw) : void 0,
          defaultUnit: defaultUnit || void 0,
          categoryName: categoryName || void 0,
          grams,
          pct
        });
      });
      return rows;
    }
    function collectDraftLines(wrapperId, kind) {
      const out = [];
      document.querySelectorAll(`#${wrapperId} .row`).forEach(function(row) {
        var _a, _b, _c;
        const name = (_b = (_a = row.querySelector(".tool-typeahead")) == null ? void 0 : _a.value) == null ? void 0 : _b.trim();
        const gi = ((_c = row.querySelector(".tool-gi-id")) == null ? void 0 : _c.value) || "";
        const qtyEl = row.querySelector(".tool-qty");
        const unitEl = row.querySelector(".tool-unit");
        const hasQty = qtyEl && qtyEl.value !== "";
        if (!name && !gi) return;
        if (kind === "container") {
          out.push({ name: name || void 0, global_item_id: gi ? parseInt(gi) : void 0, quantity: hasQty ? parseFloat(qtyEl.value) : 1 });
        } else {
          out.push({ name: name || void 0, global_item_id: gi ? parseInt(gi) : void 0, quantity: hasQty ? parseFloat(qtyEl.value) : 0, unit: ((unitEl == null ? void 0 : unitEl.value) || "").trim() || "gram" });
        }
      });
      return out;
    }
    function buildLineRow(kind) {
      const context = SoapTool.config.isAuthenticated ? "member" : "public";
      const mode = SoapTool.config.isAuthenticated ? "recipe" : "public";
      return buildToolLineRow(kind, { context, mode, unitOptionsHtml: SoapTool.config.unitOptionsHtml });
    }
    function addStubLine(kind, name) {
      const row = buildLineRow(kind);
      const input = row.querySelector(".tool-typeahead");
      const qty = row.querySelector(".tool-qty");
      if (input) {
        input.value = name;
      }
      if (qty && kind === "container") {
        qty.value = 1;
      }
      if (kind === "container") {
        document.getElementById("tool-containers").appendChild(row);
      } else if (kind === "consumable") {
        document.getElementById("tool-consumables").appendChild(row);
      } else {
        document.getElementById("tool-ingredients").appendChild(row);
      }
    }
    function buildSoapRecipePayload(calc) {
      var _a, _b, _c, _d;
      const notesBlob = buildSoapNotesBlob(calc);
      const baseIngredients = (calc.oils || []).map((oil) => ({
        name: oil.name || void 0,
        global_item_id: oil.global_item_id || void 0,
        quantity: oil.grams,
        unit: "gram",
        default_unit: oil.default_unit || void 0,
        ingredient_category_name: oil.ingredient_category_name || void 0
      }));
      const lyeName = calc.lyeType === "KOH" ? "Potassium Hydroxide (KOH)" : "Sodium Hydroxide (NaOH)";
      if (calc.lyeAdjusted > 0) {
        baseIngredients.push({ name: lyeName, quantity: round(calc.lyeAdjusted, 2), unit: "gram" });
      }
      if (calc.water > 0) {
        baseIngredients.push({ name: "Distilled Water", quantity: round(calc.water, 2), unit: "gram" });
      }
      const fragranceRows = collectFragranceRows(calc.totalOils || 0);
      fragranceRows.forEach((item) => {
        if (item.grams > 0) {
          baseIngredients.push({
            name: item.name,
            global_item_id: item.globalItemId,
            quantity: round(item.grams, 2),
            unit: "gram",
            default_unit: item.defaultUnit,
            ingredient_category_name: item.categoryName
          });
        }
      });
      if (((_a = calc.additives) == null ? void 0 : _a.lactateG) > 0) {
        const item = getAdditiveItem("additiveLactateName", "additiveLactateGi", "Sodium Lactate", "additiveLactateUnit", "additiveLactateCategory");
        baseIngredients.push({
          name: item.name,
          global_item_id: item.globalItemId,
          quantity: round(calc.additives.lactateG, 2),
          unit: "gram",
          default_unit: item.defaultUnit,
          ingredient_category_name: item.categoryName
        });
      }
      if (((_b = calc.additives) == null ? void 0 : _b.sugarG) > 0) {
        const item = getAdditiveItem("additiveSugarName", "additiveSugarGi", "Sugar", "additiveSugarUnit", "additiveSugarCategory");
        baseIngredients.push({
          name: item.name,
          global_item_id: item.globalItemId,
          quantity: round(calc.additives.sugarG, 2),
          unit: "gram",
          default_unit: item.defaultUnit,
          ingredient_category_name: item.categoryName
        });
      }
      if (((_c = calc.additives) == null ? void 0 : _c.saltG) > 0) {
        const item = getAdditiveItem("additiveSaltName", "additiveSaltGi", "Salt", "additiveSaltUnit", "additiveSaltCategory");
        baseIngredients.push({
          name: item.name,
          global_item_id: item.globalItemId,
          quantity: round(calc.additives.saltG, 2),
          unit: "gram",
          default_unit: item.defaultUnit,
          ingredient_category_name: item.categoryName
        });
      }
      if (((_d = calc.additives) == null ? void 0 : _d.citricG) > 0) {
        const item = getAdditiveItem("additiveCitricName", "additiveCitricGi", "Citric Acid", "additiveCitricUnit", "additiveCitricCategory");
        baseIngredients.push({
          name: item.name,
          global_item_id: item.globalItemId,
          quantity: round(calc.additives.citricG, 2),
          unit: "gram",
          default_unit: item.defaultUnit,
          ingredient_category_name: item.categoryName
        });
        baseIngredients.push({ name: "Extra Lye for Citric Acid", quantity: round(calc.additives.citricLyeG, 2), unit: "gram" });
      }
      return {
        name: "Soap (Draft)",
        instructions: "Draft from Soap Tools",
        predicted_yield: Math.round((calc.batchYield || 0) * 100) / 100,
        predicted_yield_unit: "gram",
        category_name: "Soaps",
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
          soap_water_g: calc.water
        },
        ingredients: baseIngredients.concat(collectDraftLines("tool-ingredients", "ingredient")),
        consumables: collectDraftLines("tool-consumables", "consumable"),
        containers: collectDraftLines("tool-containers", "container"),
        notes: JSON.stringify(notesBlob)
      };
    }
    SoapTool.recipePayload = {
      collectFragranceRows,
      collectDraftLines,
      buildLineRow,
      addStubLine,
      buildSoapRecipePayload
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_runner_inputs.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { round, toNumber, clamp } = SoapTool.helpers;
    const { formatWeight, formatPercent } = SoapTool.units;
    function getLyeSelection() {
      var _a;
      const selected = ((_a = document.querySelector('input[name="lye_type"]:checked')) == null ? void 0 : _a.value) || "NaOH";
      const purityInput = document.getElementById("lyePurity");
      const purityRaw = purityInput == null ? void 0 : purityInput.value;
      let purity = toNumber(purityInput == null ? void 0 : purityInput.value);
      const lyeType = selected === "NaOH" ? "NaOH" : "KOH";
      if (purityRaw === "" || purityRaw === null || purityRaw === void 0 || !isFinite(purity)) {
        purity = 100;
      }
      return { selected, lyeType, purity };
    }
    function applyLyeSelection() {
      const purityInput = document.getElementById("lyePurity");
      const selection = getLyeSelection();
      if (!purityInput) return;
      purityInput.removeAttribute("readonly");
      if (selection.selected === "KOH90") {
        const hint = document.getElementById("lyePurityHint");
        if (hint) hint.textContent = "90% KOH selected. Safe default purity is 90%.";
      } else {
        const hint = document.getElementById("lyePurityHint");
        if (hint) hint.textContent = "Safe default is 100%.";
      }
    }
    function getWaterMethodHelp(method) {
      if (method === "concentration") {
        return "Concentration mode uses lye amount, so superfat and purity change water.";
      }
      if (method === "ratio") {
        return "Ratio mode uses lye amount, so superfat and purity change water.";
      }
      return "Percent mode uses oils total, so superfat changes lye but not water.";
    }
    function updateStageWaterSummary(summary = null, explicitMethod = null) {
      var _a;
      const waterOutput = document.getElementById("stageWaterOutput");
      const hintOutput = document.getElementById("stageWaterComputedHint");
      const method = explicitMethod || (summary == null ? void 0 : summary.waterMethod) || ((_a = document.getElementById("waterMethod")) == null ? void 0 : _a.value) || "percent";
      if (waterOutput) {
        const hasWater = summary && isFinite(summary.waterG) && summary.waterG > 0;
        waterOutput.textContent = hasWater ? formatWeight(summary.waterG) : "--";
      }
      if (!hintOutput) return;
      if (!summary || !isFinite(summary.totalOils) || summary.totalOils <= 0) {
        hintOutput.textContent = `Set oils in Stage 2 to calculate water. ${getWaterMethodHelp(method)}`;
        return;
      }
      if (method === "concentration") {
        const concentration = summary.lyeConcentrationInput || summary.lyeConcentration || 0;
        hintOutput.textContent = `Using ${round(concentration, 1)}% lye concentration from ${formatWeight(summary.lyeAdjusted || 0)} lye.`;
        return;
      }
      if (method === "ratio") {
        const ratio = summary.waterRatioInput || summary.waterRatio || 0;
        hintOutput.textContent = `Using ${round(ratio, 2)} : 1 water-to-lye ratio from ${formatWeight(summary.lyeAdjusted || 0)} lye.`;
        return;
      }
      hintOutput.textContent = `Using ${round(summary.waterPct || 0, 1)}% of total oils (${formatWeight(summary.totalOils)}).`;
    }
    function updateLiveCalculationPreview(summary = null, explicitMethod = null) {
      var _a;
      const anchorEl = document.getElementById("lyeWaterPreviewAnchor");
      const lyeEl = document.getElementById("lyePreview");
      const waterEl = document.getElementById("waterPreview");
      const concEl = document.getElementById("concPreview");
      const ratioEl = document.getElementById("ratioPreview");
      if (!anchorEl && !lyeEl && !waterEl && !concEl && !ratioEl) return;
      const setText = (el, value) => {
        if (el) el.textContent = value;
      };
      const method = explicitMethod || (summary == null ? void 0 : summary.waterMethod) || ((_a = document.getElementById("waterMethod")) == null ? void 0 : _a.value) || "percent";
      const totalOils = toNumber(summary == null ? void 0 : summary.totalOils);
      const lye = toNumber(summary == null ? void 0 : summary.lyeAdjusted);
      const water = toNumber(summary == null ? void 0 : summary.waterG);
      if (totalOils <= 0 || lye <= 0) {
        setText(anchorEl, "Based on -- oils. All values update live as you change inputs.");
        setText(lyeEl, "--");
        setText(waterEl, "--");
        setText(concEl, "--");
        setText(ratioEl, "--");
        return;
      }
      const concentration = toNumber(summary == null ? void 0 : summary.lyeConcentration) > 0 ? toNumber(summary == null ? void 0 : summary.lyeConcentration) : lye + water > 0 ? lye / (lye + water) * 100 : 0;
      const ratio = toNumber(summary == null ? void 0 : summary.waterRatio) > 0 ? toNumber(summary == null ? void 0 : summary.waterRatio) : lye > 0 ? water / lye : 0;
      setText(anchorEl, `Based on ${formatWeight(totalOils)} oils. All values update live as you change inputs.`);
      setText(lyeEl, formatWeight(lye));
      setText(waterEl, formatWeight(water));
      setText(concEl, concentration > 0 ? formatPercent(concentration) : "--");
      setText(ratioEl, ratio > 0 ? `${round(ratio, 2)} : 1` : "--");
      if (method === "concentration") {
        const concentrationInput = toNumber(summary == null ? void 0 : summary.lyeConcentrationInput);
        if (concentrationInput > 0) {
          setText(concEl, formatPercent(concentrationInput));
        }
      }
      if (method === "ratio") {
        const ratioInput = toNumber(summary == null ? void 0 : summary.waterRatioInput);
        if (ratioInput > 0) {
          setText(ratioEl, `${round(ratioInput, 2)} : 1`);
        }
      }
    }
    function setWaterMethod() {
      var _a;
      const method = ((_a = document.getElementById("waterMethod")) == null ? void 0 : _a.value) || "percent";
      document.querySelectorAll(".water-input").forEach((el) => {
        el.classList.toggle("d-none", el.dataset.method !== method);
      });
      updateStageWaterSummary(null, method);
      updateLiveCalculationPreview(null, method);
    }
    function validateCalculation() {
      const totals = SoapTool.oils.updateOilTotals();
      const totalOils = totals.totalWeight;
      const totalPct = totals.totalPct;
      const errors = [];
      const oils = SoapTool.oils.collectOilData();
      const target = SoapTool.oils.getOilTargetGrams();
      const percentInputs = Array.from(document.querySelectorAll("#oilRows .oil-percent")).map((input) => clamp(toNumber(input.value), 0));
      const hasPercent = percentInputs.some((value) => value > 0);
      if (!oils.length || totalOils <= 0) {
        errors.push("Add at least one oil with a weight or percent.");
      }
      if (!target && totalOils <= 0 && hasPercent) {
        errors.push("Enter a total oils target or weights to convert percentages.");
      }
      if (target > 0 && totalPct > 0 && Math.abs(totalPct - 100) > 0.5) {
        errors.push("Oil percentages should total 100% (use Normalize to fix).");
      }
      if (target > 0 && totalOils > target + 0.01) {
        errors.push("Oil weights exceed the mold target.");
      } else if (!target && totalPct > 100.01) {
        errors.push("Oil percentages exceed 100%.");
      }
      return { ok: errors.length === 0, errors, totals, oils };
    }
    function readSuperfatInput() {
      const superfatInput = document.getElementById("lyeSuperfat");
      const superfatRaw = superfatInput == null ? void 0 : superfatInput.value;
      let superfat = toNumber(superfatRaw);
      if (superfatRaw === "" || superfatRaw === null || superfatRaw === void 0 || !isFinite(superfat)) {
        superfat = 5;
      }
      return superfat;
    }
    function sanitizeLyeInputs() {
      var _a, _b, _c, _d;
      const selection = getLyeSelection();
      let purity = selection.purity;
      if (!isFinite(purity)) {
        purity = 100;
      }
      const waterMethod = ((_a = document.getElementById("waterMethod")) == null ? void 0 : _a.value) || "percent";
      const waterPct = toNumber((_b = document.getElementById("waterPct")) == null ? void 0 : _b.value);
      const lyeConcentration = toNumber((_c = document.getElementById("lyeConcentration")) == null ? void 0 : _c.value);
      const waterRatio = toNumber((_d = document.getElementById("waterRatio")) == null ? void 0 : _d.value);
      return { purity, waterMethod, waterPct, lyeConcentration, waterRatio };
    }
    SoapTool.runnerInputs = {
      getLyeSelection,
      applyLyeSelection,
      setWaterMethod,
      updateStageWaterSummary,
      updateLiveCalculationPreview,
      validateCalculation,
      readSuperfatInput,
      sanitizeLyeInputs
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_runner_quota.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { getStorage } = SoapTool.helpers;
    function readCalcUsage() {
      if (!SoapTool.config.calcLimit) return { count: 0, date: null };
      const storage = getStorage();
      if (!storage) return { count: 0, date: null };
      try {
        const raw = storage.getItem("soap_calc_usage");
        const today = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
        if (!raw) return { count: 0, date: today };
        const data = JSON.parse(raw);
        if (!data || data.date !== today) {
          return { count: 0, date: today };
        }
        return { count: Number(data.count) || 0, date: today };
      } catch (_) {
        return { count: 0, date: null };
      }
    }
    function writeCalcUsage(count) {
      if (!SoapTool.config.calcLimit) return;
      const storage = getStorage();
      if (!storage) return;
      const today = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
      try {
        storage.setItem("soap_calc_usage", JSON.stringify({ count, date: today }));
      } catch (_) {
      }
    }
    function canConsumeCalcQuota() {
      if (!SoapTool.config.calcLimit) return true;
      const usage = readCalcUsage();
      if (usage.count >= SoapTool.config.calcLimit) {
        SoapTool.ui.showSoapAlert(
          "warning",
          `You have reached the ${SoapTool.config.calcLimit} calculation limit for ${SoapTool.config.calcTier} accounts. Create a free account or upgrade to keep calculating.`,
          { dismissible: true }
        );
        return false;
      }
      return true;
    }
    function consumeCalcQuota() {
      if (!SoapTool.config.calcLimit) return;
      const usage = readCalcUsage();
      const nextCount = usage.count + 1;
      writeCalcUsage(nextCount);
      const remaining = Math.max(0, SoapTool.config.calcLimit - nextCount);
      if (remaining <= 1) {
        SoapTool.ui.showSoapAlert(
          "info",
          `You have ${remaining} calculation${remaining === 1 ? "" : "s"} left on the ${SoapTool.config.calcTier} tier today.`,
          { dismissible: true, timeoutMs: 6e3 }
        );
      }
    }
    function maybeShowSignupModal(remaining) {
      if (!SoapTool.config.calcLimit || remaining === null || remaining > 1) return;
      const modalEl = document.getElementById("soapSignupModal");
      if (!modalEl) return;
      if (window2.bootstrap && window2.bootstrap.Modal) {
        const modal = window2.bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      } else {
        SoapTool.ui.showSoapAlert(
          "info",
          "You are almost at the free limit. Create a free account to keep saving your work.",
          { dismissible: true, timeoutMs: 7e3 }
        );
      }
    }
    SoapTool.runnerQuota = {
      canConsumeCalcQuota,
      consumeCalcQuota,
      maybeShowSignupModal
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_runner_service.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const state = SoapTool.state;
    function buildServicePayload({
      oils,
      selection,
      superfat,
      purity,
      waterMethod,
      waterPct,
      lyeConcentration,
      waterRatio,
      totalOils
    }) {
      const additiveSettings = SoapTool.additives.collectAdditiveSettings();
      const fragranceRows = SoapTool.recipePayload.collectFragranceRows(totalOils || 0);
      return {
        oils: (oils || []).map((oil) => ({
          name: oil.name || null,
          grams: oil.grams || 0,
          sap_koh: oil.sapKoh || 0,
          iodine: oil.iodine || 0,
          fatty_profile: oil.fattyProfile || null,
          global_item_id: oil.global_item_id || null,
          default_unit: oil.default_unit || null,
          ingredient_category_name: oil.ingredient_category_name || null
        })),
        fragrances: fragranceRows.map((row) => ({
          name: row.name || "Fragrance/Essential Oils",
          grams: row.grams || 0,
          pct: row.pct || 0
        })),
        additives: {
          lactate_pct: additiveSettings.lactatePct || 0,
          sugar_pct: additiveSettings.sugarPct || 0,
          salt_pct: additiveSettings.saltPct || 0,
          citric_pct: additiveSettings.citricPct || 0,
          lactate_name: additiveSettings.lactateName || "Sodium Lactate",
          sugar_name: additiveSettings.sugarName || "Sugar",
          salt_name: additiveSettings.saltName || "Salt",
          citric_name: additiveSettings.citricName || "Citric Acid"
        },
        lye: {
          selected: (selection == null ? void 0 : selection.selected) || "NaOH",
          superfat,
          purity
        },
        water: {
          method: waterMethod,
          water_pct: waterPct,
          lye_concentration: lyeConcentration,
          water_ratio: waterRatio
        },
        meta: {
          unit_display: state.currentUnit || "g"
        }
      };
    }
    async function calculateWithSoapService(payload) {
      var _a;
      const token = ((_a = document.querySelector('meta[name="csrf-token"]')) == null ? void 0 : _a.getAttribute("content")) || "";
      const controller = new AbortController();
      const timeoutId = window2.setTimeout(() => controller.abort(), 2500);
      try {
        const response = await fetch("/tools/api/soap/calculate", {
          method: "POST",
          signal: controller.signal,
          headers: {
            "Content-Type": "application/json",
            ...token ? { "X-CSRFToken": token } : {}
          },
          body: JSON.stringify(payload || {})
        });
        if (!response.ok) return null;
        const data = await response.json();
        if (!data || data.success !== true || typeof data.result !== "object") return null;
        return data.result;
      } catch (_) {
        return null;
      } finally {
        window2.clearTimeout(timeoutId);
      }
    }
    SoapTool.runnerService = {
      buildServicePayload,
      calculateWithSoapService
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_runner_render.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { round, toNumber } = SoapTool.helpers;
    const { formatWeight, formatPercent } = SoapTool.units;
    const state = SoapTool.state;
    const DEFAULT_ADDITIVES = {
      lactateG: 0,
      sugarG: 0,
      saltG: 0,
      citricG: 0,
      citricLyeG: 0,
      fragranceG: 0,
      fragrancePct: 0
    };
    function mapOilsForState(rows) {
      return (rows || []).map((oil) => {
        var _a;
        return {
          name: oil.name || null,
          grams: toNumber(oil.grams),
          sapKoh: toNumber((_a = oil.sap_koh) != null ? _a : oil.sapKoh),
          iodine: toNumber(oil.iodine),
          fattyProfile: oil.fatty_profile || oil.fattyProfile || null,
          global_item_id: oil.global_item_id || null,
          default_unit: oil.default_unit || null,
          ingredient_category_name: oil.ingredient_category_name || null
        };
      });
    }
    function setText(id, value) {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = value;
    }
    function renderResultsCard({
      resultsCard,
      lyeAdjusted,
      waterData,
      batchYield,
      totalOils,
      superfat
    }) {
      const card = document.getElementById("resultsCard");
      if (card) card.style.display = "block";
      const ratioValue = toNumber(resultsCard.water_lye_ratio) || waterData.waterRatio;
      setText("lyeAdjustedOutput", formatWeight(toNumber(resultsCard.lye_adjusted_g) || lyeAdjusted));
      setText("waterOutput", formatWeight(toNumber(resultsCard.water_g) || waterData.waterG));
      setText("batchYieldOutput", formatWeight(batchYield));
      setText(
        "lyeConcentrationOutput",
        formatPercent(toNumber(resultsCard.lye_concentration_pct) || waterData.lyeConcentration)
      );
      setText(
        "waterRatioOutput",
        isFinite(ratioValue) && ratioValue > 0 ? round(ratioValue, 2).toString() : "--"
      );
      setText("totalOilsOutput", formatWeight(totalOils));
      setText("superfatOutput", formatPercent(superfat));
      [
        "lyeAdjustedOutput",
        "waterOutput",
        "batchYieldOutput",
        "lyeConcentrationOutput",
        "waterRatioOutput",
        "totalOilsOutput",
        "superfatOutput"
      ].forEach((id) => SoapTool.ui.pulseValue(document.getElementById(id)));
    }
    function maybeShowGuidanceAlerts({ showAlerts, lyeTotals, purity, waterData }) {
      if (!showAlerts) return;
      if (lyeTotals.usedFallback) {
        SoapTool.ui.showSoapAlert(
          "info",
          "Some oils are missing SAP values, so an average SAP was used. Select oils with SAP data for the most accurate lye calculation.",
          { dismissible: true, timeoutMs: 7e3 }
        );
      }
      if (purity < 100) {
        SoapTool.ui.showSoapAlert(
          "info",
          `Lye purity is set to ${round(purity, 1)}%. Adjusting lye to match your real-world purity.`,
          { dismissible: true, timeoutMs: 6e3 }
        );
      }
      if (waterData.lyeConcentration < 25 || waterData.lyeConcentration > 45) {
        SoapTool.ui.showSoapAlert(
          "warning",
          "Your lye concentration is outside the common 25-45% range. Expect slower or faster trace.",
          { dismissible: true, timeoutMs: 7e3 }
        );
      }
      const mold = SoapTool.mold.getMoldSettings();
      if (mold.shape === "cylinder" && mold.waterWeight > 0 && !mold.useCylinder) {
        SoapTool.ui.showSoapAlert(
          "info",
          "Cylinder mold selected. Enable the cylinder correction if you want to leave headspace or reduce spill risk.",
          { dismissible: true, timeoutMs: 7e3 }
        );
      }
    }
    function applyServiceResult({
      serviceResult,
      validation,
      selection,
      superfat,
      purity,
      waterMethod,
      waterPct,
      lyeConcentrationInput,
      waterRatioInput,
      showAlerts
    }) {
      var _a;
      const lyeType = serviceResult.lye_type || selection.lyeType || "NaOH";
      const totalOils = toNumber(serviceResult.total_oils_g) || validation.totals.totalWeight;
      const resolvedSuperfat = toNumber(serviceResult.superfat_pct);
      const superfatValue = isFinite(resolvedSuperfat) ? resolvedSuperfat : superfat;
      const lyeTotals = {
        sapAvg: toNumber(serviceResult.sap_avg_koh),
        usedFallback: !!serviceResult.used_sap_fallback
      };
      const lyePure = toNumber(serviceResult.lye_pure_g);
      const lyeAdjusted = toNumber(serviceResult.lye_adjusted_g);
      const resolvedPurity = toNumber(serviceResult.lye_purity_pct) || purity;
      const resolvedWaterMethod = serviceResult.water_method || waterMethod;
      const resolvedWaterPct = toNumber(serviceResult.water_pct) || waterPct;
      const resolvedLyeConcentrationInput = toNumber(serviceResult.lye_concentration_input_pct) || lyeConcentrationInput;
      const resolvedWaterRatioInput = toNumber(serviceResult.water_ratio_input) || waterRatioInput;
      const waterData = {
        waterG: toNumber(serviceResult.water_g),
        lyeConcentration: toNumber(serviceResult.lye_concentration_pct),
        waterRatio: toNumber(serviceResult.water_lye_ratio)
      };
      const resultsCard = serviceResult.results_card || {};
      const qualityReport = serviceResult.quality_report || {};
      const oilsForState = mapOilsForState(serviceResult.oils || validation.oils);
      const liveSummary = {
        waterG: waterData.waterG,
        lyeAdjusted,
        totalOils,
        waterMethod: resolvedWaterMethod,
        waterPct: resolvedWaterPct,
        lyeConcentrationInput: resolvedLyeConcentrationInput,
        waterRatioInput: resolvedWaterRatioInput,
        lyeConcentration: waterData.lyeConcentration,
        waterRatio: waterData.waterRatio
      };
      SoapTool.runnerInputs.updateStageWaterSummary(liveSummary);
      SoapTool.runnerInputs.updateLiveCalculationPreview(liveSummary);
      const additives = serviceResult.additives || DEFAULT_ADDITIVES;
      if (SoapTool.additives.applyComputedOutputs) {
        SoapTool.additives.applyComputedOutputs(additives);
      }
      const batchYield = toNumber(resultsCard.batch_yield_g) || totalOils + lyeAdjusted + waterData.waterG + additives.fragranceG + additives.lactateG + additives.sugarG + additives.saltG + additives.citricG;
      if ((_a = SoapTool.mold) == null ? void 0 : _a.updateWetBatterWarning) {
        SoapTool.mold.updateWetBatterWarning(batchYield);
      }
      renderResultsCard({
        resultsCard,
        lyeAdjusted,
        waterData,
        batchYield,
        totalOils,
        superfat: superfatValue
      });
      SoapTool.ui.updateResultsWarnings(waterData);
      SoapTool.ui.updateResultsMeta();
      SoapTool.quality.updateQualitiesDisplay({
        qualities: qualityReport.qualities || {},
        fattyPercent: qualityReport.fatty_acids_pct || {},
        coveragePct: toNumber(qualityReport.coverage_pct),
        iodine: toNumber(qualityReport.iodine),
        ins: toNumber(qualityReport.ins),
        sapAvg: lyeTotals.sapAvg,
        superfat: superfatValue,
        waterData,
        additives,
        oils: oilsForState,
        totalOils,
        warnings: qualityReport.warnings || []
      });
      SoapTool.additives.updateVisualGuidance({
        tips: qualityReport.visual_guidance || []
      });
      SoapTool.stages.updateStageStatuses();
      maybeShowGuidanceAlerts({
        showAlerts,
        lyeTotals,
        purity: resolvedPurity,
        waterData
      });
      state.lastCalc = {
        totalOils,
        oils: oilsForState,
        lyeType,
        superfat: superfatValue,
        purity: resolvedPurity,
        lyePure,
        lyeAdjusted,
        water: waterData.waterG,
        waterMethod: resolvedWaterMethod,
        waterPct: resolvedWaterPct,
        lyeConcentration: waterData.lyeConcentration,
        waterRatio: waterData.waterRatio,
        sapAvg: lyeTotals.sapAvg,
        usedSapFallback: lyeTotals.usedFallback,
        additives,
        batchYield,
        qualityReport,
        export: serviceResult.export || null
      };
      return state.lastCalc;
    }
    SoapTool.runnerRender = {
      applyServiceResult
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_runner.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const state = SoapTool.state;
    const runnerInputs = SoapTool.runnerInputs;
    const runnerQuota = SoapTool.runnerQuota;
    const runnerService = SoapTool.runnerService;
    const runnerRender = SoapTool.runnerRender;
    async function calculateAll(options = {}) {
      var _a;
      const settings = {
        consumeQuota: false,
        showAlerts: true,
        ...options
      };
      try {
        if (settings.showAlerts) {
          SoapTool.ui.clearSoapAlerts();
        }
        const validation = runnerInputs.validateCalculation();
        if (!validation.ok) {
          runnerInputs.updateStageWaterSummary(null);
          runnerInputs.updateLiveCalculationPreview(null);
          if ((_a = SoapTool.mold) == null ? void 0 : _a.updateWetBatterWarning) {
            SoapTool.mold.updateWetBatterWarning(0);
          }
          if (settings.showAlerts) {
            SoapTool.ui.showSoapAlert(
              "warning",
              `<strong>Missing info:</strong><ul class="mb-0">${validation.errors.map((err) => `<li>${err}</li>`).join("")}</ul>`,
              { dismissible: true, persist: true }
            );
          }
          return null;
        }
        if (settings.consumeQuota && !runnerQuota.canConsumeCalcQuota()) {
          return null;
        }
        const superfat = runnerInputs.readSuperfatInput();
        const selection = runnerInputs.getLyeSelection();
        const sanitized = runnerInputs.sanitizeLyeInputs();
        const requestSeq = (state.calcRequestSeq || 0) + 1;
        state.calcRequestSeq = requestSeq;
        const servicePayload = runnerService.buildServicePayload({
          oils: validation.oils,
          selection,
          superfat,
          purity: sanitized.purity,
          waterMethod: sanitized.waterMethod,
          waterPct: sanitized.waterPct,
          lyeConcentration: sanitized.lyeConcentration,
          waterRatio: sanitized.waterRatio,
          totalOils: validation.totals.totalWeight
        });
        const serviceResult = await runnerService.calculateWithSoapService(servicePayload);
        if (requestSeq !== state.calcRequestSeq) {
          return state.lastCalc;
        }
        if (!serviceResult) {
          if (settings.showAlerts) {
            SoapTool.ui.showSoapAlert(
              "danger",
              "Soap calculator service is unavailable. Please try again.",
              { dismissible: true, timeoutMs: 6e3 }
            );
          }
          return null;
        }
        const calc = runnerRender.applyServiceResult({
          serviceResult,
          validation,
          selection,
          superfat,
          purity: sanitized.purity,
          waterMethod: sanitized.waterMethod,
          waterPct: sanitized.waterPct,
          lyeConcentrationInput: sanitized.lyeConcentration,
          waterRatioInput: sanitized.waterRatio,
          showAlerts: settings.showAlerts
        });
        if (settings.consumeQuota) {
          runnerQuota.consumeCalcQuota();
        }
        return calc;
      } catch (_) {
        if (settings.showAlerts) {
          SoapTool.ui.showSoapAlert("danger", "Unable to run the soap calculation right now. Please try again.", { dismissible: true, timeoutMs: 6e3 });
        }
        return null;
      }
    }
    SoapTool.runner = {
      getLyeSelection: (...args) => runnerInputs.getLyeSelection(...args),
      applyLyeSelection: (...args) => runnerInputs.applyLyeSelection(...args),
      setWaterMethod: (...args) => runnerInputs.setWaterMethod(...args),
      updateLiveCalculationPreview: (...args) => runnerInputs.updateLiveCalculationPreview(...args),
      calculateAll,
      buildSoapRecipePayload: (...args) => SoapTool.recipePayload.buildSoapRecipePayload(...args),
      buildLineRow: (...args) => SoapTool.recipePayload.buildLineRow(...args),
      addStubLine: (...args) => SoapTool.recipePayload.addStubLine(...args),
      maybeShowSignupModal: (...args) => runnerQuota.maybeShowSignupModal(...args)
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_storage.js
  (function(window2) {
    "use strict";
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { formatTime, getStorage } = SoapTool.helpers;
    const STATE_STORAGE_KEY = "soap_tool_state_v2";
    function serializeLines(wrapperId, kind) {
      const out = [];
      const rows = document.querySelectorAll(`#${wrapperId} .row`);
      rows.forEach((row) => {
        var _a, _b, _c;
        const name = (_b = (_a = row.querySelector(".tool-typeahead")) == null ? void 0 : _a.value) == null ? void 0 : _b.trim();
        const gi = ((_c = row.querySelector(".tool-gi-id")) == null ? void 0 : _c.value) || "";
        const qtyEl = row.querySelector(".tool-qty");
        const unitEl = row.querySelector(".tool-unit");
        const qty = qtyEl && qtyEl.value !== "" ? SoapTool.helpers.toNumber(qtyEl.value) : null;
        if (!name && !gi) return;
        if (kind === "container") {
          out.push({
            name: name || "",
            global_item_id: gi ? parseInt(gi) : null,
            quantity: qty && qty > 0 ? qty : 1
          });
        } else {
          out.push({
            name: name || "",
            global_item_id: gi ? parseInt(gi) : null,
            quantity: qty && qty >= 0 ? qty : 0,
            unit: (unitEl == null ? void 0 : unitEl.value) || "gram"
          });
        }
      });
      return out;
    }
    function serializeOils() {
      const oils = [];
      document.querySelectorAll("#oilRows .oil-row").forEach((row) => {
        var _a, _b, _c, _d, _e, _f, _g, _h, _i, _j;
        const name = ((_b = (_a = row.querySelector(".oil-typeahead")) == null ? void 0 : _a.value) == null ? void 0 : _b.trim()) || "";
        const grams = ((_c = row.querySelector(".oil-grams")) == null ? void 0 : _c.value) || "";
        const percent = ((_d = row.querySelector(".oil-percent")) == null ? void 0 : _d.value) || "";
        const sap = ((_e = row.querySelector(".oil-sap-koh")) == null ? void 0 : _e.value) || "";
        const iodine = ((_f = row.querySelector(".oil-iodine")) == null ? void 0 : _f.value) || "";
        const fattyRaw = ((_g = row.querySelector(".oil-fatty")) == null ? void 0 : _g.value) || "";
        const gi = ((_h = row.querySelector(".oil-gi-id")) == null ? void 0 : _h.value) || "";
        const defaultUnit = ((_i = row.querySelector(".oil-default-unit")) == null ? void 0 : _i.value) || "";
        const categoryName = ((_j = row.querySelector(".oil-category")) == null ? void 0 : _j.value) || "";
        if (!name && !grams && !percent && !gi) return;
        oils.push({
          name,
          grams,
          percent,
          sap,
          iodine,
          fattyRaw,
          gi,
          defaultUnit,
          categoryName
        });
      });
      return oils;
    }
    function serializeFragrances() {
      var _a;
      if ((_a = SoapTool.fragrances) == null ? void 0 : _a.collectFragranceData) {
        return SoapTool.fragrances.collectFragranceData();
      }
      const rows = [];
      document.querySelectorAll("#fragranceRows .fragrance-row").forEach((row) => {
        var _a2, _b, _c, _d, _e, _f, _g;
        const name = ((_b = (_a2 = row.querySelector(".fragrance-typeahead")) == null ? void 0 : _a2.value) == null ? void 0 : _b.trim()) || "";
        const grams = ((_c = row.querySelector(".fragrance-grams")) == null ? void 0 : _c.value) || "";
        const percent = ((_d = row.querySelector(".fragrance-percent")) == null ? void 0 : _d.value) || "";
        const gi = ((_e = row.querySelector(".fragrance-gi-id")) == null ? void 0 : _e.value) || "";
        const defaultUnit = ((_f = row.querySelector(".fragrance-default-unit")) == null ? void 0 : _f.value) || "";
        const categoryName = ((_g = row.querySelector(".fragrance-category")) == null ? void 0 : _g.value) || "";
        if (!name && !grams && !percent && !gi) return;
        rows.push({ name, grams, percent, gi, defaultUnit, categoryName });
      });
      return rows;
    }
    function restoreOilRow(data, index) {
      const oilRows = document.getElementById("oilRows");
      if (!oilRows || !data) return;
      const row = SoapTool.oils.buildOilRow();
      row.querySelector(".oil-typeahead").value = data.name || "";
      row.querySelector(".oil-grams").value = data.grams || "";
      row.querySelector(".oil-percent").value = data.percent || "";
      row.querySelector(".oil-sap-koh").value = data.sap || "";
      row.querySelector(".oil-iodine").value = data.iodine || "";
      row.querySelector(".oil-fatty").value = data.fattyRaw || "";
      row.querySelector(".oil-gi-id").value = data.gi || "";
      const unitEl = row.querySelector(".oil-default-unit");
      if (unitEl) unitEl.value = data.defaultUnit || "";
      const categoryEl = row.querySelector(".oil-category");
      if (categoryEl) categoryEl.value = data.categoryName || "";
      const children = Array.from(oilRows.children);
      if (index >= children.length) {
        oilRows.appendChild(row);
      } else {
        oilRows.insertBefore(row, children[index]);
      }
      return row;
    }
    function saveState() {
      var _a, _b, _c, _d, _e, _f, _g, _h, _i, _j, _k, _l, _m, _n, _o, _p, _q, _r, _s, _t, _u, _v, _w, _x, _y, _z, _A;
      const storage = getStorage();
      if (!storage) return;
      const payload = {
        version: 2,
        unit: SoapTool.state.currentUnit,
        oil_total_target: document.getElementById("oilTotalTarget").value || "",
        oils: serializeOils(),
        lye_form: {
          superfat: ((_a = document.getElementById("lyeSuperfat")) == null ? void 0 : _a.value) || "5",
          lye_type: ((_b = document.querySelector('input[name="lye_type"]:checked')) == null ? void 0 : _b.value) || "NaOH",
          lye_purity: ((_c = document.getElementById("lyePurity")) == null ? void 0 : _c.value) || "100",
          water_method: ((_d = document.getElementById("waterMethod")) == null ? void 0 : _d.value) || "percent",
          water_pct: ((_e = document.getElementById("waterPct")) == null ? void 0 : _e.value) || "",
          lye_concentration: ((_f = document.getElementById("lyeConcentration")) == null ? void 0 : _f.value) || "",
          water_ratio: ((_g = document.getElementById("waterRatio")) == null ? void 0 : _g.value) || ""
        },
        additives: {
          fragrances: serializeFragrances(),
          lactate_pct: document.getElementById("additiveLactatePct").value || "1",
          lactate_name: ((_h = document.getElementById("additiveLactateName")) == null ? void 0 : _h.value) || "",
          lactate_gi: ((_i = document.getElementById("additiveLactateGi")) == null ? void 0 : _i.value) || "",
          lactate_unit: ((_j = document.getElementById("additiveLactateUnit")) == null ? void 0 : _j.value) || "",
          lactate_category: ((_k = document.getElementById("additiveLactateCategory")) == null ? void 0 : _k.value) || "",
          sugar_pct: document.getElementById("additiveSugarPct").value || "1",
          sugar_name: ((_l = document.getElementById("additiveSugarName")) == null ? void 0 : _l.value) || "",
          sugar_gi: ((_m = document.getElementById("additiveSugarGi")) == null ? void 0 : _m.value) || "",
          sugar_unit: ((_n = document.getElementById("additiveSugarUnit")) == null ? void 0 : _n.value) || "",
          sugar_category: ((_o = document.getElementById("additiveSugarCategory")) == null ? void 0 : _o.value) || "",
          salt_pct: document.getElementById("additiveSaltPct").value || "0.5",
          salt_name: ((_p = document.getElementById("additiveSaltName")) == null ? void 0 : _p.value) || "",
          salt_gi: ((_q = document.getElementById("additiveSaltGi")) == null ? void 0 : _q.value) || "",
          salt_unit: ((_r = document.getElementById("additiveSaltUnit")) == null ? void 0 : _r.value) || "",
          salt_category: ((_s = document.getElementById("additiveSaltCategory")) == null ? void 0 : _s.value) || "",
          citric_pct: document.getElementById("additiveCitricPct").value || "0",
          citric_name: ((_t = document.getElementById("additiveCitricName")) == null ? void 0 : _t.value) || "",
          citric_gi: ((_u = document.getElementById("additiveCitricGi")) == null ? void 0 : _u.value) || "",
          citric_unit: ((_v = document.getElementById("additiveCitricUnit")) == null ? void 0 : _v.value) || "",
          citric_category: ((_w = document.getElementById("additiveCitricCategory")) == null ? void 0 : _w.value) || ""
        },
        mold: {
          water_weight: document.getElementById("moldWaterWeight").value || "",
          oil_pct: document.getElementById("moldOilPct").value || "65",
          shape: ((_x = document.getElementById("moldShape")) == null ? void 0 : _x.value) || "loaf",
          cylinder_correction: !!((_y = document.getElementById("moldCylinderCorrection")) == null ? void 0 : _y.checked),
          cylinder_factor: ((_z = document.getElementById("moldCylinderFactor")) == null ? void 0 : _z.value) || "0.85"
        },
        quality: {
          preset: ((_A = document.getElementById("qualityPreset")) == null ? void 0 : _A.value) || "balanced",
          focus: Array.from(document.querySelectorAll(".quality-focus:checked")).map((el) => el.id)
        },
        lines: {
          ingredients: serializeLines("tool-ingredients", "ingredient"),
          consumables: serializeLines("tool-consumables", "consumable"),
          containers: serializeLines("tool-containers", "container")
        },
        bulk_oils: SoapTool.bulkOilsModal && typeof SoapTool.bulkOilsModal.serializeSelection === "function" ? SoapTool.bulkOilsModal.serializeSelection() : { mode: "basics", selections: [] },
        updated_at: Date.now()
      };
      try {
        storage.setItem(STATE_STORAGE_KEY, JSON.stringify(payload));
        const lastSaved = document.getElementById("soapLastSaved");
        if (lastSaved) lastSaved.textContent = formatTime(payload.updated_at);
        SoapTool.ui.showAutosaveToast();
      } catch (_) {
      }
    }
    function restoreState() {
      var _a, _b, _c;
      const storage = getStorage();
      if (!storage) return;
      const raw = storage.getItem(STATE_STORAGE_KEY);
      if (!raw) return;
      let data = null;
      try {
        data = JSON.parse(raw);
      } catch (_) {
        return;
      }
      if (!data || typeof data !== "object") return;
      if (data.unit) {
        const unitInput = document.querySelector(`input[name="weight_unit"][value="${data.unit}"]`);
        if (unitInput) unitInput.checked = true;
        SoapTool.units.setUnit(data.unit, { skipConvert: true, skipAutoCalc: true });
      }
      if (data.oil_total_target !== void 0) {
        document.getElementById("oilTotalTarget").value = data.oil_total_target;
      }
      const oilRows = document.getElementById("oilRows");
      if (oilRows) {
        oilRows.innerHTML = "";
        const oils = Array.isArray(data.oils) && data.oils.length ? data.oils : [{}];
        oils.forEach((oil) => {
          const row = SoapTool.oils.buildOilRow();
          row.querySelector(".oil-typeahead").value = oil.name || "";
          row.querySelector(".oil-grams").value = oil.grams || "";
          row.querySelector(".oil-percent").value = oil.percent || "";
          row.querySelector(".oil-sap-koh").value = oil.sap || "";
          row.querySelector(".oil-iodine").value = oil.iodine || "";
          row.querySelector(".oil-fatty").value = oil.fattyRaw || "";
          row.querySelector(".oil-gi-id").value = oil.gi || "";
          const unitEl = row.querySelector(".oil-default-unit");
          if (unitEl) unitEl.value = oil.defaultUnit || "";
          const categoryEl = row.querySelector(".oil-category");
          if (categoryEl) categoryEl.value = oil.categoryName || "";
          oilRows.appendChild(row);
        });
      }
      if (data.lye_form) {
        const superfat = document.getElementById("lyeSuperfat");
        if (superfat) superfat.value = data.lye_form.superfat || "5";
        const lyeType = document.querySelector(`input[name="lye_type"][value="${data.lye_form.lye_type || "NaOH"}"]`);
        if (lyeType) lyeType.checked = true;
        const purity = document.getElementById("lyePurity");
        if (purity) purity.value = data.lye_form.lye_purity || "100";
        const waterMethod = document.getElementById("waterMethod");
        if (waterMethod) waterMethod.value = data.lye_form.water_method || "percent";
        const waterPct = document.getElementById("waterPct");
        if (waterPct) waterPct.value = data.lye_form.water_pct || "";
        const lyeConcentration = document.getElementById("lyeConcentration");
        if (lyeConcentration) lyeConcentration.value = data.lye_form.lye_concentration || "";
        const waterRatio = document.getElementById("waterRatio");
        if (waterRatio) waterRatio.value = data.lye_form.water_ratio || "";
        SoapTool.runner.applyLyeSelection();
      }
      if (data.additives) {
        const fragranceRows = document.getElementById("fragranceRows");
        if (fragranceRows && ((_a = SoapTool.fragrances) == null ? void 0 : _a.buildFragranceRow)) {
          fragranceRows.innerHTML = "";
          const fragrances = Array.isArray(data.additives.fragrances) && data.additives.fragrances.length ? data.additives.fragrances : null;
          if (fragrances) {
            fragrances.forEach((item) => {
              const row = SoapTool.fragrances.buildFragranceRow();
              row.querySelector(".fragrance-typeahead").value = item.name || "";
              row.querySelector(".fragrance-grams").value = item.grams || "";
              row.querySelector(".fragrance-percent").value = item.percent || "";
              row.querySelector(".fragrance-gi-id").value = item.gi || "";
              const unitEl = row.querySelector(".fragrance-default-unit");
              if (unitEl) unitEl.value = item.defaultUnit || "";
              const categoryEl = row.querySelector(".fragrance-category");
              if (categoryEl) categoryEl.value = item.categoryName || "";
              fragranceRows.appendChild(row);
            });
          } else if (data.additives.fragrance_pct || data.additives.fragrance_name || data.additives.fragrance_gi) {
            const row = SoapTool.fragrances.buildFragranceRow();
            row.querySelector(".fragrance-typeahead").value = data.additives.fragrance_name || "";
            row.querySelector(".fragrance-percent").value = data.additives.fragrance_pct || "3";
            row.querySelector(".fragrance-gi-id").value = data.additives.fragrance_gi || "";
            fragranceRows.appendChild(row);
          }
        }
        document.getElementById("additiveLactatePct").value = data.additives.lactate_pct || "1";
        const lactateName = document.getElementById("additiveLactateName");
        if (lactateName) lactateName.value = data.additives.lactate_name || "";
        const lactateGi = document.getElementById("additiveLactateGi");
        if (lactateGi) lactateGi.value = data.additives.lactate_gi || "";
        const lactateUnit = document.getElementById("additiveLactateUnit");
        if (lactateUnit) lactateUnit.value = data.additives.lactate_unit || "";
        const lactateCategory = document.getElementById("additiveLactateCategory");
        if (lactateCategory) lactateCategory.value = data.additives.lactate_category || "";
        document.getElementById("additiveSugarPct").value = data.additives.sugar_pct || "1";
        const sugarName = document.getElementById("additiveSugarName");
        if (sugarName) sugarName.value = data.additives.sugar_name || "";
        const sugarGi = document.getElementById("additiveSugarGi");
        if (sugarGi) sugarGi.value = data.additives.sugar_gi || "";
        const sugarUnit = document.getElementById("additiveSugarUnit");
        if (sugarUnit) sugarUnit.value = data.additives.sugar_unit || "";
        const sugarCategory = document.getElementById("additiveSugarCategory");
        if (sugarCategory) sugarCategory.value = data.additives.sugar_category || "";
        document.getElementById("additiveSaltPct").value = data.additives.salt_pct || "0.5";
        const saltName = document.getElementById("additiveSaltName");
        if (saltName) saltName.value = data.additives.salt_name || "";
        const saltGi = document.getElementById("additiveSaltGi");
        if (saltGi) saltGi.value = data.additives.salt_gi || "";
        const saltUnit = document.getElementById("additiveSaltUnit");
        if (saltUnit) saltUnit.value = data.additives.salt_unit || "";
        const saltCategory = document.getElementById("additiveSaltCategory");
        if (saltCategory) saltCategory.value = data.additives.salt_category || "";
        document.getElementById("additiveCitricPct").value = data.additives.citric_pct || "0";
        const citricName = document.getElementById("additiveCitricName");
        if (citricName) citricName.value = data.additives.citric_name || "";
        const citricGi = document.getElementById("additiveCitricGi");
        if (citricGi) citricGi.value = data.additives.citric_gi || "";
        const citricUnit = document.getElementById("additiveCitricUnit");
        if (citricUnit) citricUnit.value = data.additives.citric_unit || "";
        const citricCategory = document.getElementById("additiveCitricCategory");
        if (citricCategory) citricCategory.value = data.additives.citric_category || "";
      }
      if (data.mold) {
        document.getElementById("moldWaterWeight").value = data.mold.water_weight || "";
        document.getElementById("moldOilPct").value = data.mold.oil_pct || "65";
        const moldShape = document.getElementById("moldShape");
        if (moldShape) moldShape.value = data.mold.shape || "loaf";
        const cylCorrection = document.getElementById("moldCylinderCorrection");
        if (cylCorrection) cylCorrection.checked = !!data.mold.cylinder_correction;
        const cylFactor = document.getElementById("moldCylinderFactor");
        if (cylFactor) cylFactor.value = data.mold.cylinder_factor || "0.85";
        const targetInput = document.getElementById("oilTotalTarget");
        if (((_b = SoapTool.mold) == null ? void 0 : _b.syncMoldPctFromTarget) && ((_c = SoapTool.mold) == null ? void 0 : _c.syncTargetFromMold)) {
          const restoredTarget = SoapTool.units.toGrams(targetInput == null ? void 0 : targetInput.value);
          if (restoredTarget > 0) {
            SoapTool.mold.syncMoldPctFromTarget();
          } else {
            SoapTool.mold.syncTargetFromMold();
          }
        }
      }
      if (data.quality) {
        const preset = document.getElementById("qualityPreset");
        if (preset) {
          const desired = data.quality.preset || "balanced";
          const option = Array.from(preset.options).find((opt) => opt.value === desired);
          preset.value = option ? desired : "balanced";
        }
        document.querySelectorAll(".quality-focus").forEach((el) => {
          el.checked = Array.isArray(data.quality.focus) && data.quality.focus.includes(el.id);
        });
      }
      function restoreLines(wrapperId, items, kind) {
        const wrapper = document.getElementById(wrapperId);
        if (!wrapper) return;
        wrapper.innerHTML = "";
        (items || []).forEach((item) => {
          const row = SoapTool.runner.buildLineRow(kind);
          const input = row.querySelector(".tool-typeahead");
          const giHidden = row.querySelector(".tool-gi-id");
          const qtyEl = row.querySelector(".tool-qty");
          const unitEl = row.querySelector(".tool-unit");
          if (input) input.value = item.name || "";
          if (giHidden) giHidden.value = item.global_item_id || "";
          if (qtyEl && item.quantity !== void 0 && item.quantity !== null) qtyEl.value = item.quantity;
          if (unitEl && item.unit) {
            const option = Array.from(unitEl.options).find((opt) => opt.value === item.unit);
            if (option) unitEl.value = item.unit;
          }
          wrapper.appendChild(row);
        });
      }
      if (data.lines) {
        restoreLines("tool-ingredients", data.lines.ingredients, "ingredient");
        restoreLines("tool-consumables", data.lines.consumables, "consumable");
        restoreLines("tool-containers", data.lines.containers, "container");
      }
      if (SoapTool.bulkOilsModal && typeof SoapTool.bulkOilsModal.restoreState === "function") {
        SoapTool.bulkOilsModal.restoreState(data.bulk_oils || null);
      }
      SoapTool.runner.setWaterMethod();
      SoapTool.mold.updateMoldShapeUI();
      SoapTool.quality.updateQualityTargets();
      SoapTool.oils.updateOilTotals();
      SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
      SoapTool.mold.updateMoldSuggested();
      SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: false });
      if (data.updated_at) {
        const lastSaved = document.getElementById("soapLastSaved");
        if (lastSaved) lastSaved.textContent = formatTime(data.updated_at);
      }
      SoapTool.stages.updateStageStatuses();
      SoapTool.ui.showSoapAlert("info", "Restored your last soap tool session from this device.", { dismissible: true, timeoutMs: 5e3 });
    }
    let saveStateTimer = null;
    function queueStateSave() {
      if (saveStateTimer) clearTimeout(saveStateTimer);
      saveStateTimer = setTimeout(saveState, 350);
    }
    let autoCalcTimer = null;
    function queueAutoCalc() {
      if (autoCalcTimer) clearTimeout(autoCalcTimer);
      autoCalcTimer = setTimeout(() => {
        SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: false });
      }, 350);
    }
    SoapTool.storage = {
      saveState,
      restoreState,
      serializeLines,
      serializeOils,
      restoreOilRow,
      queueStateSave,
      queueAutoCalc
    };
  })(window);

  // app/static/js/tools/soaps/soap_tool_events.js
  (function(window2) {
    "use strict";
    var _a, _b;
    const SoapTool = window2.SoapTool = window2.SoapTool || {};
    const { LACTATE_CATEGORY_SET, SUGAR_CATEGORY_SET, SALT_CATEGORY_SET, CITRIC_CATEGORY_SET } = SoapTool.constants;
    const { round, toNumber, clamp } = SoapTool.helpers;
    const { formatWeight, formatPercent, toGrams } = SoapTool.units;
    const state = SoapTool.state;
    async function getCalcForExport() {
      var _a2;
      const calc = state.lastCalc || await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
      if (!calc) {
        if ((_a2 = SoapTool.ui) == null ? void 0 : _a2.showSoapAlert) {
          SoapTool.ui.showSoapAlert("warning", "Run a calculation before exporting or printing.", { dismissible: true, timeoutMs: 6e3 });
        }
        return null;
      }
      return calc;
    }
    function collectFragranceExportRows(totalOils) {
      const rows = [];
      document.querySelectorAll("#fragranceRows .fragrance-row").forEach((row) => {
        var _a2, _b2, _c, _d;
        const name = (_b2 = (_a2 = row.querySelector(".fragrance-typeahead")) == null ? void 0 : _a2.value) == null ? void 0 : _b2.trim();
        const gramsInput = (_c = row.querySelector(".fragrance-grams")) == null ? void 0 : _c.value;
        const pctInput = (_d = row.querySelector(".fragrance-percent")) == null ? void 0 : _d.value;
        let grams = toGrams(gramsInput);
        let pct = clamp(toNumber(pctInput), 0);
        if (grams <= 0 && pct > 0 && totalOils > 0) {
          grams = totalOils * (pct / 100);
        }
        if (grams <= 0 && pct <= 0 && !name) return;
        if (!pct && grams > 0 && totalOils > 0) {
          pct = grams / totalOils * 100;
        }
        rows.push({
          name: name || "Fragrance/Essential Oils",
          grams,
          pct
        });
      });
      return rows;
    }
    function collectAdditiveExportRows(additives) {
      var _a2, _b2, _c, _d, _e, _f, _g, _h;
      const rows = [];
      if (!additives) return rows;
      const lactateName = ((_b2 = (_a2 = document.getElementById("additiveLactateName")) == null ? void 0 : _a2.value) == null ? void 0 : _b2.trim()) || "Sodium Lactate";
      const sugarName = ((_d = (_c = document.getElementById("additiveSugarName")) == null ? void 0 : _c.value) == null ? void 0 : _d.trim()) || "Sugar";
      const saltName = ((_f = (_e = document.getElementById("additiveSaltName")) == null ? void 0 : _e.value) == null ? void 0 : _f.trim()) || "Salt";
      const citricName = ((_h = (_g = document.getElementById("additiveCitricName")) == null ? void 0 : _g.value) == null ? void 0 : _h.trim()) || "Citric Acid";
      if (additives.lactateG > 0) {
        rows.push({ name: lactateName, grams: additives.lactateG, pct: additives.lactatePct });
      }
      if (additives.sugarG > 0) {
        rows.push({ name: sugarName, grams: additives.sugarG, pct: additives.sugarPct });
      }
      if (additives.saltG > 0) {
        rows.push({ name: saltName, grams: additives.saltG, pct: additives.saltPct });
      }
      if (additives.citricG > 0) {
        rows.push({ name: citricName, grams: additives.citricG, pct: additives.citricPct });
      }
      return rows;
    }
    function buildFormulaCsv(calc) {
      var _a2, _b2;
      if (Array.isArray((_a2 = calc == null ? void 0 : calc.export) == null ? void 0 : _a2.csv_rows) && calc.export.csv_rows.length) {
        return calc.export.csv_rows;
      }
      const totalOils = calc.totalOils || 0;
      const rows = [["section", "name", "quantity", "unit", "percent"]];
      rows.push(["Summary", "Lye Type", calc.lyeType || "", "", ""]);
      rows.push(["Summary", "Superfat", round(calc.superfat || 0, 2), "%", ""]);
      rows.push(["Summary", "Lye Purity", round(calc.purity || 0, 1), "%", ""]);
      rows.push(["Summary", "Water Method", calc.waterMethod || "", "", ""]);
      rows.push(["Summary", "Water %", round(calc.waterPct || 0, 1), "%", ""]);
      rows.push(["Summary", "Lye Concentration", round(calc.lyeConcentration || 0, 1), "%", ""]);
      rows.push(["Summary", "Water Ratio", round(calc.waterRatio || 0, 2), "", ""]);
      rows.push(["Summary", "Total Oils", round(totalOils, 2), "gram", ""]);
      rows.push(["Summary", "Batch Yield", round(calc.batchYield || 0, 2), "gram", ""]);
      (calc.oils || []).forEach((oil) => {
        const pct = totalOils > 0 ? round(oil.grams / totalOils * 100, 2) : "";
        rows.push(["Oils", oil.name || "Oil", round(oil.grams || 0, 2), "gram", pct]);
      });
      if (calc.lyeAdjusted > 0) {
        rows.push(["Lye", calc.lyeType === "KOH" ? "Potassium Hydroxide (KOH)" : "Sodium Hydroxide (NaOH)", round(calc.lyeAdjusted, 2), "gram", ""]);
      }
      if (calc.water > 0) {
        rows.push(["Water", "Distilled Water", round(calc.water, 2), "gram", ""]);
      }
      const fragrances = collectFragranceExportRows(totalOils);
      fragrances.forEach((row) => {
        rows.push(["Fragrance", row.name, round(row.grams || 0, 2), "gram", round(row.pct || 0, 2)]);
      });
      const additiveRows = collectAdditiveExportRows(calc.additives);
      additiveRows.forEach((row) => {
        rows.push(["Additives", row.name, round(row.grams || 0, 2), "gram", round(row.pct || 0, 2)]);
      });
      if (((_b2 = calc.additives) == null ? void 0 : _b2.citricLyeG) > 0) {
        rows.push(["Additives", "Extra Lye for Citric Acid", round(calc.additives.citricLyeG, 2), "gram", ""]);
      }
      return rows;
    }
    function csvEscape(value) {
      if (value === null || value === void 0) return "";
      const str = String(value);
      if (/[",\n]/.test(str)) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    }
    function buildCsvString(rows) {
      return rows.map((row) => row.map(csvEscape).join(",")).join("\n");
    }
    function triggerCsvDownload(csvText, filename) {
      const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
    function buildPrintSheet(calc) {
      var _a2, _b2;
      if (typeof ((_a2 = calc == null ? void 0 : calc.export) == null ? void 0 : _a2.sheet_html) === "string" && calc.export.sheet_html.trim()) {
        return calc.export.sheet_html;
      }
      const totalOils = calc.totalOils || 0;
      const oils = (calc.oils || []).map((oil) => ({
        name: oil.name || "Oil",
        grams: oil.grams || 0,
        pct: totalOils > 0 ? oil.grams / totalOils * 100 : 0
      }));
      const fragrances = collectFragranceExportRows(totalOils);
      const additives = collectAdditiveExportRows(calc.additives);
      const now = (/* @__PURE__ */ new Date()).toLocaleString();
      const oilRows2 = oils.length ? oils.map((oil) => `
          <tr>
            <td>${oil.name}</td>
            <td class="text-end">${formatWeight(oil.grams)}</td>
            <td class="text-end">${formatPercent(oil.pct)}</td>
          </tr>`).join("") : '<tr><td colspan="3" class="text-muted">No oils added.</td></tr>';
      const fragranceRows2 = fragrances.length ? fragrances.map((item) => `
          <tr>
            <td>${item.name}</td>
            <td class="text-end">${formatWeight(item.grams)}</td>
            <td class="text-end">${formatPercent(item.pct)}</td>
          </tr>`).join("") : '<tr><td colspan="3" class="text-muted">No fragrances added.</td></tr>';
      const additiveRows = additives.length ? additives.map((item) => `
          <tr>
            <td>${item.name}</td>
            <td class="text-end">${formatWeight(item.grams)}</td>
            <td class="text-end">${formatPercent(item.pct)}</td>
          </tr>`).join("") : '<tr><td colspan="3" class="text-muted">No additives added.</td></tr>';
      const lyeLabel = calc.lyeType === "KOH" ? "Potassium Hydroxide (KOH)" : "Sodium Hydroxide (NaOH)";
      const extraLyeRow = ((_b2 = calc.additives) == null ? void 0 : _b2.citricLyeG) > 0 ? `<tr><td>Extra Lye for Citric Acid</td><td class="text-end">${formatWeight(calc.additives.citricLyeG)}</td></tr>` : "";
      return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Soap Formula Sheet</title>
    <style>
      body { font-family: Arial, sans-serif; color: #111; margin: 24px; }
      h1 { font-size: 20px; margin-bottom: 4px; }
      h2 { font-size: 16px; margin-top: 20px; }
      .meta { font-size: 12px; color: #555; margin-bottom: 12px; }
      table { width: 100%; border-collapse: collapse; margin-top: 8px; }
      th, td { border: 1px solid #ddd; padding: 6px 8px; font-size: 12px; }
      th { background: #f3f4f6; text-align: left; }
      .text-end { text-align: right; }
      .summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 16px; font-size: 12px; }
      .summary-item { display: flex; justify-content: space-between; border-bottom: 1px solid #eee; padding: 4px 0; }
      .text-muted { color: #666; }
    </style>
  </head>
  <body>
    <h1>Soap Formula Sheet</h1>
    <div class="meta">Generated ${now}</div>
    <div class="summary-grid">
      <div class="summary-item"><span>Lye type</span><span>${calc.lyeType || "--"}</span></div>
      <div class="summary-item"><span>Superfat</span><span>${formatPercent(calc.superfat || 0)}</span></div>
      <div class="summary-item"><span>Lye purity</span><span>${formatPercent(calc.purity || 0)}</span></div>
      <div class="summary-item"><span>Total oils</span><span>${formatWeight(totalOils)}</span></div>
      <div class="summary-item"><span>Water</span><span>${formatWeight(calc.water || 0)}</span></div>
      <div class="summary-item"><span>Batch yield</span><span>${formatWeight(calc.batchYield || 0)}</span></div>
      <div class="summary-item"><span>Water method</span><span>${calc.waterMethod || "--"}</span></div>
      <div class="summary-item"><span>Lye concentration</span><span>${formatPercent(calc.lyeConcentration || 0)}</span></div>
    </div>

    <h2>Oils</h2>
    <table>
      <thead>
        <tr><th>Oil</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr>
      </thead>
      <tbody>${oilRows2}</tbody>
    </table>

    <h2>Lye & Water</h2>
    <table>
      <thead>
        <tr><th>Item</th><th class="text-end">Weight</th></tr>
      </thead>
      <tbody>
        <tr><td>${lyeLabel}</td><td class="text-end">${formatWeight(calc.lyeAdjusted || 0)}</td></tr>
        <tr><td>Distilled Water</td><td class="text-end">${formatWeight(calc.water || 0)}</td></tr>
        ${extraLyeRow}
      </tbody>
    </table>

    <h2>Fragrance & Essential Oils</h2>
    <table>
      <thead>
        <tr><th>Fragrance</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr>
      </thead>
      <tbody>${fragranceRows2}</tbody>
    </table>

    <h2>Additives</h2>
    <table>
      <thead>
        <tr><th>Additive</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr>
      </thead>
      <tbody>${additiveRows}</tbody>
    </table>
  </body>
</html>`;
    }
    const oilRows = document.getElementById("oilRows");
    const addOilBtn = document.getElementById("addOil");
    const normalizeOilsBtn = document.getElementById("normalizeOils");
    if (addOilBtn && oilRows) {
      addOilBtn.dataset.bound = "direct";
      addOilBtn.addEventListener("click", function() {
        oilRows.appendChild(SoapTool.oils.buildOilRow());
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
      });
    }
    if (normalizeOilsBtn) {
      normalizeOilsBtn.dataset.bound = "direct";
      normalizeOilsBtn.addEventListener("click", function() {
        SoapTool.oils.normalizeOils();
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    if (oilRows) oilRows.addEventListener("input", function(e) {
      if (e.target.classList.contains("oil-grams")) {
        state.lastOilEdit = { row: e.target.closest(".oil-row"), field: "grams" };
      }
      if (e.target.classList.contains("oil-percent")) {
        state.lastOilEdit = { row: e.target.closest(".oil-row"), field: "percent" };
      }
      if (e.target.classList.contains("oil-grams") || e.target.classList.contains("oil-percent") || e.target.classList.contains("oil-typeahead")) {
        if (e.target.classList.contains("oil-typeahead")) {
          SoapTool.oils.setSelectedOilProfileFromRow(e.target.closest(".oil-row"));
        }
        SoapTool.oils.updateOilTotals();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      }
    });
    if (oilRows) oilRows.addEventListener("focusin", function(e) {
      if (e.target.classList.contains("oil-typeahead")) {
        SoapTool.oils.setSelectedOilProfileFromRow(e.target.closest(".oil-row"));
      }
    });
    if (oilRows) oilRows.addEventListener("focusout", function(e) {
      if (e.target.classList.contains("oil-typeahead")) {
        SoapTool.oils.clearSelectedOilProfile();
      }
      if (e.target.classList.contains("oil-grams")) {
        SoapTool.oils.validateOilEntry(e.target.closest(".oil-row"), "grams");
      }
      if (e.target.classList.contains("oil-percent")) {
        SoapTool.oils.validateOilEntry(e.target.closest(".oil-row"), "percent");
      }
    });
    if (oilRows) oilRows.addEventListener("keydown", function(e) {
      if (e.key !== "Enter") return;
      if (e.target.classList.contains("oil-grams")) {
        e.preventDefault();
        SoapTool.oils.validateOilEntry(e.target.closest(".oil-row"), "grams");
      }
      if (e.target.classList.contains("oil-percent")) {
        e.preventDefault();
        SoapTool.oils.validateOilEntry(e.target.closest(".oil-row"), "percent");
      }
    });
    if (oilRows) oilRows.addEventListener("mouseover", function(e) {
      if (!e.target.classList.contains("oil-typeahead")) return;
      const row = e.target.closest(".oil-row");
      if (!row || row === state.lastPreviewRow) return;
      state.lastPreviewRow = row;
      SoapTool.oils.setSelectedOilProfileFromRow(row);
    });
    if (oilRows) oilRows.addEventListener("mouseout", function(e) {
      if (e.target.classList.contains("oil-typeahead")) {
        SoapTool.oils.clearSelectedOilProfile();
      }
    });
    if (oilRows) oilRows.addEventListener("click", function(e) {
      const profileButton = e.target.closest(".oil-profile-open");
      if (profileButton) {
        const row = profileButton.closest(".oil-row");
        if (row) {
          SoapTool.oils.setSelectedOilProfileFromRow(row);
          const modalEl = document.getElementById("oilProfileModal");
          if (modalEl && window2.bootstrap) {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
          }
        }
        return;
      }
      const removeButton = e.target.closest(".remove-oil");
      if (removeButton) {
        const row = removeButton.closest(".oil-row");
        if (row) {
          state.lastRemovedOil = SoapTool.oils.serializeOilRow(row);
          state.lastRemovedOilIndex = Array.from(row.parentElement.children).indexOf(row);
          SoapTool.ui.showUndoToast("Oil removed.");
        }
        if (row && state.lastOilEdit && state.lastOilEdit.row === row) {
          state.lastOilEdit = null;
          SoapTool.oils.clearSelectedOilProfile();
        }
        if (row) row.remove();
        SoapTool.oils.updateOilTotals();
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
      }
    });
    const fragranceRows = document.getElementById("fragranceRows");
    const addFragranceBtn = document.getElementById("addFragrance");
    if (addFragranceBtn && fragranceRows) {
      addFragranceBtn.dataset.bound = "direct";
      addFragranceBtn.addEventListener("click", function() {
        fragranceRows.appendChild(SoapTool.fragrances.buildFragranceRow());
        SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
      });
    }
    if (fragranceRows) {
      fragranceRows.addEventListener("input", function(e) {
        if (e.target.classList.contains("fragrance-grams")) {
          SoapTool.state.lastFragranceEdit = { row: e.target.closest(".fragrance-row"), field: "grams" };
        }
        if (e.target.classList.contains("fragrance-percent")) {
          SoapTool.state.lastFragranceEdit = { row: e.target.closest(".fragrance-row"), field: "percent" };
        }
        if (e.target.classList.contains("fragrance-grams") || e.target.classList.contains("fragrance-percent") || e.target.classList.contains("fragrance-typeahead")) {
          SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
          SoapTool.stages.updateStageStatuses();
          SoapTool.storage.queueStateSave();
          SoapTool.storage.queueAutoCalc();
        }
      });
      fragranceRows.addEventListener("click", function(e) {
        const removeButton = e.target.closest(".remove-fragrance");
        if (!removeButton) return;
        const row = removeButton.closest(".fragrance-row");
        if (row) row.remove();
        SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    const stageTabContent = document.getElementById("soapStageTabContent");
    const getActiveStageScrollContainer = () => {
      if (!stageTabContent) return null;
      const activePane = stageTabContent.querySelector(".tab-pane.active") || stageTabContent.querySelector(".tab-pane.show.active");
      if (!activePane) return null;
      return activePane.querySelector(".soap-stage-body") || activePane;
    };
    const bindStageWheelGuard = () => {
      if (!stageTabContent) return;
      stageTabContent.addEventListener("wheel", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const numberInput = target.closest('input[type="number"]');
        if (!(numberInput instanceof HTMLInputElement)) return;
        const scrollContainer = getActiveStageScrollContainer();
        if (!(scrollContainer instanceof HTMLElement)) return;
        if (scrollContainer.scrollHeight <= scrollContainer.clientHeight + 1) return;
        if (document.activeElement === numberInput && typeof numberInput.blur === "function") {
          numberInput.blur();
        }
        const atTop = scrollContainer.scrollTop <= 0;
        const atBottom = scrollContainer.scrollTop + scrollContainer.clientHeight >= scrollContainer.scrollHeight - 1;
        if (event.deltaY < 0 && atTop || event.deltaY > 0 && atBottom) {
          return;
        }
        scrollContainer.scrollTop += event.deltaY;
        event.preventDefault();
      }, { passive: false });
    };
    if (stageTabContent) {
      stageTabContent.addEventListener("click", (event) => {
        const actionBtn = event.target.closest("[data-stage-action]");
        const soapActionBtn = event.target.closest("[data-soap-action]");
        if (!actionBtn && !soapActionBtn) return;
        event.preventDefault();
        event.stopPropagation();
        if (document.activeElement && typeof document.activeElement.blur === "function") {
          document.activeElement.blur();
        }
        if (soapActionBtn) {
          if (soapActionBtn.dataset.bound === "direct") return;
          const action2 = soapActionBtn.dataset.soapAction;
          if (action2 === "add-oil" && oilRows) {
            oilRows.appendChild(SoapTool.oils.buildOilRow());
            SoapTool.stages.updateStageStatuses();
            SoapTool.storage.queueStateSave();
          }
          if (action2 === "normalize-oils") {
            SoapTool.oils.normalizeOils();
            SoapTool.stages.updateStageStatuses();
            SoapTool.storage.queueStateSave();
            SoapTool.storage.queueAutoCalc();
          }
          if (action2 === "add-fragrance" && fragranceRows) {
            fragranceRows.appendChild(SoapTool.fragrances.buildFragranceRow());
            SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
            SoapTool.stages.updateStageStatuses();
            SoapTool.storage.queueStateSave();
          }
          return;
        }
        const action = actionBtn.dataset.stageAction;
        const index = Number(actionBtn.dataset.stageIndex);
        if (Number.isNaN(index)) return;
        if (action === "prev") SoapTool.stages.openStageByIndex(Math.max(0, index - 1));
        if (action === "next") SoapTool.stages.openStageByIndex(Math.min(SoapTool.constants.STAGE_CONFIGS.length - 1, index + 1));
        if (action === "reset") SoapTool.stages.resetStage(index + 1);
      });
      bindStageWheelGuard();
    }
    const stageTabList = document.getElementById("soapStageTabList");
    const updateStageTabSizing = () => {
      if (!stageTabList) return;
      stageTabList.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("is-expanded"));
      const active = stageTabList.querySelector(".nav-link.active");
      if (active && active.closest(".nav-item")) {
        active.closest(".nav-item").classList.add("is-expanded");
      }
    };
    if (stageTabList) {
      stageTabList.addEventListener("shown.bs.tab", () => {
        updateStageTabSizing();
        SoapTool.layout.scheduleStageHeightSync();
      });
      updateStageTabSizing();
    }
    const resultsToggle = document.getElementById("resultsCardToggle");
    const resultsCard = document.getElementById("resultsCard");
    if (resultsToggle && resultsCard) {
      resultsToggle.addEventListener("click", () => {
        resultsCard.classList.toggle("is-collapsed");
        const isCollapsed = resultsCard.classList.contains("is-collapsed");
        resultsToggle.setAttribute("aria-expanded", (!isCollapsed).toString());
        const label = isCollapsed ? "Expand formula details" : "Collapse formula details";
        resultsToggle.setAttribute("aria-label", label);
        resultsToggle.setAttribute("title", label);
        const icon = resultsToggle.querySelector("i");
        if (icon) {
          icon.classList.toggle("fa-chevron-down", isCollapsed);
          icon.classList.toggle("fa-chevron-up", !isCollapsed);
        }
      });
    }
    document.querySelectorAll('input[name="weight_unit"]').forEach((el) => {
      el.addEventListener("change", function() {
        SoapTool.units.setUnit(this.value);
        SoapTool.storage.queueStateSave();
      });
    });
    const rescaleOilsFromStageOne = () => {
      var _a2;
      SoapTool.oils.scaleOilsToTarget(void 0, { force: true });
      SoapTool.oils.updateOilTotals();
      if ((_a2 = SoapTool.mold) == null ? void 0 : _a2.updateWetBatterWarning) {
        SoapTool.mold.updateWetBatterWarning(null);
      }
    };
    const oilTotalTarget = document.getElementById("oilTotalTarget");
    if (oilTotalTarget) {
      oilTotalTarget.addEventListener("input", function() {
        SoapTool.mold.syncMoldPctFromTarget();
        rescaleOilsFromStageOne();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    const waterMethod = document.getElementById("waterMethod");
    if (waterMethod) {
      waterMethod.addEventListener("change", function() {
        SoapTool.runner.setWaterMethod();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    document.querySelectorAll('input[name="lye_type"]').forEach((el) => {
      el.addEventListener("change", function() {
        SoapTool.runner.applyLyeSelection();
        SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    });
    ["lyeSuperfat", "lyePurity", "waterPct", "lyeConcentration", "waterRatio"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      ["input", "change"].forEach((eventName) => {
        el.addEventListener(eventName, () => {
          SoapTool.storage.queueStateSave();
          SoapTool.storage.queueAutoCalc();
        });
      });
    });
    ["additiveLactatePct", "additiveSugarPct", "additiveSaltPct", "additiveCitricPct"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("input", () => {
        SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    });
    const additiveWeights = [
      { weightId: "additiveLactateWeight" },
      { weightId: "additiveSugarWeight" },
      { weightId: "additiveSaltWeight" },
      { weightId: "additiveCitricWeight" }
    ];
    additiveWeights.forEach(({ weightId }) => {
      const weightInput = document.getElementById(weightId);
      if (!weightInput) return;
      weightInput.addEventListener("input", () => {
        const totalOils = SoapTool.oils.getTotalOilsGrams();
        if (!totalOils) return;
        SoapTool.additives.updateAdditivesOutput(totalOils);
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    });
    document.querySelectorAll(".additive-typeahead").forEach((input) => {
      input.addEventListener("input", () => {
        SoapTool.storage.queueStateSave();
      });
    });
    const qualityPreset = document.getElementById("qualityPreset");
    if (qualityPreset) {
      qualityPreset.addEventListener("change", function() {
        SoapTool.quality.updateQualityTargets();
        SoapTool.storage.queueStateSave();
      });
    }
    document.querySelectorAll(".quality-focus").forEach((el) => {
      el.addEventListener("change", function() {
        SoapTool.quality.updateQualityTargets();
        SoapTool.storage.queueStateSave();
      });
    });
    const applyQualityBtn = document.getElementById("applyQualityTargets");
    if (applyQualityBtn) {
      applyQualityBtn.addEventListener("click", function() {
        SoapTool.quality.applyQualityTargets();
      });
    }
    document.querySelectorAll(".quality-target-marker").forEach((marker) => {
      marker.addEventListener("click", () => SoapTool.quality.applyQualityTargets());
      marker.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          SoapTool.quality.applyQualityTargets();
        }
      });
    });
    const moldWaterWeight = document.getElementById("moldWaterWeight");
    if (moldWaterWeight) {
      moldWaterWeight.addEventListener("input", function() {
        SoapTool.mold.syncTargetFromMold();
        rescaleOilsFromStageOne();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    const moldOilPct = document.getElementById("moldOilPct");
    if (moldOilPct) {
      moldOilPct.addEventListener("input", function() {
        SoapTool.mold.syncTargetFromMold();
        rescaleOilsFromStageOne();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    const moldShape = document.getElementById("moldShape");
    if (moldShape) {
      moldShape.addEventListener("change", function() {
        SoapTool.mold.updateMoldShapeUI();
        SoapTool.mold.syncTargetFromMold();
        rescaleOilsFromStageOne();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    const moldCylinderCorrection = document.getElementById("moldCylinderCorrection");
    if (moldCylinderCorrection) {
      moldCylinderCorrection.addEventListener("change", function() {
        SoapTool.mold.syncTargetFromMold();
        rescaleOilsFromStageOne();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    const moldCylinderFactor = document.getElementById("moldCylinderFactor");
    if (moldCylinderFactor) {
      moldCylinderFactor.addEventListener("input", function() {
        SoapTool.mold.syncTargetFromMold();
        rescaleOilsFromStageOne();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    document.querySelectorAll(".stub-btn").forEach((btn) => {
      btn.addEventListener("click", function() {
        const kind = this.dataset.stubKind;
        const name = this.dataset.stubName;
        SoapTool.runner.addStubLine(kind, name);
        SoapTool.storage.queueStateSave();
      });
    });
    const soapRoot = document.getElementById("soapToolPage");
    if (soapRoot) {
      soapRoot.addEventListener("click", function(e) {
        if (e.target.classList.contains("tool-remove")) {
          SoapTool.storage.queueStateSave();
        }
      });
      soapRoot.addEventListener("input", function(e) {
        if (e.target.matches("input, select, textarea")) {
          SoapTool.storage.queueStateSave();
          SoapTool.ui.validateNumericField(e.target);
          SoapTool.stages.updateStageStatuses();
          SoapTool.ui.flashStage(e.target.closest(".soap-stage-card"));
        }
      });
      soapRoot.addEventListener("change", function(e) {
        if (e.target.matches("input, select, textarea")) {
          SoapTool.storage.queueStateSave();
          SoapTool.ui.validateNumericField(e.target);
          SoapTool.stages.updateStageStatuses();
        }
      });
    }
    const addToolIngredient = document.getElementById("addToolIngredient");
    if (addToolIngredient) {
      addToolIngredient.addEventListener("click", function() {
        const wrapper = document.getElementById("tool-ingredients");
        if (wrapper) wrapper.appendChild(SoapTool.runner.buildLineRow("ingredient"));
        SoapTool.storage.queueStateSave();
      });
    }
    const addToolConsumable = document.getElementById("addToolConsumable");
    if (addToolConsumable) {
      addToolConsumable.addEventListener("click", function() {
        const wrapper = document.getElementById("tool-consumables");
        if (wrapper) wrapper.appendChild(SoapTool.runner.buildLineRow("consumable"));
        SoapTool.storage.queueStateSave();
      });
    }
    const addToolContainer = document.getElementById("addToolContainer");
    if (addToolContainer) {
      addToolContainer.addEventListener("click", function() {
        const wrapper = document.getElementById("tool-containers");
        if (wrapper) wrapper.appendChild(SoapTool.runner.buildLineRow("container"));
        SoapTool.storage.queueStateSave();
      });
    }
    const calcLyeBtn = document.getElementById("calcLyeBtn");
    if (calcLyeBtn) {
      calcLyeBtn.addEventListener("click", async function() {
        await SoapTool.runner.calculateAll({ consumeQuota: true, showAlerts: true });
        SoapTool.storage.queueStateSave();
      });
    }
    const saveSoapToolBtn = document.getElementById("saveSoapTool");
    if (saveSoapToolBtn) {
      saveSoapToolBtn.addEventListener("click", async function() {
        try {
          const calc = state.lastCalc || await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
          if (!calc) return;
          const payload = SoapTool.runner.buildSoapRecipePayload(calc);
          state.lastRecipePayload = payload;
          try {
            const storage = SoapTool.helpers.getStorage();
            if (storage) {
              storage.setItem("soap_recipe_payload", JSON.stringify(payload));
            }
          } catch (_) {
          }
          window2.SOAP_RECIPE_DTO = payload;
          SoapTool.ui.showSoapAlert("info", "Recipe payload is ready. Push is stubbed for now; no data has been sent.", { dismissible: true, timeoutMs: 7e3 });
        } catch (_) {
          SoapTool.ui.showSoapAlert("danger", "Unable to prepare the recipe payload. Please try again.", { dismissible: true, persist: true });
        }
      });
    }
    const exportSoapCsvBtn = document.getElementById("exportSoapCsv");
    if (exportSoapCsvBtn) {
      exportSoapCsvBtn.addEventListener("click", async function() {
        var _a2;
        const calc = await getCalcForExport();
        if (!calc) return;
        const rows = buildFormulaCsv(calc);
        const csvText = typeof ((_a2 = calc == null ? void 0 : calc.export) == null ? void 0 : _a2.csv_text) === "string" && calc.export.csv_text ? calc.export.csv_text : buildCsvString(rows);
        triggerCsvDownload(csvText, "soap_formula.csv");
      });
    }
    const printSoapSheetBtn = document.getElementById("printSoapSheet");
    if (printSoapSheetBtn) {
      printSoapSheetBtn.addEventListener("click", async function() {
        var _a2;
        const calc = await getCalcForExport();
        if (!calc) return;
        const html = buildPrintSheet(calc);
        const win = window2.open("", "_blank", "width=960,height=720");
        if (!win) {
          if ((_a2 = SoapTool.ui) == null ? void 0 : _a2.showSoapAlert) {
            SoapTool.ui.showSoapAlert("warning", "Pop-up blocked. Allow pop-ups to print the sheet.", { dismissible: true, timeoutMs: 6e3 });
          }
          return;
        }
        win.document.open();
        win.document.write(html);
        win.document.close();
        win.focus();
        win.onload = () => {
          win.print();
        };
      });
    }
    const undoRemoveBtn = document.getElementById("soapUndoRemove");
    if (undoRemoveBtn) {
      undoRemoveBtn.addEventListener("click", () => {
        if (!state.lastRemovedOil) return;
        SoapTool.storage.restoreOilRow(state.lastRemovedOil, state.lastRemovedOilIndex || 0);
        state.lastRemovedOil = null;
        state.lastRemovedOilIndex = null;
        SoapTool.oils.updateOilTotals();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }
    const setupMobileDrawer = () => {
      const drawer = document.getElementById("soapMobileDrawer");
      const drawerContent = document.getElementById("soapMobileDrawerContent");
      const drawerTitle = document.getElementById("soapMobileDrawerTitle");
      const drawerEmpty = document.getElementById("soapDrawerEmpty");
      const closeBtn = document.getElementById("soapDrawerClose");
      const qualityCard = document.getElementById("soapQualityCard");
      const resultsCard2 = document.getElementById("resultsCard");
      if (!drawer || !drawerContent || !drawerTitle || !qualityCard || !resultsCard2) return;
      const qualityHome = qualityCard.parentElement;
      const resultsHome = resultsCard2.parentElement;
      const placeholders = /* @__PURE__ */ new Map();
      let currentTarget = null;
      const isSmallScreen = () => window2.matchMedia("(max-width: 767px)").matches;
      const cardForTarget = (target) => target === "quality" ? qualityCard : resultsCard2;
      const homeForTarget = (target) => target === "quality" ? qualityHome : resultsHome;
      const titleForTarget = (target) => target === "quality" ? "Display" : "Results";
      const ensurePlaceholder = (card) => {
        let placeholder = placeholders.get(card);
        if (!placeholder) {
          placeholder = document.createElement("div");
          placeholder.className = "soap-card-placeholder";
          placeholders.set(card, placeholder);
        }
        placeholder.style.height = `${card.offsetHeight}px`;
        if (card.parentElement && card.parentElement !== drawerContent && !placeholder.parentElement) {
          card.parentElement.insertBefore(placeholder, card);
        }
      };
      const moveCardToDrawer = (card) => {
        if (!card) return;
        ensurePlaceholder(card);
        drawerContent.appendChild(card);
      };
      const restoreCard = (card, home) => {
        const placeholder = placeholders.get(card);
        if (placeholder && placeholder.parentElement) {
          placeholder.replaceWith(card);
        } else if (home && card.parentElement !== home) {
          home.appendChild(card);
        }
      };
      const updateDrawerEmpty = () => {
        if (!drawerEmpty) return;
        const isResults = currentTarget === "results";
        const resultsVisible = getComputedStyle(resultsCard2).display !== "none";
        drawerEmpty.classList.toggle("d-none", !isResults || resultsVisible);
      };
      const openDrawer = (target) => {
        if (!isSmallScreen()) return;
        if (currentTarget && currentTarget !== target) {
          restoreCard(cardForTarget(currentTarget), homeForTarget(currentTarget));
        }
        moveCardToDrawer(cardForTarget(target));
        drawerTitle.textContent = titleForTarget(target);
        currentTarget = target;
        drawer.classList.add("is-open");
        updateDrawerEmpty();
      };
      const closeDrawer = () => {
        if (!currentTarget) return;
        restoreCard(cardForTarget(currentTarget), homeForTarget(currentTarget));
        currentTarget = null;
        drawer.classList.remove("is-open");
        updateDrawerEmpty();
      };
      drawer.querySelectorAll("[data-drawer-target]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const target = btn.dataset.drawerTarget;
          if (!target) return;
          if (drawer.classList.contains("is-open") && currentTarget === target) {
            closeDrawer();
          } else {
            openDrawer(target);
          }
        });
      });
      if (closeBtn) {
        closeBtn.addEventListener("click", closeDrawer);
      }
      window2.addEventListener("resize", () => {
        if (!isSmallScreen() && currentTarget) {
          closeDrawer();
        }
      });
      const resultsObserver = new MutationObserver(() => updateDrawerEmpty());
      resultsObserver.observe(resultsCard2, { attributes: true, attributeFilter: ["style", "class"] });
    };
    setupMobileDrawer();
    window2.addEventListener("resize", SoapTool.layout.scheduleStageHeightSync);
    window2.addEventListener("load", SoapTool.layout.scheduleStageHeightSync);
    SoapTool.additives.attachAdditiveTypeahead("additiveLactateName", "additiveLactateGi", LACTATE_CATEGORY_SET, "additiveLactateUnit", "additiveLactateCategory");
    SoapTool.additives.attachAdditiveTypeahead("additiveSugarName", "additiveSugarGi", SUGAR_CATEGORY_SET, "additiveSugarUnit", "additiveSugarCategory");
    SoapTool.additives.attachAdditiveTypeahead("additiveSaltName", "additiveSaltGi", SALT_CATEGORY_SET, "additiveSaltUnit", "additiveSaltCategory");
    SoapTool.additives.attachAdditiveTypeahead("additiveCitricName", "additiveCitricGi", CITRIC_CATEGORY_SET, "additiveCitricUnit", "additiveCitricCategory");
    SoapTool.ui.applyHelperVisibility();
    SoapTool.quality.initQualityTooltips();
    SoapTool.runner.applyLyeSelection();
    SoapTool.runner.setWaterMethod();
    SoapTool.mold.updateMoldShapeUI();
    SoapTool.quality.setQualityRangeBars();
    SoapTool.units.updateUnitLabels();
    SoapTool.quality.updateQualityTargets();
    SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
    SoapTool.stages.updateStageStatuses();
    SoapTool.storage.restoreState();
    if (oilRows && !oilRows.querySelector(".oil-row")) {
      oilRows.appendChild(SoapTool.oils.buildOilRow());
    }
    if (fragranceRows && !fragranceRows.querySelector(".fragrance-row")) {
      if ((_a = SoapTool.fragrances) == null ? void 0 : _a.buildFragranceRow) {
        fragranceRows.appendChild(SoapTool.fragrances.buildFragranceRow());
      }
    }
    if ((_b = SoapTool.fragrances) == null ? void 0 : _b.updateFragranceTotals) {
      SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
    }
    SoapTool.layout.scheduleStageHeightSync();
  })(window);
})();
//# sourceMappingURL=soap_tool_bundle.js.map
