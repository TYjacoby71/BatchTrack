from __future__ import annotations

import os

from .app import create_data_builder_app


def main() -> None:
    app = create_data_builder_app()
    host = os.environ.get("DATA_BUILDER_HOST", "0.0.0.0")
    port = int(os.environ.get("DATA_BUILDER_PORT", "5051"))
    debug = os.environ.get("DATA_BUILDER_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host=host, port=port, debug=debug, use_reloader=debug)


if __name__ == "__main__":
    main()

