"""Double-click launcher: native window, no browser or persistent console."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0, str(root))

try:
    from compcontrol.__main__ import main
    code = main()
    if code:
        raise RuntimeError('CompControl could not start. Run scripts/start-windows.cmd to see details.')
except Exception:
    # A .pyw process has no terminal; never leave a silent startup failure.
    import ctypes
    ctypes.windll.user32.MessageBoxW(None,
        'CompControl could not start. Install Python 3.10+ with Tcl/Tk enabled.\n'
        'Run scripts/start-windows.cmd to see diagnostic details.', 'CompControl', 0x10)
