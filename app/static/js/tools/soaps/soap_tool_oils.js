(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { toGrams, fromGrams } = SoapTool.units;
  const { OIL_CATEGORY_SET, OIL_TIP_RULES } = SoapTool.constants;
  const { computeQualities } = SoapTool.calc;
  const state = SoapTool.state;

  function attachOilTypeahead(row){
    const input = row.querySelector('.oil-typeahead');
    const hiddenSap = row.querySelector('.oil-sap-koh');
    const hiddenIodine = row.querySelector('.oil-iodine');
    const hiddenFatty = row.querySelector('.oil-fatty');
    const hiddenGi = row.querySelector('.oil-gi-id');
    const list = row.querySelector('[data-role="suggestions"]');
    if (!input || !list || typeof window.attachMergedInventoryGlobalTypeahead !== 'function') {
      return;
    }
    window.attachMergedInventoryGlobalTypeahead({
      inputEl: input,
      listEl: list,
      mode: 'public',
      giHiddenEl: hiddenGi,
      includeInventory: false,
      includeGlobal: true,
      ingredientFirst: true,
      searchType: 'ingredient',
      resultFilter: (item, source) => matchesCategory(item, OIL_CATEGORY_SET, source),
      requireHidden: false,
      onSelection: function(picked){
        if (hiddenSap) {
          hiddenSap.value = picked?.saponification_value || '';
        }
        if (hiddenIodine) {
          hiddenIodine.value = picked?.iodine_value || '';
        }
        if (hiddenFatty) {
          hiddenFatty.value = picked?.fatty_acid_profile ? JSON.stringify(picked.fatty_acid_profile) : '';
        }
        setSelectedOilProfile(picked);
        updateOilTotals();
        SoapTool.storage.queueStateSave();
        SoapTool.storage.queueAutoCalc();
      }
    });
    input.addEventListener('input', function(){
      if (!this.value.trim()) {
        if (hiddenSap) hiddenSap.value = '';
        if (hiddenIodine) hiddenIodine.value = '';
        if (hiddenFatty) hiddenFatty.value = '';
        if (hiddenGi) hiddenGi.value = '';
        clearSelectedOilProfile();
      }
    });
  }

  function buildOilRow(){
    const row = document.createElement('div');
    row.className = 'row g-2 align-items-end oil-row mb-2';
    row.innerHTML = `
      <div class="col-md-6">
        <label class="form-label">Oil, fat, or wax</label>
        <div class="position-relative">
          <input type="text" class="form-control oil-typeahead" placeholder="Search oils, butters, waxes...">
          <input type="hidden" class="oil-sap-koh">
          <input type="hidden" class="oil-iodine">
          <input type="hidden" class="oil-fatty">
          <input type="hidden" class="oil-gi-id">
          <div class="list-group position-absolute w-100 d-none" data-role="suggestions" style="z-index:1050"></div>
        </div>
        <div class="form-text small text-muted">Filtered to oils, butters, and waxes.</div>
      </div>
      <div class="col-md-3">
        <label class="form-label">Weight <span class="badge rounded-pill soap-unit-chip unit-label">g</span></label>
        <input type="number" class="form-control oil-grams" min="0" step="0.1">
      </div>
      <div class="col-md-2">
        <label class="form-label">%</label>
        <input type="number" class="form-control oil-percent" min="0" step="0.1">
      </div>
      <div class="col-md-1 d-grid">
        <button class="btn btn-outline-danger remove-oil" type="button">Remove</button>
      </div>`;
    const mobileProfile = document.createElement('div');
    mobileProfile.className = 'col-12 d-lg-none mt-2';
    mobileProfile.innerHTML = '<button class="btn btn-sm btn-outline-secondary w-100 oil-profile-open" type="button">View oil profile</button>';
    row.appendChild(mobileProfile);
    row.querySelectorAll('.form-text').forEach(text => {
      const wrapper = text.closest('.col-md-6, .col-md-3, .col-md-2');
      if (wrapper) wrapper.classList.add('soap-field');
    });
    attachOilTypeahead(row);
    row.querySelectorAll('.unit-label').forEach(el => {
      el.textContent = state.currentUnit;
    });
    return row;
  }

  function getOilTargetGrams(){
    const mold = SoapTool.mold.getMoldSettings();
    if (mold.targetOils > 0) return mold.targetOils;
    return toGrams(document.getElementById('oilTotalTarget').value);
  }

  function deriveTargetFromRows(rows){
    const derived = [];
    rows.forEach(row => {
      const grams = toGrams(row.querySelector('.oil-grams')?.value);
      const pct = clamp(toNumber(row.querySelector('.oil-percent')?.value), 0);
      if (grams > 0 && pct > 0) {
        derived.push(grams / (pct / 100));
      }
    });
    if (!derived.length) return 0;
    const sum = derived.reduce((acc, value) => acc + value, 0);
    return sum / derived.length;
  }

  function enforceOilTargetCap(rows, target){
    if (!state.lastOilEdit || !state.lastOilEdit.row) return false;
    const lastRow = state.lastOilEdit.row;
    const otherTotal = rows.reduce((acc, row) => {
      if (row === lastRow) return acc;
      return acc + toGrams(row.querySelector('.oil-grams')?.value);
    }, 0);
    const allowed = Math.max(0, target - otherTotal);
    const gramsInput = lastRow.querySelector('.oil-grams');
    const pctInput = lastRow.querySelector('.oil-percent');
    if (!gramsInput || !pctInput) return false;
    gramsInput.value = allowed > 0 ? round(fromGrams(allowed), 2) : '';
    pctInput.value = allowed > 0 ? round((allowed / target) * 100, 2) : '';
    state.wasCapped = true;
    return true;
  }

  function updateOilLimitWarning({ totalWeight, totalPct, target, capped }){
    const warning = document.getElementById('oilLimitWarning');
    if (!warning) return;
    const messages = [];
    if (capped) {
      messages.push('Oil total hit the mold cap and was adjusted.');
    }
    if (target > 0 && totalWeight > target + 0.01) {
      const over = totalWeight - target;
      messages.push(`Oil weights exceed the target by ${round(fromGrams(over), 2)} ${state.currentUnit}.`);
    }
    if (totalPct > 100.01) {
      messages.push(`Oil percentages are over 100% by ${round(totalPct - 100, 2)}%.`);
    }
    if (messages.length) {
      warning.classList.remove('d-none');
      warning.innerHTML = `${messages.join(' ')} Adjust oils or mold % to continue.`;
    } else {
      warning.classList.add('d-none');
      warning.textContent = '';
    }
  }

  function updateOilTotals(options = {}){
    if (!options.skipEnforce) {
      state.wasCapped = false;
    }
    const rows = Array.from(document.querySelectorAll('#oilRows .oil-row'));
    const mold = SoapTool.mold.getMoldSettings();
    let target = getOilTargetGrams();
    if (!target && !mold.targetOils) {
      const derived = deriveTargetFromRows(rows);
      if (derived > 0) {
        target = derived;
        const targetInput = document.getElementById('oilTotalTarget');
        if (targetInput && !targetInput.value) {
          targetInput.value = round(fromGrams(derived), 2);
        }
      }
    }

    let totalWeight = 0;
    let totalPct = 0;

    rows.forEach(row => {
      const gramsInput = row.querySelector('.oil-grams');
      const pctInput = row.querySelector('.oil-percent');
      let grams = toGrams(gramsInput?.value);
      let pct = clamp(toNumber(pctInput?.value), 0);
      if (target > 0) {
        if (state.lastOilEdit && state.lastOilEdit.row === row && state.lastOilEdit.field === 'percent') {
          grams = pct > 0 ? target * (pct / 100) : 0;
          gramsInput.value = pct > 0 ? round(fromGrams(grams), 2) : '';
        } else {
          if (grams > 0) {
            pct = (grams / target) * 100;
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
        rows.forEach(row => {
          const gramsInput = row.querySelector('.oil-grams');
          const pctInput = row.querySelector('.oil-percent');
          const grams = toGrams(gramsInput?.value);
          if (grams > 0) {
            const pct = (grams / totalWeight) * 100;
            pctInput.value = round(pct, 2);
            totalPct += pct;
          }
        });
      } else {
        totalPct = rows.reduce((sum, row) => sum + clamp(toNumber(row.querySelector('.oil-percent')?.value), 0), 0);
      }
    }

    if (!options.skipEnforce && mold.targetOils > 0 && totalWeight > mold.targetOils + 0.01) {
      if (enforceOilTargetCap(rows, mold.targetOils)) {
        return updateOilTotals({ skipEnforce: true });
      }
    }

    state.totalOilsGrams = totalWeight;
    const totalLabel = document.getElementById('oilTotalComputed');
    if (totalLabel) {
      totalLabel.textContent = totalWeight > 0 ? `${round(fromGrams(totalWeight), 2)} ${state.currentUnit}` : '--';
    }
    document.getElementById('oilPercentTotal').textContent = round(totalPct, 2);
    updateOilLimitWarning({ totalWeight, totalPct, target, capped: state.wasCapped });
    SoapTool.additives.updateAdditivesOutput(totalWeight);
    SoapTool.mold.updateMoldSuggested();
    updateOilTips();
    return { totalWeight, totalPct, target };
  }

  function normalizeOils(){
    const rows = Array.from(document.querySelectorAll('#oilRows .oil-row'));
    if (!rows.length) return;
    const target = getOilTargetGrams();
    let totalPct = rows.reduce((sum, row) => sum + clamp(toNumber(row.querySelector('.oil-percent')?.value), 0), 0);
    if (!totalPct && target > 0) {
      totalPct = rows.reduce((sum, row) => {
        const grams = toGrams(row.querySelector('.oil-grams')?.value);
        return sum + (grams > 0 ? (grams / target) * 100 : 0);
      }, 0);
    }
    if (totalPct <= 0) return;
    rows.forEach(row => {
      const pctInput = row.querySelector('.oil-percent');
      const gramsInput = row.querySelector('.oil-grams');
      const pct = clamp(toNumber(pctInput.value), 0);
      const nextPct = (pct / totalPct) * 100;
      pctInput.value = round(nextPct, 2);
      if (target > 0) {
        gramsInput.value = nextPct > 0 ? round(fromGrams(target * (nextPct / 100)), 2) : '';
      }
    });
    updateOilTotals();
  }

  function collectOilData(){
    const oils = [];
    document.querySelectorAll('#oilRows .oil-row').forEach(row => {
      const name = row.querySelector('.oil-typeahead')?.value?.trim();
      const grams = toGrams(row.querySelector('.oil-grams')?.value);
      const sapKoh = toNumber(row.querySelector('.oil-sap-koh')?.value);
      const iodine = toNumber(row.querySelector('.oil-iodine')?.value);
      const fattyRaw = row.querySelector('.oil-fatty')?.value || '';
      const gi = row.querySelector('.oil-gi-id')?.value || '';
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
      });
    });
    return oils;
  }

  function updateSelectedOilProfileDisplay({ name, sapKoh, iodine, fattyProfile } = {}){
    const floatCard = document.getElementById('oilProfileFloat');
    const setText = (id, value) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    };
    const nameLabel = name || 'Pick an oil to preview';
    setText('selectedOilName', nameLabel);
    setText('selectedOilModalName', nameLabel);
    if (floatCard) {
      floatCard.classList.toggle('d-none', !name);
    }
    const sapValue = sapKoh > 0 ? round(sapKoh, 1) : '--';
    const iodineValue = iodine > 0 ? round(iodine, 1) : '--';
    setText('selectedOilSap', sapValue);
    setText('selectedOilModalSap', sapValue);
    setText('selectedOilIodine', iodineValue);
    setText('selectedOilModalIodine', iodineValue);

    const qualities = fattyProfile ? computeQualities(fattyProfile) : {};
    const setValue = (id, value) => {
      const safe = isFinite(value) && value > 0 ? round(value, 1) : '--';
      setText(id, safe);
    };
    setValue('selectedOilHardness', qualities.hardness);
    setValue('selectedOilModalHardness', qualities.hardness);
    setValue('selectedOilCleansing', qualities.cleansing);
    setValue('selectedOilModalCleansing', qualities.cleansing);
    setValue('selectedOilConditioning', qualities.conditioning);
    setValue('selectedOilModalConditioning', qualities.conditioning);
    setValue('selectedOilBubbly', qualities.bubbly);
    setValue('selectedOilModalBubbly', qualities.bubbly);
    setValue('selectedOilCreamy', qualities.creamy);
    setValue('selectedOilModalCreamy', qualities.creamy);

    const fattyKeys = ['lauric', 'myristic', 'palmitic', 'stearic', 'ricinoleic', 'oleic', 'linoleic', 'linolenic'];
    fattyKeys.forEach(key => {
      const baseId = `selectedOil${key.charAt(0).toUpperCase()}${key.slice(1)}`;
      const modalId = `selectedOilModal${key.charAt(0).toUpperCase()}${key.slice(1)}`;
      const value = fattyProfile ? toNumber(fattyProfile[key]) : 0;
      const safe = value > 0 ? round(value, 1) : '--';
      setText(baseId, safe);
      setText(modalId, safe);
    });
  }

  function setSelectedOilProfile(picked){
    if (!picked) {
      clearSelectedOilProfile();
      return;
    }
    state.selectedOilProfile = picked;
    let fattyProfile = picked.fatty_acid_profile || null;
    if (typeof fattyProfile === 'string') {
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
      fattyProfile,
    });
  }

  function setSelectedOilProfileFromRow(row){
    if (!row) return;
    const name = row.querySelector('.oil-typeahead')?.value?.trim();
    const sapKoh = toNumber(row.querySelector('.oil-sap-koh')?.value);
    const iodine = toNumber(row.querySelector('.oil-iodine')?.value);
    const fattyRaw = row.querySelector('.oil-fatty')?.value || '';
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
      fattyProfile,
    });
  }

  function clearSelectedOilProfile(){
    state.selectedOilProfile = null;
    state.lastPreviewRow = null;
    updateSelectedOilProfileDisplay();
  }

  function updateOilTips(){
    const tipBox = document.getElementById('oilBlendTips');
    if (!tipBox) return;
    const oils = collectOilData().filter(oil => oil.grams > 0 || oil.percent > 0);
    if (!oils.length) {
      tipBox.classList.add('d-none');
      tipBox.textContent = '';
      return;
    }
    const tips = new Set();
    oils.forEach(oil => {
      const name = (oil.name || '').toLowerCase();
      if (name) {
        OIL_TIP_RULES.forEach(rule => {
          if (rule.match.test(name)) tips.add(rule.tip);
        });
      }
      if (oil.fattyProfile && typeof oil.fattyProfile === 'object') {
        const lauric = toNumber(oil.fattyProfile.lauric);
        const myristic = toNumber(oil.fattyProfile.myristic);
        const palmitic = toNumber(oil.fattyProfile.palmitic);
        const stearic = toNumber(oil.fattyProfile.stearic);
        const ricinoleic = toNumber(oil.fattyProfile.ricinoleic);
        const oleic = toNumber(oil.fattyProfile.oleic);
        const linoleic = toNumber(oil.fattyProfile.linoleic);
        const linolenic = toNumber(oil.fattyProfile.linolenic);
        if (lauric + myristic >= 30) {
          tips.add(`${oil.name || 'This oil'} is high in lauric/myristic; expect faster trace and stronger cleansing.`);
        }
        if (palmitic + stearic >= 40) {
          tips.add(`${oil.name || 'This oil'} is high in palmitic/stearic; expect a harder bar and quicker set-up.`);
        }
        if (oleic >= 60) {
          tips.add(`${oil.name || 'This oil'} is high oleic; trace may be slow and bars may start softer.`);
        }
        if (linoleic + linolenic >= 20) {
          tips.add(`${oil.name || 'This oil'} is high in PUFAs; keep the % lower to reduce DOS risk.`);
        }
        if (ricinoleic >= 60) {
          tips.add(`${oil.name || 'This oil'} boosts lather but can feel tacky; keep under 10-15%.`);
        }
      }
    });
    const tipList = Array.from(tips).slice(0, 6);
    if (!tipList.length) {
      tipBox.classList.add('d-none');
      tipBox.textContent = '';
      return;
    }
    tipBox.classList.remove('d-none');
    tipBox.innerHTML = `<strong>Blend behavior tips:</strong><ul class="mb-0">${tipList.map(tip => `<li>${tip}</li>`).join('')}</ul>`;
  }

  function getTotalOilsGrams(){
    return state.totalOilsGrams || 0;
  }

  function serializeOilRow(row){
    if (!row) return null;
    return {
      name: row.querySelector('.oil-typeahead')?.value || '',
      grams: row.querySelector('.oil-grams')?.value || '',
      percent: row.querySelector('.oil-percent')?.value || '',
      sap: row.querySelector('.oil-sap-koh')?.value || '',
      iodine: row.querySelector('.oil-iodine')?.value || '',
      fattyRaw: row.querySelector('.oil-fatty')?.value || '',
      gi: row.querySelector('.oil-gi-id')?.value || '',
    };
  }

  function matchesCategory(item, allowedSet, source){
    const category = getItemCategoryName(item);
    if (!category) {
      return source === 'inventory';
    }
    return allowedSet.has(category);
  }

  function getItemCategoryName(item){
    if (!item || typeof item !== 'object') return null;
    return (item.ingredient && item.ingredient.ingredient_category_name)
      || item.ingredient_category_name
      || (item.ingredient_category && item.ingredient_category.name)
      || null;
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
  };
})(window);
