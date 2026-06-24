#!/usr/bin/env python3
"""
JARVIS backend — launches the round HUD and executes its commands natively.

Run:  python3 hud.py
This starts a tiny local server, opens the round HUD in your browser, and lets
the HUD actually open Mac apps, order, search, control the system, etc. through
the JARVIS engine in jarvis.py (the browser alone cannot do that).
"""
import os, json, threading, webbrowser, importlib.util
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
PORT = 8777
PAGE = "jarvis-assistant.html"

# ---- load the JARVIS engine (handle_local, open_app, etc.) from jarvis.py ----
spec = importlib.util.spec_from_file_location("jarvis", os.path.join(HERE, "jarvis.py"))
J = importlib.util.module_from_spec(spec)
spec.loader.exec_module(J)            # importing does NOT start the voice loop

# optional Claude brain if a key is in the environment / .jarvis_key
if not os.environ.get("ANTHROPIC_API_KEY") and os.path.exists(os.path.join(HERE, ".jarvis_key")):
    os.environ["ANTHROPIC_API_KEY"] = open(os.path.join(HERE, ".jarvis_key")).read().strip()
if os.environ.get("ANTHROPIC_API_KEY") and getattr(J, "anthropic", None):
    try: J.client = J.anthropic.Anthropic()
    except Exception: J.client = None

def run_command(text):
    """Execute a command through the JARVIS engine; return spoken reply or ''."""
    text = (text or "").strip()
    if not text:
        return ""
    reply = J.handle_local(text)      # opens apps / orders / searches / controls Mac
    return reply if reply is not None else ""

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parts = urlparse(self.path)
        if parts.path == "/do":
            text = parse_qs(parts.query).get("text", [""])[0]
            try: reply = run_command(text)
            except Exception as e: reply = f"Error: {e}"
            body = json.dumps({"reply": reply}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parts.path in ("/", ""):
            self.path = "/" + PAGE
        return super().do_GET()
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    url = f"http://localhost:{PORT}/{PAGE}"
    print("\033[95m" + "="*52 + "\033[0m")
    print(f"\033[96m  J.A.R.V.I.S backend online\033[0m  →  {url}")
    print(f"  Brain: {'CLAUDE ONLINE' if J.client else 'local commands only (no key)'}")
    print("  Native control: ON  ·  Ctrl-C to stop")
    print("\033[95m" + "="*52 + "\033[0m")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nJARVIS backend offline.")
