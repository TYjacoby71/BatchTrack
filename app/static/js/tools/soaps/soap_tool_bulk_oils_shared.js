(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const bulk = SoapTool.bulkOils = SoapTool.bulkOils || {};
  const { toNumber, clamp } = SoapTool.helpers;
  const state = SoapTool.state;

  const FATTY_KEYS = Array.isArray(SoapTool.constants?.FATTY_DISPLAY_KEYS)
    ? SoapTool.constants.FATTY_DISPLAY_KEYS.slice()
    : ['lauric', 'myristic', 'palmitic', 'stearic', 'ricinoleic', 'oleic', 'linoleic', 'linolenic'];
  const LOCAL_SORT_KEYS = new Set(['selected_pct', 'selected_weight_g']);
  const PAGE_SIZE = 25;
  const SCROLL_FETCH_THRESHOLD = 140;
  const SEARCH_DEBOUNCE_MS = 260;
  const DEFAULT_MODAL_STATE = {
    mode: 'basics',
    viewSelected: false,
    query: '',
    sortKey: 'name',
    sortDir: 'asc',
    selection: {},
    recordByKey: {},
    visibleRecords: [],
    offset: 0,
    totalCount: 0,
    hasMore: true,
    loading: false,
    requestToken: 0,
  };

  function queueStateSave(){
    SoapTool.storage?.queueStateSave?.();
  }

  function showAlert(level, message){
    SoapTool.ui?.showSoapAlert?.(level, message, { dismissible: true, timeoutMs: 6000 });
  }

  function getRefs(){
    return {
      modalEl: document.getElementById('bulkOilModal'),
      openBtn: document.getElementById('openBulkOilModal'),
      searchInput: document.getElementById('bulkOilSearchInput'),
      modeToggle: document.getElementById('bulkOilDisplayAllToggle'),
      viewSelectedToggle: document.getElementById('bulkOilViewSelectedToggle'),
      statusEl: document.getElementById('bulkOilCatalogStatus'),
      summaryEl: document.getElementById('bulkOilSelectedSummary'),
      stageCountEl: document.getElementById('bulkOilSelectionCount'),
      bodyEl: document.getElementById('bulkOilCatalogBody'),
      scrollEl: document.getElementById('bulkOilCatalogScroll'),
      importBtn: document.getElementById('bulkOilImportBtn'),
      clearBtn: document.getElementById('bulkOilClearSelectionBtn'),
      unitLabelEl: document.getElementById('bulkOilWeightUnitLabel'),
    };
  }

  function isSupportedSortKey(sortKey){
    if (!sortKey) return false;
    if (sortKey === 'name') return true;
    if (LOCAL_SORT_KEYS.has(sortKey)) return true;
    return FATTY_KEYS.includes(sortKey);
  }

  function ensureModalState(){
    if (!state.bulkOilModal || typeof state.bulkOilModal !== 'object') {
      state.bulkOilModal = JSON.parse(JSON.stringify(DEFAULT_MODAL_STATE));
    }
    const modalState = state.bulkOilModal;
    modalState.mode = modalState.mode === 'all' ? 'all' : 'basics';
    modalState.viewSelected = !!modalState.viewSelected;
    modalState.query = typeof modalState.query === 'string' ? modalState.query : '';
    modalState.sortKey = isSupportedSortKey(modalState.sortKey) ? modalState.sortKey : 'name';
    modalState.sortDir = modalState.sortDir === 'desc' ? 'desc' : 'asc';
    modalState.selection = modalState.selection && typeof modalState.selection === 'object' ? modalState.selection : {};
    modalState.recordByKey = modalState.recordByKey && typeof modalState.recordByKey === 'object' ? modalState.recordByKey : {};
    modalState.visibleRecords = Array.isArray(modalState.visibleRecords) ? modalState.visibleRecords : [];
    modalState.offset = Math.max(0, parseInt(modalState.offset, 10) || 0);
    modalState.totalCount = Math.max(0, parseInt(modalState.totalCount, 10) || 0);
    modalState.hasMore = modalState.hasMore !== false;
    modalState.loading = !!modalState.loading;
    modalState.requestToken = Math.max(0, parseInt(modalState.requestToken, 10) || 0);
    return modalState;
  }

  function normalizeFattyProfile(rawProfile){
    const profile = {};
    const input = rawProfile && typeof rawProfile === 'object' ? rawProfile : {};
    FATTY_KEYS.forEach(key => {
      const value = toNumber(input[key]);
      if (value > 0) {
        profile[key] = value;
      }
    });
    return profile;
  }

  function normalizeCatalogRecord(raw){
    const fattyProfile = normalizeFattyProfile(raw?.fatty_profile);
    const name = String(raw?.name || '').trim();
    const source = String(raw?.source || 'soapcalc').trim().toLowerCase() || 'soapcalc';
    const globalItemId = Number.isInteger(raw?.global_item_id)
      ? raw.global_item_id
      : (toNumber(raw?.global_item_id) > 0 ? parseInt(raw.global_item_id, 10) : null);
    const key = String(raw?.key || (globalItemId ? `global:${globalItemId}` : `${source}:${name.toLowerCase()}`));
    return {
      key,
      name,
      sap_koh: toNumber(raw?.sap_koh),
      iodine: toNumber(raw?.iodine),
      fatty_profile: fattyProfile,
      default_unit: String(raw?.default_unit || 'gram'),
      ingredient_category_name: String(raw?.ingredient_category_name || 'Oils (Carrier & Fixed)'),
      global_item_id: globalItemId,
      source,
      is_basic: !!raw?.is_basic,
    };
  }

  function updateSelectionCounters(){
    const refs = getRefs();
    const modalState = ensureModalState();
    const count = Object.keys(modalState.selection || {}).length;
    const summary = `Selected: ${count}`;
    if (refs.summaryEl) refs.summaryEl.textContent = summary;
    if (refs.stageCountEl) refs.stageCountEl.textContent = String(count);
  }

  function selectionForRecordKey(recordKey){
    const modalState = ensureModalState();
    return modalState.selection?.[recordKey] || null;
  }

  function setSelection(record, values = {}){
    const modalState = ensureModalState();
    if (!record || !record.key) return null;
    const existing = modalState.selection[record.key] || {};
    const next = {
      key: record.key,
      name: record.name,
      sap_koh: record.sap_koh,
      iodine: record.iodine,
      fatty_profile: record.fatty_profile || {},
      default_unit: record.default_unit || 'gram',
      ingredient_category_name: record.ingredient_category_name || '',
      global_item_id: record.global_item_id || null,
      source: record.source || 'soapcalc',
      is_basic: !!record.is_basic,
      selected_pct: clamp(toNumber(values.selected_pct ?? existing.selected_pct), 0, 100),
      selected_weight_g: clamp(toNumber(values.selected_weight_g ?? existing.selected_weight_g), 0),
    };
    modalState.selection[record.key] = next;
    return next;
  }

  function removeSelection(recordKey){
    const modalState = ensureModalState();
    if (modalState.selection?.[recordKey]) {
      delete modalState.selection[recordKey];
    }
  }

  function getRecordByKey(recordKey){
    const modalState = ensureModalState();
    return modalState.recordByKey?.[recordKey] || null;
  }

  function serializeSelection(){
    const modalState = ensureModalState();
    return {
      mode: modalState.mode,
      view_selected: !!modalState.viewSelected,
      query: modalState.query,
      sort_key: modalState.sortKey,
      sort_dir: modalState.sortDir,
      selections: Object.values(modalState.selection || {}).map(item => ({
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
        selected_weight_g: clamp(toNumber(item.selected_weight_g), 0),
      })),
    };
  }

  function restoreState(savedState){
    const modalState = ensureModalState();
    modalState.mode = savedState?.mode === 'all' ? 'all' : 'basics';
    modalState.viewSelected = !!savedState?.view_selected;
    modalState.query = typeof savedState?.query === 'string' ? savedState.query : '';
    modalState.sortKey = isSupportedSortKey(savedState?.sort_key) ? savedState.sort_key : 'name';
    modalState.sortDir = savedState?.sort_dir === 'desc' ? 'desc' : 'asc';
    const selection = {};
    const rows = Array.isArray(savedState?.selections) ? savedState.selections : [];
    rows.forEach(raw => {
      const key = String(raw?.key || '').trim();
      const name = String(raw?.name || '').trim();
      if (!key || !name) return;
      selection[key] = {
        key,
        name,
        sap_koh: toNumber(raw?.sap_koh),
        iodine: toNumber(raw?.iodine),
        fatty_profile: normalizeFattyProfile(raw?.fatty_profile),
        default_unit: String(raw?.default_unit || 'gram'),
        ingredient_category_name: String(raw?.ingredient_category_name || ''),
        global_item_id: toNumber(raw?.global_item_id) > 0 ? parseInt(raw.global_item_id, 10) : null,
        source: String(raw?.source || 'soapcalc'),
        is_basic: !!raw?.is_basic,
        selected_pct: clamp(toNumber(raw?.selected_pct), 0, 100),
        selected_weight_g: clamp(toNumber(raw?.selected_weight_g), 0),
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
    restoreState,
  };
})(window);
