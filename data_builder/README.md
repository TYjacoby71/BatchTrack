# Data Builder Toolkit

This folder contains the autonomous tooling that compiles the ingredient library which seeds BatchTrack.

## Components

| Module | Purpose |
| --- | --- |
| `term_collector.py` | Finds the canonical ingredient terms plus the master list of physical forms (botanical, extract, essential oil, solutions, etc.). It ships with built-in exemplar ingredients, can optionally read any directory of seed JSON you point it to, and leverages the AI API to generate 5k+ bases. |
| `database_manager.py` | Manages the resumable SQLite queue (`compiler_state.db`). |
| `ai_worker.py` | Sends the “perfect prompt” to the model for one ingredient and validates the JSON payload. |
| `compiler.py` | Orchestrates the iterative build: grabs the next term, locks it, calls the AI worker, validates, writes `output/ingredients/<slug>.json`, and updates lookup files. |

## Workflow

1. **Generate base ingredient terms (Phase 1).**
   ```bash
   python -m data_builder.term_collector \
     --target-count 5000 \   # minimum you want for this run; increase for long hauls
     --batch-size 250 \      # or try --batch-size 10 for quick smoke tests
     --terms-file data_builder/terms.txt \
     --forms-file data_builder/output/physical_forms.json
   ```
   - By default, relies solely on the built-in exemplar list plus the AI librarian. Pass `--seed-root <dir>` if you want to ingest legacy files for inspiration, or leave it blank to stay independent.
   - Uses the AI API (unless `--skip-ai`) to create a strictly alphabetical roster of base ingredients and the physical forms they appear in (including essential oils, extracts, lye solutions, tinctures, powders, etc.).
   - Writes `terms.txt` (newline list) and refreshes the `output/physical_forms.json` lookup.
   - Re-run anytime with a higher `--target-count` if you want to extend the library (e.g., 10k, 15k). Each run resumes alphabetically from the last generated term.

2. **Initialize the processing queue.**
   ```bash
   python -m data_builder.compiler --terms-file data_builder/terms.txt --max-iterations 0
   ```
   - `database_manager.initialize_queue()` ingests the term list into `compiler_state.db` with status `pending`.

3. **Compile the library (Phase 2).**
   ```bash
   OPENAI_API_KEY=... python -m data_builder.compiler --sleep-seconds 3
   ```
   - The compiler loops forever: fetches the next alphabetical term, calls `ai_worker`, writes the manicured JSON file, updates `physical_forms.json`/`taxonomies.json`, and marks the task `completed` (or `error`).
   - Each ingredient lives in its own file, e.g., `output/ingredients/lavender.json` containing the parent ingredient and all of its items/forms.

## Output Layout

```
data_builder/
  output/
    ingredients/        # one file per ingredient (parent + items/forms)
    physical_forms.json # curated lookup (seeded by term_collector, enriched by compiler)
    taxonomies.json     # auto-built during compilation
```

## Notes

- All scripts share the same OpenAI credentials via `OPENAI_API_KEY`.
- `term_collector.py` handles the “find 5–10k base ingredients” requirement and treats the target count as a minimum, not a cap. Configure `--batch-size` as low as 5–10 for exploratory passes.
- The `compiler.py` loop is resume-safe. If it stops mid-run, rerun the same command and it continues with the next `pending` term.
- Physical forms include essential oil, absolute, CO₂ extract, hydrosol, infusion, powder, chopped, buds, lye solution, tincture, glycerite, etc., ensuring every ingredient+form combination can be represented as an inventory item later.
