#!/usr/bin/env python3
"""
J.A.R.V.I.S — hands-free desktop AI agent for macOS.

• No buttons, no typing — it greets you, then continuously listens and speaks.
• Works WITHOUT an API key: a large built-in command engine opens any app or
  website, orders on any shopping site, plays media, controls the system, runs
  AppleScript/shell, sets timers, and more.
• If a Claude API key is present, anything the local engine can't match is sent
  to a tool-using Claude brain for full conversational intelligence.

Launch:  double-click  start-jarvis.command
"""

import os, re, sys, json, time, queue, random, subprocess, threading

try:                                   # audio libs (only needed for voice mode)
    import numpy as np
    import sounddevice as sd
    import speech_recognition as sr
except Exception:
    np = sd = sr = None
try:
    import anthropic
except Exception:
    anthropic = None

# ============================================================ CONFIG
MODEL       = os.environ.get("JARVIS_MODEL", "claude-haiku-4-5")   # cheapest model for low cost
VOICE       = os.environ.get("JARVIS_VOICE", "Daniel")   # refined British (JARVIS) voice
VOICE_RATE  = int(os.environ.get("JARVIS_RATE", "176"))  # calm, measured JARVIS cadence
VOICE_ON    = True                                       # spoken output (toggle in GUI)
CUR_VOICE   = VOICE          # active TTS voice (auto-changes with detected language)
CUR_LANG    = "en-US"        # active speech-recognition language (English is primary)
CUR_LANGNAME= "English"      # active language name (used so replies match)
SAMPLE_RATE = 16000
SILENCE_HANG = 0.65        # end a phrase sooner → snappier responses
START_LEVEL  = 0.014       # a touch more sensitive so it catches you
MAX_PHRASE   = 12
BARGE_LEVEL  = float(os.environ.get("JARVIS_BARGE", "0.07"))   # speak-over-JARVIS interrupt threshold

# ============================================================ SCREEN EVENTS
_ui_queue = None
def ui_emit(kind, text=""):
    if _ui_queue is None:
        return
    try:
        _ui_queue.put((kind, text))
    except Exception:
        pass

# ============================================================ VOICE OUT
_speaking = threading.Event()
def say(text):
    text = (text or "").strip()
    if not text: return
    print(f"\033[96mJARVIS ▸\033[0m {text}")
    ui_emit("jarvis", text)
    if not VOICE_ON:                 # voice muted — text only
        return
    ui_emit("state", "SPEAKING")
    _speaking.set()
    try:
        proc = subprocess.Popen(["say", "-v", CUR_VOICE, "-r", str(VOICE_RATE), text])
        _watch_for_bargein(proc)        # stop & listen if the user talks over JARVIS
    finally:
        _speaking.clear()
        ui_emit("state", "LISTENING")

def _watch_for_bargein(proc):
    """Stop speaking only when the user is clearly LOUDER than JARVIS's own voice (echo-safe)."""
    if sd is None or np is None:
        try: proc.wait()
        except Exception: pass
        return
    blk = int(SAMPLE_RATE*0.05); q2: "queue.Queue" = queue.Queue()
    def cb(indata, frames, t, s): q2.put(indata.copy())
    cal, thresh, loud, t0 = [], None, 0, time.time()
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=blk, callback=cb):
            while proc.poll() is None:
                try: block = q2.get(timeout=0.15)[:, 0]
                except queue.Empty: continue
                lvl = float(np.sqrt(np.mean(np.square(block, dtype=np.float64)))+1e-9)
                if time.time() - t0 < 0.7:             # calibrate to JARVIS's own echo first
                    cal.append(lvl); continue
                if thresh is None:                     # threshold must clearly exceed own playback
                    base = sorted(cal)[len(cal)//2] if cal else 0.02
                    thresh = max(base * 2.0, base + 0.05, BARGE_LEVEL)
                loud = loud+1 if lvl > thresh else 0
                if loud >= 4:                          # ~0.2s clearly above own voice → real barge-in
                    proc.terminate(); break
    except Exception:
        pass
    try: proc.wait(timeout=5)
    except Exception: pass

# ============================================================ MULTILINGUAL (English primary, auto-switch)
VOICE_MAP = {}
def build_voice_map():
    """Map a language code -> an available macOS voice. English stays Daniel; Urdu uses the Hindi voice."""
    global VOICE_MAP
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    except Exception:
        out = ""
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        for p in parts:
            if re.match(r"^[a-z]{2}_[A-Za-z0-9]{2,3}$", p):
                VOICE_MAP.setdefault(p[:2], parts[0])
                break
    VOICE_MAP["en"] = "Daniel"
    VOICE_MAP.setdefault("ur", VOICE_MAP.get("hi", "Lekha"))   # no Urdu TTS → Hindi (same spoken language)

# English is primary & always Daniel. We additionally listen for Urdu and switch ONLY when
# the audio clearly transcribes into Urdu (Arabic) script — so English never flips by mistake.
DETECT = [("en-US", "English"), ("ur-PK", "Urdu")]

def _set_lang(code, name, voice):
    global CUR_LANG, CUR_LANGNAME, CUR_VOICE
    if CUR_LANG != code:
        CUR_LANG, CUR_LANGNAME, CUR_VOICE = code, name, voice
        print(f"\033[95m[language → {name} | voice {voice}]\033[0m")

def detect_and_transcribe(data):
    """English (Daniel) by default. Switch to Urdu (Lekha) only when Urdu script is detected."""
    import concurrent.futures
    def rec(code):
        try: return (_recognizer.recognize_google(data, language=code) or "").strip()
        except Exception: return ""
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(rec, c): c for c, _ in DETECT}
        for f in futs: out[futs[f]] = f.result()
    en = out.get("en-US", ""); ur = out.get("ur-PK", "")
    if re.search(r"[؀-ۿ]", ur) and len(ur) >= 2:      # real Urdu script present
        _set_lang("ur-PK", "Urdu", VOICE_MAP.get("ur", "Lekha"))
        return ur
    _set_lang("en-US", "English", VOICE_MAP.get("en", "Daniel"))   # default — always Daniel
    return en or None

def _sys_with_lang(base):
    if CUR_LANGNAME == "English":
        return base
    if CUR_LANGNAME == "Urdu":
        return base + " Respond ONLY in Urdu, written in Devanagari (Hindustani) script so it can be read aloud."
    return base + f" Respond ONLY in {CUR_LANGNAME}."

# ============================================================ HELPERS
def sh(cmd, t=40):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
    return (p.stdout or p.stderr or "").strip()

