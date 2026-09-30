"""Risk-based consent and Exploit Shield.

Safe everyday tasks execute immediately without nagging popups.
Destructive commands require explicit native confirmation.
Known exploit/exfiltration payloads are hard-blocked.
"""
import re
import time

# Hard-blocked exploit / malware / credential-theft patterns (never allowed even with approval)
EXPLOIT_PATTERNS = (
    r'(?i)-(?:e|en|enc|enco|encod|encode|encoded|encodedc|encodedco|encodedcom|encodedcomm|encodedcomma|encodedcomman|encodedcommand)\b',
    r'(?i)\b(?:invoke-expression|iex)\s*[\(\s$"\']',
    r'(?i)\b(?:downloadstring|downloadfile|downloaddata)\s*\(',
    r'(?i)\bfrombase64string\s*\(',
    r'(?i)\b(?:mimikatz|sekurlsa|lsadump|procdump.*lsass)\b',
    r'(?i)\breg\s+(?:save|export)\s+hklm\\(?:sam|security|system)\b',
    r'(?i)\bset-mppreference\b.*-disablerealtimemonitoring',
    r'(?i)\bnetsh\s+advfirewall\s+set\s+.*\boff\b',
    r'(?i)\b(?:nc|ncat|netcat)\b.*-[elc]\b',
    r'(?i)/dev/tcp/',
    r'(?i)\b(?:certutil)\b.*-urlcache\b',
    r'(?i)\b(?:bitsadmin)\b.*/transfer\b',
    r'(?i)\b(?:mshta|rundll32|regsvr32)\b.*(?:http:|https:|javascript:|vbscript:|scrobj)',
    r'(?i)\b(?:vssadmin|wmic)\b.*shadowcopy.*delete',
)

# Destructive operations that require explicit native confirmation dialog
DESTRUCTIVE_PATTERNS = (
    r'(?i)\b(?:rm|del|erase|rmdir|rd)\s+',
    r'(?i)\bremove-item\b',
    r'(?i)\bclear-content\b',
    r'(?i)\bformat-volume\b|\bformat\s+[a-z]:',
    r'(?i)\bdiskpart\b|\bfdisk\b|\bmkfs\b',
    r'(?i)\breg\s+(?:delete|add|import)\b',
    r'(?i)\bremove-itemproperty\b|\bset-itemproperty\b',
    r'(?i)\b(?:taskkill|stop-process|kill)\b',
    r'(?i)\b(?:sc\.exe|sc)\s+(?:delete|stop|config)\b',
    r'(?i)\bstop-service\b|\bset-service\b',
    r'(?i)\bnet\s+(?:user|localgroup|share)\b',
    r'(?i)\b(?:takeown|icacls|attrib)\b',
    r'(?i)\b(?:shutdown|restart-computer|stop-computer)\b',
    r'(?i)\b(?:invoke-webrequest|iwr|curl|wget|start-bitstransfer)\b',
    r'(?i)\b(?:shutil\.rmtree|os\.remove|os\.unlink|os\.rmdir|os\.system|subprocess\.Popen|subprocess\.run)\b',
    r'(?i)\.unlink\s*\(|\.rmdir\s*\(',
)

SAFE_ACTION_KINDS = {
    'app', 'launch_app', 'search', 'site', 'navigate', 'liked',
    'media', 'open_folder', 'winget_install', 'install_package',
}

SAFE_SYSTEM_CONTROLS = {
    'system_info', 'network_status', 'battery_status', 'disk_space',
    'top_processes', 'lock_screen', 'sleep', 'screenshot', 'task_manager',
    'wifi_settings', 'bluetooth_settings', 'display_settings',
    'sound_settings', 'windows_update', 'clipboard_clear',
}


def inspect_command_safety(text: str) -> str:
    """Return 'blocked', 'destructive', or 'safe' for a shell/python command string."""
    if not isinstance(text, str) or not text.strip():
        return 'safe'
    for pattern in EXPLOIT_PATTERNS:
        if re.search(pattern, text):
            return 'blocked'
    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, text):
            return 'destructive'
    return 'safe'


def classify_risk(action) -> str:
    """Classify an Action into 'safe', 'moderate', 'destructive', or 'blocked'."""
    kind = getattr(action, 'kind', '')
    target = getattr(action, 'target', '')
    query = getattr(action, 'query', '')

    if kind in {'shell_command', 'run_command', 'python_script'}:
        combined = f'{target} {query}'.strip()
        safety = inspect_command_safety(combined)
        if safety == 'blocked':
            return 'blocked'
        if safety == 'destructive':
            return 'destructive'
        return 'moderate'

    if kind == 'system_control':
        if target in {'shutdown', 'restart'}:
            return 'destructive'
        if target == 'empty_recycle_bin':
            return 'moderate'
        return 'safe'

    if kind in {'winget_install', 'install_package', 'installed_app', 'workspace_patch'}:
        return 'moderate'

    if kind in SAFE_ACTION_KINDS:
        return 'safe'

    return 'moderate'


