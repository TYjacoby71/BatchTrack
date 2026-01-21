# Data Builder Toolkit

This folder contains the autonomous tooling that compiles the ingredient library which seeds BatchTrack.

## One supported path (canonical)

This repo is intentionally opinionated: **there is ONE supported way to run the data builder.**

- **Do not run individual stage scripts** like `ingest_source_items.py`, `merge_source_items.py`, `pubchem_stage1_match.py`, etc.
- Those modules exist for internal structure/testing, but the only supported CLI entrypoint **before AI** is:

```bash
python3 -m data_builder.ingredients.run_pre_ai_pipeline ...
```

### Numbered “SI pipeline” wrappers (repo-visible order)

If you want the run order to be obvious when browsing the repo, use the numbered wrappers:

- **SI 1**: `data_builder/ingredients/si_pipeline/si_01_ingest.py`
- **SI 2a**: `data_builder/ingredients/si_pipeline/si_02a_pubchem_match.py`
- **SI 2b**: `data_builder/ingredients/si_pipeline/si_02b_pubchem_retry.py`
- **SI 3**: `data_builder/ingredients/si_pipeline/si_03_pubchem_fetch.py`
- **SI 4**: `data_builder/ingredients/si_pipeline/si_04_pubchem_apply.py`

They call `run_pre_ai_pipeline` with a fixed `--stage` and accept the same flags (notably `--db-path`).

This is designed to be:
- deterministic (no AI)
- resume-safe
- reviewable between stages
- compatible with hosted environments like Replit (throttle + bounded concurrency)

## Components

| Module | Purpose |
| --- | --- |
| `ingredients/term_collector.py` | Finds the canonical ingredient terms plus the master list of physical forms (botanical, extract, essential oil, solutions, etc.). It ships with built-in exemplar ingredients, can optionally read any directory of seed JSON you point it to, and leverages the AI API to generate 5k+ bases. Every ingredient receives a 1–10 relevance score so the compiler can process the most impactful items first. |
| `ingredients/database_manager.py` | Manages the SQLite state DB (`compiler_state.db`) and persists cluster/term metadata. |
| `ingredients/ai_worker.py` | Sends the “perfect prompt” to the model for one ingredient and validates the JSON payload (including category assignment, shelf-life-in-days, and optional form bypass flags for items like water/ice). |
| `ingredients/compiler.py` | Orchestrates the iterative build: grabs the next term, locks it, calls the AI worker, validates, writes `ingredients/output/ingredients/<slug>.json`, and updates lookup files. |

## Workflow

### Canonical deterministic pre-AI pipeline (CosIng + TGSC → PubChem)

This pipeline deterministically:
- ingests item rows into `source_items` (variation/form parsing + provenance)
- merges cross-source identities into `source_catalog_items`
- de-dupes into `merged_item_forms`
- bundles items into `source_definitions`
- derives canonical base terms into `normalized_terms`
- stores `normalized_terms` for reference alongside definition clusters
- runs **PubChem** matching + caching + fill-only apply (no overwrites)

#### 0) Pick a state DB path (recommended)

```bash
# Use a single SQLite DB file as the state store for the whole run.
DB="/absolute/path/to/state.db"
```

#### 1) Ingestion (deterministic, DB-only)

This resets ingestion-stage tables in the DB (one-shot, non-overlapping) and rebuilds:
`source_items`, `source_catalog_items`, `merged_item_forms`, `source_definitions`, `normalized_terms`.

```bash
python3 -m data_builder.ingredients.run_pre_ai_pipeline \
  --db-path "$DB" \
  --stage ingest
```

**Review checkpoint (ingestion):** verify `source_definitions` are created and item counts look sane.

#### 2) PubChem Stage 1: match (run everything once, in batches)

This assigns PubChem CIDs to deterministic items/terms and buckets the rest.
Every record ends in exactly one bucket:
- `matched` (1 CID)
- `no_match` (0 CIDs for all identifiers)
- `ambiguous` (>1 CID; we do not guess)
- `retry` (rate-limit/server-busy/transient; retry later)

Recommended Replit-safe settings (shared egress IPs):

```bash
export PUBCHEM_WORKERS=16
export PUBCHEM_MIN_INTERVAL_SECONDS=0.25
export PUBCHEM_RETRIES=8
export PUBCHEM_BACKOFF_SECONDS=0.8
export PUBCHEM_MAX_RETRY_RUNS=3
```

Run the first pass in batches (repeat until the logs show `scanned: 0`):

```bash
python3 -m data_builder.ingredients.run_pre_ai_pipeline \
  --db-path "$DB" \
  --stage pubchem_match \
  --match-limit 5000 \
  --term-match-limit 5000
```

#### 2b) PubChem Stage 1 retry passes (only the retry bucket)

After the first full pass is done, rerun only the retry bucket.
This is intentionally not automatic “all at once”: you run retry passes explicitly.

Run up to 3 passes (or until `retry: 0`):

```bash
python3 -m data_builder.ingredients.run_pre_ai_pipeline \
  --db-path "$DB" \
  --stage pubchem_retry \
  --match-limit 5000 \
  --term-match-limit 5000
```

After 3 retry runs, any remaining retry items are deterministically downgraded to `no_match`
with `error=exhausted_retries:...`.

#### 3) PubChem Stage 2: fetch/cache (grouped bundles)

PubChem properties live in two “bundles”:
- **PropertyTable (batchable by CID list)**: identifiers + computed physchem
- **PUG View (per CID)**: experimental/text sections (density/solubility/boiling point/etc.)

Run:

```bash
python3 -m data_builder.ingredients.run_pre_ai_pipeline \
  --db-path "$DB" \
  --stage pubchem_fetch \
  --batch-size 100
```