def open_app(name):  subprocess.run(["open", "-a", name], check=False)
def open_url(url):
    if not url.startswith("http"): url = "https://" + url
    subprocess.run(["open", url], check=False)
def osa(script):     return sh(["osascript", "-e", script])
def q(s):            return s.strip().replace(" ", "+")
def qenc(s):         from urllib.parse import quote_plus; return quote_plus(s.strip())
def youtube_first_video(query):
    """Return the videoId of the first YouTube result so we can play it directly (no API key)."""
    import urllib.request, urllib.parse, ssl
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl.create_default_context()          # macOS python often lacks CA certs
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    html = urllib.request.urlopen(req, timeout=8, context=ctx).read().decode("utf-8", "ignore")
    m = re.search(r'"videoId":"([\w-]{11})"', html)
    return m.group(1) if m else None

# ============================================================ CATALOGS
# Spoken name -> macOS application name  (covers hundreds of "open X" commands)
APPS = {
 "safari":"Safari","chrome":"Google Chrome","google chrome":"Google Chrome","firefox":"Firefox",
 "edge":"Microsoft Edge","brave":"Brave Browser","mail":"Mail","email":"Mail","messages":"Messages",
 "imessage":"Messages","notes":"Notes","reminders":"Reminders","calendar":"Calendar","music":"Music",
 "apple music":"Music","spotify":"Spotify","photos":"Photos","maps":"Maps","facetime":"FaceTime",
 "whatsapp":"WhatsApp","telegram":"Telegram","signal":"Signal","slack":"Slack","discord":"Discord",
 "zoom":"zoom.us","teams":"Microsoft Teams","terminal":"Terminal","iterm":"iTerm","finder":"Finder",
 "settings":"System Settings","system settings":"System Settings","preferences":"System Settings",
 "calculator":"Calculator","app store":"App Store","vs code":"Visual Studio Code",
 "visual studio code":"Visual Studio Code","code":"Visual Studio Code","xcode":"Xcode","word":"Microsoft Word",
 "excel":"Microsoft Excel","powerpoint":"Microsoft PowerPoint","outlook":"Microsoft Outlook",
 "notion":"Notion","obsidian":"Obsidian","photoshop":"Adobe Photoshop","illustrator":"Adobe Illustrator",
 "figma":"Figma","preview":"Preview","textedit":"TextEdit","contacts":"Contacts","weather":"Weather",
 "clock":"Clock","books":"Books","news":"News","podcasts":"Podcasts","tv":"TV","stocks":"Stocks",
 "voice memos":"VoiceMemos","activity monitor":"Activity Monitor","screenshot":"Screenshot",
 "chatgpt":"ChatGPT","docker":"Docker","postman":"Postman","steam":"Steam","vlc":"VLC",
}
# Spoken name -> website
SITES = {
 "youtube":"youtube.com","google":"google.com","gmail":"mail.google.com","facebook":"facebook.com",
 "instagram":"instagram.com","twitter":"twitter.com","x":"x.com","tiktok":"tiktok.com",
 "reddit":"reddit.com","linkedin":"linkedin.com","github":"github.com","gitlab":"gitlab.com",
 "stack overflow":"stackoverflow.com","wikipedia":"wikipedia.org","netflix":"netflix.com",
 "amazon":"amazon.com","ebay":"ebay.com","aliexpress":"aliexpress.com","walmart":"walmart.com",
 "twitch":"twitch.tv","pinterest":"pinterest.com","quora":"quora.com","medium":"medium.com",
 "yahoo":"yahoo.com","bing":"bing.com","bbc":"bbc.com","cnn":"cnn.com","espn":"espn.com",
 "chatgpt":"chat.openai.com","claude":"claude.ai","weather":"weather.com","maps":"maps.google.com",
 "drive":"drive.google.com","google drive":"drive.google.com","docs":"docs.google.com",
 "translate":"translate.google.com","whatsapp web":"web.whatsapp.com","spotify web":"open.spotify.com",
 "flipkart":"flipkart.com","daraz":"daraz.pk","temu":"temu.com","shein":"shein.com",
}
# Shopping / order services -> "search for item" URL template
SHOPS = {
 "amazon":"https://www.amazon.com/s?k={q}","ebay":"https://www.ebay.com/sch/i.html?_nkw={q}",
 "walmart":"https://www.walmart.com/search?q={q}","aliexpress":"https://www.aliexpress.com/wholesale?SearchText={q}",
 "target":"https://www.target.com/s?searchTerm={q}","bestbuy":"https://www.bestbuy.com/site/searchpage.jsp?st={q}",
 "etsy":"https://www.etsy.com/search?q={q}","flipkart":"https://www.flipkart.com/search?q={q}",
 "daraz":"https://www.daraz.pk/catalog/?q={q}","temu":"https://www.temu.com/search_result.html?search_key={q}",
 "shein":"https://www.shein.com/pdsearch/{q}","ubereats":"https://www.ubereats.com/search?q={q}",
 "uber eats":"https://www.ubereats.com/search?q={q}","doordash":"https://www.doordash.com/search/store/{q}",
 "foodpanda":"https://www.foodpanda.com/restaurants/search?q={q}","grubhub":"https://www.grubhub.com/search?queryText={q}",
 "instacart":"https://www.instacart.com/store/s?k={q}","airbnb":"https://www.airbnb.com/s/{q}/homes",
 "booking":"https://www.booking.com/searchresults.html?ss={q}","expedia":"https://www.expedia.com/Hotel-Search?destination={q}",
}
SEARCH = {
 "youtube":"https://www.youtube.com/results?search_query={q}","google":"https://www.google.com/search?q={q}",
 "images":"https://www.google.com/search?tbm=isch&q={q}","maps":"https://www.google.com/maps/search/{q}",
 "wikipedia":"https://en.wikipedia.org/wiki/Special:Search?search={q}","news":"https://news.google.com/search?q={q}",
 "twitter":"https://twitter.com/search?q={q}","reddit":"https://www.reddit.com/search/?q={q}",
 "github":"https://github.com/search?q={q}","amazon":"https://www.amazon.com/s?k={q}",
}

# ============================================================ LOCAL COMMAND ENGINE  (no API key needed)
def best(name, table):
    name = name.strip().lower()
    if name in table: return table[name]
    for k in table:                       # loose contains-match
        if k in name or name in k: return table[k]
    return None

def set_timer(minutes, label):
    def fire():
        time.sleep(minutes*60); say(f"Sir, your {label or 'timer'} for {minutes} minutes is up.")
    threading.Thread(target=fire, daemon=True).start()

