"""Windowed executable bootstrap: surface failures without a missing console."""
import ctypes

if __name__ == '__main__':
    try:
        from compcontrol.__main__ import main
        code = main()
    except Exception:
        code = 1
    if code:
        ctypes.windll.user32.MessageBoxW(None,
            'CompControl could not start. Keep the full application folder together.\n'
            'For source diagnostics, run scripts/start-windows.cmd. Do not run as administrator.',
            'CompControl startup error', 0x10)
    raise SystemExit(code)
