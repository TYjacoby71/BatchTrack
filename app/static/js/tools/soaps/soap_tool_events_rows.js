(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const state = SoapTool.state;

  function bindOilRows(oilRows){
    if (!oilRows) return;

    const addOilBtn = document.getElementById('addOil');
    const normalizeOilsBtn = document.getElementById('normalizeOils');
    if (addOilBtn) {
      addOilBtn.dataset.bound = 'direct';
      addOilBtn.addEventListener('click', function(){
        oilRows.appendChild(SoapTool.oils.buildOilRow());
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
      });
    }
    if (normalizeOilsBtn) {
      normalizeOilsBtn.dataset.bound = 'direct';
      normalizeOilsBtn.addEventListener('click', function(){
        SoapTool.oils.normalizeOils();
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      });
    }

    oilRows.addEventListener('input', function(e){
      if (e.target.classList.contains('oil-grams')) {
        state.lastOilEdit = { row: e.target.closest('.oil-row'), field: 'grams' };
      }
      if (e.target.classList.contains('oil-percent')) {
        state.lastOilEdit = { row: e.target.closest('.oil-row'), field: 'percent' };
      }
      if (e.target.classList.contains('oil-grams')
        || e.target.classList.contains('oil-percent')
        || e.target.classList.contains('oil-typeahead')) {
        if (e.target.classList.contains('oil-typeahead')) {
          SoapTool.oils.setSelectedOilProfileFromRow(e.target.closest('.oil-row'));
        }
        SoapTool.oils.updateOilTotals();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      }
    });

    oilRows.addEventListener('focusin', function(e){
      if (e.target.classList.contains('oil-typeahead')) {
        SoapTool.oils.setSelectedOilProfileFromRow(e.target.closest('.oil-row'));
      }
    });

    oilRows.addEventListener('focusout', function(e){
      if (e.target.classList.contains('oil-typeahead')) {
        SoapTool.oils.clearSelectedOilProfile();
      }
      if (e.target.classList.contains('oil-grams')) {
        SoapTool.oils.validateOilEntry(e.target.closest('.oil-row'), 'grams');
      }
      if (e.target.classList.contains('oil-percent')) {
        SoapTool.oils.validateOilEntry(e.target.closest('.oil-row'), 'percent');
      }
    });

    oilRows.addEventListener('keydown', function(e){
      if (e.key !== 'Enter') return;
      if (e.target.classList.contains('oil-grams')) {
        e.preventDefault();
        SoapTool.oils.validateOilEntry(e.target.closest('.oil-row'), 'grams');
      }
      if (e.target.classList.contains('oil-percent')) {
        e.preventDefault();
        SoapTool.oils.validateOilEntry(e.target.closest('.oil-row'), 'percent');
      }
    });

    oilRows.addEventListener('mouseover', function(e){
      if (!e.target.classList.contains('oil-typeahead')) return;
      const row = e.target.closest('.oil-row');
      if (!row || row === state.lastPreviewRow) return;
      state.lastPreviewRow = row;
      SoapTool.oils.setSelectedOilProfileFromRow(row);
    });

    oilRows.addEventListener('mouseout', function(e){
      if (e.target.classList.contains('oil-typeahead')) {
        SoapTool.oils.clearSelectedOilProfile();
      }
    });

    oilRows.addEventListener('click', function(e){
      const profileButton = e.target.closest('.oil-profile-open');
      if (profileButton) {
        const row = profileButton.closest('.oil-row');
        if (row) {
          SoapTool.oils.setSelectedOilProfileFromRow(row);
          const modalEl = document.getElementById('oilProfileModal');
          if (modalEl && window.bootstrap) {
            const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
          }
        }
        return;
      }
      const removeButton = e.target.closest('.remove-oil');
      if (removeButton) {
        const row = removeButton.closest('.oil-row');
        if (row) {
          state.lastRemovedOil = SoapTool.oils.serializeOilRow(row);
          state.lastRemovedOilIndex = Array.from(row.parentElement.children).indexOf(row);
          SoapTool.ui.showUndoToast('Oil removed.');
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
  }

  function bindFragranceRows(fragranceRows){
    if (!fragranceRows) return;
    const addFragranceBtn = document.getElementById('addFragrance');
    if (addFragranceBtn) {
      addFragranceBtn.dataset.bound = 'direct';
      addFragranceBtn.addEventListener('click', function(){
        fragranceRows.appendChild(SoapTool.fragrances.buildFragranceRow());
        SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
      });
    }
    fragranceRows.addEventListener('input', function(e){
      if (e.target.classList.contains('fragrance-grams')) {
        SoapTool.state.lastFragranceEdit = { row: e.target.closest('.fragrance-row'), field: 'grams' };
      }
      if (e.target.classList.contains('fragrance-percent')) {
        SoapTool.state.lastFragranceEdit = { row: e.target.closest('.fragrance-row'), field: 'percent' };
      }
      if (e.target.classList.contains('fragrance-grams')
        || e.target.classList.contains('fragrance-percent')
        || e.target.classList.contains('fragrance-typeahead')) {
        SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
        SoapTool.stages.updateStageStatuses();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      }
    });
    fragranceRows.addEventListener('click', function(e){
      const removeButton = e.target.closest('.remove-fragrance');
      if (!removeButton) return;
      const row = removeButton.closest('.fragrance-row');
      if (row && SoapTool.state.lastFragranceEdit?.row === row) {
        SoapTool.state.lastFragranceEdit = null;
      }
      if (row) row.remove();
      SoapTool.fragrances.updateFragranceTotals(SoapTool.oils.getTotalOilsGrams());
      SoapTool.stages.updateStageStatuses();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }

  function bindStageTabContent({ oilRows, fragranceRows }){
    const stageTabContent = document.getElementById('soapStageTabContent');
    if (!stageTabContent) return;

    const getActiveStageScrollContainer = () => {
      const activePane = stageTabContent.querySelector('.tab-pane.active') || stageTabContent.querySelector('.tab-pane.show.active');
      if (!activePane) return null;
      return activePane.querySelector('.soap-stage-body') || activePane;
    };

    stageTabContent.addEventListener('wheel', event => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const numberInput = target.closest('input[type="number"]');
      if (!(numberInput instanceof HTMLInputElement)) return;
      const scrollContainer = getActiveStageScrollContainer();
      if (!(scrollContainer instanceof HTMLElement)) return;
      if (scrollContainer.scrollHeight <= scrollContainer.clientHeight + 1) return;
      if (document.activeElement === numberInput && typeof numberInput.blur === 'function') {
        numberInput.blur();
      }
      const atTop = scrollContainer.scrollTop <= 0;
      const atBottom = (
        scrollContainer.scrollTop + scrollContainer.clientHeight
      ) >= (scrollContainer.scrollHeight - 1);
      if ((event.deltaY < 0 && atTop) || (event.deltaY > 0 && atBottom)) {
        return;
      }
      scrollContainer.scrollTop += event.deltaY;
      event.preventDefault();
    }, { passive: false });

    stageTabContent.addEventListener('click', event => {
      const actionBtn = event.target.closest('[data-stage-action]');
      const soapActionBtn = event.target.closest('[data-soap-action]');
      if (!actionBtn && !soapActionBtn) return;
      event.preventDefault();
      event.stopPropagation();
      if (document.activeElement && typeof document.activeElement.blur === 'function') {
        document.activeElement.blur();
      }
      if (soapActionBtn) {
        if (soapActionBtn.dataset.bound === 'direct') return;
        const action = soapActionBtn.dataset.soapAction;
        if (action === 'add-oil' && oilRows) {
          oilRows.appendChild(SoapTool.oils.buildOilRow());
          SoapTool.stages.updateStageStatuses();
          SoapTool.storage.queueStateSave();
        }
        if (action === 'normalize-oils') {
          SoapTool.oils.normalizeOils();
          SoapTool.stages.updateStageStatuses();
          SoapTool.storage.queueStateSave();
          SoapTool.storage.queueAutoCalc();
        }
        if (action === 'add-fragrance' && fragranceRows) {
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
      if (action === 'prev') SoapTool.stages.openStageByIndex(Math.max(0, index - 1));
      if (action === 'next') SoapTool.stages.openStageByIndex(Math.min(SoapTool.constants.STAGE_CONFIGS.length - 1, index + 1));
      if (action === 'reset') SoapTool.stages.resetStage(index + 1);
    });
  }

  function bindUndo(){
    const undoRemoveBtn = document.getElementById('soapUndoRemove');
    if (!undoRemoveBtn) return;
    undoRemoveBtn.addEventListener('click', () => {
      if (!state.lastRemovedOil) return;
      SoapTool.storage.restoreOilRow(state.lastRemovedOil, state.lastRemovedOilIndex || 0);
      state.lastRemovedOil = null;
      state.lastRemovedOilIndex = null;
      SoapTool.oils.updateOilTotals();
      SoapTool.storage.queueStateSave();
      SoapTool.storage.queueAutoCalc();
    });
  }

  function bind(){
    const oilRows = document.getElementById('oilRows');
    const fragranceRows = document.getElementById('fragranceRows');
    bindOilRows(oilRows);
    bindFragranceRows(fragranceRows);
    bindStageTabContent({ oilRows, fragranceRows });
    bindUndo();
    return { oilRows, fragranceRows };
  }

  SoapTool.eventsRows = {
    bind,
  };
})(window);