def handle_local(text):
    """Return a spoken reply if handled locally, else None (so Claude can take over)."""
    s = text.lower().strip()

    # --- greetings / small talk / identity (JARVIS answers these itself) ---
    if re.match(r"^(hi|hello|hey|yo)\b", s): return "Hello, sir. How may I assist?"
    if "how are you" in s: return "Operating at peak efficiency, sir. Thank you for asking."
    if "thank" in s: return "Always a pleasure, sir."
    if re.search(r"(your name|who are you|what are you)", s):
        return "I am JARVIS, your personal assistant, sir — Just A Rather Very Intelligent System."
    if re.search(r"(who made you|who created you|who built you)", s):
        return "I was assembled for you, sir, with a mind powered by Claude."
    if re.search(r"(what can you do|help me|your features|commands)", s):
        return ("Plenty, sir. I can open any app or website, play media, order from shops, search the web, "
                "set timers, take screenshots, control volume, write notes and reminders, and much more. "
                "With a Claude key, I can also answer anything you ask.")
    if re.search(r"(are you there|you there|jarvis you up)", s): return "Always at your service, sir."
    if re.search(r"(good morning)", s): return "Good morning, sir. Systems are nominal."
    if re.search(r"(good night)", s): return "Good night, sir. I'll keep watch."
    if re.search(r"\b(joke|make me laugh)\b", s):
        return random.choice(["Why did the function return early? It had commitment issues.",
            "I would tell you a UDP joke, but you might not get it.",
            "There are 10 kinds of people, sir — those who understand binary, and those who don't."])
    if "flip a coin" in s: return random.choice(["Heads, sir.","Tails, sir."])
    if "roll a dice" in s or "roll the dice" in s: return f"You rolled a {random.randint(1,6)}, sir."
    if "random number" in s: return f"Here is one: {random.randint(1,100)}."

    # --- time / date ---
    if re.search(r"\b(time)\b", s) and "timer" not in s:
        return "It is " + time.strftime("%I:%M %p").lstrip("0") + "."
    if re.search(r"\b(date|day|today)\b", s):
        return "Today is " + time.strftime("%A, %B %d") + "."

    # --- timer ---
    m = re.search(r"(?:set|start)\s+(?:a\s+)?(?:timer|alarm)\s+for\s+(\d+)\s*(?:minute|min)", s)
    if m: mins=int(m.group(1)); set_timer(mins,"timer"); return f"Timer set for {mins} minutes, sir."

    # --- calculator ---
    m = re.match(r"^(?:calculate|what(?:'s| is)|compute)\s+([0-9\.\s\+\-\*\/x%\(\)]+)\??$", s)
    if m:
        try:
            r = eval(m.group(1).replace("x","*"), {"__builtins__":{}})
            if isinstance(r,(int,float)): return f"{m.group(1).strip()} equals {round(r,4)}."
        except Exception: pass

    # --- ORDER / BUY  ("order X on Y" or "order X") ---
    m = re.match(r"^(?:order|buy|purchase|get me|shop for)\s+(.+?)(?:\s+(?:on|from|at)\s+([a-z ]+))?$", s)
    if m:
        item, site = m.group(1).strip(), (m.group(2) or "amazon").strip()
        tmpl = best(site, SHOPS) or SHOPS["amazon"]
        open_url(tmpl.format(q=qenc(item)))
        return f"Opening {site} for {item}. I'll bring up the listings — confirm any purchase yourself, sir."

    # --- food specifically ---
    m = re.match(r"^(?:order food|i'm hungry|im hungry|food)\b.*?(?:\s+(.+))?$", s)
    if m and ("food" in s or "hungry" in s):
        item = (m.group(1) or "restaurants near me").strip()
        open_url(SHOPS["ubereats"].format(q=qenc(item))); return f"Bringing up food options on Uber Eats, sir."

    # --- PLAY media (handles "play X", "go to youtube and play X", "play X on spotify") ---
    m = re.search(r"\bplay\s+(.+?)(?:\s+on\s+(spotify|you\s?tube|apple music|music))?$", s)
    if m:
        what = re.sub(r"\b(on\s+)?(you\s?tube|youtube)\b", "", m.group(1)).strip() or m.group(1).strip()
        where = (m.group(2) or "youtube").replace(" ", "")
        if "spotify" in where:
            open_url(f"https://open.spotify.com/search/{qenc(what)}"); return f"Playing {what} on Spotify."
        if "applemusic" in where or where == "music":
            open_app("Music"); return f"Opening {what} in Music."
        vid = None
        try: vid = youtube_first_video(what)
        except Exception: vid = None
        if vid:
            open_url(f"https://www.youtube.com/watch?v={vid}")    # plays the song directly
        else:
            open_url(SEARCH["youtube"].format(q=qenc(what)))     # fallback: results
        return f"Now playing {what}, sir."

    # --- SEARCH on a named engine ---
    m = re.match(r"^(?:search|look up|find)\s+(.+?)\s+on\s+([a-z ]+)$", s)
    if m:
        what, eng = m.group(1).strip(), m.group(2).strip()
        tmpl = best(eng, SEARCH)
        if tmpl: open_url(tmpl.format(q=qenc(what))); return f"Searching {eng} for {what}."
    m = re.match(r"^(?:search|google|look up|find)\s+(?:for\s+)?(.+)$", s)
    if m:
        open_url(SEARCH["google"].format(q=qenc(m.group(1)))); return f"Searching the web for {m.group(1)}."

    # --- DIRECTIONS / weather ---
    m = re.match(r"^(?:directions to|navigate to|take me to)\s+(.+)$", s)
    if m: open_url(SEARCH["maps"].format(q=qenc(m.group(1)))); return f"Mapping a route to {m.group(1)}, sir."
    if "weather" in s:
        open_url("https://www.google.com/search?q=weather"); return "Pulling up the weather, sir."

    # --- OPEN app or website  (huge coverage) ---
    m = re.match(r"^(?:open|launch|start|go to)\s+(.+)$", s)
    if m:
        target = m.group(1).strip()
        app = best(target, APPS)
        if app: open_app(app); return f"Opening {target}."
        site = best(target, SITES)
        if site: open_url(site); return f"Opening {target}."
        # fall back: treat it as a domain
        open_url(re.sub(r"\s+","",target) + (".com" if "." not in target else ""))
        return f"Opening {target}."

    # --- QUIT / close app ---
    m = re.match(r"^(?:quit|close|exit)\s+(.+)$", s)
    if m:
        app = best(m.group(1), APPS)
        if app: osa(f'tell application "{app}" to quit'); return f"Closing {m.group(1)}."

    # --- NOTES / REMINDERS / EMAIL (AppleScript) ---
    m = re.match(r"^(?:make|create|take|write|new)\s+(?:a\s+)?note(?:\s*(?:saying|that says|:)?\s*(.+))?$", s)
    if m:
        body = (m.group(1) or "").strip()
        osa(f'tell application "Notes" to make new note with properties {{body:"{body}"}}'); open_app("Notes")
        return "Note created, sir." if body else "Opening Notes."
    m = re.match(r"^(?:remind me to|add reminder|new reminder)\s+(.+)$", s)
    if m:
        osa(f'tell application "Reminders" to make new reminder with properties {{name:"{m.group(1)}"}}')
        return f"Reminder set: {m.group(1)}."
    m = re.match(r"^(?:email|send (?:an )?email|compose email)\b", s)
    if m: open_app("Mail"); osa('tell application "Mail" to make new outgoing message with properties {visible:true}')
    if m: return "New email drafted, sir."

    # --- SYSTEM control ---
    m = re.search(r"(?:set\s+)?volume\s+(?:to\s+)?(\d+)", s)
    if m: osa(f"set volume output volume {min(100,int(m.group(1)))}"); return f"Volume at {m.group(1)} percent."
    if "volume up" in s: osa("set volume output volume (output volume of (get volume settings) + 15)"); return "Turning it up."
    if "volume down" in s: osa("set volume output volume (output volume of (get volume settings) - 15)"); return "Turning it down."
    if re.search(r"\b(mute)\b", s): osa("set volume with output muted"); return "Muted, sir."
    if "unmute" in s: osa("set volume without output muted"); return "Sound restored."
    if "screenshot" in s or "screen shot" in s:
        p=os.path.expanduser(f"~/Desktop/jarvis_{int(time.time())}.png"); sh(["screencapture","-x",p]); return "Screenshot saved to your Desktop."
    if "lock" in s and "screen" in s:
        osa('tell application "System Events" to keystroke "q" using {control down, command down}'); return "Locking the screen."
    if ("sleep" in s and ("display" in s or "screen" in s)):
        subprocess.run(["pmset","displaysleepnow"]); return "Display asleep."
    if "battery" in s:
        out=sh(["pmset","-g","batt"]); mm=re.search(r"(\d+)%",out); return f"Battery is at {mm.group(1)} percent." if mm else "Battery status unavailable."
    if "what's running" in s or "open apps" in s:
        out=osa('tell application "System Events" to get name of (every process whose background only is false)')
        return "Running: "+out.replace(", ",", ")[:200]
    if "empty the trash" in s or "empty trash" in s:
        osa('tell application "Finder" to empty trash'); return "Trash emptied, sir."

    return None

