(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { toGrams, fromGrams } = SoapTool.units;
  const state = SoapTool.state;
  const FATTY_KEYS = Array.isArray(SoapTool.constants?.FATTY_DISPLAY_KEYS)
    ? SoapTool.constants.FATTY_DISPLAY_KEYS.slice()
    : ['lauric', 'myristic', 'palmitic', 'stearic', 'ricinoleic', 'oleic', 'linoleic', 'linolenic'];
  const LAZY_CHUNK_SIZE = 35;
  const DEFAULT_MODAL_STATE = {
    mode: 'basics',
    query: '',
    sortKey: 'name',
    sortDir: 'asc',
    selection: {},
    catalog: {
      basics: null,
      all: null,
    },
    recordByKey: {},
    filteredRecords: [],
    renderedCount: 0,
  };
  let modalInstance = null;

  function ensureModalState(){
    if (!state.bulkOilModal) {
      state.bulkOilModal = JSON.parse(JSON.stringify(DEFAULT_MODAL_STATE));
    }
    const modalState = state.bulkOilModal;
    modalState.selection = modalState.selection || {};
    modalState.catalog = modalState.catalog || { basics: null, all: null };
    modalState.recordByKey = modalState.recordByKey || {};
    modalState.filteredRecords = modalState.filteredRecords || [];
    modalState.renderedCount = toNumber(modalState.renderedCount) || 0;
    modalState.mode = modalState.mode === 'all' ? 'all' : 'basics';
    modalState.sortKey = modalState.sortKey || 'name';
    modalState.sortDir = modalState.sortDir === 'desc' ? 'desc' : 'asc';
    modalState.query = typeof modalState.query === 'string' ? modalState.query : '';
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
    const aliases = Array.isArray(raw?.aliases) ? raw.aliases.filter(Boolean).map(value => String(value)) : [];
    const name = String(raw?.name || '').trim();
    const source = String(raw?.source || 'soapcalc').trim().toLowerCase() || 'soapcalc';
    const globalItemId = Number.isInteger(raw?.global_item_id) ? raw.global_item_id : (toNumber(raw?.global_item_id) > 0 ? parseInt(raw.global_item_id, 10) : null);
    const key = String(raw?.key || (globalItemId ? `global:${globalItemId}` : `${source}:${name.toLowerCase()}`));
    return {
      key,
      name,
      aliases,
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

  function sortButtonsLabel(){
    document.querySelectorAll('.bulk-oil-sort').forEach(button => {
      const modalState = ensureModalState();
      const label = button.dataset.label || button.textContent || '';
      const key = button.dataset.sortKey || '';
      if (modalState.sortKey === key) {
        button.textContent = `${label} ${modalState.sortDir === 'asc' ? '▲' : '▼'}`;
      } else {
        button.textContent = label;
      }
    });
  }

  function updateSelectionCounters(){
    const refs = getRefs();
    const modalState = ensureModalState();
    const count = Object.keys(modalState.selection || {}).length;
    const summary = `Selected: ${count}`;
    if (refs.summaryEl) refs.summaryEl.textContent = summary;
    if (refs.stageCountEl) refs.stageCountEl.textContent = String(count);
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

  function getSortValue(record, sortKey){
    if (sortKey === 'name') return record.name || '';
    if (sortKey === 'selected_pct') return selectionForRecordKey(record.key)?.selected_pct || 0;
    if (sortKey === 'selected_weight_g') return selectionForRecordKey(record.key)?.selected_weight_g || 0;
    if (FATTY_KEYS.includes(sortKey)) return toNumber(record.fatty_profile?.[sortKey]);
    return '';
  }

  function getFilteredSortedRecords(){
    const modalState = ensureModalState();
    const baseRecords = modalState.catalog?.[modalState.mode] || [];
    const query = (modalState.query || '').trim().toLowerCase();
    const filtered = query
      ? baseRecords.filter(record => {
          const nameBlob = `${record.name} ${(record.aliases || []).join(' ')} ${record.ingredient_category_name || ''}`.toLowerCase();
          return nameBlob.includes(query);
        })
      : baseRecords.slice();
    filtered.sort((left, right) => {
      const primary = compareValues(
        getSortValue(left, modalState.sortKey),
        getSortValue(right, modalState.sortKey),
        modalState.sortDir
      );
      if (primary !== 0) return primary;
      return compareValues(left.name || '', right.name || '', 'asc');
    });
    return filtered;
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
    const category = record.ingredient_category_name ? ` · ${record.ingredient_category_name}` : '';
    nameCell.innerHTML = `<div class="fw-semibold small">${record.name}</div><div class="text-muted small">${record.source}${category}</div>`;
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

  function refreshCatalogStatus(){
    const modalState = ensureModalState();
    const modeLabel = modalState.mode === 'all' ? 'all oils' : 'SoapCalc basics';
    updateStatusText(`Showing ${modalState.renderedCount}/${modalState.filteredRecords.length} in ${modeLabel}`);
  }

  function appendLazyRows(){
    const modalState = ensureModalState();
    const refs = getRefs();
    if (!refs.bodyEl) return;
    if (modalState.renderedCount >= modalState.filteredRecords.length) {
      refreshCatalogStatus();
      return;
    }
    const fragment = document.createDocumentFragment();
    const nextSlice = modalState.filteredRecords.slice(
      modalState.renderedCount,
      modalState.renderedCount + LAZY_CHUNK_SIZE
    );
    nextSlice.forEach(record => {
      fragment.appendChild(createRow(record));
    });
    refs.bodyEl.appendChild(fragment);
    modalState.renderedCount += nextSlice.length;
    refreshCatalogStatus();
  }

  function renderCatalog(reset = true){
    const modalState = ensureModalState();
    const refs = getRefs();
    if (!refs.bodyEl) return;
    modalState.filteredRecords = getFilteredSortedRecords();
    if (reset) {
      modalState.renderedCount = 0;
      refs.bodyEl.innerHTML = '';
      appendLazyRows();
    } else {
      const rows = Array.from(refs.bodyEl.querySelectorAll('tr[data-record-key]'));
      rows.forEach(row => {
        const record = getRecordByKey(row.dataset.recordKey || '');
        if (record) {
          updateRowFromSelection(row, record);
        }
      });
      refreshCatalogStatus();
    }
    sortButtonsLabel();
    updateSelectionCounters();
  }

  async function fetchCatalog(mode){
    const modalState = ensureModalState();
    updateStatusText('Loading catalog...');
    const response = await fetch(`/tools/api/soap/oils-catalog?mode=${encodeURIComponent(mode)}`);
    if (!response.ok) {
      throw new Error('Unable to load oils catalog');
    }
    const payload = await response.json();
    if (!payload || payload.success !== true || !payload.result || !Array.isArray(payload.result.records)) {
      throw new Error('Invalid oils catalog response');
    }
    const normalized = payload.result.records.map(normalizeCatalogRecord);
    modalState.catalog[mode] = normalized;
    normalized.forEach(record => {
      modalState.recordByKey[record.key] = record;
    });
  }

  async function ensureCatalogLoaded(mode){
    const modalState = ensureModalState();
    if (Array.isArray(modalState.catalog?.[mode])) {
      return;
    }
    await fetchCatalog(mode);
  }

  function importSelectedToStage(){
    const modalState = ensureModalState();
    const selectionEntries = Object.values(modalState.selection || {});
    if (!selectionEntries.length) {
      SoapTool.ui.showSoapAlert('warning', 'Pick at least one oil before importing.', { dismissible: true, timeoutMs: 6000 });
      return;
    }
    const oilRows = document.getElementById('oilRows');
    if (!oilRows) return;

    const ordered = selectionEntries.slice().sort((left, right) => String(left.name || '').localeCompare(String(right.name || '')));
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
      if (gramsInput) {
        gramsInput.value = item.selected_weight_g > 0 ? round(fromGrams(item.selected_weight_g), 2) : '';
      }

      oilRows.appendChild(row);
    });

    SoapTool.oils.updateOilTotals();
    SoapTool.stages.updateStageStatuses();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
    SoapTool.ui.showSoapAlert(
      'info',
      `Imported ${selectionEntries.length} oil${selectionEntries.length === 1 ? '' : 's'} from bulk picker.`,
      { dismissible: true, timeoutMs: 6000 }
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

    try {
      await ensureCatalogLoaded(modalState.mode);
      renderCatalog(true);
      if (modalInstance) {
        modalInstance.show();
      }
    } catch (_) {
      updateStatusText('Unable to load oils catalog.');
      SoapTool.ui.showSoapAlert('danger', 'Unable to load bulk oils catalog right now.', { dismissible: true, timeoutMs: 6000 });
    }
  }

  async function handleModeToggle(checked){
    const modalState = ensureModalState();
    modalState.mode = checked ? 'all' : 'basics';
    try {
      await ensureCatalogLoaded(modalState.mode);
      renderCatalog(true);
    } catch (_) {
      updateStatusText('Unable to load oils catalog.');
    }
    SoapTool.storage.queueStateSave();
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

    updateSelectionCounters();
    SoapTool.storage.queueStateSave();
  }

  function handleSortClick(event){
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
    renderCatalog(true);
    SoapTool.storage.queueStateSave();
  }

  function clearSelection(){
    const modalState = ensureModalState();
    modalState.selection = {};
    renderCatalog(false);
    SoapTool.storage.queueStateSave();
  }

  function handleScroll(){
    const refs = getRefs();
    if (!refs.scrollEl) return;
    const threshold = 120;
    const atBottom = refs.scrollEl.scrollTop + refs.scrollEl.clientHeight >= refs.scrollEl.scrollHeight - threshold;
    if (atBottom) {
      appendLazyRows();
    }
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
    if (!savedState || typeof savedState !== 'object') {
      updateSelectionCounters();
      return;
    }
    const modalState = ensureModalState();
    modalState.mode = savedState.mode === 'all' ? 'all' : 'basics';
    modalState.query = typeof savedState.query === 'string' ? savedState.query : '';
    modalState.sortKey = typeof savedState.sort_key === 'string' ? savedState.sort_key : 'name';
    modalState.sortDir = savedState.sort_dir === 'desc' ? 'desc' : 'asc';
    const selection = {};
    const rows = Array.isArray(savedState.selections) ? savedState.selections : [];
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
    updateSelectionCounters();
  }

  function onUnitChanged(){
    const refs = getRefs();
    if (refs.unitLabelEl) refs.unitLabelEl.textContent = state.currentUnit || 'g';
    if (refs.modalEl && refs.modalEl.classList.contains('show')) {
      renderCatalog(false);
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
        renderCatalog(true);
        SoapTool.storage.queueStateSave();
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
      if (localRefs.searchInput) {
        localRefs.searchInput.focus();
      }
    });
  }

  bindEvents();
  updateSelectionCounters();

  SoapTool.bulkOilsModal = {
    openModal,
    serializeSelection,
    restoreState,
    onUnitChanged,
  };
})(window);
