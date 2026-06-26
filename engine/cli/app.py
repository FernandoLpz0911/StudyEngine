"""Launch the full graphical app: python -m engine.cli.app.

One command serves the built React UI and the API from a single FastAPI process
and opens it in your browser — no separate frontend dev server, no second
terminal. If the frontend has not been built yet, it is built once with npm
(requires Node); thereafter the prebuilt bundle is reused.
"""
from __future__ import annotations

import argparse
import subprocess
import threading
import webbrowser
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"
_DIST = _FRONTEND / "dist"


def _ensure_built() -> bool:
    """Build the frontend if no bundle exists. Return True if a bundle is ready."""
    if (_DIST / "index.html").exists():
        return True
    npm = __import__("shutil").which("npm")
    if npm is None:
        print(
            "Frontend not built and npm not found. Install Node, then run:\n"
            "  cd frontend && npm install && npm run build"
        )
        return False
    print("Building frontend (first run only)…")
    subprocess.run([npm, "install"], cwd=_FRONTEND, check=True)
    subprocess.run([npm, "run", "build"], cwd=_FRONTEND, check=True)
    return (_DIST / "index.html").exists()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the StudyEngine graphical app.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not _ensure_built():
        raise SystemExit(1)

    import uvicorn

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"StudyEngine running at {url}  (Ctrl-C to stop)")
    uvicorn.run("engine.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
