# Image Upload Checklist

Last updated: 2026-02-23

This is the single checklist to track image uploads across the repo.

## How check-off works

Only mark an item as `[x]` when all of the following are true:

1. The file exists at the exact path shown below.
2. The file has a real image extension (`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.svg`, `.avif`).
3. The file is not empty (size > 0 bytes).
4. The file is not a placeholder/sample/temp image.

Placeholder policy:
- Do not use filenames/content intended as placeholders (for example: `placeholder`, `sample`, `demo`, `temp`, `test`).
- If a path is listed here, it should hold the final production asset.

---

## 1) Homepage images (actively referenced in templates)

### 1.1 Testimonial logos/photos (`app/templates/homepage.html`)

- [ ] `app/static/images/homepage/testimonials/customer-1-logo.png`
- [ ] `app/static/images/homepage/testimonials/customer-1-photo.jpg`
- [ ] `app/static/images/homepage/testimonials/customer-2-logo.png`
- [ ] `app/static/images/homepage/testimonials/customer-2-photo.jpg`
- [ ] `app/static/images/homepage/testimonials/customer-3-logo.png`
- [ ] `app/static/images/homepage/testimonials/customer-3-photo.jpg`

### 1.2 Open Graph images (already present)

- [x] `app/static/images/og/batchtrack-default-og.svg`
- [x] `app/static/images/og/batchtrack-pricing-og.svg`

---

## 2) Homepage planned asset slots (from `app/static/images/homepage/*/IMAGE_CREDITS.md`)

### 2.1 Hero

- [ ] `app/static/images/homepage/hero/hero-background.jpg`
- [ ] `app/static/images/homepage/hero/hero-overlay.png`

### 2.2 Features

- [ ] `app/static/images/homepage/features/batch-tracking.png`
- [ ] `app/static/images/homepage/features/fifo-inventory.png`
- [ ] `app/static/images/homepage/features/analytics-dashboard.png`
- [ ] `app/static/images/homepage/features/timer-management.png`
- [ ] `app/static/images/homepage/features/qr-codes.png`
- [ ] `app/static/images/homepage/features/mobile-friendly.png`

### 2.3 Integrations

- [ ] `app/static/images/homepage/integrations/shopify-logo.png`
- [ ] `app/static/images/homepage/integrations/etsy-logo.png`
- [ ] `app/static/images/homepage/integrations/quickbooks-logo.png`
- [ ] `app/static/images/homepage/integrations/zapier-logo.png`
- [ ] `app/static/images/homepage/integrations/slack-logo.png`

### 2.4 App screenshots/demo

- [ ] `app/static/images/homepage/app-screenshots/dashboard-screenshot.png`
- [ ] `app/static/images/homepage/app-screenshots/mobile-app-screenshot.png`
- [ ] `app/static/images/homepage/app-screenshots/batch-view-screenshot.png`
- [ ] `app/static/images/homepage/app-screenshots/demo-video-thumbnail.jpg`

---

## 3) Help Center gallery images (`/help/how-it-works`)

Template expects this naming pattern:
`app/static/images/help/<section-slug>/<section-slug>-<index>.png`

### 3.1 getting-started

- [ ] `app/static/images/help/getting-started/getting-started-1.png`
- [ ] `app/static/images/help/getting-started/getting-started-2.png`

### 3.2 inventory

- [ ] `app/static/images/help/inventory/inventory-1.png`
- [ ] `app/static/images/help/inventory/inventory-2.png`
- [ ] `app/static/images/help/inventory/inventory-3.png`

### 3.3 inventory-adjustments

- [ ] `app/static/images/help/inventory-adjustments/inventory-adjustments-1.png`
- [ ] `app/static/images/help/inventory-adjustments/inventory-adjustments-2.png`

### 3.4 recipes

- [ ] `app/static/images/help/recipes/recipes-1.png`
- [ ] `app/static/images/help/recipes/recipes-2.png`

### 3.5 planning

- [ ] `app/static/images/help/planning/planning-1.png`
- [ ] `app/static/images/help/planning/planning-2.png`
- [ ] `app/static/images/help/planning/planning-3.png`
- [ ] `app/static/images/help/planning/planning-4.png`

### 3.6 costing

- [ ] `app/static/images/help/costing/costing-1.png`
- [ ] `app/static/images/help/costing/costing-2.png`

### 3.7 products

- [ ] `app/static/images/help/products/products-1.png`
- [ ] `app/static/images/help/products/products-2.png`
- [ ] `app/static/images/help/products/products-3.png`

### 3.8 labels-exports

- [ ] `app/static/images/help/labels-exports/labels-exports-1.png`
- [ ] `app/static/images/help/labels-exports/labels-exports-2.png`

### 3.9 public-tools

- [ ] `app/static/images/help/public-tools/public-tools-1.png`
- [ ] `app/static/images/help/public-tools/public-tools-2.png`

---

## 4) Marketplace recipe cover uploads (runtime-generated)

These are uploaded through the app UI (not pre-seeded manually):

- Upload directory: `app/static/product_images/recipes/`
- Pattern: `app/static/product_images/recipes/<uuid>.<ext>`

Notes:
- `recipe.cover_image_path` and `recipe.cover_image_url` are populated by upload logic.
- Do not add placeholder images in this directory.

