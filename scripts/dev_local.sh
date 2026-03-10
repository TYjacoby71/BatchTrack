#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage:"
  echo "  scripts/dev_local.sh run"
  echo "  scripts/dev_local.sh db <alembic-subcommand> [args...]"
  echo "  scripts/dev_local.sh flask <flask-subcommand> [args...]"
  echo
  echo "Examples:"
  echo "  scripts/dev_local.sh db current"
  echo "  scripts/dev_local.sh db upgrade"
  echo "  scripts/dev_local.sh run"
  echo
  echo "Safety defaults:"
  echo "  - Forces FLASK_ENV=development (unless already set)."
  echo "  - Unsets remote DB env vars so local commands never hit deployed DB."
  echo "  - Sets SQLALCHEMY_CREATE_ALL=0 unless explicitly provided."
  echo
  echo "Override:"
  echo "  Set DEV_ALLOW_DEPLOYED_DB=1 to skip DB env sanitization."
}

sanitize_env() {
  export FLASK_ENV="${FLASK_ENV:-development}"
  export FLASK_APP="${FLASK_APP:-run.py}"
  export SQLALCHEMY_CREATE_ALL="${SQLALCHEMY_CREATE_ALL:-0}"

  if [[ "${DEV_ALLOW_DEPLOYED_DB:-0}" != "1" ]]; then
    unset DATABASE_URL
    unset DATABASE_INTERNAL_URL
    unset SQLALCHEMY_DATABASE_URI
    unset BATCHTRACK_FORCE_DB_URL
  fi
}

main() {
  if [[ $# -lt 1 ]]; then
    usage
    exit 1
  fi

  sanitize_env

  cmd="$1"
  shift

  case "$cmd" in
    run)
      exec python3 run.py
      ;;
    db)
      if [[ $# -lt 1 ]]; then
        usage
        exit 1
      fi
      exec python3 -m flask --app "${FLASK_APP}" db "$@"
      ;;
    flask)
      if [[ $# -lt 1 ]]; then
        usage
        exit 1
      fi
      exec python3 -m flask --app "${FLASK_APP}" "$@"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      echo "Unknown command: $cmd" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
