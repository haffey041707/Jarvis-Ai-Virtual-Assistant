#!/bin/bash
# Double-click this file to set up and launch JARVIS.
cd "$(dirname "$0")" || exit 1

echo "╭───────────────────────────────────────────╮"
echo "│   J.A.R.V.I.S  —  first-run setup           │"
echo "╰───────────────────────────────────────────╯"

MODE="${1:-}"
unset __PYVENV_LAUNCHER__
unset PYTHONHOME
unset PYTHONPATH

run_arm64() {
  if /usr/bin/arch -arm64 /usr/bin/true >/dev/null 2>&1; then
    /usr/bin/arch -arm64 "$@"
  else
    "$@"
  fi
}

# 1) private virtual environment (one-time)
if [ ! -d ".venv" ]; then
  SYSTEM_PY="$(command -v python3)"
  [ -z "$SYSTEM_PY" ] && { echo "Python 3 not found. Install from python.org"; read -r; exit 1; }
  echo "→ Creating virtual environment…"
  run_arm64 "$SYSTEM_PY" -m venv .venv
fi
PY="$PWD/.venv/bin/python"
[ ! -x "$PY" ] && { echo "Virtual environment is damaged. Delete .venv and run again."; read -r; exit 1; }

# 2) dependencies (installed only when missing)
if ! run_arm64 "$PY" - <<'PY'
mods = ("numpy", "sounddevice", "speech_recognition", "anthropic")
missing = []
for mod in mods:
    try:
        __import__(mod)
    except Exception:
        missing.append(mod)
if missing:
    print("Missing:", ", ".join(missing))
    raise SystemExit(1)
PY
then
  echo "→ Installing dependencies. This may take a few minutes on first run…"
  run_arm64 "$PY" -m pip install --upgrade pip
  run_arm64 "$PY" -m pip install --upgrade numpy sounddevice SpeechRecognition anthropic || {
    echo
    echo "Dependency install failed. Check your internet connection, then run this launcher again."
    read -r
    exit 1
  }
else
  echo "→ Dependencies ready."
fi

# 3) API key — ask once, remember in a local file
if [ -f ".jarvis_key" ]; then
  export ANTHROPIC_API_KEY="$(cat .jarvis_key)"
fi
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo
  echo "No Claude API key found. Starting in key-free mode."
  echo "To enable Claude later, save your key in .jarvis_key in this folder."
fi

# 4) launch
echo "→ Launching JARVIS. Grant microphone access if macOS asks."
echo
if [ "$MODE" = "--screen" ] || [ "${JARVIS_SCREEN:-}" = "1" ]; then
  run_arm64 "$PY" jarvis.py --screen
else
  run_arm64 "$PY" jarvis.py
fi

echo
echo "JARVIS has exited. Press Enter to close."
read -r
