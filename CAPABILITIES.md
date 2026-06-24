# J.A.R.V.I.S — What it can do

Two versions:

| | **Desktop agent** `jarvis.py` | **Browser** `jarvis-assistant.html` |
|---|---|---|
| Setup | double-click `start-jarvis.command` | double-click the HTML |
| Hands-free | ✅ greets, listens & speaks automatically | ✅ after one "Engage" tap |
| Open native Mac apps | ✅ **yes** | ❌ websites only |
| Control apps (AppleScript) | ✅ **yes** | ❌ |
| Run shell commands / files | ✅ **yes** | ❌ |
| Open websites / order pages | ✅ | ✅ |
| Conversational AI (Claude) | ✅ | ✅ |

> The desktop agent is the powerful one — it actually controls your Mac. The browser is the instant, no-install demo.

## How "1000 features" works
JARVIS isn't a fixed menu of buttons. The Claude brain is wired to **8 generic power-tools** — `open_app`, `run_applescript`, `run_shell`, `open_url`, `web_search`, `shop_or_order`, `type_text`, `system_control`. Because AppleScript + shell can drive *anything* on macOS, the set of things you can ask for is effectively unlimited. Below are example commands by category — say them naturally.

### Apps & productivity
- "Open Safari / Spotify / Notes / WhatsApp / VS Code / Photoshop."
- "Open Notes and write a note: buy milk and call the bank."
- "Create a reminder to call mom at 6 pm."
- "Add a calendar event tomorrow at 3 called Dentist."
- "Compose an email to john@x.com about the meeting."
- "Open Terminal and run `ls ~/Downloads`."

### Web, search & ordering
- "Search the web for the best laptops 2026."
- "Order AirPods on Amazon." → opens the listings, you confirm payment.
- "Order a pizza on Uber Eats."
- "Play lo-fi beats on YouTube."
- "Open Google Maps directions to the airport."
- "Find me a flight to Dubai." (opens results)

### System control
- "Set the volume to 30." / "Mute." / "Unmute."
- "Take a screenshot." (saved to Desktop)
- "Lock the screen." / "Put the display to sleep."
- "What's my battery level?"

### Files & automation (desktop only)
- "Make a folder called Projects on my Desktop."
- "Move all PDFs from Downloads to Documents."
- "How much free disk space do I have?"
- "Show my Wi-Fi network."

### Knowledge & conversation
- "Explain quantum entanglement simply."
- "Summarise the news about AI." / "Translate 'good morning' to Japanese."
- "Tell me a joke." / "What should I cook with eggs and rice?"

### Control phrases
- "Go to sleep" / "Stop listening" → pause. "Wake up" → resume.
- "Shut down JARVIS" → quit (desktop).

## Safety
- Purchases: JARVIS takes you to the cart/checkout — **you confirm payment**.
- Clearly destructive shell commands (`rm -rf /`, `mkfs`, etc.) are refused.
- The API key lives only on your machine (`.jarvis_key`, or browser localStorage).

## First run
1. Double-click **`start-jarvis.command`** (Desktop agent) — it installs deps, asks for your Claude key once, then starts talking.
2. macOS will ask for **Microphone** permission — allow it. For full app control it may also ask for **Accessibility** (System Settings ▸ Privacy & Security ▸ Accessibility) so it can type/click in apps.
3. Just talk.