**Review checkpoint (fetch):** the log shows `pubchem fetch: { unique_cids: ..., fetched_property: ..., fetched_pug_view: ... }`.

#### 4) PubChem Stage 3: apply (fill-only)

This writes PubChem fields back into:
- `merged_item_forms.merged_specs_json` (fill-only; never overwrites existing values)
- `normalized_terms.sources_json['pubchem']` (provenance)

Run:

```bash
python3 -m data_builder.ingredients.run_pre_ai_pipeline \
  --db-path "$DB" \
  --stage pubchem_apply
```

At this point the DB is “ready for AI” (compiler stage) because:
- ingestion is complete
- PubChem enrichment is applied where available
- `normalized_terms` exists for reference alongside cluster records

1. **Stage 1: term completion on clusters.**
   ```bash
   OPENAI_API_KEY=... python -m data_builder.ingredients.compiler --stage 1
   ```
   - Operates on `source_definitions` clusters (derived from ingestion) and writes normalized term core fields into `compiled_clusters`.
   - The cluster-based compiler is now the only supported AI path; legacy term queues are no longer used.

2. **Stage 2: item compilation per cluster.**
   ```bash
   OPENAI_API_KEY=... python -m data_builder.ingredients.compiler --stage 2
   ```
   - Completes ingestion-derived item stubs per cluster and persists compiled ingredient payloads.

3. **Stage 3: optional enumeration.**
   ```bash
   OPENAI_API_KEY=... python -m data_builder.ingredients.run_enumeration --limit 50
   ```
   - Adds new item identities after Stage 2 and updates compiled ingredient payloads.

## Output Layout

```
data_builder/
  ingredients/
    output/
      ingredients/        # one file per ingredient (parent + items/forms)
      physical_forms.json # curated lookup (seeded by term_collector, enriched by compiler)
      taxonomies.json     # auto-built during compilation
```

## Notes

- All scripts share the same OpenAI credentials via `OPENAI_API_KEY`.
- `term_collector.py` remains available for supplemental term discovery, but cluster compilation is the only supported AI build path.
- Ingredient categories are standardized (`Botanical`, `Mineral`, `Animal-Derived`, `Fermentation`, `Chemical`, `Resin`, `Wax`, `Fat or Oil`, `Sugar or Sweetener`, `Acid`, `Salt`, `Solution or Stock`, `Aroma or Flavor`, `Colorant`, `Functional Additive`) and every ingredient JSON includes one of these.
- The `compiler.py` cluster runner is resume-safe. If it stops mid-run, rerun the same stage and it continues with the next pending cluster/items.
- Physical forms are maintained in `output/physical_forms.json`, which the seeder can process before touching ingredient files. They include essential oil, absolute, CO₂ extract, hydrosol, infusion, powder, chopped, buds, dairy variants, lye solution, tincture, glycerite, etc., ensuring every ingredient+form combination can be represented as an inventory item later. Ingredients like water/ice can set a `form_bypass` flag so display names stay clean.

### Optional external data sources

`data_builder/ingredients/sources.py` can enrich each ingredient with facts from public/reference databases. All lookups are optional—if a key/file is missing the builder simply skips that source. Supported inputs today:

| Source | Environment variable(s) | Optional local file | Notes |
| --- | --- | --- | --- |
| **PubChem (NIH)** | `PUBCHEM_API_KEY` (optional; many endpoints are public) | – | Provides CAS numbers, densities, boiling points, SMILES/InChI. |
| **EU CosIng** | – | `COSING_CSV_PATH` (defaults to `data_builder/ingredients/data_sources/cosing.csv`) | Download the CosIng Excel/CSV export and drop it into the data_sources folder. |
| **USDA FoodData Central** | `USDA_API_KEY` | – | Needed for baking/beverage nutrition, moisture, SRM. Sign up for a free key at api.nal.usda.gov. |
| **HSCG Ingredient Directory** | – | `HSCG_CSV_PATH` (`…/hscg_ingredients.csv`) | Export the member directory or scrape the public preview into CSV. |
| **EWG Skin Deep** | `EWG_API_KEY` | – | Adds safety ratings and hazard tags for cosmetics. |
| **The Good Scents Company (TGSC)** | `TGSC_API_KEY` (if you have partner access) | `TGSC_CSV_PATH` | Use the API if available; otherwise drop a CSV export. |
| **Health Canada Natural Health Products (NHP)** | `NHP_API_KEY` (optional) | `NHP_JSON_PATH` (`…/health_canada_nhp.json`) | You can download JSON batches from health-products.canada.ca or scrape the search UI. |

Any file path variables default to the `data_builder/ingredients/data_sources/` directory, so you can just place the CSV/JSON there without setting environment variables. To override, point the corresponding `_PATH` variable at another location (e.g., `COSING_CSV_PATH=/mnt/data/cosing.csv`).

## Deterministic source ingestion (CosIng + TGSC)

In addition to the AI compiler, `data_builder/ingredients/` includes a **deterministic ingestion + merge pipeline** that produces a traceable, de-duplicated “item-form” layer before any AI enrichment.

- **`ingest_source_items.py`**: reads `data_sources/cosing.csv` + `data_sources/tgsc_ingredients.csv` and writes 1:1 `source_items` rows (plus derived `normalized_terms`) into the SQLite DB.
- **`merge_source_items.py`**: deterministically merges duplicate item-forms into `merged_item_forms` (one row per `derived_term + derived_variation + derived_physical_form`), while keeping all source row keys for provenance.

Curated vocab tables (physical forms, variations, refinement levels, master categories, and master-category rules) are shipped as JSON under `data_builder/ingredients/data_sources/vocab/` and are also seeded into the DB tables on first run.
