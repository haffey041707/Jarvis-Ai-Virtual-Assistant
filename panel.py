#!/usr/bin/env python3
"""JARVIS native panel — thin launcher. Opens the round HUD window with voice.
(Same as running `python jarvis.py`.)"""
import os, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("jarvis", os.path.join(here, "jarvis.py"))
J = importlib.util.module_from_spec(spec)
spec.loader.exec_module(J)

if __name__ == "__main__":
    J.gui_panel()
