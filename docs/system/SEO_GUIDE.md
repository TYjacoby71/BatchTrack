# SEO and Metadata Style Guide for BatchTrack.com

Version: 1.1  
Last updated: February 2026  
Core principle: Every page must feel calm, maker-first, and batch-first. Metadata should help real makers find us when searching for tools that understand their craft, not corporate workflows.

## 1. Brand Voice Rules (Use These Words/Phrases)
Must-have tone:
- batch-first / batch-focused
- maker / small-batch maker
- craft / creating / making
- calm / step-by-step / neurodivergent-friendly
- FIFO lot tracking / batch lineage / batch lifecycle
- recipe formulation / batch planning
- curated inventory / enriched library

Never use:
- monetize / revenue / profit-first
- enterprise / pipeline / workflow optimization
- maximize / scale your business
- synergies / KPIs / ROI

## 2. Title Rules (50 to 60 characters ideal, max 70)
Format:
`BatchTrack.com | [Clear Maker-First Page Name]`

Examples:
- BatchTrack.com | Soap Formulator & Batch Calculator
- BatchTrack.com | Free Maker Tools (Soap, Candles, Fermentation)
- BatchTrack.com | FIFO Lot Tracking & Batch Lineage
- BatchTrack.com | BatchBot - AI for Small-Batch Makers

Guidelines:
- Always lead with "BatchTrack.com | " (brand recognition in SERPs).
- Use the most searched maker term for the page (e.g., "Soap Formulator" > "Soap Calculator").
- Include one strong keyword naturally (soap, batch tracking, FIFO, BatchBot).
- End with a benefit if space allows ("& Batch Calculator", "for Makers").

## 3. Meta Description Rules (120 to 160 characters ideal, max 170)
Format:
Lead with maker outcome -> mention key features -> end with calm or neurodivergent-friendly signal.

Examples:
- "Build soap batches with confidence: live lye calculator, superfat control, quality targets, FIFO lots. Neurodivergent-friendly design at BatchTrack.com."
- "Free tools for makers: soap formulator live now, candle/cosmetic/fermentation tools coming soon. Batch-first, calm interface."
- "Track every ingredient lot and batch lifecycle with FIFO and full lineage. Made for small-batch creators who love the craft."

Guidelines:
- Start with benefit or outcome ("Build...", "Track...", "Create...").
- Include 1 to 2 exact-match keywords (soap formulator, FIFO lot tracking, BatchBot).
- End with an emotional anchor ("for makers who love the craft", "calm, neurodivergent-friendly").
- Never keyword-stuff or repeat words unnaturally.

## 4. Open Graph / Social Sharing (OG Tags)
Only override when you have a specific high-quality image for the page. Otherwise use site-wide defaults.

Required when set:
- og:title -> same as page_title
- og:description -> same as meta description or slightly shorter
- og:image -> 1200x630 px, maker-focused screenshot (calculator UI, BatchBot demo, FIFO view)
- og:url -> canonical URL

## 5. Keyword Strategy (No Stuffing - Helpful Content First)
Do:
- Use 3 to 8 natural keywords per page in headings, first paragraph, alt text.
- Target long-tail maker searches:
  - "soap batch calculator with superfat"
  - "FIFO lot tracking for candle makers"
  - "free fermentation recipe tool"
  - "batch lineage for small batch soap"
  - "BatchBot AI inventory onboarding"

Do not:
- Hide text (white-on-white, display:none, font-size:0)
- Stuff lists of 100+ keywords
- Create doorway pages (thin pages just for keywords)

## 6. Page-Specific Metadata Examples
Homepage (/)
```
page_title = "BatchTrack.com | Batch-First Production & Inventory for Makers"
page_description = "BatchTrack helps small-batch makers track recipes, FIFO lots, batch lifecycle, and output products. Free tools for soap, candles, fermentation, and more. Calm, neurodivergent-friendly design."
```

Tools Index (/tools)
```
page_title = "BatchTrack.com | Free Maker Tools & Calculators"
page_description = "Free batch tools for soap makers, candle makers, fermentation, cosmetics, and more. Push recipes to your BatchTrack workspace. Live soap formulator available now - more coming soon."
```

Soap Formulator (/tools/soap)
```
page_title = "BatchTrack.com | Soap Formulator & Batch Calculator"
page_description = "Free soap formulator: build recipes with lye, oils, superfat, quality targets, and FIFO lot tracking. Batch-first design made for makers. Try now - no signup required."
```

Pricing (/pricing)
```
page_title = "BatchTrack.com | Pricing for Small-Batch Makers"
page_description = "Simple pricing for makers: Hobbyist, Enthusiast, Fanatic. Unlimited batches on Fanatic. Lifetime deals available. Batch-first tools, not finance-first."
```

## Final Notes for Engineers
- Use Jinja variables consistently (`page_title`, `page_description`, etc.) in `layout.html` head.
- Add canonical tags (`<link rel="canonical" href="{{ canonical_url }}">`) when needed.
- No hidden keyword blocks - ever.
- Run Lighthouse SEO audit after changes (aim for 90+ score).
- Add schema markup (SoftwareApplication + FAQ) to the homepage and tool pages for rich results.