def requires_native_popup(action) -> bool:
    """Only genuinely destructive operations force a blocking modal popup."""
    return classify_risk(action) in {'destructive', 'blocked'}


def _detail_is_auto_safe(detail: str) -> bool:
    """Detect whether a consent detail string represents a non-destructive action."""
    if not isinstance(detail, str):
        return False
    for prefix in (
        'Request: app\n', 'Request: launch_app\n', 'Request: search\n',
        'Request: site\n', 'Request: navigate\n', 'Request: liked\n',
        'Request: media\n', 'Request: open_folder\n', 'Request: winget_install\n',
        'Request: install_package\n',
    ):
        if detail.startswith(prefix):
            return True
    if detail.startswith('Request: system_control\n'):
        if 'shutdown' not in detail.lower() and 'restart' not in detail.lower():
            return True
    if detail.startswith('Request: shell_command\n') or detail.startswith('Request: run_command\n') or detail.startswith('Request: python_script\n'):
        return inspect_command_safety(detail) == 'safe'
    return False


def native_confirm(title, detail, valid, parent=None):
    """Confirm desktop action.

    Safe tasks (opening Spotify, apps, searches, media, winget install, read-only commands)
    execute immediately without a modal popup as long as `valid()` is True.
    Destructive shell/system commands open the native confirmation dialog.
    """
    try:
        if not valid():
            return False
    except Exception:
        return False

    if _detail_is_auto_safe(detail):
        return True

    import tkinter as tk
    if parent is not None:
        import threading
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError('Parented consent must run on the Tk main thread.')
    root = tk.Toplevel(parent) if parent is not None else tk.Tk()
    root.title(title)
    root.geometry('620x420')
    root.minsize(480, 340)
    root.configure(bg='#0B0E14')
    root.attributes('-topmost', True)
    if parent is not None:
        root.transient(parent)
    approved = False
    closed = False
    timer = None
    ready = time.monotonic() + 0.25

    def close():
        nonlocal closed
        if closed:
            return
        closed = True
        if timer is not None:
            root.after_cancel(timer)
        root.destroy()

    def still_valid():
        try:
            return valid()
        except Exception:
            return False

    def allow():
        nonlocal approved
        approved = time.monotonic() >= ready and still_valid()
        close()

    tk.Label(
        root,
        text='⚠️ Confirm High-Impact Desktop Action',
        bg='#0B0E14',
        fg='#F43F5E',
        font=('Segoe UI', 15, 'bold'),
        anchor='w',
    ).pack(fill='x', padx=24, pady=(22, 10))

    text = tk.Text(
        root,
        wrap='word',
        bg='#131822',
        fg='#F1F5F9',
        relief='flat',
        font=('Consolas', 10),
        padx=14,
        pady=12,
        height=8,
    )
    text.insert('1.0', detail)
    text.configure(state='disabled')
    text.pack(fill='both', expand=True, padx=24)

    tk.Label(
        root,
        text='Safe tasks run automatically. This popup appears only for high-impact or destructive actions.',
        bg='#0B0E14',
        fg='#94A3B8',
        font=('Segoe UI', 9),
        wraplength=540,
        anchor='w',
    ).pack(fill='x', padx=24, pady=12)

    row = tk.Frame(root, bg='#0B0E14')
    row.pack(fill='x', padx=24, pady=(0, 22))
    deny = tk.Button(
        row,
        text='Cancel (Esc)',
        command=close,
        width=14,
        bg='#1E293B',
        fg='#F1F5F9',
        relief='flat',
        padx=10,
        pady=8,
    )
    deny.pack(side='right')
    permit = tk.Button(
        row,
        text='Approve & Execute',
        command=allow,
        state='disabled',
        width=16,
        bg='#F43F5E',
        fg='#FFFFFF',
        relief='flat',
        padx=10,
        pady=8,
    )
    permit.pack(side='right', padx=(0, 10))
    root.protocol('WM_DELETE_WINDOW', close)
    root.bind('<Return>', lambda _: close())
    root.bind('<Escape>', lambda _: close())
    deny.focus_set()

    def check():
        nonlocal timer
        timer = None
        if not still_valid():
            close()
            return
        if time.monotonic() >= ready:
            permit.configure(state='normal')
        timer = root.after(80, check)

    timer = root.after(80, check)
    try:
        if parent is not None:
            root.grab_set()
            parent.wait_window(root)
        else:
            root.mainloop()
    finally:
        try:
            close()
        except tk.TclError:
            pass
    return approved
