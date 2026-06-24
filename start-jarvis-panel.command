#!/bin/bash
# Double-click to open JARVIS as its own native Python window (with voice).
cd "$(dirname "$0")" || exit 1

# need the venv (audio libraries) for voice
if [ ! -d .venv ]; then
  echo "Setting up (first run)…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q numpy sounddevice SpeechRecognition anthropic
fi
./.venv/bin/python -c "import sounddevice,numpy,speech_recognition,webview,cv2" 2>/dev/null \
  || ./.venv/bin/pip install -q numpy sounddevice SpeechRecognition anthropic pywebview opencv-contrib-python

# load saved Claude key if present
[ -f .jarvis_key ] && export ANTHROPIC_API_KEY="$(cat .jarvis_key)"

echo "Opening JARVIS panel… (allow Microphone access if macOS asks)"
./.venv/bin/python panel.py

echo
echo "JARVIS panel closed. Press Enter."
read -r
