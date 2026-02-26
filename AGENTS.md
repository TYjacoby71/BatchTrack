# AGENTS.md

## Cursor Cloud specific instructions

### Overview
BatchTrack is a multi-tenant Flask SaaS app for small-batch makers (soap, candles, etc.). Single service, server-rendered (Jinja2), SQLite for local dev, PostgreSQL for production.

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
```
python3 run.py
```
Runs on `http://localhost:5000` with hot-reload. See `Makefile` target `dev`.

### Running tests
```
python3 -m pytest tests/ -v --tb=short
```
Tests use SQLite in-memory and require no external services. The full suite takes ~10 minutes. Use `-x` to stop on first failure for faster iteration. See `Makefile` target `test`.

Note: 15 pre-existing test failures exist in the codebase (as of Feb 2026).

### Linting
```
ruff check app/ tests/
black --check app/ tests/
isort --check-only app/ tests/
```
See `Makefile` target `lint`. Some pre-existing lint findings exist.

### Asset building (Node.js)
```
npm ci
npm run build:assets
```
Node/esbuild is used only for asset bundling; the app runs fine without building assets for development.

### Key paths
- `app/` — Flask application (blueprints, services, models, templates)
- `tests/` — pytest test suite
- `migrations/` — Alembic migrations (designed for PostgreSQL)
- `scripts/` — Utility scripts (build assets, validation, maintenance)
- `docs/` — System and changelog documentation
- `run.py` — Dev server entry point
- `Makefile` — Common dev commands
- `.env.example` — Environment variable template
