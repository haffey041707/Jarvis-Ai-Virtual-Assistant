#!/bin/bash
# Double-click to launch the JARVIS round HUD from the Python backend.
cd "$(dirname "$0")" || exit 1

PY="python3"
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; fi

# load saved key if present
[ -f .jarvis_key ] && export ANTHROPIC_API_KEY="$(cat .jarvis_key)"

echo "Launching JARVIS HUD backend…"
"$PY" hud.py

echo
echo "JARVIS backend stopped. Press Enter to close."
read -r
