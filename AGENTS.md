# AGENTS.md

## Cursor Cloud specific instructions

### Overview
BatchTrack is a multi-tenant Flask SaaS app for small-batch makers (soap, candles, etc.). Single service, server-rendered (Jinja2), SQLite for local dev, PostgreSQL for production.

### PATH requirement
Pip installs binaries (pytest, flask, ruff, black, isort) to `~/.local/bin`. The update script exports this to PATH, and `~/.bashrc` should contain `export PATH="$HOME/.local/bin:$PATH"`. The update script also creates a `python` -> `python3` symlink in `~/.local/bin` so that `Makefile` targets (which use `python`) work.

### Critical environment variables
The VM may have `DATABASE_URL` and `REDIS_URL` injected from secrets pointing to remote services. For **local development and testing**, you **must** unset them so the app falls back to SQLite and SimpleCache:
```
unset DATABASE_URL
unset REDIS_URL
export FLASK_ENV=development
export FLASK_SECRET_KEY=<any-dev-string>
export SQLALCHEMY_CREATE_ALL=true
```

### Database setup (one-time, after fresh clone)
Alembic migrations have PostgreSQL-specific steps that error on SQLite (migration 0012 ALTER constraint). Use `SQLALCHEMY_CREATE_ALL=true` to create tables from models, then seed:
```
flask init-production
```
Seed data includes default org, users (`admin`/`admin`, `dev`/`dev123`), permissions, subscription tiers, units, and the global ingredient library.

### Running the dev server
See `Makefile` target `dev` (`python run.py`). Runs on `http://localhost:5000` with hot-reload.

### Running tests
See `Makefile` target `test` (`python -m pytest tests/ -v`). Tests use SQLite in-memory and require no external services. The full suite takes ~10 minutes. Use `-x` to stop on first failure for faster iteration.

Note: 15 pre-existing test failures exist in the codebase (as of Feb 2026).

### Linting
See `Makefile` target `lint`. Dev tools (`ruff`, `black`, `isort`) are installed by the update script (not in `requirements.txt`). Some pre-existing lint findings exist.

### Asset building (Node.js)
`npm run build:assets` — esbuild bundles JS/CSS. Only needed for production builds; the app runs fine without it during development.

### Key paths
- `app/` — Flask application (blueprints, services, models, templates)
- `tests/` — pytest test suite
- `migrations/` — Alembic migrations (designed for PostgreSQL)
- `scripts/` — Utility scripts (build assets, validation, maintenance)
- `docs/` — System and changelog documentation
- `run.py` — Dev server entry point
- `Makefile` — Common dev commands (`make help` for full list)
- `.env.example` — Environment variable template
