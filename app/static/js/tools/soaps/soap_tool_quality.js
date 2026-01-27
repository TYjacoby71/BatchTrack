(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { formatWeight, formatPercent } = SoapTool.units;
  const { computeFattyAcids, computeQualities, computeOilQualityScores } = SoapTool.calc;
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

  function setProgress(id, value, label){
    const bar = document.getElementById(id);
    if (!bar) return;
    if (!isFinite(value)) {
      bar.style.width = '0%';
      return;
    }
    const clamped = Math.max(0, Math.min(100, value));
    bar.style.width = `${clamped}%`;
    bar.setAttribute('aria-valuemin', '0');
    bar.setAttribute('aria-valuemax', '100');
    bar.setAttribute('aria-valuenow', clamped.toFixed(1));
    if (label) {
      bar.setAttribute('aria-label', label);
    }
  }

  function setQualityBarColor(bar, value, range){
    if (!bar || !range) return;
    bar.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-secondary');
    if (!isFinite(value)) {
      bar.classList.add('bg-secondary');
      return;
    }
    if (value < range[0]) {
      bar.classList.add('bg-warning');
    } else if (value > range[1]) {
      bar.classList.add('bg-danger');
    } else {
      bar.classList.add('bg-success');
    }
  }

  function setScaledBar(id, value, range, max, label){
    const bar = document.getElementById(id);
    if (!bar) return;
    const safeValue = isFinite(value) ? value : 0;
    const clamped = Math.max(0, Math.min(max, safeValue));
    const width = max > 0 ? (clamped / max) * 100 : 0;
    bar.style.width = `${width}%`;
    bar.setAttribute('aria-valuemin', '0');
    bar.setAttribute('aria-valuemax', String(max));
    bar.setAttribute('aria-valuenow', clamped.toFixed(1));
    if (label) {
      bar.setAttribute('aria-label', label);
    }
    setQualityBarColor(bar, safeValue, range);
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
      const start = document.getElementById(`quality${name}RangeStart`);
      const ideal = document.getElementById(`quality${name}RangeIdeal`);
      const end = document.getElementById(`quality${name}RangeEnd`);
      if (start && ideal && end) {
        const startPct = Math.max(0, Math.min(100, (min / scale) * 100));
        const idealPct = Math.max(0, Math.min(100, ((max - min) / scale) * 100));
        const endPct = Math.max(0, Math.min(100, 100 - ((max / scale) * 100)));
        start.style.width = `${startPct}%`;
        ideal.style.width = `${idealPct}%`;
        end.style.width = `${endPct}%`;
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
    const totals = {};
    let total = 0;
    FATTY_DISPLAY_KEYS.forEach(key => {
      const value = clamp(toNumber(fattyPercent[key]), 0, 100);
      totals[key] = value;
      total += value;
    });
    FATTY_DISPLAY_KEYS.forEach(key => {
      const el = document.getElementById(`fattyBar${key.charAt(0).toUpperCase()}${key.slice(1)}`);
      if (!el) return;
      const width = total > 0 ? (totals[key] / total) * 100 : 0;
      el.style.width = `${width}%`;
      el.style.backgroundColor = FATTY_BAR_COLORS[key] || 'var(--color-muted)';
      el.title = `${key.charAt(0).toUpperCase()}${key.slice(1)}: ${round(totals[key], 1)}%`;
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

  function applyQualityTargets(){
    const targets = getQualityTargets();
    if (!targets) {
      showSoapAlert('info', 'Select a quality target to nudge the blend.', { dismissible: true, timeoutMs: 5000 });
      return;
    }
    const rows = Array.from(document.querySelectorAll('#oilRows .oil-row'));
    const oils = rows.map(row => {
      const grams = SoapTool.units.toGrams(row.querySelector('.oil-grams')?.value);
      const fattyRaw = row.querySelector('.oil-fatty')?.value || '';
      let fattyProfile = null;
      if (fattyRaw) {
        try {
          fattyProfile = JSON.parse(fattyRaw);
        } catch (_) {
          fattyProfile = null;
        }
      }
      return { row, grams, fattyProfile };
    }).filter(item => item.grams > 0);

    if (!oils.length) {
      showSoapAlert('warning', 'Add oils before nudging toward a target.', { dismissible: true, timeoutMs: 5000 });
      return;
    }

    const fatty = computeFattyAcids(oils.map(oil => ({
      grams: oil.grams,
      fattyProfile: oil.fattyProfile,
    })));
    const currentQualities = computeQualities(fatty.percent);
    const deltas = {
      hardness: clamp((targets.hardness - currentQualities.hardness) / 100, -1, 1),
      cleansing: clamp((targets.cleansing - currentQualities.cleansing) / 100, -1, 1),
      conditioning: clamp((targets.conditioning - currentQualities.conditioning) / 100, -1, 1),
      bubbly: clamp((targets.bubbly - currentQualities.bubbly) / 100, -1, 1),
      creamy: clamp((targets.creamy - currentQualities.creamy) / 100, -1, 1),
    };

    const totalOils = oils.reduce((sum, oil) => sum + oil.grams, 0);
    const adjusted = [];
    let totalAdjusted = 0;
    const strength = 0.8;
    const missingFatty = oils.filter(oil => !oil.fattyProfile || typeof oil.fattyProfile !== 'object').length;
    if (missingFatty === oils.length) {
      showSoapAlert('warning', 'None of the selected oils have fatty acid data, so targets cannot be applied.', { dismissible: true, timeoutMs: 6000 });
      return;
    }
    if (missingFatty) {
      showSoapAlert('info', 'Some oils are missing fatty acid data. The nudge will only use oils with profiles.', { dismissible: true, timeoutMs: 5000 });
    }

    oils.forEach(oil => {
      const scores = computeOilQualityScores(oil.fattyProfile);
      const adjustment = (deltas.hardness * scores.hardness)
        + (deltas.cleansing * scores.cleansing)
        + (deltas.conditioning * scores.conditioning)
        + (deltas.bubbly * scores.bubbly)
        + (deltas.creamy * scores.creamy);
      const factor = clamp(1 + adjustment * strength, 0.2, 1.8);
      const next = oil.grams * factor;
      adjusted.push({ row: oil.row, grams: next });
      totalAdjusted += next;
    });

    if (totalAdjusted <= 0) {
      showSoapAlert('warning', 'Unable to adjust blend with current data.', { dismissible: true, timeoutMs: 5000 });
      return;
    }

    const scale = totalOils / totalAdjusted;
    const target = SoapTool.oils.getOilTargetGrams() || totalOils;
    adjusted.forEach(item => {
      const grams = item.grams * scale;
      const gramsInput = item.row.querySelector('.oil-grams');
      const pctInput = item.row.querySelector('.oil-percent');
      if (gramsInput) gramsInput.value = grams > 0 ? round(SoapTool.units.fromGrams(grams), 2) : '';
      if (pctInput && target > 0) {
        const percent = (grams / target) * 100;
        pctInput.value = percent > 0 ? round(percent, 2) : '';
      }
    });

    SoapTool.oils.updateOilTotals();
    SoapTool.storage.queueStateSave();
    SoapTool.storage.queueAutoCalc();
    showSoapAlert('info', 'Blend nudged toward selected targets. Re-check results and adjust as needed.', { dismissible: true, timeoutMs: 6000 });
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
      waterData,
      additives,
      oils,
      totalOils,
    } = data;

    const hasCoverage = coveragePct > 0;

    function setQuality(name, value){
      const label = document.getElementById(`quality${name}Value`);
      const bar = document.getElementById(`quality${name}Bar`);
      const hintEl = document.getElementById(`quality${name}Hint`);
      if (!label) return;
      label.textContent = hasCoverage && isFinite(value) ? round(value, 1) : '--';
      pulseValue(label);
      setProgress(`quality${name}Bar`, hasCoverage ? value : 0, name);
      const rangeKey = name.toLowerCase();
      const range = QUALITY_RANGES[rangeKey];
      if (bar && range) {
        setQualityBarColor(bar, value, range);
        if (hasCoverage && isFinite(value)) {
          bar.title = `${name}: ${round(value, 1)} (ideal ${range[0]}-${range[1]}). ${QUALITY_HINTS[rangeKey] || ''}`.trim();
        } else {
          bar.title = `${name}: -- (ideal ${range[0]}-${range[1]}). ${QUALITY_HINTS[rangeKey] || ''}`.trim();
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
          hintEl.textContent = QUALITY_FEEL_HINTS[rangeKey]?.ok || '';
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
    setScaledBar('iodineBar', iodine, IODINE_RANGE, IODINE_SCALE_MAX, 'Iodine');
    setScaledBar('insBar', ins, INS_RANGE, INS_SCALE_MAX, 'INS');

    const sat = (fattyPercent.lauric || 0) + (fattyPercent.myristic || 0) + (fattyPercent.palmitic || 0) + (fattyPercent.stearic || 0);
    const unsat = (fattyPercent.ricinoleic || 0) + (fattyPercent.oleic || 0) + (fattyPercent.linoleic || 0) + (fattyPercent.linolenic || 0);
    const ratioEl = document.getElementById('fattySatRatio');
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

    const warnings = [];
    const pufa = (fattyPercent.linoleic || 0) + (fattyPercent.linolenic || 0);
    const lauricMyristic = (fattyPercent.lauric || 0) + (fattyPercent.myristic || 0);
    const concentration = waterData?.lyeConcentration || 0;

    if (iodine > 70) warnings.push('High iodine value can mean softer bars or faster rancidity.');
    if (ins > 0 && ins < 136) warnings.push('INS is low (below 136); bars may be soft or have shorter shelf life.');
    if (ins > 170) warnings.push('INS is high; bars may be brittle or overly cleansing.');
    if (hasCoverage && pufa > 15) warnings.push('High linoleic/linolenic (PUFA) increases DOS risk; consider antioxidant or more stable oils.');
    if (hasCoverage && isFinite(qualities.hardness) && qualities.hardness < QUALITY_RANGES.hardness[0]) warnings.push('Hardness looks low; bars may be soft or slow to unmold.');
    if (hasCoverage && isFinite(qualities.cleansing) && qualities.cleansing > QUALITY_RANGES.cleansing[1]) warnings.push('Cleansing is high; consider more conditioning oils.');
    if (hasCoverage && isFinite(qualities.bubbly) && qualities.bubbly < QUALITY_RANGES.bubbly[0]) warnings.push('Bubbly lather is low; add 5-10% castor or coconut for more foam.');
    if (hasCoverage && lauricMyristic > 35) warnings.push('High lauric/myristic (coconut/palm kernel/babassu) can be drying or crumbly; cut warm and keep superfat at least 5%.');
    if (superfat !== undefined && superfat >= 15) warnings.push('Superfat is high (15%+); bars can be softer/greasy and may have shorter shelf life.');
    if (concentration > 0 && concentration < 27) warnings.push('Very high water: slower trace and more shrinkage/ash. Consider a higher lye concentration for a firmer bar sooner.');
    if (concentration > 40) warnings.push('Low water: faster trace and more heat. Work quickly and avoid overheating.');
    if (additives?.fragrancePct > 3) warnings.push('Fragrance load above 3% can accelerate trace; follow supplier usage rates.');
    if (additives?.citricPct > 0) warnings.push('Citric acid consumes lye; extra lye has been added. Recheck if you also use vinegar or other acids.');
    if (Array.isArray(oils) && totalOils > 0) {
      const positiveOils = oils.filter(oil => oil.grams > 0);
      if (positiveOils.length === 1) {
        warnings.push('Single-oil recipe; consider blending for balanced hardness, cleansing, and longevity.');
      } else if (positiveOils.length > 1) {
        const maxShare = Math.max(...positiveOils.map(oil => (oil.grams / totalOils) * 100));
        if (maxShare >= 90) warnings.push('One oil is over 90% of the formula; consider blending for balance.');
      }
    }
    const warningBox = document.getElementById('soapQualityWarnings');
    if (warnings.length) {
      warningBox.classList.remove('d-none');
      warningBox.innerHTML = `<strong>Guidance & flags:</strong><ul class="mb-0">${warnings.map(w => `<li>${w}</li>`).join('')}</ul>`;
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
