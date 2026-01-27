(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};

  const QUALITY_RANGES = {
    hardness: [29, 54],
    cleansing: [12, 22],
    conditioning: [44, 69],
    bubbly: [14, 46],
    creamy: [16, 48],
  };

  const QUALITY_HINTS = {
    hardness: 'Durable bar that resists mush.',
    cleansing: 'Higher values feel more stripping.',
    conditioning: 'Silky, moisturizing feel.',
    bubbly: 'Fluffy lather and big bubbles.',
    creamy: 'Stable, creamy lather.',
  };

  const QUALITY_FEEL_HINTS = {
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
  };

  const IODINE_RANGE = [41, 70];
  const IODINE_SCALE_MAX = 100;
  const INS_RANGE = [136, 170];
  const INS_SCALE_MAX = 250;

  const QUALITY_BASE = {
    hardness: (QUALITY_RANGES.hardness[0] + QUALITY_RANGES.hardness[1]) / 2,
    cleansing: (QUALITY_RANGES.cleansing[0] + QUALITY_RANGES.cleansing[1]) / 2,
    conditioning: (QUALITY_RANGES.conditioning[0] + QUALITY_RANGES.conditioning[1]) / 2,
    bubbly: (QUALITY_RANGES.bubbly[0] + QUALITY_RANGES.bubbly[1]) / 2,
    creamy: (QUALITY_RANGES.creamy[0] + QUALITY_RANGES.creamy[1]) / 2,
  };

  const QUALITY_PRESETS = {
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
  };

  const FATTY_BAR_COLORS = {
    lauric: 'var(--color-primary)',
    myristic: 'var(--color-info)',
    palmitic: 'var(--color-warning)',
    stearic: 'var(--color-muted)',
    ricinoleic: 'var(--color-info-hover)',
    oleic: 'var(--color-success)',
    linoleic: 'var(--color-primary-hover)',
    linolenic: 'var(--color-danger)',
  };

  const FATTY_DISPLAY_KEYS = [
    'lauric',
    'myristic',
    'palmitic',
    'stearic',
    'ricinoleic',
    'oleic',
    'linoleic',
    'linolenic',
  ];

  const OIL_TIP_RULES = [
    { match: /coconut|palm kernel|babassu|murumuru/i, tip: 'High lauric oils trace fast and feel cleansing; keep superfat >= 5%.' },
    { match: /olive|avocado|rice bran|canola|sunflower|safflower|almond|apricot|macadamia|camellia|grapeseed|hazelnut/i, tip: 'High-oleic liquid oils trace slowly and stay softer early on; allow a longer cure.' },
    { match: /castor/i, tip: 'Castor boosts lather but can feel sticky above 10-15%.' },
    { match: /cocoa|shea|mango|kokum|sal|illipe|tallow|lard|palm|stearic/i, tip: 'Hard fats/butters set up quickly; melt fully and keep batter warm for a smooth pour.' },
    { match: /beeswax|candelilla|carnauba|wax/i, tip: 'Waxes harden fast and can seize; keep usage low and add hot.' },
    { match: /hemp|flax|linseed|evening primrose|borage|rosehip|black currant|chia|pomegranate/i, tip: 'High-PUFA oils shorten shelf life; keep low and add antioxidant.' },
  ];

  const UNIT_FACTORS = { g: 1, oz: 28.3495, lb: 453.592 };

  const STAGE_CONFIGS = [
    { id: 1, tabId: 'soapStage1Tab', paneId: 'soapStage1Pane', required: true },
    { id: 2, tabId: 'soapStage2Tab', paneId: 'soapStage2Pane', required: true },
    { id: 3, tabId: 'soapStage3Tab', paneId: 'soapStage3Pane', required: true },
    { id: 4, tabId: 'soapStage4Tab', paneId: 'soapStage4Pane', required: true },
    { id: 5, tabId: 'soapStage5Tab', paneId: 'soapStage5Pane', required: false },
    { id: 6, tabId: 'soapStage6Tab', paneId: 'soapStage6Pane', required: false },
  ];

  const OIL_CATEGORY_SET = new Set(['Oils (Carrier & Fixed)', 'Butters & Solid Fats', 'Waxes']);
  const FRAGRANCE_CATEGORY_SET = new Set(['Essential Oils', 'Fragrance Oils']);
  const LACTATE_CATEGORY_SET = new Set(['Aqueous Solutions & Blends', 'Preservatives & Additives']);
  const SUGAR_CATEGORY_SET = new Set(['Sugars & Syrups']);
  const SALT_CATEGORY_SET = new Set(['Salts & Minerals']);
  const CITRIC_CATEGORY_SET = new Set(['Preservatives & Additives', 'Salts & Minerals', 'Aqueous Solutions & Blends']);

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