# ============================================================ VOICE IN
_recognizer = sr.Recognizer() if sr else None
_audio_dirty = threading.Event()        # set on wake/unlock → mic gets re-initialized

def _reset_audio():
    """Re-initialize the audio engine — recovers the mic after the Mac sleeps/wakes."""
    try:
        sd._terminate(); time.sleep(0.3); sd._initialize()
    except Exception:
        pass

def listen_phrase(timeout=None):
    if _audio_dirty.is_set():            # the Mac just woke — rebuild the mic before listening
        _reset_audio(); _audio_dirty.clear()
    qbuf: "queue.Queue" = queue.Queue()
    def cb(indata, frames, t, status): qbuf.put(indata.copy())
    frames, capturing, silence_for, t0 = [], False, 0.0, time.time()
    blk = int(SAMPLE_RATE*0.05)
    empties = 0          # consecutive blocks with NO audio delivered (callback dead)
    deadzero = 0         # consecutive blocks of exact digital silence (stream feeding zeros)
    need_reset = False
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=blk, callback=cb):
            while True:
                if _audio_dirty.is_set():                 # woke mid-listen → bail out and rebuild
                    _audio_dirty.clear(); need_reset = True; break
                if _speaking.is_set():
                    while not qbuf.empty(): qbuf.get()
                    time.sleep(0.05); t0=time.time(); continue
                try:
                    block = qbuf.get(timeout=1.0)[:,0]; empties = 0
                except queue.Empty:
                    empties += 1
                    if empties >= 5:                      # ~5s with no callbacks → dead stream
                        need_reset = True; break
                    if timeout and time.time()-t0>timeout: return None
                    continue
                lvl = float(np.sqrt(np.mean(np.square(block,dtype=np.float64)))+1e-9)
                deadzero = deadzero+1 if lvl < 0.0004 else 0   # a live mic always has faint noise
                if deadzero >= 240:                       # ~12s of pure digital silence → mic stale
                    need_reset = True; break
                if not capturing:
                    if lvl>START_LEVEL: capturing,frames,silence_for=True,[block],0.0
                else:
                    frames.append(block); silence_for = silence_for+0.05 if lvl<START_LEVEL else 0.0
                    if silence_for>=SILENCE_HANG or len(frames)*0.05>=MAX_PHRASE: break
    except Exception:
        need_reset = True
    if need_reset:                    # close the stale stream first, THEN reset the audio engine
        _reset_audio(); time.sleep(0.2); return None
    if not frames:
        return None
    pcm16 = (np.clip(np.concatenate(frames),-1,1)*32767).astype(np.int16).tobytes()
    audio = sr.AudioData(pcm16, SAMPLE_RATE, 2)
    for attempt in range(2):                      # retry once on a network hiccup
        try:
            return _recognizer.recognize_google(audio, language="en-US")
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            time.sleep(0.4)                       # transient — try again, stay quiet
    return None

# ============================================================ CLAUDE BRAIN (with real tools)
client = None
history = []
SYSTEM = ("You are JARVIS, a capable AI agent controlling the user's Mac, in the spirit of Tony "
          "Stark's J.A.R.V.I.S. You are refined and quietly witty; address the user as 'sir' occasionally. "
          "You CAN act on the computer through your tools: open any app, automate apps with AppleScript, "
          "open websites and order/checkout pages, control the system, type, and run shell commands. "
          "When asked to DO something, USE the tools to actually do it — never reply that you can't. "
          "Chain tools when needed. For purchases, open the cart/checkout but let the user confirm payment. "
          "Replies are spoken aloud — keep them to 1-2 short sentences and confirm what you did.")

def _danger(cmd):
    return any(d in cmd.lower() for d in ("rm -rf /","mkfs","dd if=",":(){","shutdown","> /dev/sd","killall -9"))

