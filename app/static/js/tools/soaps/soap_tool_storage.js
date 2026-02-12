(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { formatTime, getStorage } = SoapTool.helpers;
  const STATE_STORAGE_KEY = 'soap_tool_state_v2';

  function serializeLines(wrapperId, kind){
    const out = [];
    const rows = document.querySelectorAll(`#${wrapperId} .row`);
    rows.forEach(row => {
      const name = row.querySelector('.tool-typeahead')?.value?.trim();
      const gi = row.querySelector('.tool-gi-id')?.value || '';
      const qtyEl = row.querySelector('.tool-qty');
      const unitEl = row.querySelector('.tool-unit');
      const qty = qtyEl && qtyEl.value !== '' ? SoapTool.helpers.toNumber(qtyEl.value) : null;
      if (!name && !gi) return;
      if (kind === 'container') {
        out.push({
          name: name || '',
          global_item_id: gi ? parseInt(gi) : null,
          quantity: qty && qty > 0 ? qty : 1,
        });
      } else {
        out.push({
          name: name || '',
          global_item_id: gi ? parseInt(gi) : null,
          quantity: qty && qty >= 0 ? qty : 0,
          unit: unitEl?.value || 'gram',
        });
      }
    });
    return out;
  }

  function serializeOils(){
    const oils = [];
    document.querySelectorAll('#oilRows .oil-row').forEach(row => {
      const name = row.querySelector('.oil-typeahead')?.value?.trim() || '';
      const grams = row.querySelector('.oil-grams')?.value || '';
      const percent = row.querySelector('.oil-percent')?.value || '';
      const sap = row.querySelector('.oil-sap-koh')?.value || '';
      const iodine = row.querySelector('.oil-iodine')?.value || '';
      const fattyRaw = row.querySelector('.oil-fatty')?.value || '';
      const gi = row.querySelector('.oil-gi-id')?.value || '';
      const defaultUnit = row.querySelector('.oil-default-unit')?.value || '';
      const categoryName = row.querySelector('.oil-category')?.value || '';
      if (!name && !grams && !percent && !gi) return;
      oils.push({
        name,
        grams,
        percent,
        sap,
        iodine,
        fattyRaw,
        gi,
        defaultUnit,
        categoryName,
      });
    });
    return oils;
  }

  function serializeFragrances(){
    if (SoapTool.fragrances?.collectFragranceData) {
      return SoapTool.fragrances.collectFragranceData();
    }
    const rows = [];
    document.querySelectorAll('#fragranceRows .fragrance-row').forEach(row => {
      const name = row.querySelector('.fragrance-typeahead')?.value?.trim() || '';
      const grams = row.querySelector('.fragrance-grams')?.value || '';
      const percent = row.querySelector('.fragrance-percent')?.value || '';
      const gi = row.querySelector('.fragrance-gi-id')?.value || '';
      const defaultUnit = row.querySelector('.fragrance-default-unit')?.value || '';
      const categoryName = row.querySelector('.fragrance-category')?.value || '';
      if (!name && !grams && !percent && !gi) return;
      rows.push({ name, grams, percent, gi, defaultUnit, categoryName });
    });
    return rows;
  }

  function restoreOilRow(data, index){
    const oilRows = document.getElementById('oilRows');
    if (!oilRows || !data) return;
    const row = SoapTool.oils.buildOilRow();
    row.querySelector('.oil-typeahead').value = data.name || '';
    row.querySelector('.oil-grams').value = data.grams || '';
    row.querySelector('.oil-percent').value = data.percent || '';
    row.querySelector('.oil-sap-koh').value = data.sap || '';
    row.querySelector('.oil-iodine').value = data.iodine || '';
    row.querySelector('.oil-fatty').value = data.fattyRaw || '';
    row.querySelector('.oil-gi-id').value = data.gi || '';
    const unitEl = row.querySelector('.oil-default-unit');
    if (unitEl) unitEl.value = data.defaultUnit || '';
    const categoryEl = row.querySelector('.oil-category');
    if (categoryEl) categoryEl.value = data.categoryName || '';
    const children = Array.from(oilRows.children);
    if (index >= children.length) {
      oilRows.appendChild(row);
    } else {
      oilRows.insertBefore(row, children[index]);
    }
    return row;
  }

  function saveState(){
    const storage = getStorage();
    if (!storage) return;
    const payload = {
      version: 2,
      unit: SoapTool.state.currentUnit,
      oil_total_target: document.getElementById('oilTotalTarget').value || '',
      oils: serializeOils(),
      lye_form: {
        superfat: document.getElementById('lyeSuperfat')?.value || '5',
        lye_type: document.querySelector('input[name="lye_type"]:checked')?.value || 'NaOH',
        lye_purity: document.getElementById('lyePurity')?.value || '100',
        water_method: document.getElementById('waterMethod')?.value || 'percent',
        water_pct: document.getElementById('waterPct')?.value || '33',
        lye_concentration: document.getElementById('lyeConcentration')?.value || '33',
        water_ratio: document.getElementById('waterRatio')?.value || '2',
      },
      additives: {
        fragrances: serializeFragrances(),
        lactate_pct: document.getElementById('additiveLactatePct').value || '1',
        lactate_name: document.getElementById('additiveLactateName')?.value || '',
        lactate_gi: document.getElementById('additiveLactateGi')?.value || '',
        lactate_unit: document.getElementById('additiveLactateUnit')?.value || '',
        lactate_category: document.getElementById('additiveLactateCategory')?.value || '',
        sugar_pct: document.getElementById('additiveSugarPct').value || '1',
        sugar_name: document.getElementById('additiveSugarName')?.value || '',
        sugar_gi: document.getElementById('additiveSugarGi')?.value || '',
        sugar_unit: document.getElementById('additiveSugarUnit')?.value || '',
        sugar_category: document.getElementById('additiveSugarCategory')?.value || '',
        salt_pct: document.getElementById('additiveSaltPct').value || '0.5',
        salt_name: document.getElementById('additiveSaltName')?.value || '',
        salt_gi: document.getElementById('additiveSaltGi')?.value || '',
        salt_unit: document.getElementById('additiveSaltUnit')?.value || '',
        salt_category: document.getElementById('additiveSaltCategory')?.value || '',
        citric_pct: document.getElementById('additiveCitricPct').value || '0',
        citric_name: document.getElementById('additiveCitricName')?.value || '',
        citric_gi: document.getElementById('additiveCitricGi')?.value || '',
        citric_unit: document.getElementById('additiveCitricUnit')?.value || '',
        citric_category: document.getElementById('additiveCitricCategory')?.value || '',
      },
      mold: {
        water_weight: document.getElementById('moldWaterWeight').value || '',
        oil_pct: document.getElementById('moldOilPct').value || '65',
        shape: document.getElementById('moldShape')?.value || 'loaf',
        cylinder_correction: !!document.getElementById('moldCylinderCorrection')?.checked,
        cylinder_factor: document.getElementById('moldCylinderFactor')?.value || '0.85',
      },
      quality: {
        preset: document.getElementById('qualityPreset')?.value || 'balanced',
        focus: Array.from(document.querySelectorAll('.quality-focus:checked')).map(el => el.id),
      },
      lines: {
        ingredients: serializeLines('tool-ingredients', 'ingredient'),
        consumables: serializeLines('tool-consumables', 'consumable'),
        containers: serializeLines('tool-containers', 'container'),
      },
      bulk_oils: (SoapTool.bulkOilsModal && typeof SoapTool.bulkOilsModal.serializeSelection === 'function')
        ? SoapTool.bulkOilsModal.serializeSelection()
        : { mode: 'basics', selections: [] },
      updated_at: Date.now(),
    };
    try {
      storage.setItem(STATE_STORAGE_KEY, JSON.stringify(payload));
      const lastSaved = document.getElementById('soapLastSaved');
      if (lastSaved) lastSaved.textContent = formatTime(payload.updated_at);
      SoapTool.ui.showAutosaveToast();
    } catch (_) {}
  }

  function restoreState(){
    const storage = getStorage();
    if (!storage) return;
    const raw = storage.getItem(STATE_STORAGE_KEY);
    if (!raw) return;
    let data = null;
    try {
      data = JSON.parse(raw);
    } catch (_) {
      return;
    }
    if (!data || typeof data !== 'object') return;

    if (data.unit) {
      const unitInput = document.querySelector(`input[name="weight_unit"][value="${data.unit}"]`);
      if (unitInput) unitInput.checked = true;
      SoapTool.units.setUnit(data.unit, { skipConvert: true, skipAutoCalc: true });
    }

    if (data.oil_total_target !== undefined) {
      document.getElementById('oilTotalTarget').value = data.oil_total_target;
    }

    const oilRows = document.getElementById('oilRows');
    if (oilRows) {
      oilRows.innerHTML = '';
      const oils = Array.isArray(data.oils) && data.oils.length ? data.oils : [{}];
      oils.forEach(oil => {
        const row = SoapTool.oils.buildOilRow();
        row.querySelector('.oil-typeahead').value = oil.name || '';
        row.querySelector('.oil-grams').value = oil.grams || '';
        row.querySelector('.oil-percent').value = oil.percent || '';
        row.querySelector('.oil-sap-koh').value = oil.sap || '';
        row.querySelector('.oil-iodine').value = oil.iodine || '';
        row.querySelector('.oil-fatty').value = oil.fattyRaw || '';
        row.querySelector('.oil-gi-id').value = oil.gi || '';
        const unitEl = row.querySelector('.oil-default-unit');
        if (unitEl) unitEl.value = oil.defaultUnit || '';
        const categoryEl = row.querySelector('.oil-category');
        if (categoryEl) categoryEl.value = oil.categoryName || '';
        oilRows.appendChild(row);
      });
    }

    if (data.lye_form) {
      const superfat = document.getElementById('lyeSuperfat');
      if (superfat) superfat.value = data.lye_form.superfat || '5';
      const lyeType = document.querySelector(`input[name="lye_type"][value="${data.lye_form.lye_type || 'NaOH'}"]`);
      if (lyeType) lyeType.checked = true;
      const purity = document.getElementById('lyePurity');
      if (purity) purity.value = data.lye_form.lye_purity || '100';
      const waterMethod = document.getElementById('waterMethod');
      if (waterMethod) waterMethod.value = data.lye_form.water_method || 'percent';
      const waterPct = document.getElementById('waterPct');
      if (waterPct) waterPct.value = data.lye_form.water_pct || '33';
      const lyeConcentration = document.getElementById('lyeConcentration');
      if (lyeConcentration) lyeConcentration.value = data.lye_form.lye_concentration || '33';
      const waterRatio = document.getElementById('waterRatio');
      if (waterRatio) waterRatio.value = data.lye_form.water_ratio || '2';
      SoapTool.runner.applyLyeSelection();
    }

    if (data.additives) {
      const fragranceRows = document.getElementById('fragranceRows');
      if (fragranceRows && SoapTool.fragrances?.buildFragranceRow) {
        fragranceRows.innerHTML = '';
        const fragrances = Array.isArray(data.additives.fragrances) && data.additives.fragrances.length
          ? data.additives.fragrances
          : null;
        if (fragrances) {
          fragrances.forEach(item => {
            const row = SoapTool.fragrances.buildFragranceRow();
            row.querySelector('.fragrance-typeahead').value = item.name || '';
            row.querySelector('.fragrance-grams').value = item.grams || '';
            row.querySelector('.fragrance-percent').value = item.percent || '';
            row.querySelector('.fragrance-gi-id').value = item.gi || '';
            const unitEl = row.querySelector('.fragrance-default-unit');
            if (unitEl) unitEl.value = item.defaultUnit || '';
            const categoryEl = row.querySelector('.fragrance-category');
            if (categoryEl) categoryEl.value = item.categoryName || '';
            fragranceRows.appendChild(row);
          });
        } else if (data.additives.fragrance_pct || data.additives.fragrance_name || data.additives.fragrance_gi) {
          const row = SoapTool.fragrances.buildFragranceRow();
          row.querySelector('.fragrance-typeahead').value = data.additives.fragrance_name || '';
          row.querySelector('.fragrance-percent').value = data.additives.fragrance_pct || '3';
          row.querySelector('.fragrance-gi-id').value = data.additives.fragrance_gi || '';
          fragranceRows.appendChild(row);
        }
      }
      document.getElementById('additiveLactatePct').value = data.additives.lactate_pct || '1';
      const lactateName = document.getElementById('additiveLactateName');
      if (lactateName) lactateName.value = data.additives.lactate_name || '';
      const lactateGi = document.getElementById('additiveLactateGi');
      if (lactateGi) lactateGi.value = data.additives.lactate_gi || '';
      const lactateUnit = document.getElementById('additiveLactateUnit');
      if (lactateUnit) lactateUnit.value = data.additives.lactate_unit || '';
      const lactateCategory = document.getElementById('additiveLactateCategory');
      if (lactateCategory) lactateCategory.value = data.additives.lactate_category || '';
      document.getElementById('additiveSugarPct').value = data.additives.sugar_pct || '1';
      const sugarName = document.getElementById('additiveSugarName');
      if (sugarName) sugarName.value = data.additives.sugar_name || '';
      const sugarGi = document.getElementById('additiveSugarGi');
      if (sugarGi) sugarGi.value = data.additives.sugar_gi || '';
      const sugarUnit = document.getElementById('additiveSugarUnit');
      if (sugarUnit) sugarUnit.value = data.additives.sugar_unit || '';
      const sugarCategory = document.getElementById('additiveSugarCategory');
      if (sugarCategory) sugarCategory.value = data.additives.sugar_category || '';
      document.getElementById('additiveSaltPct').value = data.additives.salt_pct || '0.5';
      const saltName = document.getElementById('additiveSaltName');
      if (saltName) saltName.value = data.additives.salt_name || '';
      const saltGi = document.getElementById('additiveSaltGi');
      if (saltGi) saltGi.value = data.additives.salt_gi || '';
      const saltUnit = document.getElementById('additiveSaltUnit');
      if (saltUnit) saltUnit.value = data.additives.salt_unit || '';
      const saltCategory = document.getElementById('additiveSaltCategory');
      if (saltCategory) saltCategory.value = data.additives.salt_category || '';
      document.getElementById('additiveCitricPct').value = data.additives.citric_pct || '0';
      const citricName = document.getElementById('additiveCitricName');
      if (citricName) citricName.value = data.additives.citric_name || '';
      const citricGi = document.getElementById('additiveCitricGi');
      if (citricGi) citricGi.value = data.additives.citric_gi || '';
      const citricUnit = document.getElementById('additiveCitricUnit');
      if (citricUnit) citricUnit.value = data.additives.citric_unit || '';
      const citricCategory = document.getElementById('additiveCitricCategory');
      if (citricCategory) citricCategory.value = data.additives.citric_category || '';
    }

    if (data.mold) {
      document.getElementById('moldWaterWeight').value = data.mold.water_weight || '';
      document.getElementById('moldOilPct').value = data.mold.oil_pct || '65';
      const moldShape = document.getElementById('moldShape');
      if (moldShape) moldShape.value = data.mold.shape || 'loaf';
      const cylCorrection = document.getElementById('moldCylinderCorrection');
      if (cylCorrection) cylCorrection.checked = !!data.mold.cylinder_correction;
      const cylFactor = document.getElementById('moldCylinderFactor');
      if (cylFactor) cylFactor.value = data.mold.cylinder_factor || '0.85';
      const targetInput = document.getElementById('oilTotalTarget');
      if (SoapTool.mold?.syncMoldPctFromTarget && SoapTool.mold?.syncTargetFromMold) {
        const restoredTarget = SoapTool.units.toGrams(targetInput?.value);
        if (restoredTarget > 0) {
          SoapTool.mold.syncMoldPctFromTarget();
        } else {
          SoapTool.mold.syncTargetFromMold();
        }
      }
    }
    if (data.quality) {
      const preset = document.getElementById('qualityPreset');
      if (preset) {
        const desired = data.quality.preset || 'balanced';
        const option = Array.from(preset.options).find(opt => opt.value === desired);
        preset.value = option ? desired : 'balanced';
      }
      document.querySelectorAll('.quality-focus').forEach(el => {
        el.checked = Array.isArray(data.quality.focus) && data.quality.focus.includes(el.id);
      });
    }

    function restoreLines(wrapperId, items, kind){
      const wrapper = document.getElementById(wrapperId);
      if (!wrapper) return;
      wrapper.innerHTML = '';
      (items || []).forEach(item => {
        const row = SoapTool.runner.buildLineRow(kind);
        const input = row.querySelector('.tool-typeahead');
        const giHidden = row.querySelector('.tool-gi-id');
        const qtyEl = row.querySelector('.tool-qty');
        const unitEl = row.querySelector('.tool-unit');
        if (input) input.value = item.name || '';
        if (giHidden) giHidden.value = item.global_item_id || '';
        if (qtyEl && item.quantity !== undefined && item.quantity !== null) qtyEl.value = item.quantity;
        if (unitEl && item.unit) {
          const option = Array.from(unitEl.options).find(opt => opt.value === item.unit);
          if (option) unitEl.value = item.unit;
        }
        wrapper.appendChild(row);
      });
    }

    if (data.lines) {
      restoreLines('tool-ingredients', data.lines.ingredients, 'ingredient');
      restoreLines('tool-consumables', data.lines.consumables, 'consumable');
      restoreLines('tool-containers', data.lines.containers, 'container');
    }
    if (SoapTool.bulkOilsModal && typeof SoapTool.bulkOilsModal.restoreState === 'function') {
      SoapTool.bulkOilsModal.restoreState(data.bulk_oils || null);
    }

    SoapTool.runner.setWaterMethod();
    SoapTool.mold.updateMoldShapeUI();
    SoapTool.quality.updateQualityTargets();
    SoapTool.oils.updateOilTotals();
    SoapTool.additives.updateAdditivesOutput(SoapTool.oils.getTotalOilsGrams());
    SoapTool.mold.updateMoldSuggested();
    SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: false });
    if (data.updated_at) {
      const lastSaved = document.getElementById('soapLastSaved');
      if (lastSaved) lastSaved.textContent = formatTime(data.updated_at);
    }
    SoapTool.stages.updateStageStatuses();
    SoapTool.ui.showSoapAlert('info', 'Restored your last soap tool session from this device.', { dismissible: true, timeoutMs: 5000 });
  }

  let saveStateTimer = null;
  function queueStateSave(){
    if (saveStateTimer) clearTimeout(saveStateTimer);
    saveStateTimer = setTimeout(saveState, 350);
  }

  let autoCalcTimer = null;
  function queueAutoCalc(){
    if (autoCalcTimer) clearTimeout(autoCalcTimer);
    autoCalcTimer = setTimeout(() => {
      SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: false });
    }, 350);
  }

  SoapTool.storage = {
    saveState,
    restoreState,
    serializeLines,
    serializeOils,
    restoreOilRow,
    queueStateSave,
    queueAutoCalc,
  };
})(window);
