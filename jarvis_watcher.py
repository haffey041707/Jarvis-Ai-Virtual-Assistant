#!/usr/bin/env python3
"""
JARVIS watcher — stays running in the background and launches JARVIS whenever you
unlock the Mac (Touch ID / password) or wake it from sleep. This is what makes
JARVIS appear automatically when you open your laptop.
"""
import os, time, subprocess
from AppKit import NSWorkspace, NSObject
from Foundation import NSDistributedNotificationCenter, NSRunLoop, NSDate

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.expanduser("~/Desktop/JARVIS.app")

def jarvis_running():
    r = subprocess.run(["pgrep", "-f", "jarvis.py"], capture_output=True, text=True)
    return bool(r.stdout.strip())

def launch_jarvis():
    if jarvis_running():
        return
    if os.path.exists(APP):
        subprocess.Popen(["open", "-a", APP])          # launches as the app (best for camera/mic permissions)
    else:
        subprocess.Popen([os.path.join(HERE, ".venv/bin/python"), os.path.join(HERE, "jarvis.py")])

class Watcher(NSObject):
    def handle_(self, note):
        time.sleep(1.2)        # let the session settle after unlock/wake
        launch_jarvis()

def main():
    w = Watcher.alloc().init()
    # Touch ID / password unlock:
    NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
        w, "handle:", "com.apple.screenIsUnlocked", None)
    # wake from sleep:
    NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
        w, "handle:", "NSWorkspaceDidWakeNotification", None)
    launch_jarvis()            # also launch now (at login / when the watcher starts)
    rl = NSRunLoop.currentRunLoop()
    while True:
        rl.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(60))

if __name__ == "__main__":
    main()