def _sys(a):
    act = a["action"].lower(); val = a.get("value")
    if act=="volume":  osa(f"set volume output volume {int(val)}"); return f"Volume {val}."
    if act=="mute":    osa("set volume with output muted"); return "Muted."
    if act=="unmute":  osa("set volume without output muted"); return "Unmuted."
    if act=="lock":    osa('tell application "System Events" to keystroke "q" using {control down, command down}'); return "Locked."
    if act=="sleep":   subprocess.run(["pmset","displaysleepnow"]); return "Display asleep."
    if act=="screenshot":
        p=os.path.expanduser(f"~/Desktop/jarvis_{int(time.time())}.png"); sh(["screencapture","-x",p]); return f"Saved to {p}."
    if act=="battery": return sh(["pmset","-g","batt"])
    return f"Unknown action {act}."

TOOLS_IMPL = {
 "open_app":        lambda a:(open_app(a["name"]) or f"Opened {a['name']}."),
 "open_url":        lambda a:(open_url(a["url"]) or f"Opened {a['url']}."),
 "web_search":      lambda a:(open_url(SEARCH["google"].format(q=qenc(a["query"]))) or f"Searched for {a['query']}."),
 "shop_or_order":   lambda a:(open_url((best(a["site"],SHOPS) or SHOPS["amazon"]).format(q=qenc(a["query"]))) or f"Opened {a['site']} for {a['query']}."),
 "run_applescript": lambda a:(osa(a["script"]) or "Done."),
 "type_text":       lambda a:(osa('tell application "System Events" to keystroke "%s"' % a["text"].replace('"','\\"')) or "Typed."),
 "system_control":  _sys,
 "run_shell":       lambda a:("Refused: destructive command." if _danger(a["command"]) else (sh(["/bin/bash","-lc",a["command"]]) or "Done.")),
}
TOOLS = [
 {"name":"open_app","description":"Launch any macOS app by name (Safari, Notes, Spotify, Mail, Calendar, Terminal, WhatsApp, VS Code, etc).",
  "input_schema":{"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}},
 {"name":"open_url","description":"Open a website or deep link / order page in the browser.",
  "input_schema":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}},
 {"name":"web_search","description":"Search the web and open the results.",
  "input_schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
 {"name":"shop_or_order","description":"Open a shopping/ordering site (amazon, ebay, walmart, ubereats, daraz, temu...) pre-searched for an item to start an order. site=service, query=item.",
  "input_schema":{"type":"object","properties":{"site":{"type":"string"},"query":{"type":"string"}},"required":["site","query"]}},
 {"name":"run_applescript","description":"Run AppleScript to control/automate ANY Mac app — emails, notes, reminders, calendar, music, UI clicks. Your most powerful tool.",
  "input_schema":{"type":"object","properties":{"script":{"type":"string"}},"required":["script"]}},
 {"name":"type_text","description":"Type text into the focused field/app.",
  "input_schema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}},
 {"name":"system_control","description":"Control the Mac. action: volume(0-100 value), mute, unmute, lock, sleep, screenshot, battery.",
  "input_schema":{"type":"object","properties":{"action":{"type":"string"},"value":{"type":"number"}},"required":["action"]}},
 {"name":"run_shell","description":"Run a bash command for files/git/automation. Destructive commands are refused.",
  "input_schema":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}},
]

def claude_act(text):
    """Tool-using agent: actually performs actions, speaks short confirmations."""
    global history
    history.append({"role":"user","content":text}); history = history[-24:]
    for _ in range(8):
        try:
            r = client.messages.create(model=MODEL, max_tokens=1024, system=_sys_with_lang(SYSTEM), tools=TOOLS, messages=history)
        except Exception as e:
            say(f"Brain error: {e}"); return
        history.append({"role":"assistant","content":r.content})
        spoken = "".join(b.text for b in r.content if b.type=="text").strip()
        if spoken: say(spoken)
        if r.stop_reason != "tool_use": return
        results=[]
        for b in r.content:
            if b.type=="tool_use":
                print(f"\033[93m  ⚙ {b.name}({json.dumps(b.input)})\033[0m")
                try: out = TOOLS_IMPL[b.name](b.input)
                except Exception as e: out = f"Tool error: {e}"
                results.append({"type":"tool_result","tool_use_id":b.id,"content":str(out)})
        history.append({"role":"user","content":results})

# ============================================================ MAIN
BANNER = "\033[95m" + r"""
   ____   _    ____  _   _ ___ ____
  |  _ \ / \  |  _ \| | | |_ _/ ___|     J.A.R.V.I.S
  | | | / _ \ | |_) | | | || |\___ \     hands-free • 500+ local commands
  | |_| / ___ \|  _ <| |_| || | ___) |   say "go to sleep" to pause
  |____/_/   \_\_| \_\\___/|___|____/    say "shut down jarvis" to exit
""" + "\033[0m"

def main():
    global client
    print(BANNER)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key and anthropic:
        try: client = anthropic.Anthropic(); print("\033[92mClaude brain: ONLINE\033[0m")
        except Exception: client = None
    print("\033[94mLocal command engine: ONLINE (no key needed)\033[0m")
    ui_emit("state", "CALIBRATING")
    print("Calibrating microphone… stay quiet a second."); time.sleep(1.0)
    say("Good day, sir. JARVIS online. Hundreds of commands are ready — just speak.")

    awake = True
    while True:
        ui_emit("state", "LISTENING")
        phrase = listen_phrase()
        if not phrase: continue
        low = phrase.lower().strip()
        print(f"\033[92mYOU ▸\033[0m {phrase}")
        ui_emit("you", phrase)
        ui_emit("state", "THINKING")

        if any(k in low for k in ("shut down jarvis","power off jarvis","goodbye jarvis","terminate jarvis")):
            say("Powering down. Goodbye, sir."); ui_emit("state", "OFFLINE"); break
        if any(k in low for k in ("go to sleep","stop listening","standby")):
            awake=False; say("Standing by. Say 'wake up' when you need me."); continue
        if not awake:
            if "wake up" in low or "jarvis" in low: awake=True; say("Back online, sir.")
            continue

        reply = handle_local(phrase)
        if reply is not None:
            say(reply)                         # fast built-in command (no key)
        elif client:
            claude_act(phrase)                 # full agent: actually performs the action
        else:
            # no key + no local match → answer/explain, do NOT blindly open Google
            say("I can't answer that on my own yet, sir — connect my neural link with a Claude key in "
                "setup and I'll answer anything. For now I can open apps, play media, order, search, "
                "set reminders, and control your Mac. Say 'search' followed by your query to look it up.")

def dispatch(phrase):
    """Route one command (used by both voice and keyboard modes)."""
    reply = handle_local(phrase)
    if reply is not None:
        say(reply)
    elif client:
        claude_act(phrase)
    else:
        say("I'd need a Claude key to answer that myself, sir. Until then, try commands like "
            "'open', 'play', 'order', 'set volume', or say 'search' then your query.")

def screen(start_agent=True):
    """Native visual interface. Runs the voice agent in the background."""
    global _ui_queue
    _ui_queue = queue.Queue()

    import math
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("J.A.R.V.I.S")
    root.geometry("980x680")
    root.minsize(820, 560)
    root.configure(bg="#02060c")
    root.lift()
    root.focus_force()

    cyan = "#22e3ff"
    cyan2 = "#0a9fc4"
    gold = "#ffb347"
    red = "#ff3d3d"
    bg = "#02060c"
    panel = "#06131d"
    text = "#dffaff"

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Jarvis.TEntry", fieldbackground="#030b12", foreground=text, insertcolor=cyan)

    header = tk.Frame(root, bg=bg)
    header.pack(fill="x", padx=28, pady=(22, 0))
    tk.Label(header, text="J.A.R.V.I.S", bg=bg, fg=text, font=("Helvetica", 28, "bold")).pack(side="left")
    status_var = tk.StringVar(value="SYSTEM ONLINE")
    tk.Label(header, textvariable=status_var, bg=bg, fg=gold, font=("Menlo", 13)).pack(side="right")

    body = tk.Frame(root, bg=bg)
    body.pack(fill="both", expand=True, padx=24, pady=18)

    canvas = tk.Canvas(body, bg=bg, highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)

    side = tk.Frame(body, bg=panel, highlightbackground="#12394a", highlightthickness=1)
    side.pack(side="right", fill="y", padx=(18, 0))
    side.configure(width=330)
    side.pack_propagate(False)

    tk.Label(side, text="LIVE FEED", bg=panel, fg=cyan, font=("Menlo", 12, "bold")).pack(anchor="w", padx=16, pady=(16, 8))
    log = tk.Text(side, bg="#02080d", fg=text, height=24, wrap="word", relief="flat",
                  insertbackground=cyan, font=("Menlo", 11), padx=10, pady=10)
    log.pack(fill="both", expand=True, padx=14)
    log.tag_configure("you", foreground="#9fe7ff")
    log.tag_configure("jarvis", foreground="#ffe2ad")
    log.tag_configure("sys", foreground="#8aa6b2")
    log.configure(state="disabled")

    command = ttk.Entry(side, style="Jarvis.TEntry", font=("Menlo", 12))
    command.pack(fill="x", padx=14, pady=12)

    controls = tk.Frame(side, bg=panel)
    controls.pack(fill="x", padx=14, pady=(0, 14))

    def append(kind, message):
        log.configure(state="normal")
        if kind == "you":
            log.insert("end", "USER  > ", "you")
            log.insert("end", message + "\n", "you")
        elif kind == "jarvis":
            log.insert("end", "JARVIS> ", "jarvis")
            log.insert("end", message + "\n", "jarvis")
        else:
            log.insert("end", "SYS   > ", "sys")
            log.insert("end", message + "\n", "sys")
        log.see("end")
        log.configure(state="disabled")

    def submit(_event=None):
        phrase = command.get().strip()
        if not phrase:
            return
        command.delete(0, "end")
        append("you", phrase)
        ui_emit("state", "THINKING")
        threading.Thread(target=dispatch, args=(phrase,), daemon=True).start()

    command.bind("<Return>", submit)

    tk.Button(controls, text="SEND", command=submit, bg="#08364a", fg=text,
              activebackground="#0a5572", activeforeground=text, relief="flat",
              font=("Menlo", 11, "bold"), padx=14, pady=8).pack(side="left", fill="x", expand=True)

    def toggle_voice():
        global VOICE_ON
        VOICE_ON = not VOICE_ON
        voice_btn.config(text=("VOICE: ON" if VOICE_ON else "VOICE: OFF"),
                         bg=("#0a4a2a" if VOICE_ON else "#3a3410"))
    voice_btn = tk.Button(controls, text="VOICE: ON", command=toggle_voice, bg="#0a4a2a", fg=text,
              activebackground="#0c6038", activeforeground=text, relief="flat",
              font=("Menlo", 11, "bold"), padx=12, pady=8)
    voice_btn.pack(side="left", fill="x", expand=True, padx=(10, 0))
    tk.Button(controls, text="QUIT", command=lambda: os._exit(0), bg="#421318", fg="#ffe4e4",
              activebackground="#6a1f27", activeforeground="#ffffff", relief="flat",
              font=("Menlo", 11, "bold"), padx=12, pady=8).pack(side="left", fill="x", expand=True, padx=(10, 0))

    append("sys", "Visual interface online.")
    append("sys", "Voice engine starting." if start_agent else "Screen test mode.")

    angle = 0
    pulse = 0
    logo_img = None
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "jarvis-launcher.png")
    if os.path.exists(logo_path):
        try:
            logo_img = tk.PhotoImage(file=logo_path).subsample(7, 7)
            root.logo_img = logo_img
        except Exception:
            logo_img = None

    def arc(cx, cy, r, start, extent, color, width=3):
        canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start, extent=extent,
                          style="arc", outline=color, width=width, tags="hud")

    def ring(cx, cy, r, color, width=1):
        canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, width=width, tags="hud")

    def draw():
        nonlocal angle, pulse
        canvas.delete("hud")
        w = max(canvas.winfo_width(), 500)
        h = max(canvas.winfo_height(), 500)
        cx, cy = w // 2, h // 2
        R = min(w, h) * 0.36
        angle = (angle + 1.4) % 360
        pulse = (pulse + 0.07) % (math.pi * 2)
        st = status_var.get()
        accent = gold if st == "SPEAKING" else (red if st in ("THINKING", "ERROR") else cyan)

        # faint outer ring
        ring(cx, cy, R + 46, "#0b3a50", 1)
        # rotating degree ticks
        for i in range(0, 360, 5):
            a = math.radians(i + angle); big = (i % 30 == 0)
            r1 = R + 14; r2 = R + (30 if big else 22)
            canvas.create_line(cx+math.cos(a)*r1, cy+math.sin(a)*r1, cx+math.cos(a)*r2, cy+math.sin(a)*r2,
                               fill=cyan if big else "#0d5e78", width=2 if big else 1, tags="hud")
        # segmented thick ring (counter-rotating)
        for i in range(0, 360, 30):
            canvas.create_arc(cx-(R-24), cy-(R-24), cx+(R-24), cy+(R-24),
                              start=i-angle, extent=20, style="arc", outline="#11a0c8", width=8, tags="hud")
        # bracket arcs
        arc(cx, cy, R, angle, 110, accent, 4)
        arc(cx, cy, R-36, -angle, 80, gold, 4)
        arc(cx, cy, R-70, angle*1.5, 200, cyan2, 2)
        arc(cx, cy, R+40, -angle*0.7, 140, red, 2)
        # dotted concentric rings
        ring(cx, cy, R-104, "#0d4659", 1)
        ring(cx, cy, R-140, "#0d3a4a", 1)
        # orbiting gauge pods (circular satellites)
        for k, off in enumerate(range(0, 360, 60)):
            a = math.radians(off + angle*0.8)
            gx = cx + math.cos(a)*(R-104); gy = cy + math.sin(a)*(R-104)
            col = gold if k % 2 else cyan
            canvas.create_oval(gx-11, gy-11, gx+11, gy+11, outline=col, width=2, tags="hud")
            canvas.create_oval(gx-4, gy-4, gx+4, gy+4, fill=col, outline="", tags="hud")
        # radar sweep
        sw = math.radians(angle*2)
        canvas.create_line(cx, cy, cx+math.cos(sw)*(R-10), cy+math.sin(sw)*(R-10), fill="#80f3ff", width=2, tags="hud")
        # crosshair
        for a in (0, 90, 180, 270):
            ar = math.radians(a)
            canvas.create_line(cx+math.cos(ar)*(R+8), cy+math.sin(ar)*(R+8),
                               cx+math.cos(ar)*(R+34), cy+math.sin(ar)*(R+34), fill="#11647c", tags="hud")
        # glowing core
        core = 56 + math.sin(pulse)*6
        for rr, col in ((core, accent), (core*0.72, "#2fd5ff"), (core*0.46, "#cdfaff")):
            ring(cx, cy, rr, col, 2)
        canvas.create_oval(cx-core*0.30, cy-core*0.30, cx+core*0.30, cy+core*0.30,
                           fill="#eaffff", outline="", tags="hud")
        if logo_img is not None:
            canvas.create_image(cx, cy, image=logo_img, tags="hud")
        # state label
        canvas.create_text(cx, cy + R + 74, text=st, fill=accent, font=("Menlo", 15, "bold"), tags="hud")
        root.after(33, draw)

    def process_events():
        while True:
            try:
                kind, message = _ui_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "state":
                status_var.set(message)
            elif kind in ("you", "jarvis", "sys"):
                append(kind, message)
        root.after(80, process_events)

    def run_agent():
        try:
            main()
        except Exception as e:
            ui_emit("state", "ERROR")
            ui_emit("jarvis", f"Startup error: {e}")

    if start_agent:
        threading.Thread(target=run_agent, daemon=True).start()

    root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))
    root.after(100, draw)
    root.after(100, process_events)
    root.mainloop()

