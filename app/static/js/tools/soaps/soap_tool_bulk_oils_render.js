(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
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
    updateSelectionCounters,
  } = shared;

  function updateStatusText(text){
    const refs = getRefs();
    if (refs.statusEl) refs.statusEl.textContent = text;
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

  function applyViewSelectedOrderingIfNeeded(){
    const modalState = ensureModalState();
    if (!modalState.viewSelected) return;
    const selected = [];
    const others = [];
    modalState.visibleRecords.forEach(record => {
      if (selectionForRecordKey(record.key)) {
        selected.push(record);
      } else {
        others.push(record);
      }
    });
    modalState.visibleRecords = selected.concat(others);
  }

  function applyClientOrdering(){
    applyLocalSelectionSortIfNeeded();
    applyViewSelectedOrderingIfNeeded();
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

  bulk.render = {
    updateStatusText,
    refreshCatalogStatus,
    applyLocalSelectionSortIfNeeded,
    applyViewSelectedOrderingIfNeeded,
    applyClientOrdering,
    normalizeServerSortKey,
    sortButtonsLabel,
    renderVisibleRecords,
  };
})(window);
