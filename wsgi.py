
"""WSGI entrypoint for production servers (Gunicorn, uWSGI, etc.)."""

from app import create_app

app = create_app()


if __name__ == "__main__":
    raise SystemExit(
        "This module exposes a WSGI callable for servers like Gunicorn. "
        "Run `python run.py` for the development server instead."
    )
