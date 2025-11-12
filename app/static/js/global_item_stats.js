const defaultOptions = {
  offcanvasId: 'globalItemDetail',
  loadingId: 'giDetailLoading',
  contentId: 'giDetailContent',
  developerLinkId: 'giDevLink',
  storeLinkId: 'giStoreLink',
  nameId: 'giName',
  typeId: 'giType',
  ingredientNameId: 'giIngredientName',
  ingredientInciId: 'giInciName',
  ingredientCasId: 'giCasNumber',
  categoryId: 'giCategory',
  unitId: 'giUnit',
  densityId: 'giDensity',
  physicalFormId: 'giPhysicalForm',
  functionsId: 'giFunctions',
  applicationsId: 'giApplications',
  containerSectionId: 'giContainerMeta',
  containerMaterialId: 'giMaterial',
  containerTypeStyleId: 'giTypeStyle',
  containerColorId: 'giColor',
  ingredientSectionId: 'giIngredientStats',
  ingredientGridId: 'giPropsGrid',
  costStatsId: 'giCostStats',
  metaId: 'giMeta',
  developerLinkBase: null,
  storeLinkHref: null,
};

let globalOptions = { ...defaultOptions };

export function configureGlobalItemStats(options = {}) {
  globalOptions = { ...globalOptions, ...options };
}

function getElement(id) {
  return id ? document.getElementById(id) : null;
}

function setText(id, value) {
  const el = getElement(id);
  if (el) {
    el.textContent = value ?? '';
  }
}

function formatNumber(value, digits = 2) {
  return typeof value === 'number' && !Number.isNaN(value) ? value.toFixed(digits) : '-';
}

function formatText(value) {
  if (value === null || value === undefined) {
    return '–';
  }
  if (typeof value === 'string' && value.trim() === '') {
    return '–';
  }
  return value;
}

function formatList(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return '–';
  }
  return values.join(', ');
}

function showElement(el, show = true) {
  if (!el) return;
  el.style.display = show ? '' : 'none';
}

