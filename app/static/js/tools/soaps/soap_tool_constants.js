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
    quality_hints: {
      hardness: 'Durable bar that resists mush.',
      cleansing: 'Higher values feel more stripping.',
      conditioning: 'Silky, moisturizing feel.',
      bubbly: 'Fluffy lather and big bubbles.',
      creamy: 'Stable, creamy lather.',
    },
    quality_feel_hints: {
      hardness: {
        low: 'Soft bar, slower unmold.',
        ok: 'Balanced hardness for daily use.',
        high: 'Very hard bar, can feel brittle.',
      },
      cleansing: {
        low: 'Very mild cleansing.',
        ok: 'Balanced cleansing.',
        high: 'Strong cleansing, can be drying.',
      },
      conditioning: {
        low: 'Less conditioning feel.',
        ok: 'Smooth and conditioning.',
        high: 'Very conditioning, may feel oily.',
      },
      bubbly: {
        low: 'Low bubbly lather.',
        ok: 'Balanced bubbly lather.',
        high: 'Very bubbly, big foam.',
      },
      creamy: {
        low: 'Light creamy lather.',
        ok: 'Creamy and stable.',
        high: 'Dense creamy lather.',
      },
    },
    iodine_range: [41, 70],
    iodine_scale_max: 100,
    ins_range: [136, 170],
    ins_scale_max: 250,
    quality_base: {
      hardness: 41.5,
      cleansing: 17,
      conditioning: 56.5,
      bubbly: 30,
      creamy: 32,
    },
    quality_presets: {
      balanced: {
        hardness: 40,
        cleansing: 15,
        conditioning: 55,
        bubbly: 25,
        creamy: 25,
        iodine: 55,
        ins: 160,
      },
      bubbly: {
        hardness: 35,
        cleansing: 20,
        conditioning: 50,
        bubbly: 35,
        creamy: 25,
        iodine: 60,
        ins: 150,
      },
      creamy: {
        hardness: 45,
        cleansing: 12,
        conditioning: 60,
        bubbly: 20,
        creamy: 35,
        iodine: 50,
        ins: 155,
      },
      hard: {
        hardness: 50,
        cleansing: 18,
        conditioning: 48,
        bubbly: 22,
        creamy: 28,
        iodine: 45,
        ins: 165,
      },
      gentle: {
        hardness: 35,
        cleansing: 10,
        conditioning: 65,
        bubbly: 15,
        creamy: 20,
        iodine: 65,
        ins: 140,
      },
      castile: {
        hardness: 20,
        cleansing: 5,
        conditioning: 75,
        bubbly: 10,
        creamy: 15,
        iodine: 80,
        ins: 110,
      },
      shampoo: {
        hardness: 30,
        cleansing: 22,
        conditioning: 50,
        bubbly: 30,
        creamy: 25,
        iodine: 60,
        ins: 145,
      },
      utility: {
        hardness: 70,
        cleansing: 50,
        conditioning: 20,
        bubbly: 50,
        creamy: 20,
        iodine: 10,
        ins: 250,
      },
      luxury: {
        hardness: 55,
        cleansing: 10,
        conditioning: 55,
        bubbly: 15,
        creamy: 40,
        iodine: 50,
        ins: 150,
      },
      palmFree: {
        hardness: 42,
        cleansing: 16,
        conditioning: 58,
        bubbly: 22,
        creamy: 28,
        iodine: 55,
        ins: 155,
      },
    },
    fatty_bar_colors: {
      lauric: 'var(--color-primary)',
      myristic: 'var(--color-info)',
      palmitic: 'var(--color-warning)',
      stearic: 'var(--color-muted)',
      ricinoleic: 'var(--color-info-hover)',
      oleic: 'var(--color-success)',
      linoleic: 'var(--color-primary-hover)',
      linolenic: 'var(--color-danger)',
    },
    fatty_display_keys: [
      'lauric',
      'myristic',
      'palmitic',
      'stearic',
      'ricinoleic',
      'oleic',
      'linoleic',
      'linolenic',
    ],
    oil_tip_rules: [
      { pattern: 'coconut|palm kernel|babassu|murumuru', flags: 'i', tip: 'High lauric oils trace fast and feel cleansing; keep superfat >= 5%.' },
      { pattern: 'olive|avocado|rice bran|canola|sunflower|safflower|almond|apricot|macadamia|camellia|grapeseed|hazelnut', flags: 'i', tip: 'High-oleic liquid oils trace slowly and stay softer early on; allow a longer cure.' },
      { pattern: 'castor', flags: 'i', tip: 'Castor boosts lather but can feel sticky above 10-15%.' },
      { pattern: 'cocoa|shea|mango|kokum|sal|illipe|tallow|lard|palm|stearic', flags: 'i', tip: 'Hard fats/butters set up quickly; melt fully and keep batter warm for a smooth pour.' },
      { pattern: 'beeswax|candelilla|carnauba|wax', flags: 'i', tip: 'Waxes harden fast and can seize; keep usage low and add hot.' },
      { pattern: 'hemp|flax|linseed|evening primrose|borage|rosehip|black currant|chia|pomegranate', flags: 'i', tip: 'High-PUFA oils shorten shelf life; keep low and add antioxidant.' },
    ],
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
  const qualityHintSource = { ...FALLBACK_POLICY.quality_hints, ...asObject(injectedPolicy.quality_hints) };
  const qualityFeelHintSource = { ...FALLBACK_POLICY.quality_feel_hints, ...asObject(injectedPolicy.quality_feel_hints) };
  const qualityBaseSource = { ...FALLBACK_POLICY.quality_base, ...asObject(injectedPolicy.quality_base) };
  const qualityPresetSource = { ...FALLBACK_POLICY.quality_presets, ...asObject(injectedPolicy.quality_presets) };
  const fattyColorSource = { ...FALLBACK_POLICY.fatty_bar_colors, ...asObject(injectedPolicy.fatty_bar_colors) };
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
    hardness: qualityHintSource.hardness || FALLBACK_POLICY.quality_hints.hardness,
    cleansing: qualityHintSource.cleansing || FALLBACK_POLICY.quality_hints.cleansing,
    conditioning: qualityHintSource.conditioning || FALLBACK_POLICY.quality_hints.conditioning,
    bubbly: qualityHintSource.bubbly || FALLBACK_POLICY.quality_hints.bubbly,
    creamy: qualityHintSource.creamy || FALLBACK_POLICY.quality_hints.creamy,
  };

  const QUALITY_FEEL_HINTS = {
    hardness: { ...FALLBACK_POLICY.quality_feel_hints.hardness, ...asObject(qualityFeelHintSource.hardness) },
    cleansing: { ...FALLBACK_POLICY.quality_feel_hints.cleansing, ...asObject(qualityFeelHintSource.cleansing) },
    conditioning: { ...FALLBACK_POLICY.quality_feel_hints.conditioning, ...asObject(qualityFeelHintSource.conditioning) },
    bubbly: { ...FALLBACK_POLICY.quality_feel_hints.bubbly, ...asObject(qualityFeelHintSource.bubbly) },
    creamy: { ...FALLBACK_POLICY.quality_feel_hints.creamy, ...asObject(qualityFeelHintSource.creamy) },
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

  const QUALITY_PRESETS = {};
  Object.entries(qualityPresetSource).forEach(([presetName, presetValues]) => {
    if (!presetValues || typeof presetValues !== 'object') return;
    QUALITY_PRESETS[presetName] = { ...presetValues };
  });

  const FATTY_BAR_COLORS = { ...fattyColorSource };
  const FATTY_DISPLAY_KEYS = asStringArray(
    injectedPolicy.fatty_display_keys,
    FALLBACK_POLICY.fatty_display_keys
  );

  const OIL_TIP_RULES = (
    Array.isArray(injectedPolicy.oil_tip_rules) ? injectedPolicy.oil_tip_rules : FALLBACK_POLICY.oil_tip_rules
  )
    .map(rule => {
      const source = asObject(rule);
      const pattern = typeof source.pattern === 'string' ? source.pattern : '';
      const flags = typeof source.flags === 'string' ? source.flags : 'i';
      const tip = typeof source.tip === 'string' ? source.tip : '';
      if (!pattern || !tip) return null;
      try {
        return { match: new RegExp(pattern, flags), tip };
      } catch (_) {
        return null;
      }
    })
    .filter(Boolean);

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
  };
})(window);
