# SEO Metadata Style Guide (BatchTrack.com)

## Purpose
Keep metadata consistent, maker-first, and batch-first. This guide is the prompt
template for page titles, descriptions, and open graph defaults across the app.

## Brand + Tone
- **Brand name:** BatchTrack.com (use this exact spelling in titles).
- **Design premise:** Neurodivergent-friendly, calm, step-by-step.
- **Language:** Maker and batch first. Use craft terms, not corporate terms.
- **Avoid:** Profit-first or enterprise language (e.g., "maximize revenue",
  "monetize", "pipeline", "enterprise workflow", "synergies").

## Required Metadata Fields
Set these per page when possible:
- `page_title`
- `page_description`
- `canonical_url` (when the URL is not the request base or has filters)
- `page_og_image` (only when a specific share image exists)

The base layout uses these variables to populate the SEO tags.

## Title Format
**Default:** `BatchTrack.com | [Page Name]`

Guidelines:
- 50–65 characters preferred.
- Use a clear maker-first page name.
- Include the tool or workflow name when relevant.

## Description Format
Guidelines:
- 120–160 characters preferred.
- Lead with the maker outcome or batch outcome.
- Include tool names for overview pages.
- Mention "neurodivergent-friendly" where it fits naturally.
- Avoid corporate language and keep the tone supportive.

## Maker + Batch First Language
Prefer:
- "maker workflows"
- "batch planning"
- "recipe formulation"
- "inventory-first"
- "yield and quality"

Avoid:
- "monetization"
- "enterprise"
- "pipeline"
- "workflow optimization"

## Examples

### Maker Tools Index
```
page_title: "BatchTrack.com | Maker Tools"
page_description: "BatchTrack.com maker tools: Soap Formulator live now; candle, lotion/cosmetic, herbalist, and baker tools coming soon. Neurodivergent-friendly."
```

### Soap Formulator
```
page_title: "BatchTrack.com | Soap Formulator"
page_description: "BatchTrack.com Soap Formulator for makers: build batch-first recipes with lye, oils, superfat, and quality targets. Neurodivergent-friendly."
```

### Recipe Detail
```
page_title: "BatchTrack.com | [Recipe Name]"
page_description: "BatchTrack.com recipe details for makers: ingredients, yield, batch history, and lineage notes in a calm, batch-first layout."
```

## Open Graph Notes
Only set `page_og_image` when a specific, high-quality share image exists for
the page. Otherwise let the default behavior stand to avoid stale images.
