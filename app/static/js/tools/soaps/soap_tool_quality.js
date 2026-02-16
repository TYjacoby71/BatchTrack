(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const {
    QUALITY_RANGES,
    QUALITY_HINTS,
    QUALITY_FEEL_HINTS,
    IODINE_RANGE,
    IODINE_SCALE_MAX,
    INS_RANGE,
    INS_SCALE_MAX,
    QUALITY_BASE,
    QUALITY_PRESETS,
    FATTY_BAR_COLORS,
    FATTY_DISPLAY_KEYS,
  } = SoapTool.constants;

  const { pulseValue, showSoapAlert } = SoapTool.ui;

  function setBarFill({ barId, fillId, value, max, label }){
    const bar = document.getElementById(barId);
    const fill = document.getElementById(fillId);
    if (!bar || !fill) return null;
    const safeValue = isFinite(value) ? value : 0;
    const clamped = Math.max(0, Math.min(max, safeValue));
    const width = max > 0 ? (clamped / max) * 100 : 0;
    fill.style.width = `${width}%`;
    bar.setAttribute('aria-valuemin', '0');
    bar.setAttribute('aria-valuemax', String(max));
    bar.setAttribute('aria-valuenow', clamped.toFixed(1));
    if (label) {
      bar.setAttribute('aria-label', label);
    }
    return { bar, fill, value: safeValue };
  }

  function setQualityBarColor(fill, value, range){
    if (!fill || !range) return;
    fill.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-secondary');
    if (!isFinite(value)) {
      fill.classList.add('bg-secondary');
      return;
    }
    if (value < range[0]) {
      fill.classList.add('bg-warning');
    } else if (value > range[1]) {
      fill.classList.add('bg-danger');
    } else {
      fill.classList.add('bg-success');
    }
  }

  function setScaledBar(barId, fillId, value, range, max, label){
    const result = setBarFill({ barId, fillId, value, max, label });
    if (!result) return;
    setQualityBarColor(result.fill, value, range);
  }

  function setQualityRangeBars(){
    const rangeConfig = {
      hardness: { range: QUALITY_RANGES.hardness, scale: 100 },
      cleansing: { range: QUALITY_RANGES.cleansing, scale: 100 },
      conditioning: { range: QUALITY_RANGES.conditioning, scale: 100 },
      bubbly: { range: QUALITY_RANGES.bubbly, scale: 100 },
      creamy: { range: QUALITY_RANGES.creamy, scale: 100 },
      iodine: { range: IODINE_RANGE, scale: IODINE_SCALE_MAX },
      ins: { range: INS_RANGE, scale: INS_SCALE_MAX },
    };
    Object.entries(rangeConfig).forEach(([key, config]) => {
      const [min, max] = config.range;
      const scale = config.scale;
      const name = key.charAt(0).toUpperCase() + key.slice(1);
      const barId = key === 'iodine' ? 'iodineBar' : (key === 'ins' ? 'insBar' : `quality${name}Bar`);
      const safe = document.getElementById(`quality${name}Safe`);
      if (safe) {
        const startPct = Math.max(0, Math.min(100, (min / scale) * 100));
        const widthPct = Math.max(0, Math.min(100, ((max - min) / scale) * 100));
        safe.style.left = `${startPct}%`;
        safe.style.width = `${widthPct}%`;
        safe.title = `Safe range ${round(min, 0)}-${round(max, 0)}`;
      }
      const bar = document.getElementById(barId);
      if (bar) {
        bar.dataset.safeRange = `${round(min, 0)}-${round(max, 0)}`;
      }
      const minLabel = document.getElementById(`quality${name}RangeMin`);
      const maxLabel = document.getElementById(`quality${name}RangeMax`);
      if (minLabel) minLabel.textContent = round(min, 0);
      if (maxLabel) maxLabel.textContent = round(max, 0);
    });
  }

  function updateQualitySliders(qualities, superfat){
    const hardness = clamp(qualities.hardness || 0, 0, 100);
    const bubbly = clamp(qualities.bubbly || 0, 0, 100);
    const conditioning = clamp(qualities.conditioning || 0, 0, 100);
    const greasyScore = clamp(conditioning + (superfat || 0) * 3, 0, 100);
    const hardEl = document.getElementById('feelHardness');
    const bubblyEl = document.getElementById('feelBubbly');
    const conditioningEl = document.getElementById('feelConditioning');
    const greasyEl = document.getElementById('feelGreasy');
    if (hardEl) hardEl.value = round(hardness, 1);
    if (bubblyEl) bubblyEl.value = round(bubbly, 1);
    if (conditioningEl) conditioningEl.value = round(conditioning, 1);
    if (greasyEl) greasyEl.value = round(greasyScore, 1);
  }

  function updateFattyBar(fattyPercent){
    FATTY_DISPLAY_KEYS.forEach(key => {
      const el = document.getElementById(`fattyBar${key.charAt(0).toUpperCase()}${key.slice(1)}`);
      if (!el) return;
      const value = clamp(toNumber(fattyPercent[key]), 0, 100);
      const width = value;
      el.style.width = `${width}%`;
      el.style.backgroundColor = FATTY_BAR_COLORS[key] || 'var(--color-muted)';
      el.title = `${key.charAt(0).toUpperCase()}${key.slice(1)}: ${round(value, 1)}%`;
    });
  }

  function getQualityTargets(){
    const preset = document.getElementById('qualityPreset')?.value || 'balanced';
    const focusEls = Array.from(document.querySelectorAll('.quality-focus:checked'));
    if (preset === 'none' && !focusEls.length) return null;
    const base = preset === 'none'
      ? { ...QUALITY_BASE }
      : (QUALITY_PRESETS[preset] ? { ...QUALITY_PRESETS[preset] } : { ...QUALITY_BASE });
    focusEls.forEach(el => {
      const attr = el.dataset.attr;
      const direction = el.dataset.direction;
      const range = QUALITY_RANGES[attr];
      if (!range) return;
      base[attr] = direction === 'low' ? range[0] : range[1];
    });
    return base;
  }

  function updateQualityTargets(){
    const targets = getQualityTargets();
    const markers = {
      hardness: document.getElementById('qualityHardnessTarget'),
      cleansing: document.getElementById('qualityCleansingTarget'),
      conditioning: document.getElementById('qualityConditioningTarget'),
      bubbly: document.getElementById('qualityBubblyTarget'),
      creamy: document.getElementById('qualityCreamyTarget'),
      iodine: document.getElementById('iodineTarget'),
      ins: document.getElementById('insTarget'),
    };
    Object.entries(markers).forEach(([key, marker]) => {
      if (!marker) return;
      const labelEl = document.getElementById(`${marker.id}Label`);
      if (!targets) {
        marker.classList.add('d-none');
        if (labelEl) labelEl.textContent = '';
        return;
      }
      const value = toNumber(targets[key]);
      if (!isFinite(value)) {
        marker.classList.add('d-none');
        if (labelEl) labelEl.textContent = '';
        return;
      }
      const scaleMax = key === 'iodine' ? IODINE_SCALE_MAX : (key === 'ins' ? INS_SCALE_MAX : 100);
      const clamped = clamp(value, 0, scaleMax);
      marker.classList.remove('d-none');
      marker.style.left = `${(clamped / scaleMax) * 100}%`;
      marker.setAttribute('aria-label', `Apply ${key} target`);
      marker.setAttribute('role', 'button');
      marker.setAttribute('tabindex', '0');
      marker.title = `Target ${key}: ${round(value, 1)}`;
      if (labelEl) {
        labelEl.textContent = round(value, 1);
      }
    });
  }

  async function applyQualityTargets(){
    const targets = getQualityTargets();
    if (!targets) {
      showSoapAlert('info', 'Select a quality target to nudge the blend.', { dismissible: true, timeoutMs: 5000 });
      return;
    }
    const rows = Array.from(document.querySelectorAll('#oilRows .oil-row'));
    const oils = rows.map((row, rowIndex) => {
      const grams = SoapTool.units.toGrams(row.querySelector('.oil-grams')?.value);
      const fattyRaw = row.querySelector('.oil-fatty')?.value || '';
      const name = row.querySelector('.oil-typeahead')?.value?.trim() || null;
      const sapKoh = toNumber(row.querySelector('.oil-sap-koh')?.value);
      const iodine = toNumber(row.querySelector('.oil-iodine')?.value);
      let fattyProfile = null;
      if (fattyRaw) {
        try {
          fattyProfile = JSON.parse(fattyRaw);
        } catch (_) {
          fattyProfile = null;
        }
      }
      return { row, rowIndex, name, grams, sapKoh, iodine, fattyProfile };
    }).filter(item => item.grams > 0);

    if (!oils.length) {
      showSoapAlert('warning', 'Add oils before nudging toward a target.', { dismissible: true, timeoutMs: 5000 });
      return;
    }
    const targetOils = SoapTool.oils.getOilTargetGrams() || oils.reduce((sum, oil) => sum + oil.grams, 0);
    const requestPayload = {
      oils: oils.map(item => ({
        row_index: item.rowIndex,
        name: item.name,
        grams: item.grams,
        sap_koh: item.sapKoh,
        iodine: item.iodine,
        fatty_profile: item.fattyProfile,
      })),
      targets,
      target_oils_g: targetOils,
    };
    const response = await SoapTool.runnerService?.applyQualityNudge?.(requestPayload);
    if (!response || response.ok !== true) {
      const errorMessage = response?.error || 'Unable to nudge blend right now. Please try again.';
      showSoapAlert('warning', errorMessage, { dismissible: true, timeoutMs: 6000 });
      return;
    }
    const warnings = Array.isArray(response.warnings) ? response.warnings : [];
    warnings.forEach(message => {
      showSoapAlert('info', message, { dismissible: true, timeoutMs: 5000 });
    });
    const adjustedRows = Array.isArray(response.adjusted_rows) ? response.adjusted_rows : [];
    adjustedRows.forEach(item => {
      const index = Number(item?.index);
      const grams = toNumber(item?.grams);
      if (!isFinite(index) || index < 0 || !isFinite(grams)) return;
      const row = rows[index];
      if (!row) return;
      const gramsInput = row.querySelector('.oil-grams');
      const pctInput = row.querySelector('.oil-percent');
      if (gramsInput) gramsInput.value = grams > 0 ? round(SoapTool.units.fromGrams(grams), 2) : '';
      if (pctInput && targetOils > 0) {
        const percent = (grams / targetOils) * 100;
        pctInput.value = percent > 0 ? round(percent, 2) : '';
      }
    });
    SoapTool.oils.updateOilTotals();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
    showSoapAlert('info', response.message || 'Blend nudged toward selected targets. Re-check results and adjust as needed.', { dismissible: true, timeoutMs: 6000 });
  }

  function updateQualitiesDisplay(data){
    const {
      qualities,
      fattyPercent,
      coveragePct,
      iodine,
      ins,
      sapAvg,
      superfat,
      warnings: serviceWarnings,
    } = data;

    const hasCoverage = coveragePct > 0;

    function setQuality(name, value){
      const label = document.getElementById(`quality${name}Value`);
      const hintEl = document.getElementById(`quality${name}Hint`);
      if (!label) return;
      label.textContent = hasCoverage && isFinite(value) ? round(value, 1) : '--';
      pulseValue(label);
      const rangeKey = name.toLowerCase();
      const range = QUALITY_RANGES[rangeKey];
      const fillResult = setBarFill({
        barId: `quality${name}Bar`,
        fillId: `quality${name}Fill`,
        value: hasCoverage ? value : 0,
        max: 100,
        label: name
      });
      if (fillResult && range) {
        setQualityBarColor(fillResult.fill, value, range);
        if (hasCoverage && isFinite(value)) {
          fillResult.bar.title = `${name}: ${round(value, 1)} (safe ${range[0]}-${range[1]}). ${QUALITY_HINTS[rangeKey] || ''}`.trim();
        } else {
          fillResult.bar.title = `${name}: -- (safe ${range[0]}-${range[1]}). ${QUALITY_HINTS[rangeKey] || ''}`.trim();
        }
      }
      if (hintEl && range) {
        if (!hasCoverage || !isFinite(value)) {
          hintEl.textContent = '';
        } else if (value < range[0]) {
          hintEl.textContent = QUALITY_FEEL_HINTS[rangeKey]?.low || '';
        } else if (value > range[1]) {
          hintEl.textContent = QUALITY_FEEL_HINTS[rangeKey]?.high || '';
        } else {
          hintEl.textContent = '';
        }
      }
    }

    setQuality('Hardness', qualities.hardness);
    setQuality('Cleansing', qualities.cleansing);
    setQuality('Conditioning', qualities.conditioning);
    setQuality('Bubbly', qualities.bubbly);
    setQuality('Creamy', qualities.creamy);

    const coverageNote = document.getElementById('fattyCoverageNote');
    if (coverageNote) {
      coverageNote.textContent = coveragePct > 0
        ? `Fatty acid coverage: ${round(coveragePct, 1)}% of oils`
        : 'Fatty acid coverage: not enough data yet';
    }

    const iodineEl = document.getElementById('iodineValue');
    const insEl = document.getElementById('insValue');
    const sapEl = document.getElementById('sapAvgValue');
    if (iodineEl) {
      iodineEl.textContent = iodine > 0 ? round(iodine, 1) : '--';
      pulseValue(iodineEl);
    }
    if (insEl) {
      insEl.textContent = ins > 0 ? round(ins, 1) : '--';
      pulseValue(insEl);
    }
    if (sapEl) {
      sapEl.textContent = sapAvg > 0 ? round(sapAvg, 1) : '--';
      pulseValue(sapEl);
    }
    setScaledBar('iodineBar', 'iodineFill', iodine, IODINE_RANGE, IODINE_SCALE_MAX, 'Iodine');
    setScaledBar('insBar', 'insFill', ins, INS_RANGE, INS_SCALE_MAX, 'INS');

    const sat = (fattyPercent.lauric || 0) + (fattyPercent.myristic || 0) + (fattyPercent.palmitic || 0) + (fattyPercent.stearic || 0);
    const unsat = (fattyPercent.ricinoleic || 0) + (fattyPercent.oleic || 0) + (fattyPercent.linoleic || 0) + (fattyPercent.linolenic || 0);
    const ratioEl = document.getElementById('fattySatRatioResult');
    if (ratioEl) {
      ratioEl.textContent = (sat + unsat) > 0 ? `${round(sat, 0)}:${round(unsat, 0)}` : '--';
      pulseValue(ratioEl);
    }

    FATTY_DISPLAY_KEYS.forEach(key => {
      const id = `fatty${key.charAt(0).toUpperCase()}${key.slice(1)}`;
      const value = fattyPercent[key];
      document.getElementById(id).textContent = hasCoverage && value ? `${round(value, 1)}%` : '--';
    });
    updateQualitySliders(qualities, superfat || 0);
    updateFattyBar(fattyPercent);
    updateQualityTargets();

    const warnings = Array.isArray(serviceWarnings) ? serviceWarnings.slice() : [];
    const warningBox = document.getElementById('soapQualityWarnings');
    if (!warningBox) {
      SoapTool.layout.scheduleStageHeightSync();
      return;
    }
    if (warnings.length) {
      warningBox.classList.remove('d-none');
      SoapTool.ui.renderTitledList(warningBox, 'Guidance & flags:', warnings);
    } else {
      warningBox.classList.add('d-none');
      warningBox.textContent = '';
    }
    SoapTool.layout.scheduleStageHeightSync();
  }

  function initQualityTooltips(){
    document.querySelectorAll('.soap-quality-help').forEach(btn => {
      const key = btn.dataset.quality;
      if (QUALITY_HINTS[key]) {
        btn.setAttribute('title', QUALITY_HINTS[key]);
      }
    });
    if (window.bootstrap?.Tooltip) {
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        bootstrap.Tooltip.getOrCreateInstance(el);
      });
    }
  }

  SoapTool.quality = {
    setQualityRangeBars,
    updateQualityTargets,
    applyQualityTargets,
    updateQualitiesDisplay,
    initQualityTooltips,
  };
})(window);
