(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};

  const FALLBACK_POLICY = {
    quality_ranges: {
      hardness: [29, 54],
      cleansing: [12, 22],
      conditioning: [44, 69],
      bubbly: [14, 46],
      creamy: [16, 48],
    },
    iodine_range: [41, 70],
    iodine_scale_max: 100,
    ins_range: [136, 170],
    ins_scale_max: 250,
    quality_base: {},
    fatty_display_keys: ['lauric', 'myristic', 'palmitic', 'stearic', 'ricinoleic', 'oleic', 'linoleic', 'linolenic'],
    unit_factors: { g: 1, oz: 28.3495, lb: 453.592 },
    stage_configs: [
      { id: 1, tab_id: 'soapStage1Tab', pane_id: 'soapStage1Pane', required: true },
      { id: 2, tab_id: 'soapStage2Tab', pane_id: 'soapStage2Pane', required: true },
      { id: 3, tab_id: 'soapStage3Tab', pane_id: 'soapStage3Pane', required: true },
      { id: 4, tab_id: 'soapStage4Tab', pane_id: 'soapStage4Pane', required: false },
      { id: 5, tab_id: 'soapStage5Tab', pane_id: 'soapStage5Pane', required: false },
    ],
    ingredient_category_filters: {
      oils: ['Oils (Carrier & Fixed)', 'Butters & Solid Fats', 'Waxes'],
      fragrances: ['Essential Oils', 'Fragrance Oils'],
      lactate_additives: ['Aqueous Solutions & Blends', 'Preservatives & Additives'],
      sugar_additives: ['Sugars & Syrups'],
      salt_additives: ['Salts & Minerals'],
      citric_additives: ['Preservatives & Additives', 'Salts & Minerals', 'Aqueous Solutions & Blends'],
    },
    citric_lye_factors: { NaOH: 0.624, KOH: 0.71 },
    default_inputs: {
      unit: 'g',
      mold_oil_pct: 65,
      mold_shape: 'loaf',
      mold_cylinder_correction: false,
      mold_cylinder_factor: 0.85,
      lye_type: 'NaOH',
      water_method: 'percent',
      superfat_pct: 5,
      lye_purity_pct: 100,
      water_pct: 33,
      lye_concentration_pct: 33,
      water_ratio: 2,
      additive_lactate_pct: 1,
      additive_sugar_pct: 1,
      additive_salt_pct: 0.5,
      additive_citric_pct: 0,
      quality_preset: 'balanced',
      fragrance_pct: 3,
    },
  };

  function asObject(value){
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
    return value;
  }

  function asStringArray(value, fallback = []){
    if (!Array.isArray(value)) return fallback.slice();
    return value
      .map(entry => typeof entry === 'string' ? entry.trim() : '')
      .filter(Boolean);
  }

  function asRange(value, fallback){
    if (!Array.isArray(value) || value.length < 2) return fallback.slice();
    const min = Number(value[0]);
    const max = Number(value[1]);
    if (!isFinite(min) || !isFinite(max)) return fallback.slice();
    return [min, max];
  }

  function asNumber(value, fallback){
    const parsed = Number(value);
    return isFinite(parsed) ? parsed : fallback;
  }

  const injectedPolicy = asObject(window.soapToolPolicy);
  const qualityRangeSource = { ...FALLBACK_POLICY.quality_ranges, ...asObject(injectedPolicy.quality_ranges) };
  const qualityHintSource = asObject(injectedPolicy.quality_hints);
  const qualityFeelHintSource = asObject(injectedPolicy.quality_feel_hints);
  const qualityBaseSource = { ...FALLBACK_POLICY.quality_base, ...asObject(injectedPolicy.quality_base) };
  const qualityPresetSource = asObject(injectedPolicy.quality_presets);
  const fattyColorSource = asObject(injectedPolicy.fatty_bar_colors);
  const unitFactorSource = { ...FALLBACK_POLICY.unit_factors, ...asObject(injectedPolicy.unit_factors) };
  const categoryFilterSource = {
    ...FALLBACK_POLICY.ingredient_category_filters,
    ...asObject(injectedPolicy.ingredient_category_filters),
  };

  const QUALITY_RANGES = {
    hardness: asRange(qualityRangeSource.hardness, FALLBACK_POLICY.quality_ranges.hardness),
    cleansing: asRange(qualityRangeSource.cleansing, FALLBACK_POLICY.quality_ranges.cleansing),
    conditioning: asRange(qualityRangeSource.conditioning, FALLBACK_POLICY.quality_ranges.conditioning),
    bubbly: asRange(qualityRangeSource.bubbly, FALLBACK_POLICY.quality_ranges.bubbly),
    creamy: asRange(qualityRangeSource.creamy, FALLBACK_POLICY.quality_ranges.creamy),
  };

  const QUALITY_HINTS = {
    hardness: qualityHintSource.hardness || '',
    cleansing: qualityHintSource.cleansing || '',
    conditioning: qualityHintSource.conditioning || '',
    bubbly: qualityHintSource.bubbly || '',
    creamy: qualityHintSource.creamy || '',
  };

  const QUALITY_FEEL_HINTS = {
    hardness: asObject(qualityFeelHintSource.hardness),
    cleansing: asObject(qualityFeelHintSource.cleansing),
    conditioning: asObject(qualityFeelHintSource.conditioning),
    bubbly: asObject(qualityFeelHintSource.bubbly),
    creamy: asObject(qualityFeelHintSource.creamy),
  };

  const IODINE_RANGE = asRange(injectedPolicy.iodine_range, FALLBACK_POLICY.iodine_range);
  const IODINE_SCALE_MAX = asNumber(injectedPolicy.iodine_scale_max, FALLBACK_POLICY.iodine_scale_max);
  const INS_RANGE = asRange(injectedPolicy.ins_range, FALLBACK_POLICY.ins_range);
  const INS_SCALE_MAX = asNumber(injectedPolicy.ins_scale_max, FALLBACK_POLICY.ins_scale_max);

  const QUALITY_BASE = {
    hardness: asNumber(qualityBaseSource.hardness, (QUALITY_RANGES.hardness[0] + QUALITY_RANGES.hardness[1]) / 2),
    cleansing: asNumber(qualityBaseSource.cleansing, (QUALITY_RANGES.cleansing[0] + QUALITY_RANGES.cleansing[1]) / 2),
    conditioning: asNumber(qualityBaseSource.conditioning, (QUALITY_RANGES.conditioning[0] + QUALITY_RANGES.conditioning[1]) / 2),
    bubbly: asNumber(qualityBaseSource.bubbly, (QUALITY_RANGES.bubbly[0] + QUALITY_RANGES.bubbly[1]) / 2),
    creamy: asNumber(qualityBaseSource.creamy, (QUALITY_RANGES.creamy[0] + QUALITY_RANGES.creamy[1]) / 2),
  };

  const QUALITY_PRESETS = { balanced: { ...QUALITY_BASE } };
  Object.entries(qualityPresetSource).forEach(([presetName, presetValues]) => {
    if (!presetValues || typeof presetValues !== 'object') return;
    QUALITY_PRESETS[presetName] = { ...presetValues };
  });

  const FATTY_BAR_COLORS = { ...fattyColorSource };
  const FATTY_DISPLAY_KEYS = asStringArray(
    injectedPolicy.fatty_display_keys,
    FALLBACK_POLICY.fatty_display_keys
  );

  const OIL_TIP_RULES = [];

  const UNIT_FACTORS = {
    g: asNumber(unitFactorSource.g, FALLBACK_POLICY.unit_factors.g),
    oz: asNumber(unitFactorSource.oz, FALLBACK_POLICY.unit_factors.oz),
    lb: asNumber(unitFactorSource.lb, FALLBACK_POLICY.unit_factors.lb),
  };

  const stageRows = Array.isArray(injectedPolicy.stage_configs)
    ? injectedPolicy.stage_configs
    : FALLBACK_POLICY.stage_configs;
  const mappedStageConfigs = stageRows
    .map((entry, index) => {
      const stage = asObject(entry);
      const fallback = FALLBACK_POLICY.stage_configs[index] || {};
      const id = asNumber(stage.id, asNumber(fallback.id, index + 1));
      const tabId = stage.tabId || stage.tab_id || fallback.tabId || fallback.tab_id;
      const paneId = stage.paneId || stage.pane_id || fallback.paneId || fallback.pane_id;
      if (!tabId || !paneId) return null;
      return {
        id,
        tabId,
        paneId,
        required: typeof stage.required === 'boolean' ? stage.required : !!fallback.required,
      };
    })
    .filter(Boolean);
  const STAGE_CONFIGS = mappedStageConfigs.length
    ? mappedStageConfigs
    : FALLBACK_POLICY.stage_configs.map(stage => ({
      id: stage.id,
      tabId: stage.tab_id,
      paneId: stage.pane_id,
      required: !!stage.required,
    }));

  const OIL_CATEGORY_SET = new Set(asStringArray(categoryFilterSource.oils, FALLBACK_POLICY.ingredient_category_filters.oils));
  const FRAGRANCE_CATEGORY_SET = new Set(asStringArray(categoryFilterSource.fragrances, FALLBACK_POLICY.ingredient_category_filters.fragrances));
  const LACTATE_CATEGORY_SET = new Set(asStringArray(categoryFilterSource.lactate_additives, FALLBACK_POLICY.ingredient_category_filters.lactate_additives));
  const SUGAR_CATEGORY_SET = new Set(asStringArray(categoryFilterSource.sugar_additives, FALLBACK_POLICY.ingredient_category_filters.sugar_additives));
  const SALT_CATEGORY_SET = new Set(asStringArray(categoryFilterSource.salt_additives, FALLBACK_POLICY.ingredient_category_filters.salt_additives));
  const CITRIC_CATEGORY_SET = new Set(asStringArray(categoryFilterSource.citric_additives, FALLBACK_POLICY.ingredient_category_filters.citric_additives));
  const citricFactors = { ...FALLBACK_POLICY.citric_lye_factors, ...asObject(injectedPolicy.citric_lye_factors) };
  const CITRIC_LYE_FACTORS = {
    NaOH: asNumber(citricFactors.NaOH, FALLBACK_POLICY.citric_lye_factors.NaOH),
    KOH: asNumber(citricFactors.KOH, FALLBACK_POLICY.citric_lye_factors.KOH),
  };
  const defaultInputsSource = { ...FALLBACK_POLICY.default_inputs, ...asObject(injectedPolicy.default_inputs) };
  const DEFAULT_INPUTS = {
    unit: defaultInputsSource.unit || FALLBACK_POLICY.default_inputs.unit,
    moldOilPct: asNumber(defaultInputsSource.mold_oil_pct, FALLBACK_POLICY.default_inputs.mold_oil_pct),
    moldShape: defaultInputsSource.mold_shape || FALLBACK_POLICY.default_inputs.mold_shape,
    moldCylinderCorrection: !!defaultInputsSource.mold_cylinder_correction,
    moldCylinderFactor: asNumber(defaultInputsSource.mold_cylinder_factor, FALLBACK_POLICY.default_inputs.mold_cylinder_factor),
    lyeType: defaultInputsSource.lye_type || FALLBACK_POLICY.default_inputs.lye_type,
    waterMethod: defaultInputsSource.water_method || FALLBACK_POLICY.default_inputs.water_method,
    superfatPct: asNumber(defaultInputsSource.superfat_pct, FALLBACK_POLICY.default_inputs.superfat_pct),
    lyePurityPct: asNumber(defaultInputsSource.lye_purity_pct, FALLBACK_POLICY.default_inputs.lye_purity_pct),
    waterPct: asNumber(defaultInputsSource.water_pct, FALLBACK_POLICY.default_inputs.water_pct),
    lyeConcentrationPct: asNumber(defaultInputsSource.lye_concentration_pct, FALLBACK_POLICY.default_inputs.lye_concentration_pct),
    waterRatio: asNumber(defaultInputsSource.water_ratio, FALLBACK_POLICY.default_inputs.water_ratio),
    additiveLactatePct: asNumber(defaultInputsSource.additive_lactate_pct, FALLBACK_POLICY.default_inputs.additive_lactate_pct),
    additiveSugarPct: asNumber(defaultInputsSource.additive_sugar_pct, FALLBACK_POLICY.default_inputs.additive_sugar_pct),
    additiveSaltPct: asNumber(defaultInputsSource.additive_salt_pct, FALLBACK_POLICY.default_inputs.additive_salt_pct),
    additiveCitricPct: asNumber(defaultInputsSource.additive_citric_pct, FALLBACK_POLICY.default_inputs.additive_citric_pct),
    qualityPreset: defaultInputsSource.quality_preset || FALLBACK_POLICY.default_inputs.quality_preset,
    fragrancePct: asNumber(defaultInputsSource.fragrance_pct, FALLBACK_POLICY.default_inputs.fragrance_pct),
  };

  SoapTool.constants = {
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
    OIL_TIP_RULES,
    UNIT_FACTORS,
    STAGE_CONFIGS,
    OIL_CATEGORY_SET,
    FRAGRANCE_CATEGORY_SET,
    LACTATE_CATEGORY_SET,
    SUGAR_CATEGORY_SET,
    SALT_CATEGORY_SET,
    CITRIC_CATEGORY_SET,
    CITRIC_LYE_FACTORS,
    DEFAULT_INPUTS,
  };
})(window);
