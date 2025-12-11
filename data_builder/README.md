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
     --target-count 5000 \   # minimum you want for this run; increase for long hauls
     --batch-size 250 \      # or try --batch-size 10 for quick smoke tests
     --terms-file data_builder/ingredients/terms.json \
     --forms-file data_builder/ingredients/output/physical_forms.json
   ```
   - By default, relies solely on the built-in exemplar list plus the AI librarian. Pass `--seed-root <dir>` if you want to ingest legacy files for inspiration, or leave it blank to stay independent.
   - Uses the AI API (unless `--skip-ai`) to create a strictly alphabetical roster of base ingredients, assign them to canonical categories, and enumerate the physical forms they appear in (including essential oils, extracts, lye solutions, tinctures, powders, dairy variants, etc.).
   - Writes `terms.json` (each entry includes `{ "term": "...", "priority": 1-10 }`) and refreshes the `output/physical_forms.json` lookup.
   - Re-run anytime with a higher `--target-count` if you want to extend the library (e.g., 10k, 15k). Each run resumes alphabetically from the last generated term.

2. **Initialize the processing queue.**
   ```bash
   python -m data_builder.ingredients.compiler --terms-file data_builder/ingredients/terms.json --max-ingredients 0
   ```
   - `database_manager.initialize_queue()` ingests the term list into `compiler_state.db` with status `pending`, preserving each term’s 1–10 priority score.

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
