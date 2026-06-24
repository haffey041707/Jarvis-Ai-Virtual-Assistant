# 🤖 J.A.R.V.I.S — AI Virtual Assistant

> *Just A Rather Very Intelligent System* — a hands-free, voice-driven AI desktop assistant for macOS with an Iron-Man-style holographic interface, **face-recognition login**, and a Claude-powered brain.

A personal project by **[@haffey041707](https://github.com/haffey041707)**.
**Proprietary — All Rights Reserved.** See [LICENSE](LICENSE).

---

## ✨ Features

### 🎙️ Voice control (hands-free, no buttons)
- Greets you, then continuously listens and replies in a refined British voice.
- **Quiet mode** — *"Jarvis, keep quiet"* → silent until *"Jarvis, wake up."*
- **Standby** — *"go to sleep"* → Iron-Man standby reactor screen → re-authenticates on wake.

### 🔐 Biometric face authentication
- One-time face enrollment, then a themed **scanning-ray** auth panel.
- Opens **only for the owner** — green ✓ *ACCESS GRANTED*, stays silent for unknown faces.

### 🚀 Auto-launch
- Opens automatically when you **unlock your Mac with Touch ID / wake from sleep** (background watcher) and at login.
- Desktop `JARVIS.app` launcher.
- **Mic self-heals** across sleep/wake — stays connected without restarting.

### 🧩 What it can do (works with NO API key)
- **Open any app** (~70) or **website** (~50) by voice.
- **Play any song** — opens and plays the actual video in one shot.
- **Order / buy anything** on ~20 shops (Amazon, eBay, Uber Eats, Daraz, …).
- **Web search**, directions, weather, time, date, timers, calculator.
- **System control** — volume, mute, screenshot, lock, sleep, battery.
- **Notes, reminders, email** via AppleScript.

### 🧠 AI brain (optional Claude API key)
- Answers any question and performs open-ended tasks via 8 tools
  (`open_app · open_url · web_search · shop_or_order · run_applescript · type_text · system_control · run_shell`).
- Default model: **Claude Haiku 4.5** (lowest cost).

### 🖥️ Interface
- Round **Iron-Man HUD** — orbiting gauges, rings, radar, reactor core, reactive states.
- **Responsive** — also usable from a phone browser.

---

## 🛠️ Setup (macOS)

```bash
git clone https://github.com/haffey041707/Jarvis-Ai-Virtual-Assistant.git
cd Jarvis-Ai-Virtual-Assistant
python3 -m venv .venv
./.venv/bin/pip install numpy sounddevice SpeechRecognition anthropic pywebview opencv-contrib-python
./.venv/bin/python jarvis.py
```

Or double-click **`start-jarvis-panel.command`** (handles setup automatically).

- Grant **Microphone** and **Camera** permission when macOS asks.
- (Optional) Add a Claude API key from [console.anthropic.com](https://console.anthropic.com) via the in-app **🔑 ADD CLAUDE API KEY** bar — it's stored locally in `.jarvis_key` (never committed).

### Run modes
| Command | Mode |
|---|---|
| `python jarvis.py` | Native HUD window (default) |
| `python jarvis.py type` | Type-to-test (no mic) |
| `python jarvis.py enroll` | Re-register your face |
| `python hud.py` | Browser version (also serves to your **phone** on the same Wi-Fi) |

### 📱 Use it on your phone
Run `python hud.py` on the Mac, then open `http://<your-mac-ip>:8777/jarvis-assistant.html` in your phone's browser — the UI is responsive.

---

## 🗂️ Project structure
- `jarvis.py` — core agent (voice, commands, AI brain, HUD window, face/auth/standby flow)
- `face.py` — face enrollment & recognition (OpenCV)
- `jarvis_watcher.py` — auto-launch on unlock / wake
- `jarvis-assistant.html` — main Iron-Man HUD UI
- `jarvis-auth.html` — biometric auth panel
- `jarvis-standby.html` — standby reactor screen
- `hud.py` — browser/server launcher
- `start-jarvis-panel.command` — one-click launcher

---

## ⚠️ Requirements
macOS · Python 3.10+ · webcam & microphone · (optional) Claude API key.

---

## 📜 License
**Proprietary — All Rights Reserved.** This is a personal project; no permission is granted to use, copy, or redistribute it. See [LICENSE](LICENSE).
