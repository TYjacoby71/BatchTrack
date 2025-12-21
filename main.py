#!/usr/bin/env python3
"""
Replit entrypoint wrapper.

Having an explicit `main.py` avoids Replit falling back to the last-run
terminal command when the configured entrypoint doesn't exist.
"""

from run import main


if __name__ == "__main__":
    main()

