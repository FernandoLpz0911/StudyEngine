#!/usr/bin/env bash
# One-shot setup + launch for running StudyEngine entirely on an Android phone,
# no server or network required — via Termux (https://f-droid.org/packages/com.termux/).
#
# Installs core deps only (skips the fsrs[optimizer] torch/pandas extra — that's
# only needed for `engine.cli.fsrs_fit`, not for normal study sessions), builds
# the frontend once, then serves the whole app on 127.0.0.1 for the phone's own
# browser. Re-run any time; steps that are already done are skipped.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if command -v pkg >/dev/null 2>&1; then
  pkg install -y python nodejs git
fi

python -m pip install --quiet --upgrade pip
python -m pip install --quiet fastapi uvicorn numpy scipy "fsrs>=6.0.0" httpx

if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm install && npm run build)
fi

echo "Starting StudyEngine at http://127.0.0.1:8000 — open that URL in Chrome," \
     "then use Chrome's menu > 'Add to Home screen' to install it as an app icon."
if command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url http://127.0.0.1:8000 &
fi
exec python -m engine.cli.app --host 127.0.0.1 --port 8000 --no-browser
