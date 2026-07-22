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
  # numpy/scipy have no PyPI wheels for Termux's bionic libc and are painfully
  # slow (or fail) to build from source on-device — use Termux's own
  # precompiled packages instead. rust/binutils are there because pydantic-core
  # (a FastAPI dependency) is also unavailable as a wheel and must build.
  pkg install -y python python-numpy python-scipy nodejs git rust binutils
fi

# pydantic-core (FastAPI dep) builds via maturin/Rust and refuses to run
# unless ANDROID_API_LEVEL is set — Termux doesn't export it, so read it off
# the device.
export ANDROID_API_LEVEL="${ANDROID_API_LEVEL:-$(getprop ro.build.version.sdk 2>/dev/null || echo 24)}"
python -m pip install --quiet fastapi uvicorn "fsrs>=6.0.0" httpx

if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm install && npm run build)
fi

# Android kills backgrounded apps by default — switching to Chrome can take
# Termux (and this server) down with it. A wake lock stops the OS from
# suspending Termux for CPU/doze reasons; it does NOT override a device's own
# battery-optimization killer, so also set Termux to "Unrestricted" battery
# under Android Settings > Apps > Termux > Battery, and don't swipe away
# Termux's notification — that's what keeps the process alive in the background.
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock
fi

echo "Starting StudyEngine at http://127.0.0.1:8000 — open that URL in Chrome," \
     "then use Chrome's menu > 'Add to Home screen' to install it as an app icon." \
     "Keep Termux running in the background (see battery note above) or the" \
     "server will die when you switch away."
if command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url http://127.0.0.1:8000 &
fi
exec python -m engine.cli.app --host 127.0.0.1 --port 8000 --no-browser
