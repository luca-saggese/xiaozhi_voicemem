"""Entrypoint CLI: `python -m runtime`."""

from __future__ import annotations

from runtime.server import main

if __name__ == "__main__":
    raise SystemExit(main())
