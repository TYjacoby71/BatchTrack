# Ingredient Library Builder

This standalone tool ingests a master ingredient queue, calls an AI worker for each term, validates structured responses, and emits golden-source JSON files consumed by the BatchTrack seed scripts.

## Project Layout

```
data_builder/
  ai_worker.py        # AI prompt construction + response validation
  config.py           # Settings and shared constants
  main.py             # Orchestrator CLI
  schema.py           # Pydantic models + controlled vocab
  state.py            # SQLite queue helpers
  storage.py          # JSON writers and merge logic
  terms.txt           # Seed list of ingredient names
  output/             # Generated category JSON (git tracked via .gitkeep)
```

## Quickstart

1. Create a virtualenv and install requirements:
   ```bash
   pip install -r data_builder/requirements.txt
   ```
2. Export your LLM credentials (e.g., `OPENAI_API_KEY`).
3. Populate `data_builder/terms.txt` with one ingredient name per line.
4. Initialize the queue:
   ```bash
   python3 -m data_builder.state init
   ```
5. Run the orchestrator:
   ```bash
   python3 -m data_builder.main --batch 50
   ```

The CLI processes ingredients in batches, writes JSON to `output/`, and tracks progress inside `state.db`. Re-running the script is idempotent: completed rows are skipped, failed rows remain flagged for review.