export async function openGlobalItemStats(globalItemId, options = {}) {
  const opts = { ...globalOptions, ...options };

  if (!globalItemId) {
    console.warn('openGlobalItemStats requires a global item id');
    return;
  }

  const offcanvasEl = getElement(opts.offcanvasId);
  const loadingEl = getElement(opts.loadingId);
  const contentEl = getElement(opts.contentId);

  if (!offcanvasEl || !loadingEl || !contentEl) {
    console.error('Global item stats drawer elements are missing');
    return;
  }

  if (typeof bootstrap === 'undefined' || !bootstrap.Offcanvas) {
    console.error('Bootstrap Offcanvas is required to open global item stats.');
    return;
  }

  showElement(loadingEl, true);
  loadingEl.innerHTML = `
    <div class="spinner-border" role="status">
      <span class="visually-hidden">Loading...</span>
    </div>
    <p class="mt-2 mb-0">Loading item details...</p>`;
  showElement(contentEl, false);

  const offcanvas = bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl);
  offcanvas.show();

  let payload;
  try {
    const response = await fetch(`/global-items/${globalItemId}/stats`, {
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      const bodyText = await response.text();
      throw new Error(`HTTP ${response.status}: ${bodyText.slice(0, 160)}`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      const preview = await response.text();
      throw new Error(`Unexpected response format. Preview: ${preview.slice(0, 160)}`);
    }

    payload = await response.json();
  } catch (err) {
    console.error('Failed to load global item stats', err);
    loadingEl.innerHTML = `<div class="alert alert-danger mb-0">Failed to load item details.<br><small>${err.message}</small></div>`;
    return;
  }

  if (!payload?.success) {
    const error = payload?.error || 'Unknown error';
    loadingEl.innerHTML = `<div class="alert alert-warning mb-0">${error}</div>`;
    return;
  }

  const item = payload.item || {};
  const categoryVisibility = payload.category_visibility || {};
  const cost = payload.cost || {};

  setText(opts.nameId, item.name || `#${globalItemId}`);
  setText(opts.typeId, item.item_type || '');
  const ingredientInfo = item.ingredient || {};
  setText(opts.ingredientNameId, formatText(ingredientInfo.name));
  setText(opts.ingredientInciId, formatText(ingredientInfo.inci_name || item.inci_name));
  setText(opts.ingredientCasId, formatText(ingredientInfo.cas_number));
  setText(opts.categoryId, item.ingredient_category_name || '');
  setText(opts.unitId, item.default_unit || '');
  setText(opts.densityId, item.density != null ? Number(item.density).toFixed(3) : '');
  setText(opts.physicalFormId, formatText(item.physical_form));
  setText(opts.functionsId, formatList(item.functions));
  setText(opts.applicationsId, formatList(item.applications));

  // Container metadata
  const isContainer = item.item_type === 'container' || item.item_type === 'packaging';
  const containerSection = getElement(opts.containerSectionId);
  showElement(containerSection, isContainer);
  if (isContainer) {
    setText(opts.containerMaterialId, item.container_material || '');
    const typeStyle = [item.container_type || '', item.container_style ? `(${item.container_style})` : '']
      .join(' ')
      .trim();
    setText(opts.containerTypeStyleId, typeStyle);
    setText(opts.containerColorId, item.container_color || '');
  }

  // Ingredient fields
  const isIngredient = item.item_type === 'ingredient';
  const ingredientSection = getElement(opts.ingredientSectionId);
  const ingredientGrid = getElement(opts.ingredientGridId);
  showElement(ingredientSection, isIngredient);
  if (isIngredient && ingredientGrid) {
    ingredientGrid.innerHTML = '';
    const addProp = (label, value, show) => {
      if (!show) return;
      const display = value == null || value === '' ? '-' : value;
      const col = document.createElement('div');
      col.innerHTML = `<div><strong>${label}:</strong> ${display}</div>`;
      ingredientGrid.appendChild(col);
    };

    addProp('Saponification', item.saponification_value, categoryVisibility.show_saponification_value);
    addProp('Iodine', item.iodine_value, categoryVisibility.show_iodine_value);
    addProp('Melting Point (°C)', item.melting_point_c, categoryVisibility.show_melting_point);
    addProp('Flash Point (°C)', item.flash_point_c, categoryVisibility.show_flash_point);
    addProp('pH', item.ph_value, categoryVisibility.show_ph_value);
    addProp('Moisture %', item.moisture_content_percent, categoryVisibility.show_moisture_content);
    addProp('Shelf Life (months)', item.shelf_life_months, categoryVisibility.show_shelf_life_months);
    addProp('Comedogenic', item.comedogenic_rating, categoryVisibility.show_comedogenic_rating);
  }

  // Cost summary
  const costStatsEl = getElement(opts.costStatsId);
  if (costStatsEl) {
    if (cost.count && cost.count > 0) {
      const mean = formatNumber(cost.mean_ex_outliers, 2);
      const low = formatNumber(cost.low, 2);
      const high = formatNumber(cost.high, 2);
      const minVal = formatNumber(cost.min, 2);
      const maxVal = formatNumber(cost.max, 2);
      costStatsEl.innerHTML = `Average: $${mean} (excluding outliers)<br>Low/High: $${low} – $${high}<br>Extremes: $${minVal} – $${maxVal} (n=${cost.count})`;
    } else {
      costStatsEl.textContent = 'No cost data yet.';
    }
  }

  const metaEl = getElement(opts.metaId);
  if (metaEl) {
    const aliases = formatList(item.aliases);
    const certifications = formatList(item.certifications);
    const usage = formatText(item.recommended_usage_rate);
    const fragrance = formatText(item.recommended_fragrance_load_pct);
    const shelfLifeDays = item.recommended_shelf_life_days;
    const shelfLifeDisplay = Number.isFinite(Number(shelfLifeDays))
      ? `${shelfLifeDays} day${Number(shelfLifeDays) === 1 ? '' : 's'}`
      : '–';
    metaEl.innerHTML = `
      <div><strong>Aliases:</strong> ${aliases}</div>
      <div><strong>Certifications:</strong> ${certifications}</div>
      <div><strong>Recommended Usage:</strong> ${usage}</div>
      <div><strong>Fragrance Load:</strong> ${fragrance}</div>
      <div><strong>Recommended Shelf Life:</strong> ${shelfLifeDisplay}</div>
    `;
  }

  // Developer link
  const devLink = getElement(opts.developerLinkId);
  if (devLink) {
    if (opts.developerLinkBase) {
      devLink.href = `${opts.developerLinkBase}${globalItemId}`;
      showElement(devLink, true);
    } else {
      showElement(devLink, false);
    }
  }

  // Store link (currently placeholder)
  const storeLink = getElement(opts.storeLinkId);
  if (storeLink) {
    if (opts.storeLinkHref) {
      storeLink.href = `${opts.storeLinkHref}${globalItemId}`;
      storeLink.classList.remove('disabled');
      storeLink.setAttribute('aria-disabled', 'false');
      storeLink.removeAttribute('tabindex');
      showElement(storeLink, true);
    } else {
      showElement(storeLink, false);
    }
  }

  showElement(loadingEl, false);
  showElement(contentEl, true);
}

export function bindGlobalItemStatTriggers(selector, options = {}) {
  if (!selector) return;
  const elements = document.querySelectorAll(selector);
  elements.forEach((el) => {
    el.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      const id = el.dataset.globalItemId || el.getAttribute('data-global-item-id');
      if (!id) {
        console.warn('Global item trigger missing data-global-item-id');
        return;
      }
      openGlobalItemStats(id, options);
    });
  });
}

// Convenience for inline handlers
if (typeof window !== 'undefined') {
  window.configureGlobalItemStats = configureGlobalItemStats;
  window.openGlobalItemStats = openGlobalItemStats;
  window.bindGlobalItemStatTriggers = bindGlobalItemStatTriggers;
}
