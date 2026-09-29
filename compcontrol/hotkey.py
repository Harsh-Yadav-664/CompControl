"""Windows summon shortcut on its own message thread; never records keystrokes."""
import ctypes
import platform
import queue
import threading
from ctypes import wintypes


class SummonHotkey:
    ID = 0x4343
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012

    def __init__(self, root, callback):
        self.root, self.callback = root, callback
        self.active = False
        self.closed = False
        self.timer = None
        self.events = queue.Queue()
        if platform.system() != 'Windows':
            self.status = 'Ctrl+L focuses the request'
            return
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        self.user32.RegisterHotKey.restype = wintypes.BOOL
        self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.UnregisterHotKey.restype = wintypes.BOOL
        self.user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        self.user32.GetMessageW.restype = ctypes.c_int
        self.user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
        self.user32.PeekMessageW.restype = wintypes.BOOL
        self.user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.PostThreadMessageW.restype = wintypes.BOOL
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        self.ready.wait()
        self.status = 'Ctrl+Alt+Space to summon' if self.active else 'Hotkey unavailable · use the taskbar'
        if self.active:
            self._poll()

    def _listen(self):
        try:
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD
            self.thread_id = kernel32.GetCurrentThreadId()
            # Create the message queue before publishing readiness/shutdown support.
            msg = wintypes.MSG()
            self.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
            # Ctrl + Alt + Space, MOD_NOREPEAT. Registration belongs to this thread.
            self.active = bool(self.user32.RegisterHotKey(None, self.ID, 0x4003, 0x20))
        except (OSError, AttributeError):
            self.active = False
        finally:
            # A failed setup must never leave the Tk constructor waiting forever.
            self.ready.set()
        if not self.active:
            return
        try:
            msg = wintypes.MSG()
            while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == self.WM_HOTKEY and msg.wParam == self.ID:
                    self.events.put(True)
        finally:
            self.user32.UnregisterHotKey(None, self.ID)

    def _poll(self):
        if self.closed:
            return
        received = False
        while True:
            try:
                self.events.get_nowait()
                received = True
            except queue.Empty:
                break
        if received:
            self.callback()
        if not self.closed:
            self.timer = self.root.after(120, self._poll)

    def close(self):
        self.closed = True
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.active:
            self.user32.PostThreadMessageW(self.thread_id, self.WM_QUIT, 0, 0)
            self.thread.join(timeout=1)
            self.active = False
