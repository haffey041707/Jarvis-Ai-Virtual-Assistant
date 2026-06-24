import sys
from AppKit import NSImage, NSWorkspace
img = NSImage.alloc().initWithContentsOfFile_(sys.argv[1])
ok = NSWorkspace.sharedWorkspace().setIcon_forFile_options_(img, sys.argv[2], 0)
print("icon applied:", bool(ok))
