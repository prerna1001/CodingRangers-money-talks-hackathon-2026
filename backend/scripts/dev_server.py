"""Start the API with backend/ as the working directory, whatever directory
the launcher happened to start in.

config.py resolves ./.cache, ./data and the SQLite file relative to the
current directory, so uvicorn has to run from backend/ -- and the editor's
run configuration doesn't always start there.

Usage:
    venv/bin/python scripts/dev_server.py [--port 8000] [--no-reload]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))

    import uvicorn

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        reload_dirs=[str(BACKEND_DIR)],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
