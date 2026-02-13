#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Python dependencies"
pip install -r requirements.txt

if [[ -f "package.json" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm is required for flask build-assets but is not available on PATH." >&2
    exit 1
  fi

  if [[ -f "package-lock.json" ]]; then
    echo "==> Installing Node dependencies with npm ci"
    npm ci
  else
    echo "==> Installing Node dependencies with npm install (no lockfile found)"
    npm install
  fi
else
  echo "==> Skipping Node dependency install (package.json not found)"
fi

export FLASK_APP="${FLASK_APP:-wsgi.py}"

if [[ "${SKIP_DB_MIGRATIONS:-0}" == "1" ]]; then
  echo "==> Skipping flask db upgrade (SKIP_DB_MIGRATIONS=1)"
else
  echo "==> Applying database migrations"
  flask db upgrade
fi

if [[ "${SKIP_ASSET_BUILD:-0}" == "1" ]]; then
  echo "==> Skipping flask build-assets (SKIP_ASSET_BUILD=1)"
else
  echo "==> Building static assets"
  flask build-assets
fi