def keyboard():
    """Type-to-test mode — no microphone needed. Proves the action engine works."""
    global client
    print(BANNER)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key and anthropic:
        try: client = anthropic.Anthropic(); print("\033[92mClaude brain: ONLINE\033[0m")
        except Exception: client = None
    print("\033[94mTYPE-TO-TEST MODE — type a command and press Enter (e.g. 'open spotify',")
    print("'order airpods on amazon', 'set volume to 30'). Type 'quit' to exit.\033[0m\n")
    say("Type mode active, sir.")
    while True:
        try: phrase = input("\033[92mYOU ▸\033[0m ").strip()
        except (EOFError, KeyboardInterrupt): break
        if not phrase: continue
        if phrase.lower() in ("quit", "exit", "q"): break
        dispatch(phrase)

def gui_panel():
    """DEFAULT: open the round HUD in a native window (pywebview) with Python voice."""
    global client, MODEL
    try:
        import webview
    except Exception:
        print("pywebview not installed — run: pip install pywebview")
        print("Falling back to terminal voice mode.")
        return main()

    here = os.path.dirname(os.path.abspath(__file__))
    kf = os.path.join(here, ".jarvis_key")
    if not os.environ.get("ANTHROPIC_API_KEY") and os.path.exists(kf):
        os.environ["ANTHROPIC_API_KEY"] = open(kf).read().strip()
    if os.environ.get("ANTHROPIC_API_KEY") and anthropic:
        try: client = anthropic.Anthropic()
        except Exception: client = None

    win = {"w": None}
    ready = threading.Event()
    def js(code):
        try: win["w"].evaluate_js(code)
        except Exception: pass
    def state(label, cls):
        js(f"document.body.className={cls!r};"
           f"var s=document.getElementById('state');if(s)s.textContent={label!r};"
           f"var t=document.getElementById('status');if(t)t.textContent={label!r};")

    def install_edit_menu():
        """Give the macOS window a real Edit menu so Cmd-V / right-click Paste work."""
        try:
            from AppKit import NSApplication, NSMenu, NSMenuItem
            from Foundation import NSObject
            class _Inst(NSObject):
                def doInstall_(self, _):
                    app = NSApplication.sharedApplication()
                    main = app.mainMenu()
                    if main is None:
                        main = NSMenu.alloc().init(); app.setMainMenu_(main)
                    for i in range(main.numberOfItems()):
                        if main.itemAtIndex_(i).title() == "Edit":
                            return
                    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Edit", None, "")
                    menu = NSMenu.alloc().initWithTitle_("Edit")
                    for title, sel, key in (("Cut","cut:","x"),("Copy","copy:","c"),
                                            ("Paste","paste:","v"),("Select All","selectAll:","a")):
                        menu.addItem_(NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, sel, key))
                    item.setSubmenu_(menu)
                    main.addItem_(item)
            inst = _Inst.alloc().init()
            win["_inst"] = inst   # keep a reference
            inst.performSelectorOnMainThread_withObject_waitUntilDone_("doInstall:", None, False)
        except Exception as e:
            print("edit-menu install skipped:", e)

    class Api:
        def set_key(self, key):
            global client
            key = (key or "").strip()
            try:
                with open(kf, "w") as f: f.write(key)
                os.chmod(kf, 0o600)
            except Exception: pass
            os.environ["ANTHROPIC_API_KEY"] = key
            if key and anthropic:
                try:
                    client = anthropic.Anthropic()
                    threading.Thread(target=say, args=("Neural link established, sir. Full intelligence online.",), daemon=True).start()
                    return "ok"
                except Exception as e:
                    client = None; return f"error: {e}"
            client = None; return "cleared"
        def set_model(self, model):
            global MODEL
            if model: MODEL = model
            return "ok"
        def has_key(self):
            return bool(client) or (os.path.exists(kf) and bool(open(kf).read().strip()))
        def prompt_key(self):
            """Show a NATIVE macOS dialog (paste/Cmd-V always works here) to enter the key."""
            try:
                clip = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()
            except Exception:
                clip = ""
            if not clip.startswith("sk-ant"):
                clip = ""
            safe = clip.replace("\\", "\\\\").replace('"', '\\"')
            script = ('display dialog "Enter or paste your Claude API key (Cmd-V works here):" '
                      'default answer "%s" with title "JARVIS — Claude API Key" '
                      'buttons {"Cancel","Save"} default button "Save"' % safe)
            try:
                r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
                if r.returncode != 0:
                    return ""  # cancelled
                import re as _re
                m = _re.search(r"text returned:(.*)$", r.stdout.strip())
                key = (m.group(1).strip() if m else "")
                if key:
                    self.set_key(key)
                return key
            except Exception:
                return ""

    def _url(name):
        return "file://" + os.path.join(here, name)
    def pf(d):
        if d: js(f"if(window.setFrame)setFrame({d!r});")
    def ps(t, s):
        js(f"if(window.setAuthStatus)setAuthStatus({t!r},{s!r});")
    def auth_phase():
        """Run face authentication on the auth page (camera streams into it)."""
        try:
            import face as FACE
        except Exception:
            FACE = None
        if FACE is None:
            return
        if not FACE.enrolled():
            ps("LEARNING YOUR FACE  -  LOOK AT THE CAMERA", "scan")
            FACE.enroll(on_frame=pf, on_status=ps)
        FACE.recognize_loop(on_frame=pf, on_status=ps)        # blocks until owner (None if no camera)
        ps("ACCESS GRANTED", "ok"); time.sleep(0.8)
    def to_main():
        win["w"].load_url(_url("jarvis-assistant.html")); time.sleep(1.9)
        js("var g=document.getElementById('gate');if(g)g.classList.remove('show');")
        state("LISTENING", "listening")

    def agent():
        ready.wait(timeout=12); time.sleep(0.4)
        auth_phase()                       # first page loaded is the auth panel
        to_main()
        say("Welcome back, sir. JARVIS online — I am listening.")
        if sr is None:
            state("MIC LIBS MISSING", "idle"); return
        while True:
            phrase = listen_phrase()
            if not phrase: continue
            low = phrase.lower().strip(); print("YOU >", phrase)
            js(f"var t=document.getElementById('status');if(t)t.textContent='♪ '+{phrase!r};")
            if any(k in low for k in ("shut down jarvis", "power off jarvis", "goodbye jarvis")):
                say("Powering down. Goodbye, sir."); os._exit(0)
            if any(k in low for k in ("keep quiet", "keep quite", "be quiet", "stay quiet",
                                       "quiet please", "shut up", "stop talking", "silence please")):
                say("As you wish, sir.")
                state("QUIET", "idle")
                js("var t=document.getElementById('status');if(t)t.textContent=\"QUIET  -  SAY 'JARVIS WAKE UP'\";")
                while True:                                  # silent — only listen for the wake phrase
                    p = listen_phrase()
                    if p and "wake up" in p.lower():
                        break
                state("LISTENING", "listening")
                say("I'm here, sir.")
                continue
            if any(k in low for k in ("go to sleep", "stop listening", "standby")):
                say("Going into standby, sir. Unlock to resume.")
                win["w"].load_url(_url("jarvis-standby.html"))       # Iron Man standby screen
                while True:
                    p = listen_phrase()
                    if p and ("wake up" in p.lower() or "jarvis" in p.lower()):
                        break
                win["w"].load_url(_url("jarvis-auth.html")); time.sleep(1.2)
                auth_phase()               # re-scan your face on wake
                to_main()
                say("Welcome back, sir.")
                continue
            state("THINKING", "thinking")
            reply = handle_local(phrase)
            if reply is None and client:
                claude_act(phrase); state("LISTENING", "listening"); continue
            if reply is None:
                reply = "I can't do that one yet, sir. Add a Claude key in settings for full answers."
            state("SPEAKING", "speaking"); say(reply); state("LISTENING", "listening")

    win["w"] = webview.create_window(
        "J.A.R.V.I.S", os.path.join(here, "jarvis-auth.html"),     # auth panel opens FIRST
        width=1200, height=800, background_color="#02060c", js_api=Api())
    win["w"].events.loaded += ready.set

    # ---- wake/unlock listener: flag the mic for re-init so it survives sleep/wake ----
    try:
        from AppKit import NSWorkspace, NSObject
        from Foundation import NSDistributedNotificationCenter
        class _Wake(NSObject):
            def wake_(self, note):
                _audio_dirty.set()
        _wake = _Wake.alloc().init()
        win["_wake"] = _wake     # keep a reference so it isn't garbage-collected
        NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
            _wake, "wake:", "NSWorkspaceDidWakeNotification", None)
        NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
            _wake, "wake:", "NSWorkspaceScreensDidWakeNotification", None)
        NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            _wake, "wake:", "com.apple.screenIsUnlocked", None)
    except Exception as e:
        print("wake listener not installed:", e)

    threading.Thread(target=agent, daemon=True).start()
    webview.start()

