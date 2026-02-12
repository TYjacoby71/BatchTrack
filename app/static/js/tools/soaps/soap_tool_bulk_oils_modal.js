(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { toGrams, fromGrams } = SoapTool.units;
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
  let modalInstance = null;
  let searchDebounceTimer = null;

  function queueStateSave(){
    SoapTool.storage?.queueStateSave?.();
  }

  function showAlert(level, message){
    SoapTool.ui?.showSoapAlert?.(level, message, { dismissible: true, timeoutMs: 6000 });
  }

  function ensureModalState(){
    if (!state.bulkOilModal || typeof state.bulkOilModal !== 'object') {
      state.bulkOilModal = JSON.parse(JSON.stringify(DEFAULT_MODAL_STATE));
    }
    const modalState = state.bulkOilModal;
    modalState.mode = modalState.mode === 'all' ? 'all' : 'basics';
    modalState.query = typeof modalState.query === 'string' ? modalState.query : '';
    modalState.sortKey = typeof modalState.sortKey === 'string' ? modalState.sortKey : 'name';
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

  function getRefs(){
    return {
      modalEl: document.getElementById('bulkOilModal'),
      openBtn: document.getElementById('openBulkOilModal'),
      searchInput: document.getElementById('bulkOilSearchInput'),
      modeToggle: document.getElementById('bulkOilDisplayAllToggle'),
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

  function updateStatusText(text){
    const refs = getRefs();
    if (refs.statusEl) refs.statusEl.textContent = text;
  }

  function updateSelectionCounters(){
    const refs = getRefs();
    const modalState = ensureModalState();
    const count = Object.keys(modalState.selection || {}).length;
    const summary = `Selected: ${count}`;
    if (refs.summaryEl) refs.summaryEl.textContent = summary;
    if (refs.stageCountEl) refs.stageCountEl.textContent = String(count);
  }

  function refreshCatalogStatus(){
    const modalState = ensureModalState();
    const modeLabel = modalState.mode === 'all' ? 'all oils' : 'SoapCalc basics';
    if (modalState.loading && !modalState.visibleRecords.length) {
      updateStatusText('Loading oils...');
      return;
    }
    if (!modalState.visibleRecords.length) {
      const noMatchLabel = modalState.query ? 'No oils match that search.' : 'No oils available.';
      updateStatusText(noMatchLabel);
      return;
    }
    const loaded = modalState.visibleRecords.length;
    const total = modalState.totalCount;
    const moreHint = modalState.hasMore ? ' • scroll for more' : '';
    const queryHint = modalState.query ? ` • search: "${modalState.query}"` : '';
    updateStatusText(`Loaded ${loaded}/${total} in ${modeLabel}${queryHint}${moreHint}`);
  }

  function compareValues(aValue, bValue, dir){
    if (typeof aValue === 'string' || typeof bValue === 'string') {
      const left = String(aValue || '').toLowerCase();
      const right = String(bValue || '').toLowerCase();
      if (left < right) return dir === 'asc' ? -1 : 1;
      if (left > right) return dir === 'asc' ? 1 : -1;
      return 0;
    }
    const aNum = toNumber(aValue);
    const bNum = toNumber(bValue);
    if (aNum < bNum) return dir === 'asc' ? -1 : 1;
    if (aNum > bNum) return dir === 'asc' ? 1 : -1;
    return 0;
  }

  function selectionForRecordKey(recordKey){
    const modalState = ensureModalState();
    return modalState.selection?.[recordKey] || null;
  }

  function localSortValue(record, sortKey){
    if (sortKey === 'selected_pct') return selectionForRecordKey(record.key)?.selected_pct || 0;
    if (sortKey === 'selected_weight_g') return selectionForRecordKey(record.key)?.selected_weight_g || 0;
    return '';
  }

  function applyLocalSelectionSortIfNeeded(){
    const modalState = ensureModalState();
    if (!LOCAL_SORT_KEYS.has(modalState.sortKey)) return;
    modalState.visibleRecords.sort((left, right) => {
      const primary = compareValues(
        localSortValue(left, modalState.sortKey),
        localSortValue(right, modalState.sortKey),
        modalState.sortDir
      );
      if (primary !== 0) return primary;
      return compareValues(left.name || '', right.name || '', 'asc');
    });
  }

  function normalizeServerSortKey(sortKey){
    const key = String(sortKey || '').trim().toLowerCase();
    if (key === 'name') return key;
    if (FATTY_KEYS.includes(key)) return key;
    return 'name';
  }

  function sortButtonsLabel(){
    const modalState = ensureModalState();
    document.querySelectorAll('.bulk-oil-sort').forEach(button => {
      if (!button.dataset.label) {
        button.dataset.label = String(button.textContent || '').replace(/[▲▼]\s*$/, '').trim();
      }
      const label = button.dataset.label || '';
      const key = button.dataset.sortKey || '';
      if (modalState.sortKey === key) {
        button.textContent = `${label} ${modalState.sortDir === 'asc' ? '▲' : '▼'}`;
      } else {
        button.textContent = label;
      }
    });
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

  function updateRowFromSelection(row, record){
    const selection = selectionForRecordKey(record.key);
    const checkbox = row.querySelector('.bulk-oil-check');
    const pctInput = row.querySelector('.bulk-oil-pct');
    const weightInput = row.querySelector('.bulk-oil-weight');
    if (checkbox) checkbox.checked = !!selection;
    if (pctInput) pctInput.value = selection && selection.selected_pct > 0 ? round(selection.selected_pct, 2) : '';
    if (weightInput) {
      weightInput.value = selection && selection.selected_weight_g > 0
        ? round(fromGrams(selection.selected_weight_g), 2)
        : '';
    }
  }

  function createFattyCell(value){
    const cell = document.createElement('td');
    cell.className = 'bulk-oil-acid';
    const numeric = toNumber(value);
    cell.textContent = numeric > 0 ? round(numeric, 1).toString() : '--';
    return cell;
  }

  function createRow(record){
    const row = document.createElement('tr');
    row.dataset.recordKey = record.key;

    const pickCell = document.createElement('td');
    pickCell.className = 'text-center';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'form-check-input bulk-oil-check';
    pickCell.appendChild(checkbox);
    row.appendChild(pickCell);

    const nameCell = document.createElement('td');
    nameCell.className = 'bulk-oil-name';
    const title = document.createElement('div');
    title.className = 'fw-semibold small';
    title.textContent = record.name;
    const detail = document.createElement('div');
    detail.className = 'text-muted small';
    const category = record.ingredient_category_name ? ` · ${record.ingredient_category_name}` : '';
    detail.textContent = `${record.source}${category}`;
    nameCell.appendChild(title);
    nameCell.appendChild(detail);
    row.appendChild(nameCell);

    FATTY_KEYS.forEach(key => {
      row.appendChild(createFattyCell(record.fatty_profile?.[key]));
    });

    const pctCell = document.createElement('td');
    const pctInput = document.createElement('input');
    pctInput.type = 'number';
    pctInput.min = '0';
    pctInput.max = '100';
    pctInput.step = '0.1';
    pctInput.className = 'form-control form-control-sm bulk-oil-input bulk-oil-pct';
    pctCell.appendChild(pctInput);
    row.appendChild(pctCell);

    const weightCell = document.createElement('td');
    const weightInput = document.createElement('input');
    weightInput.type = 'number';
    weightInput.min = '0';
    weightInput.step = '0.1';
    weightInput.className = 'form-control form-control-sm bulk-oil-input bulk-oil-weight';
    weightCell.appendChild(weightInput);
    row.appendChild(weightCell);

    updateRowFromSelection(row, record);
    return row;
  }

  function renderVisibleRecords(){
    const refs = getRefs();
    const modalState = ensureModalState();
    if (!refs.bodyEl) return;
    refs.bodyEl.innerHTML = '';
    const fragment = document.createDocumentFragment();
    modalState.visibleRecords.forEach(record => {
      fragment.appendChild(createRow(record));
    });
    refs.bodyEl.appendChild(fragment);
    sortButtonsLabel();
    updateSelectionCounters();
    refreshCatalogStatus();
  }

  function resetVisibleCatalogForFetch(){
    const modalState = ensureModalState();
    const refs = getRefs();
    modalState.visibleRecords = [];
    modalState.offset = 0;
    modalState.totalCount = 0;
    modalState.hasMore = true;
    if (refs.bodyEl) refs.bodyEl.innerHTML = '';
    if (refs.scrollEl) refs.scrollEl.scrollTop = 0;
  }

  async function fetchCatalogPage({ reset = false } = {}){
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
    params.set('mode', modalState.mode);
    params.set('offset', String(modalState.offset));
    params.set('limit', String(PAGE_SIZE));
    params.set('q', modalState.query || '');
    params.set('sort_key', normalizeServerSortKey(modalState.sortKey));
    params.set('sort_dir', modalState.sortDir === 'desc' ? 'desc' : 'asc');

    try {
      const response = await fetch(`/tools/api/soap/oils-catalog?${params.toString()}`);
      if (!response.ok) {
        throw new Error('Unable to load oils catalog');
      }
      const payload = await response.json();
      if (!payload || payload.success !== true || !payload.result || !Array.isArray(payload.result.records)) {
        throw new Error('Invalid oils catalog response');
      }
      if (requestToken !== modalState.requestToken) {
        return;
      }
      const records = payload.result.records.map(normalizeCatalogRecord);
      const nextOffset = Math.max(0, parseInt(payload.result.next_offset, 10) || (modalState.offset + records.length));
      const totalCount = Math.max(records.length, parseInt(payload.result.count, 10) || 0);
      const hasMore = !!payload.result.has_more;

      records.forEach(record => {
        modalState.recordByKey[record.key] = record;
      });
      modalState.visibleRecords = reset
        ? records.slice()
        : modalState.visibleRecords.concat(records);
      modalState.offset = nextOffset;
      modalState.totalCount = totalCount;
      modalState.hasMore = hasMore;
      applyLocalSelectionSortIfNeeded();
      renderVisibleRecords();
    } catch (_) {
      if (requestToken === modalState.requestToken) {
        updateStatusText('Unable to load oils catalog.');
      }
      throw _;
    } finally {
      if (requestToken === modalState.requestToken) {
        modalState.loading = false;
        refreshCatalogStatus();
      }
    }
  }

  function importSelectedToStage(){
    const modalState = ensureModalState();
    const selectionEntries = Object.values(modalState.selection || {});
    if (!selectionEntries.length) {
      showAlert('warning', 'Pick at least one oil before importing.');
      return;
    }
    const oilRows = document.getElementById('oilRows');
    if (!oilRows) return;

    const ordered = selectionEntries
      .slice()
      .sort((left, right) => String(left.name || '').localeCompare(String(right.name || '')));
    ordered.forEach(item => {
      const row = SoapTool.oils.buildOilRow();
      if (!row) return;
      const nameInput = row.querySelector('.oil-typeahead');
      const sapInput = row.querySelector('.oil-sap-koh');
      const iodineInput = row.querySelector('.oil-iodine');
      const fattyInput = row.querySelector('.oil-fatty');
      const giInput = row.querySelector('.oil-gi-id');
      const unitInput = row.querySelector('.oil-default-unit');
      const categoryInput = row.querySelector('.oil-category');
      const gramsInput = row.querySelector('.oil-grams');
      const percentInput = row.querySelector('.oil-percent');

      if (nameInput) nameInput.value = item.name || '';
      if (sapInput) sapInput.value = item.sap_koh > 0 ? round(item.sap_koh, 3) : '';
      if (iodineInput) iodineInput.value = item.iodine > 0 ? round(item.iodine, 3) : '';
      if (fattyInput) fattyInput.value = item.fatty_profile && Object.keys(item.fatty_profile).length ? JSON.stringify(item.fatty_profile) : '';
      if (giInput) giInput.value = item.global_item_id || '';
      if (unitInput) unitInput.value = item.default_unit || '';
      if (categoryInput) categoryInput.value = item.ingredient_category_name || '';
      if (percentInput) percentInput.value = item.selected_pct > 0 ? round(item.selected_pct, 2) : '';
      if (gramsInput) gramsInput.value = item.selected_weight_g > 0 ? round(fromGrams(item.selected_weight_g), 2) : '';
      oilRows.appendChild(row);
    });

    SoapTool.oils.updateOilTotals();
    SoapTool.stages.updateStageStatuses();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
    showAlert(
      'info',
      `Imported ${selectionEntries.length} oil${selectionEntries.length === 1 ? '' : 's'} from bulk picker.`
    );
  }

  async function openModal(){
    const refs = getRefs();
    const modalState = ensureModalState();
    if (!refs.modalEl) return;
    if (!modalInstance && window.bootstrap?.Modal) {
      modalInstance = window.bootstrap.Modal.getOrCreateInstance(refs.modalEl);
    }
    if (refs.searchInput) refs.searchInput.value = modalState.query || '';
    if (refs.modeToggle) refs.modeToggle.checked = modalState.mode === 'all';
    if (refs.unitLabelEl) refs.unitLabelEl.textContent = state.currentUnit || 'g';
    if (modalInstance) modalInstance.show();
    sortButtonsLabel();
    updateSelectionCounters();
    try {
      await fetchCatalogPage({ reset: true });
    } catch (_) {
      showAlert('danger', 'Unable to load bulk oils catalog right now.');
    }
  }

  function handleBodyInput(event){
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const row = target.closest('tr[data-record-key]');
    if (!row) return;
    const recordKey = row.dataset.recordKey || '';
    const record = getRecordByKey(recordKey);
    if (!record) return;

    const checkbox = row.querySelector('.bulk-oil-check');
    const pctInput = row.querySelector('.bulk-oil-pct');
    const weightInput = row.querySelector('.bulk-oil-weight');
    const pct = clamp(toNumber(pctInput?.value), 0, 100);
    const selectedWeightG = clamp(toGrams(weightInput?.value), 0);
    const hasValues = pct > 0 || selectedWeightG > 0;
    const isChecked = !!checkbox?.checked;

    if (isChecked || hasValues) {
      if (checkbox) checkbox.checked = true;
      setSelection(record, {
        selected_pct: pct,
        selected_weight_g: selectedWeightG,
      });
    } else {
      removeSelection(recordKey);
    }

    if (LOCAL_SORT_KEYS.has(ensureModalState().sortKey)) {
      applyLocalSelectionSortIfNeeded();
      renderVisibleRecords();
    } else {
      updateSelectionCounters();
    }
    queueStateSave();
  }

  async function handleModeToggle(checked){
    const modalState = ensureModalState();
    modalState.mode = checked ? 'all' : 'basics';
    queueStateSave();
    try {
      await fetchCatalogPage({ reset: true });
    } catch (_) {
      showAlert('danger', 'Unable to load bulk oils catalog right now.');
    }
  }

  async function handleSortClick(event){
    const button = event.target instanceof HTMLElement ? event.target.closest('.bulk-oil-sort') : null;
    if (!button) return;
    const sortKey = button.getAttribute('data-sort-key') || 'name';
    const modalState = ensureModalState();
    if (modalState.sortKey === sortKey) {
      modalState.sortDir = modalState.sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      modalState.sortKey = sortKey;
      modalState.sortDir = sortKey === 'name' ? 'asc' : 'desc';
    }
    queueStateSave();
    if (LOCAL_SORT_KEYS.has(modalState.sortKey)) {
      applyLocalSelectionSortIfNeeded();
      renderVisibleRecords();
      return;
    }
    try {
      await fetchCatalogPage({ reset: true });
    } catch (_) {
      showAlert('danger', 'Unable to load oils in that sort order.');
    }
  }

  function clearSelection(){
    const modalState = ensureModalState();
    modalState.selection = {};
    if (LOCAL_SORT_KEYS.has(modalState.sortKey)) {
      applyLocalSelectionSortIfNeeded();
      renderVisibleRecords();
    } else {
      renderVisibleRecords();
    }
    queueStateSave();
  }

  async function handleScroll(){
    const refs = getRefs();
    const modalState = ensureModalState();
    if (!refs.scrollEl) return;
    if (modalState.loading || !modalState.hasMore) return;
    const isNearBottom = refs.scrollEl.scrollTop + refs.scrollEl.clientHeight >= refs.scrollEl.scrollHeight - SCROLL_FETCH_THRESHOLD;
    if (!isNearBottom) return;
    try {
      await fetchCatalogPage({ reset: false });
    } catch (_) {
      showAlert('danger', 'Unable to load more oils right now.');
    }
  }

  function scheduleSearchReload(){
    if (searchDebounceTimer) window.clearTimeout(searchDebounceTimer);
    searchDebounceTimer = window.setTimeout(async () => {
      try {
        await fetchCatalogPage({ reset: true });
      } catch (_) {
        showAlert('danger', 'Unable to search oils right now.');
      }
    }, SEARCH_DEBOUNCE_MS);
  }

  function serializeSelection(){
    const modalState = ensureModalState();
    return {
      mode: modalState.mode,
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
    modalState.query = typeof savedState?.query === 'string' ? savedState.query : '';
    modalState.sortKey = typeof savedState?.sort_key === 'string' ? savedState.sort_key : 'name';
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
    sortButtonsLabel();
  }

  function onUnitChanged(){
    const refs = getRefs();
    if (refs.unitLabelEl) refs.unitLabelEl.textContent = state.currentUnit || 'g';
    if (refs.modalEl?.classList.contains('show')) {
      renderVisibleRecords();
    }
  }

  function bindEvents(){
    const refs = getRefs();
    if (!refs.modalEl) return;
    if (refs.openBtn) {
      refs.openBtn.addEventListener('click', () => {
        openModal();
      });
    }
    if (refs.searchInput) {
      refs.searchInput.addEventListener('input', () => {
        const modalState = ensureModalState();
        modalState.query = refs.searchInput.value || '';
        queueStateSave();
        scheduleSearchReload();
      });
    }
    if (refs.modeToggle) {
      refs.modeToggle.addEventListener('change', async () => {
        await handleModeToggle(!!refs.modeToggle.checked);
      });
    }
    if (refs.scrollEl) {
      refs.scrollEl.addEventListener('scroll', handleScroll);
    }
    if (refs.bodyEl) {
      refs.bodyEl.addEventListener('input', handleBodyInput);
      refs.bodyEl.addEventListener('change', handleBodyInput);
    }
    refs.modalEl.querySelectorAll('.bulk-oil-sort').forEach(button => {
      button.addEventListener('click', handleSortClick);
    });
    if (refs.importBtn) {
      refs.importBtn.addEventListener('click', () => {
        importSelectedToStage();
      });
    }
    if (refs.clearBtn) {
      refs.clearBtn.addEventListener('click', () => {
        clearSelection();
      });
    }
    refs.modalEl.addEventListener('shown.bs.modal', () => {
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
    onUnitChanged,
  };
})(window);
