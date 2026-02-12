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
    applyLocalSelectionSortIfNeeded,
    sortButtonsLabel,
    renderVisibleRecords,
  } = render;
  const { fetchCatalogPage } = api;

  let modalInstance = null;
  let searchDebounceTimer = null;

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
    }
    renderVisibleRecords();
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