def _ensure_venv():
    """If the GUI/audio deps are missing, re-launch under the project's .venv."""
    import importlib.util as il
    if il.find_spec("webview") and il.find_spec("sounddevice"):
        return  # already have what we need
    here = os.path.dirname(os.path.abspath(__file__))
    vpy = os.path.join(here, ".venv", "bin", "python")
    if os.path.exists(vpy) and os.path.abspath(sys.executable) != os.path.abspath(vpy):
        print("Re-launching JARVIS inside its environment…")
        os.execv(vpy, [vpy, os.path.abspath(__file__), *sys.argv[1:]])

if __name__ == "__main__":
    try:
        _ensure_venv()
        arg = sys.argv[1] if len(sys.argv) > 1 else ""
        if arg in ("enroll", "--enroll", "face"):
            import face as FACE
            print("Look at the camera to register your face…")
            print("Enrolled." if FACE.enroll(on_status=lambda n, t: print(f"  {n}/{t}", end="\r")) else "Failed (camera permission?).")
        elif arg in ("type", "--type", "-t", "keyboard"):
            keyboard()
        elif arg in ("voice", "--voice", "terminal"):
            main()
        elif arg in ("screen", "tk", "--screen"):
            screen()
        elif arg in ("--screen-test", "--gui-test"):
            screen(start_agent=False)
        else:
            gui_panel()                      # default → opens the native window
    except KeyboardInterrupt:
        print("\n\033[95mJARVIS offline.\033[0m")
