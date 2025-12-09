## BatchTrack SEO Acceleration Plan

This plan treats BatchTrack like a SaaS product that needs a modern SEO surface across the app, public library, and marketing site. The goal is to expose the global item dataset, capture intent with tools/help content, and tighten the technical plumbing so Google can crawl, index, and rank the experience.

### 1. Open Up the Global Library
- **Whitelist the routes**: add `global_library_bp.global_library` (and upcoming detail routes) to `RouteAccessConfig.PUBLIC_ENDPOINTS` so `/global-items` and derived pages are crawlable without auth.
- **Add deterministic slugs**: extend `GlobalItem` with a slug column (e.g., `name -> kebab-case`) and backfill existing rows. Enforce uniqueness per `item_type`.
- **Detail pages**: create `/global-items/<slug>` renderers that load metadata, stats, and related items. Each page needs unique `<title>`, meta description, canonical tag, and internal breadcrumbs.
- **Structured data**: embed JSON-LD (`Product`, `HowTo`, `FAQ`, `DefinedTerm`) built from `metadata_json`, density, SAP values, etc. Reuse `/global-items/<id>/stats` so the page shows authoritative numbers.
- **Internal links**: from the table view, link to the slug page; from recipes/inventory forms, link “View spec” to the public page so crawlers discover it through authenticated surfaces (they can’t tap modals).

### 2. Marketing Site Integration
- **Deploy the MDX corpus**: ship the Next.js marketing site described in `marketing/README.md`, sourcing `marketing/content/**`. Each MDX file becomes a prerendered route (`/`, `/features`, `/help/*`, `/docs/*`, `/changelog`).
- **Surface the library**: during build, export global items to JSON (id, slug, metadata, stats) and hydrate static pages under `/library`, `/library/type/<type>`, `/library/category/<category>`. Cross-link back to `/global-items/<slug>` inside the app.
- **Tools landing pages**: for every calculator (`/tools/soap`, `/tools/candles`, etc.), create marketing companions with long-form copy, screenshots, FAQs, and CTAs so we can rank for calculator queries.

### 3. Technical SEO Plumbing
- **Head tags**: update `app/templates/layout.html` to accept per-route `page_title`, `page_description`, canonical URL, and OG/Twitter tags. Fallback to sensible defaults for authenticated surfaces.
- **Robots & sitemap**: replace `marketing/public/robots.txt` + `sitemap.xml` placeholders with generated files. Sitemaps should be segmented (core pages, help, library index, library items, calculators) and include the production domain.
- **Open Graph / social cards**: add OG defaults on both the marketing site and `layout.html`, plus item-specific cards (title, description, hero image) generated from `metadata_json`.
- **Performance & UX**: ensure `/global-items` responses are cacheable (HTTP caching or CDN) and support pagination/Lazy load so Googlebot can crawl >500 items. Provide server-rendered lists before JS enhancements.

### 4. Content & Authority Programs
- **Library enrichment sweeps**: populate `metadata_json` for every global item with:
  - `meta_title`, `meta_description`
  - copy blocks: “Uses”, “Packaging guidance”, “Recommended containers”, “Safety notes”
  - FAQs and supplier references (non-indexed outbound links with `rel="nofollow sponsored"` when appropriate).
- **Topical clusters**: for each vertical (soap, candles, lotions, baking, herbal), publish:
  - Category landing pages describing the workflow
  - Tool walkthroughs linking to the calculators
  - Library highlight articles (“Top 10 soy waxes”, etc.) that link to individual items
  - Case studies / spotlights (source from `data/spotlights.json`)
- **Email + social reuse**: repurpose new articles into `marketing/content/emails/*` to keep the nurture sequences aligned with SEO campaigns.

### 5. Analytics & Measurement
- **Search Console + Analytics**: verify the marketing domain and app subdomain separately. Submit all sitemap indices after each deploy.
- **Event tracking**: instrument outbound clicks from library pages to signup/login and track conversions tied to organic landing pages.
- **Log coverage**: add health dashboards (could live in Developer > Analytics) to monitor crawl status codes, sitemap freshness, and top landing pages sourced from organic traffic.

### 6. Implementation Sequence
1. **Week 1** – Open `/global-items`, add slug column + migrations, implement detail page template with head tags, update sitemap/robots to include live domain.
2. **Week 2** – Export library JSON + integrate into the Next.js marketing site; publish the existing MDX docs/help pages; launch structured data.
3. **Week 3** – Content sprint: enrich metadata for top 200 items, publish calculator landing pages, create 3 topical guides that interlink items, tools, and signup funnels.
4. **Week 4** – Measurement + iteration: connect Search Console, set up analytics dashboards, and backlog future enhancements (automatic schema updates, programmatic listicles, supplier partnerships).

Following this plan gives Google a crawlable, content-rich surface tied directly to the proprietary global library—driving both authority and targeted acquisition for BatchTrack.
