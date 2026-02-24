# Image Upload Checklist

Last updated: 2026-02-24

This is the single checklist to track image uploads across the repo.

## How check-off works

Only mark an item as `[x]` when all of the following are true:

1. The file exists at the exact path shown below.
2. The file has a supported media extension:
   - Images: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.svg`, `.avif`
   - Videos: `.mp4`, `.webm`, `.ogg`, `.mov`, `.m4v`
3. The file is not empty (size > 0 bytes).
4. The file is not a placeholder/sample/temp image.

Placeholder policy:
- Do not use filenames/content intended as placeholders (for example: `placeholder`, `sample`, `demo`, `temp`, `test`).
- If a path is listed here, it should hold the final production asset.

---

## 1) Homepage images (actively referenced in templates)

### Quick rule for homepage

For homepage media slots, use **one file per object folder**:

- Tools: one file per tool folder
- Features: one file per feature folder
- Hero / CTA / Integrations / Testimonials: one file per named folder

### 1.1 Testimonial logos/photos (`app/templates/homepage.html`)

Put one file in each folder:

- [ ] `app/static/images/homepage/testimonials/customer-1/logo/<one-media-file>`
- [ ] `app/static/images/homepage/testimonials/customer-1/photo/<one-media-file>`
- [ ] `app/static/images/homepage/testimonials/customer-2/logo/<one-media-file>`
- [ ] `app/static/images/homepage/testimonials/customer-2/photo/<one-media-file>`
- [ ] `app/static/images/homepage/testimonials/customer-3/logo/<one-media-file>`
- [ ] `app/static/images/homepage/testimonials/customer-3/photo/<one-media-file>`

### 1.2 Open Graph images (already present)

- [x] `app/static/images/og/batchtrack-default-og.svg`
- [x] `app/static/images/og/batchtrack-pricing-og.svg`

---

## 2) Homepage planned asset slots (from `app/static/images/homepage/*/IMAGE_CREDITS.md`)

### 2.1 Hero

Put one file in:

- [ ] `app/static/images/homepage/hero/primary/<one-media-file>`

### 2.2 Features

The homepage feature cards now support folder-based uploads (no strict filename required).
Drop one media file into each folder below; the page will pick it up automatically.

Primary homepage feature cards (auto-rendered):

- [ ] `app/static/images/homepage/features/recipe-tracking/<one-media-file>`
- [ ] `app/static/images/homepage/features/fifo-inventory/<one-media-file>`
- [ ] `app/static/images/homepage/features/batch-in-progress/<one-media-file>`

Secondary "More Features" cards (auto-rendered):

- [ ] `app/static/images/homepage/features/more-fifo-inventory/<one-media-file>`
- [ ] `app/static/images/homepage/features/more-qr-code-labels/<one-media-file>`
- [ ] `app/static/images/homepage/features/more-timer-management/<one-media-file>`

Additional planned feature artwork folders:

- [ ] `app/static/images/homepage/features/analytics-dashboard/<one-media-file>`
- [ ] `app/static/images/homepage/features/timer-management/<one-media-file>`
- [ ] `app/static/images/homepage/features/qr-codes/<one-media-file>`
- [ ] `app/static/images/homepage/features/mobile-friendly/<one-media-file>`

### 2.3 Integrations

Put one file in each:

- [ ] `app/static/images/homepage/integrations/shopify/<one-media-file>`
- [ ] `app/static/images/homepage/integrations/etsy/<one-media-file>`
- [ ] `app/static/images/homepage/integrations/quickbooks/<one-media-file>`
- [ ] `app/static/images/homepage/integrations/zapier/<one-media-file>`
- [ ] `app/static/images/homepage/integrations/slack/<one-media-file>`

### 2.4 App screenshots/demo

Homepage final CTA media slot:

- [ ] `app/static/images/homepage/app-screenshots/final-cta/<one-media-file>`

### 2.5 Tool card image folders (homepage tools row)

The homepage tools row is folder-based. Put exactly **one** media file in each folder:

- `app/static/images/homepage/tools/`
- [ ] `app/static/images/homepage/tools/soap/<one-media-file>`
- [ ] `app/static/images/homepage/tools/lotions/<one-media-file>`
- [ ] `app/static/images/homepage/tools/baker/<one-media-file>`
- [ ] `app/static/images/homepage/tools/candles/<one-media-file>`
- [ ] `app/static/images/homepage/tools/herbal/<one-media-file>`

---

## 3) Help Center gallery images (`/help/how-it-works`)

Help gallery is now folder-based and supports image/video.
Drop files into each section folder; files are displayed in alphabetical order.

### 3.1 getting-started

- [ ] `app/static/images/help/getting-started/` (first 2 media files used)

### 3.2 inventory

- [ ] `app/static/images/help/inventory/` (first 3 media files used)

### 3.3 inventory-adjustments

- [ ] `app/static/images/help/inventory-adjustments/` (first 2 media files used)

### 3.4 recipes

- [ ] `app/static/images/help/recipes/` (first 2 media files used)

### 3.5 planning

- [ ] `app/static/images/help/planning/` (first 4 media files used)

### 3.6 costing

- [ ] `app/static/images/help/costing/` (first 2 media files used)

### 3.7 products

- [ ] `app/static/images/help/products/` (first 3 media files used)

### 3.8 labels-exports

- [ ] `app/static/images/help/labels-exports/` (first 2 media files used)

### 3.9 public-tools

- [ ] `app/static/images/help/public-tools/` (first 2 media files used)

---

## 4) Marketplace recipe cover uploads (runtime-generated)

These are uploaded through the app UI (not pre-seeded manually):

- Upload directory: `app/static/product_images/recipes/`
- Pattern: `app/static/product_images/recipes/<uuid>.<ext>`

Notes:
- `recipe.cover_image_path` and `recipe.cover_image_url` are populated by upload logic.
- Do not add placeholder images in this directory.

