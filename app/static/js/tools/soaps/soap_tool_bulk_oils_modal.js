(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
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
    restoreState,
  } = shared;
  const {
    applyClientOrdering,
    sortButtonsLabel,
    renderVisibleRecords,
  } = render;
  const { fetchCatalogPage } = api;

  let modalInstance = null;
  let searchDebounceTimer = null;

  function closeModal(){
    const refs = getRefs();
    if (!refs.modalEl) return;
    if (!modalInstance && window.bootstrap?.Modal) {
      modalInstance = window.bootstrap.Modal.getOrCreateInstance(refs.modalEl);
    }
    if (modalInstance) modalInstance.hide();
  }

  function getStageRowsContainer(){
    return document.getElementById('oilRows');
  }

  function getStageRows(){
    return Array.from(document.querySelectorAll('#oilRows .oil-row'));
  }

  function normalizeName(value){
    return String(value || '').trim().toLowerCase();
  }

  function stageRowName(row){
    return normalizeName(row?.querySelector('.oil-typeahead')?.value);
  }

  function stageRowGi(row){
    const raw = String(row?.querySelector('.oil-gi-id')?.value || '').trim();
    return raw ? raw : '';
  }

  function stageRowByKey(recordKey, fallbackRecord){
    const normalizedKey = String(recordKey || '').trim();
    if (!normalizedKey) return null;
    const rows = getStageRows();
    let row = rows.find(entry => String(entry.dataset.bulkOilKey || '') === normalizedKey);
    if (row) return row;
    const gi = String(fallbackRecord?.global_item_id || '').trim();
    if (gi) {
      row = rows.find(entry => stageRowGi(entry) === gi);
      if (row) return row;
    }
    const name = normalizeName(fallbackRecord?.name);
    if (name) {
      row = rows.find(entry => stageRowName(entry) === name);
      if (row) return row;
    }
    return null;
  }

  function applySelectionToStageRow(row, item){
    if (!row || !item) return;
    row.dataset.bulkOilKey = item.key || '';
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
  }

  function upsertStageRowForSelection(item){
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

  function removeStageRowForSelection(recordKey, fallbackRecord){
    const row = stageRowByKey(recordKey, fallbackRecord);
    if (!row) return;
    if (state.lastOilEdit && state.lastOilEdit.row === row) {
      state.lastOilEdit = null;
      SoapTool.oils.clearSelectedOilProfile();
    }
    row.remove();
  }

  function clearStageRows(){
    const rows = getStageRows();
    rows.forEach(row => {
      if (state.lastOilEdit && state.lastOilEdit.row === row) {
        state.lastOilEdit = null;
      }
      row.remove();
    });
    SoapTool.oils.clearSelectedOilProfile();
  }

  function notifyStageOilChanged(){
    SoapTool.oils.updateOilTotals();
    SoapTool.stages.updateStageStatuses();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
  }

  function normalizeSelectionKey(rawName, rawGi, rawKey){
    const explicit = String(rawKey || '').trim();
    if (explicit) return explicit;
    const gi = String(rawGi || '').trim();
    if (gi) return `global:${gi}`;
    const name = normalizeName(rawName);
    if (name) return `soapcalc:${name}`;
    return '';
  }

  function buildSelectionFromStage(){
    const selection = {};
    getStageRows().forEach(row => {
      const name = String(row.querySelector('.oil-typeahead')?.value || '').trim();
      const sap = toNumber(row.querySelector('.oil-sap-koh')?.value);
      const iodine = toNumber(row.querySelector('.oil-iodine')?.value);
      const giRaw = String(row.querySelector('.oil-gi-id')?.value || '').trim();
      const unit = String(row.querySelector('.oil-default-unit')?.value || 'gram');
      const categoryName = String(row.querySelector('.oil-category')?.value || '');
      const selectedPct = clamp(toNumber(row.querySelector('.oil-percent')?.value), 0, 100);
      const selectedWeightG = clamp(toGrams(row.querySelector('.oil-grams')?.value), 0);
      const fattyRaw = String(row.querySelector('.oil-fatty')?.value || '');
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
        name: name || 'Unnamed oil',
        sap_koh: sap,
        iodine,
        fatty_profile: fattyProfile,
        default_unit: unit || 'gram',
        ingredient_category_name: categoryName,
        global_item_id: giRaw ? parseInt(giRaw, 10) : null,
        source: giRaw ? 'global' : 'soapcalc',
        is_basic: !giRaw,
        selected_pct: selectedPct,
        selected_weight_g: selectedWeightG,
      };
    });
    return selection;
  }

  function hydrateSelectionFromStage(){
    const modalState = ensureModalState();
    modalState.selection = buildSelectionFromStage();
    updateSelectionCounters();
  }

  function syncAllSelectionsToStage(){
    const modalState = ensureModalState();
    const selectedItems = Object.values(modalState.selection || {});
    const expectedKeys = new Set(selectedItems.map(item => item.key));
    getStageRows().forEach(row => {
      const key = String(row.dataset.bulkOilKey || '').trim();
      if (!key || !expectedKeys.has(key)) {
        row.remove();
      }
    });
    selectedItems
      .slice()
      .sort((left, right) => String(left.name || '').localeCompare(String(right.name || '')))
      .forEach(item => {
        upsertStageRowForSelection(item);
      });
    notifyStageOilChanged();
  }

  async function openModal(){
    const refs = getRefs();
    const modalState = ensureModalState();
    if (!refs.modalEl) return;
    hydrateSelectionFromStage();
    if (!modalInstance && window.bootstrap?.Modal) {
      modalInstance = window.bootstrap.Modal.getOrCreateInstance(refs.modalEl);
    }
    if (refs.searchInput) refs.searchInput.value = modalState.query || '';
    if (refs.modeToggle) refs.modeToggle.checked = modalState.mode === 'all';
    if (refs.viewSelectedToggle) refs.viewSelectedToggle.checked = !!modalState.viewSelected;
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
      const selected = setSelection(record, {
        selected_pct: pct,
        selected_weight_g: selectedWeightG,
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

  function handleViewSelectedToggle(checked){
    const modalState = ensureModalState();
    modalState.viewSelected = !!checked;
    applyClientOrdering();
    renderVisibleRecords();
    queueStateSave();
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
      applyClientOrdering();
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
    clearStageRows();
    if (LOCAL_SORT_KEYS.has(modalState.sortKey) || modalState.viewSelected) {
      applyClientOrdering();
    }
    renderVisibleRecords();
    notifyStageOilChanged();
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

  function saveAndClose(){
    syncAllSelectionsToStage();
    queueStateSave();
    closeModal();
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
    if (refs.viewSelectedToggle) {
      refs.viewSelectedToggle.addEventListener('change', () => {
        handleViewSelectedToggle(!!refs.viewSelectedToggle.checked);
      });
    }
    if (refs.scrollEl) {
      refs.scrollEl.addEventListener('scroll', handleScroll);
    }
    if (refs.bodyEl) {
      refs.bodyEl.addEventListener('change', handleBodyInput);
      refs.bodyEl.addEventListener('keydown', event => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) return;
        const isCommitField = target.classList.contains('bulk-oil-pct')
          || target.classList.contains('bulk-oil-weight');
        if (!isCommitField || event.key !== 'Enter') return;
        // Commit numeric edits only when the user confirms the field.
        event.preventDefault();
        target.blur();
      });
    }
    refs.modalEl.querySelectorAll('.bulk-oil-sort').forEach(button => {
      button.addEventListener('click', handleSortClick);
    });
    if (refs.importBtn) {
      refs.importBtn.addEventListener('click', () => {
        saveAndClose();
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
