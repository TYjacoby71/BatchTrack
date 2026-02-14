(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp, buildSoapcalcSearchBuilder } = SoapTool.helpers;
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
    const hiddenUnit = row.querySelector('.oil-default-unit');
    const hiddenCategory = row.querySelector('.oil-category');
    const list = row.querySelector('[data-role="suggestions"]');
    if (!input || !list || typeof window.attachMergedInventoryGlobalTypeahead !== 'function') {
      return;
    }
    const builder = buildSoapcalcSearchBuilder();
    window.attachMergedInventoryGlobalTypeahead({
      inputEl: input,
      listEl: list,
      mode: 'public',
      giHiddenEl: hiddenGi,
      includeInventory: false,
      includeGlobal: true,
      ingredientFirst: true,
      globalUrlBuilder: builder,
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
        if (hiddenUnit) {
          hiddenUnit.value = picked?.default_unit || '';
        }
        if (hiddenCategory) {
          hiddenCategory.value = picked?.ingredient_category_name || '';
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
        if (hiddenUnit) hiddenUnit.value = '';
        if (hiddenCategory) hiddenCategory.value = '';
        clearSelectedOilProfile();
      }
    });
  }

  function buildOilRow(){
    const template = document.getElementById('oilRowTemplate');
    const row = template?.content?.querySelector('.oil-row')?.cloneNode(true);
    if (!row) {
      return document.createElement('div');
    }
    row.querySelectorAll('input').forEach(input => {
      input.value = '';
    });
    row.querySelectorAll('.form-text').forEach(text => {
      const wrapper = text.closest('.soap-field-stack, [class*="col-"]');
      if (wrapper) wrapper.classList.add('soap-field');
    });
    attachOilTypeahead(row);
    row.querySelectorAll('.unit-suffix').forEach(el => {
      el.dataset.suffix = state.currentUnit;
    });
    return row;
  }

  function getOilTargetGrams(){
    const targetInput = document.getElementById('oilTotalTarget');
    const manualTarget = toGrams(targetInput?.value);
    if (manualTarget > 0) return manualTarget;
    const mold = SoapTool.mold.getMoldSettings();
    if (mold.targetOils > 0) return mold.targetOils;
    return 0;
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

  function getRowLimits(row, target){
    if (!row || !target || target <= 0) {
      return { allowedGrams: null, allowedPct: null };
    }
    const rows = Array.from(document.querySelectorAll('#oilRows .oil-row'));
    const otherTotal = rows.reduce((acc, current) => {
      if (current === row) return acc;
      return acc + toGrams(current.querySelector('.oil-grams')?.value);
    }, 0);
    const otherPct = rows.reduce((acc, current) => {
      if (current === row) return acc;
      return acc + clamp(toNumber(current.querySelector('.oil-percent')?.value), 0);
    }, 0);
    const allowedPct = Math.max(0, 100 - otherPct);
    const allowedByTotal = Math.max(0, target - otherTotal);
    const allowedByPct = (target * allowedPct) / 100;
    const allowedGrams = Math.max(0, Math.min(allowedByTotal, allowedByPct));
    return { allowedGrams, allowedPct };
  }

  function setOilHint(row, field, message){
    if (!row) return;
    const hint = row.querySelector(`[data-role="oil-${field}-hint"]`);
    if (!hint) return;
    if (message) {
      hint.textContent = message;
      hint.classList.add('is-visible');
    } else {
      hint.textContent = '';
      hint.classList.remove('is-visible');
    }
  }

  function bounceInput(input){
    if (!input) return;
    input.classList.remove('oil-input-bounce');
    void input.offsetWidth;
    input.classList.add('oil-input-bounce');
  }

  function validateOilEntry(row, field, options = {}){
    const target = getOilTargetGrams();
    if (!row || !target || target <= 0) {
      setOilHint(row, field, '');
      return;
    }
    const gramsInput = row.querySelector('.oil-grams');
    const pctInput = row.querySelector('.oil-percent');
    const limits = getRowLimits(row, target);
    if (field === 'grams' && gramsInput) {
      const grams = toGrams(gramsInput.value);
      let message = '';
      if (grams > target + 0.01) {
        message = 'Entry exceeds the max oils allowed in stage 2.';
      } else if (limits.allowedGrams !== null && grams > limits.allowedGrams + 0.01) {
        message = `Must be under ${round(fromGrams(limits.allowedGrams), 2)} ${state.currentUnit} to stay within the stage 2 oil limit.`;
      }
      if (message) {
        const nextValue = limits.allowedGrams !== null ? round(fromGrams(limits.allowedGrams), 2) : round(fromGrams(target), 2);
        gramsInput.value = nextValue > 0 ? nextValue : '';
        setOilHint(row, field, message);
        gramsInput.classList.add('oil-input-warning');
        bounceInput(gramsInput);
        updateOilTotals();
      } else {
        gramsInput.classList.remove('oil-input-warning');
        setOilHint(row, field, '');
      }
    }
    if (field === 'percent' && pctInput) {
      const pct = clamp(toNumber(pctInput.value), 0);
      let message = '';
      if (pct > 100.01) {
        message = 'Entry exceeds the max oils allowed in stage 2.';
      } else if (limits.allowedPct !== null && pct > limits.allowedPct + 0.01) {
        message = `Must be under ${round(limits.allowedPct, 2)}% to stay within the stage 2 oil limit.`;
      }
      if (message) {
        const nextPct = limits.allowedPct !== null ? round(limits.allowedPct, 2) : 100;
        pctInput.value = nextPct > 0 ? nextPct : '';
        setOilHint(row, field, message);
        pctInput.classList.add('oil-input-warning');
        bounceInput(pctInput);
        updateOilTotals();
      } else {
        pctInput.classList.remove('oil-input-warning');
        setOilHint(row, field, '');
      }
    }
  }

  function scaleOilsToTarget(target, options = {}){
    const rows = Array.from(document.querySelectorAll('#oilRows .oil-row'));
    const nextTarget = target ?? getOilTargetGrams();
    const force = !!options.force;
    if (!nextTarget || nextTarget <= 0 || !rows.length) {
      state.lastOilTarget = nextTarget;
      return;
    }
    const totalPct = rows.reduce((sum, row) => sum + clamp(toNumber(row.querySelector('.oil-percent')?.value), 0), 0);
    const totalWeight = rows.reduce((sum, row) => sum + toGrams(row.querySelector('.oil-grams')?.value), 0);
    if (totalPct <= 0 && totalWeight <= 0) {
      state.lastOilTarget = nextTarget;
      return;
    }
    if (!force && state.lastOilTarget && Math.abs(state.lastOilTarget - nextTarget) < 0.01) {
      return;
    }
    if (totalPct > 0) {
      rows.forEach(row => {
        const pctInput = row.querySelector('.oil-percent');
        const gramsInput = row.querySelector('.oil-grams');
        const pct = clamp(toNumber(pctInput?.value), 0);
        const share = totalPct > 0 ? (pct / totalPct) : 0;
        if (gramsInput) {
          gramsInput.value = share > 0 ? round(fromGrams(nextTarget * share), 2) : '';
        }
        if (pctInput) {
          pctInput.value = share > 0 ? round(share * 100, 2) : '';
        }
      });
    } else if (totalWeight > 0) {
      const ratio = nextTarget / totalWeight;
      rows.forEach(row => {
        const gramsInput = row.querySelector('.oil-grams');
        const pctInput = row.querySelector('.oil-percent');
        const grams = toGrams(gramsInput?.value);
        if (gramsInput) {
          const nextGrams = grams > 0 ? grams * ratio : 0;
          gramsInput.value = nextGrams > 0 ? round(fromGrams(nextGrams), 2) : '';
        }
        if (pctInput) {
          const nextGrams = toGrams(gramsInput?.value);
          pctInput.value = nextGrams > 0 ? round((nextGrams / nextTarget) * 100, 2) : '';
        }
      });
    }
    state.lastOilTarget = nextTarget;
    updateOilTotals({ skipEnforce: true });
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
    if (SoapTool.fragrances?.updateFragranceTotals) {
      SoapTool.fragrances.updateFragranceTotals(totalWeight);
    }
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
      const defaultUnit = row.querySelector('.oil-default-unit')?.value || '';
      const categoryName = row.querySelector('.oil-category')?.value || '';
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
        ingredient_category_name: categoryName || null,
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
      defaultUnit: row.querySelector('.oil-default-unit')?.value || '',
      categoryName: row.querySelector('.oil-category')?.value || '',
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
    validateOilEntry,
    scaleOilsToTarget,
  };
})(window);
