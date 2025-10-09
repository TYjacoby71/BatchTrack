# Exports

This document describes export routes, formats, and data sources for both recipe-based and public tool-based previews.

## Routes

- Recipe (auth + org-scoped):
  - HTML preview
    - /exports/recipe/<id>/soap-inci
    - /exports/recipe/<id>/candle-label
    - /exports/recipe/<id>/baker-sheet
    - /exports/recipe/<id>/lotion-inci
  - CSV
    - /exports/recipe/<id>/soap-inci.csv
    - /exports/recipe/<id>/candle-label.csv
    - /exports/recipe/<id>/baker-sheet.csv
    - /exports/recipe/<id>/lotion-inci.csv
  - PDF
    - /exports/recipe/<id>/soap-inci.pdf
    - /exports/recipe/<id>/candle-label.pdf
    - /exports/recipe/<id>/baker-sheet.pdf
    - /exports/recipe/<id>/lotion-inci.pdf

- Public tools (no auth, session-based):
  - HTML preview
    - /exports/tool/soaps/inci
    - /exports/tool/candles/label
    - /exports/tool/baker/sheet
    - /exports/tool/lotions/inci
  - CSV
    - /exports/tool/soaps/inci.csv
    - /exports/tool/candles/label.csv
    - /exports/tool/baker/sheet.csv
    - /exports/tool/lotions/inci.csv
  - PDF
    - /exports/tool/soaps/inci.pdf
    - /exports/tool/candles/label.pdf
    - /exports/tool/baker/sheet.pdf
    - /exports/tool/lotions/inci.pdf

## Formats

- CSV: simple comma-separated tables, UTF-8
- PDF: currently returns the HTML bytes with application/pdf content type; upgradeable to real PDF via ReportLab/WeasyPrint later

## Data sources

- Recipes: `Recipe` model, including `recipe.category_data` for category-specific content
- Batches (future): `batch.plan_snapshot.category_extension` for planned values
- Public tools: `session['tool_draft']` with `category_data` and line arrays
