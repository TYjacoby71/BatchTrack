# Data Builder Toolkit

This folder contains the autonomous tooling that compiles the ingredient library which seeds BatchTrack.

## Components

| Module | Purpose |
| --- | --- |
| `ingredients/term_collector.py` | Finds the canonical ingredient terms plus the master list of physical forms (botanical, extract, essential oil, solutions, etc.). It ships with built-in exemplar ingredients, can optionally read any directory of seed JSON you point it to, and leverages the AI API to generate 5k+ bases. Every ingredient receives a 1–10 relevance score so the compiler can process the most impactful items first. |
| `ingredients/database_manager.py` | Manages the resumable SQLite queue (`compiler_state.db`) and persists per-term priority. |
| `ingredients/ai_worker.py` | Sends the “perfect prompt” to the model for one ingredient and validates the JSON payload (including category assignment, shelf-life-in-days, and optional form bypass flags for items like water/ice). |
| `ingredients/compiler.py` | Orchestrates the iterative build: grabs the next term, locks it, calls the AI worker, validates, writes `ingredients/output/ingredients/<slug>.json`, and updates lookup files. |

## Workflow

1. **Generate base ingredient terms (Phase 1).**
   ```bash
   python -m data_builder.ingredients.term_collector \
     --mode single_letter \   # fill one letter deeply (recommended)
     --letter A \             # optional; defaults to inferred-from-DB, else A
     --count 5000             # how many NEW terms to queue now
   ```
   - Stage 1 uses `compiler_state.db` as the source of truth for resuming and ratcheting.
   - By default, relies solely on the built-in exemplar list plus the AI librarian. If you want to ingest legacy seed files, pass `--ingest-seeds --seed-root <dir>`. The `output/` folder is always ignored.
   - Uses the AI API (unless `--skip-ai`) to create a strictly alphabetical roster of base ingredients, assign them to canonical categories, and enumerate the physical forms they appear in (including essential oils, extracts, lye solutions, tinctures, powders, dairy variants, etc.).
   - Queues terms directly into `compiler_state.db` (no `terms.json` required).
   - Re-run anytime with a higher `--count` to extend the library. Each run resumes from the last generated term (or last term per letter in parallel modes).

   Round-robin across letters:
   ```bash
   python -m data_builder.ingredients.term_collector --mode round_robin --count 2600
   ```

   Parallel per-letter (faster, capped by `--workers`):
   ```bash
   python -m data_builder.ingredients.term_collector --mode parallel_letters --count 2600 --workers 6
   ```

2. **Initialize the processing queue.**
   ```bash
   python -m data_builder.ingredients.compiler --terms-file data_builder/ingredients/terms.json --max-ingredients 0
   ```
   - Legacy only: `database_manager.initialize_queue()` can ingest an external `terms.json` list into `compiler_state.db`.

3. **Compile the library (Phase 2).**
   ```bash
   OPENAI_API_KEY=... python -m data_builder.ingredients.compiler \
     --sleep-seconds 3 \
     --max-ingredients 0 \        # optional cap per run
     --min-priority 8             # focus on the most relevant ingredients first
   ```
   - The compiler loops until the queue is empty (or until `--max-ingredients` is reached): fetches the highest-priority pending term, calls `ai_worker`, writes the manicured JSON file, updates `physical_forms.json`/`taxonomies.json`, and marks the task `completed` (or `error`).
   - Each ingredient lives in its own file, e.g., `output/ingredients/lavender.json` containing the parent ingredient and all of its items/forms.

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
- `term_collector.py` handles the “find 5–10k base ingredients” requirement and treats the target count as a minimum, not a cap. Configure `--batch-size` as low as 5–10 for exploratory passes. Every record is scored 1–10 for relevance so you can run the compiler against only the highest-impact items (e.g., `--min-priority 9`).
- Ingredient categories are standardized (`Botanical`, `Mineral`, `Animal-Derived`, `Fermentation`, `Chemical`, `Resin`, `Wax`, `Fat or Oil`, `Sugar or Sweetener`, `Acid`, `Salt`, `Solution or Stock`, `Aroma or Flavor`, `Colorant`, `Functional Additive`) and every ingredient JSON includes one of these.
- The `compiler.py` loop is resume-safe. If it stops mid-run, rerun the same command and it continues with the next `pending` term, honoring whatever `--min-priority` threshold you set.
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
