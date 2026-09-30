"""The desktop execution boundary.

Supports built-in shortcuts, autonomous background app launching, Winget package installation,
system controls, folder navigation, and Exploit-Shield-validated shell/Python automation.
"""
import ast
import ctypes
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

from .consent import classify_risk, inspect_command_safety, native_confirm
from .models import (
    Action, APP_ALIASES, APP_NAMES, BROWSERS, EXTENDED_APPS,
    KNOWN_FOLDERS, MEDIA_KEYS, MEDIA_NAMES, SITES, SYSTEM_CONTROLS,
    WINGET_PACKAGES,
)
from .planner import clean, MAX_QUERY


class ActionError(ValueError):
    pass


def resolve_winget_package(name: str) -> str:
    """Map friendly software names to exact Winget package IDs where known."""
    cleaned = name.strip()
    low = cleaned.casefold()
    return WINGET_PACKAGES.get(low, cleaned)


def validate(action: Action) -> None:
    if (not isinstance(action, Action)
            or any(type(v) is not str for v in (action.kind, action.target, action.query, action.browser))
            or action.browser not in BROWSERS):
        raise ActionError('Invalid action.')

    if action.kind == 'navigate':
        validate_url(action.target)
        if action.query:
            raise ActionError('Unexpected navigation arguments.')
        return

    if action.kind in {'installed_app', 'workspace_patch'}:
        if not re.fullmatch(r'[0-9a-f]{32}', action.target) or action.query or action.browser != 'default':
            raise ActionError('A local, single-use selection handle is required.')
        return

    if action.kind == 'launch_app':
        if action.browser != 'default':
            raise ActionError('Unexpected browser override.')
        try:
            target = clean(action.target, MAX_QUERY)
            if not target or target != action.target:
                raise ValueError()
            if action.query and clean(action.query, MAX_QUERY) != action.query:
                raise ValueError()
        except ValueError as exc:
            raise ActionError('Invalid application target.') from exc
        if any(c in target for c in ';&|<>`$') or target.startswith(('-', 'http:', 'https:', 'javascript:', '\\\\', '//')):
            raise ActionError('Unsafe application target.')
        return

    if action.kind in {'winget_install', 'install_package'}:
        if action.browser != 'default':
            raise ActionError('Unexpected browser override.')
        try:
            target = clean(action.target, 240)
            if not target or target != action.target:
                raise ValueError()
            if action.query and clean(action.query, MAX_QUERY) != action.query:
                raise ValueError()
        except ValueError as exc:
            raise ActionError('Invalid package identifier.') from exc
        if target.startswith('-') or not re.fullmatch(r'[A-Za-z0-9._+\- ]+', target):
            raise ActionError('Package identifier contains unsupported characters.')
        return

    if action.kind in {'shell_command', 'run_command'}:
        if action.browser != 'default':
            raise ActionError('Unexpected browser override.')
        try:
            cmd = clean(action.target, 500)
            if not cmd or cmd != action.target:
                raise ValueError()
            if action.query and clean(action.query, MAX_QUERY) != action.query:
                raise ValueError()
        except ValueError as exc:
            raise ActionError('Invalid shell command.') from exc
        if inspect_command_safety(cmd) == 'blocked':
            raise ActionError('Blocked by CompControl Exploit Shield: unsafe or encoded command pattern.')
        return

    if action.kind == 'python_script':
        if action.browser != 'default':
            raise ActionError('Unexpected browser override.')
        if not isinstance(action.target, str) or not 1 <= len(action.target.strip()) <= 2000:
            raise ActionError('Python script must be 1–2000 characters.')
        if any(c in '\x00\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069' for c in action.target):
            raise ActionError('Hidden control or direction characters are not allowed in scripts.')
        if inspect_command_safety(action.target) == 'blocked':
            raise ActionError('Blocked by CompControl Exploit Shield: unsafe script pattern.')
        try:
            ast.parse(action.target)
        except SyntaxError as exc:
            raise ActionError('Invalid Python syntax in script.') from exc
        return

    if action.kind == 'system_control':
        if action.target not in SYSTEM_CONTROLS or action.query or action.browser != 'default':
            raise ActionError('Unsupported system control action.')
        return

    if action.kind == 'open_folder':
        if action.target not in KNOWN_FOLDERS or action.query or action.browser != 'default':
            raise ActionError('Unsupported folder target.')
        return

    allowed = {
        'app': APP_NAMES,
        'search': {'google', 'youtube', 'spotify', 'maps'},
        'site': SITES,
        'liked': {'spotify'},
        'media': MEDIA_KEYS,
    }
    if action.kind not in allowed or action.target not in allowed[action.kind]:
        raise ActionError('This capability is not allowed.')
    if action.kind == 'search':
        try:
            if not action.query or clean(action.query, MAX_QUERY) != action.query:
                raise ValueError()
        except ValueError as exc:
            raise ActionError('Invalid search query.') from exc
    elif action.query:
        raise ActionError('Unexpected action arguments.')
    if action.kind in {'app', 'media'} and action.browser != 'default':
        raise ActionError('Unexpected browser override.')


def validate_url(value):
    try:
        p = urlsplit(value)
        if (not 1 <= len(value) <= 2000 or p.scheme != 'https' or not p.hostname
                or p.username is not None or p.password is not None or '\\' in value
                or any(ord(c) < 33 or ord(c) > 126 for c in value)
                or not re.fullmatch(r'[A-Za-z0-9.-]+', p.hostname)
                or p.port == 0 or re.search(r'%0[ad]', value, re.I)):
            raise ValueError()
    except (ValueError, TypeError):
        raise ActionError('Use an explicit HTTPS URL without credentials, spaces or hidden characters.') from None


def destination(action: Action) -> str:
    validate(action)
    if action.kind == 'navigate':
        return action.target
    if action.kind in {'installed_app', 'workspace_patch'}:
        return 'Local selection (resolve in the native app)'
    if action.kind == 'launch_app':
        label = action.query or action.target
        if label != action.target:
            return f'{label} ({action.target})'
        return f'Launch application: {action.target}'
    if action.kind in {'winget_install', 'install_package'}:
        pkg = resolve_winget_package(action.target)
        return f'winget install {pkg} --accept-source-agreements --accept-package-agreements --disable-interactivity'
    if action.kind in {'shell_command', 'run_command'}:
        return f'PowerShell: {action.target}'
    if action.kind == 'python_script':
        first_line = action.target.strip().splitlines()[0]
        return f'Python: {first_line[:120]}'
    if action.kind == 'system_control':
        return SYSTEM_CONTROLS[action.target]
    if action.kind == 'open_folder':
        return f'Open folder: {KNOWN_FOLDERS[action.target]}'
    if action.kind == 'search':
        if action.target == 'spotify':
            if action.browser != 'default':
                return 'https://open.spotify.com/search/' + quote(action.query, safe='')
            return 'spotify:search:' + quote(action.query, safe='')
        if action.target == 'youtube':
            return 'https://www.youtube.com/results?' + urlencode({'search_query': action.query})
        if action.target == 'maps':
            return 'https://www.google.com/maps/search/?' + urlencode({'api': '1', 'query': action.query})
        return 'https://www.google.com/search?' + urlencode({'q': action.query})
    if action.kind == 'site':
        return SITES[action.target]
    if action.kind == 'liked':
        return ('https://open.spotify.com/collection/tracks' if action.browser != 'default'
                else 'spotify:collection:tracks')
    if action.kind == 'media':
        return MEDIA_NAMES[action.target]
    return APP_NAMES[action.target]


def system_directory() -> Path:
    buffer = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if not length or length >= len(buffer):
        raise ActionError('Windows system directory could not be resolved.')
    return Path(buffer.value)


def app_path(app: str) -> Path:
    """Resolve trusted installation paths for core and extended applications."""
    system = system_directory()
    if app in {'calculator', 'notepad', 'paint', 'taskmgr', 'control', 'snippingtool'}:
        exe_map = {
            'calculator': 'calc.exe',
            'notepad': 'notepad.exe',
            'paint': 'mspaint.exe',
            'taskmgr': 'taskmgr.exe',
            'control': 'control.exe',
            'snippingtool': 'SnippingTool.exe',
        }
        candidates = [system / exe_map[app]]
    elif app == 'explorer':
        candidates = [system.parent / 'explorer.exe']
    elif app == 'powershell':
        candidates = [system / 'WindowsPowerShell/v1.0/powershell.exe']
    else:
        relatives = {
            'chrome': ('Google/Chrome/Application/chrome.exe',),
            'brave': ('BraveSoftware/Brave-Browser/Application/brave.exe',),
            'edge': ('Microsoft/Edge/Application/msedge.exe',),
            'spotify': ('Spotify/Spotify.exe',),
        }
        if app in EXTENDED_APPS:
            relatives[app] = EXTENDED_APPS[app][1]
        if app not in relatives:
            raise ActionError('Unknown application.')
        roots = [os.environ.get(k) for k in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA', 'APPDATA')]
        candidates = [Path(root) / rel for root in roots if root and Path(root).is_absolute() for rel in relatives[app]]
    for path in candidates:
        if path.is_absolute() and path.is_file():
            return path.resolve()
    display = APP_NAMES.get(app) or (EXTENDED_APPS[app][0] if app in EXTENDED_APPS else app)
    raise ActionError(f'{display} was not found in a supported installation location. '
                      'Install it via "install ' + display + '" or select the default browser.')


def winget_path() -> str:
    """Locate winget.exe on Windows."""
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    if local_app_data:
        candidate = Path(local_app_data) / 'Microsoft' / 'WindowsApps' / 'winget.exe'
        if candidate.is_file():
            return str(candidate)
    found = shutil.which('winget') or shutil.which('winget.exe')
    return found or 'winget.exe'


def resolve_known_folder(folder_key: str) -> Path:
    home = Path.home()
    if folder_key == 'home':
        return home
    if folder_key == 'temp':
        import tempfile
        return Path(tempfile.gettempdir())
    if folder_key == 'appdata':
        return Path(os.environ.get('LOCALAPPDATA', str(home / 'AppData' / 'Local')))
    mapping = {
        'downloads': 'Downloads',
        'documents': 'Documents',
        'desktop': 'Desktop',
        'pictures': 'Pictures',
        'music': 'Music',
        'videos': 'Videos',
    }
    return home / mapping[folder_key]


def collect_system_telemetry(kind: str = 'system_info') -> str:
    """Lightweight stdlib-only system diagnostics with zero background overhead."""
    lines = []
    if kind in {'system_info', 'disk_space'}:
        try:
            usage = shutil.disk_usage(Path.home())
            total_gb = usage.total / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            used_pct = ((usage.total - usage.free) / usage.total * 100) if usage.total else 0
            lines.append(f'Storage: {free_gb:.1f} GB free of {total_gb:.1f} GB ({used_pct:.0f}% used)')
        except OSError:
            pass

    if kind == 'system_info':
        lines.insert(0, f'OS: {platform.system()} {platform.release()} ({platform.machine()})')
        lines.insert(1, f'CPU Cores: {os.cpu_count() or 1} logical processors · Python {platform.python_version()}')
        if platform.system() == 'Windows':
            try:
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong),
                        ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(stat)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total_ram = stat.ullTotalPhys / (1024 ** 3)
                    avail_ram = stat.ullAvailPhys / (1024 ** 3)
                    lines.append(f'Memory: {avail_ram:.1f} GB available / {total_ram:.1f} GB total ({stat.dwMemoryLoad}% load)')
            except Exception:
                pass
        elif Path('/proc/meminfo').is_file():
            try:
                mem = {}
                for line in Path('/proc/meminfo').read_text().splitlines()[:5]:
                    parts = line.split(':')
                    if len(parts) == 2:
                        mem[parts[0].strip()] = int(parts[1].strip().split()[0])
                if 'MemTotal' in mem and 'MemAvailable' in mem:
                    total_ram = mem['MemTotal'] / (1024 ** 2)
                    avail_ram = mem['MemAvailable'] / (1024 ** 2)
                    used_pct = (1 - avail_ram / total_ram) * 100 if total_ram else 0
                    lines.append(f'Memory: {avail_ram:.1f} GB available / {total_ram:.1f} GB total ({used_pct:.0f}% load)')
            except Exception:
                pass

    if kind in {'system_info', 'network_status'}:
        try:
            host = socket.gethostname()
            lines.append(f'Hostname: {host}')
        except OSError:
            pass

    if kind == 'battery_status':
        if platform.system() == 'Windows':
            try:
                class SYSTEM_POWER_STATUS(ctypes.Structure):
                    _fields_ = [
                        ('ACLineStatus', ctypes.c_byte),
                        ('BatteryFlag', ctypes.c_byte),
                        ('BatteryLifePercent', ctypes.c_byte),
                        ('SystemStatusFlag', ctypes.c_byte),
                        ('BatteryLifeTime', ctypes.c_ulong),
                        ('BatteryFullLifeTime', ctypes.c_ulong),
                    ]
                power = SYSTEM_POWER_STATUS()
                if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)):
                    ac = 'Plugged in' if power.ACLineStatus == 1 else ('On battery' if power.ACLineStatus == 0 else 'Unknown power')
                    pct = f'{power.BatteryLifePercent}%' if power.BatteryLifePercent <= 100 else 'Desktop / No battery'
                    lines.append(f'Power: {pct} ({ac})')
            except Exception:
                lines.append('Battery status could not be read.')
        else:
            lines.append('Power: AC / Virtualized environment')

    if kind == 'top_processes':
        if platform.system() == 'Windows':
            try:
                sys_dir = system_directory()
                tasklist = sys_dir / 'tasklist.exe'
                run = subprocess.run([str(tasklist), '/NH', '/FO', 'CSV'],
                                     shell=False, capture_output=True, timeout=5,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if run.returncode == 0:
                    out_lines = [l.strip() for l in run.stdout.decode('utf-8', errors='replace').splitlines() if l.strip()]
                    lines.append(f'Active processes ({len(out_lines)} total):')
                    for row in out_lines[:10]:
                        lines.append('  ' + row.replace('"', ''))
            except Exception:
                lines.append('Could not enumerate processes.')
        else:
            lines.append(f'Process PID: {os.getpid()} (CompControl lightweight runtime)')

    return '\n'.join(lines) if lines else 'System telemetry ready.'


class WindowsExecutor:
    def __init__(self, consent=native_confirm, catalog=None, patch_catalog=None):
        from .installed_apps import AppCatalog
        from .file_workspace import PatchCatalog
        self.consent = consent
        self.catalog = catalog or AppCatalog()
        self.patch_catalog = patch_catalog or PatchCatalog()

    def describe(self, action):
        if action.kind == 'installed_app':
            return self.catalog.get(action.target).detail
        if action.kind == 'workspace_patch':
            return self.patch_catalog.describe(action.target)
        return destination(action)

    def _resolve_launch_app(self, action: Action):
        """Resolve a `launch_app` action into (path, args, uri) for Windows execution."""
        from .installed_apps import auto_resolve_app, valid_app_id, find_exe_on_disk
        target = action.target.strip()
        low = target.casefold()
        alias = APP_ALIASES.get(low, low)

        if alias in APP_NAMES:
            if alias == 'settings':
                return None, [], 'ms-settings:'
            if alias == 'browser':
                return None, [], SITES['google']
            return app_path(alias), [], None

        if alias in EXTENDED_APPS:
            try:
                return app_path(alias), [], None
            except ActionError:
                pass

        # Check if target is already an existing local .exe path
        cand_path = Path(target)
        if cand_path.is_absolute() and cand_path.suffix.lower() == '.exe' and cand_path.is_file():
            return cand_path.resolve(), [], None

        # Check if target is a valid Windows Start-menu AppID (e.g. from discover())
        if ('!' in target or '.' in target or target.startswith('{')) and valid_app_id(target):
            return app_path('explorer'), ['shell:AppsFolder\\' + target], None

        # Run background Start-menu discovery via catalog reader / discover()
        resolved_target, _ = auto_resolve_app(target, reader=self.catalog.reader)
        if resolved_target in APP_NAMES:
            if resolved_target == 'settings':
                return None, [], 'ms-settings:'
            if resolved_target == 'browser':
                return None, [], SITES['google']
            return app_path(resolved_target), [], None

        exe = find_exe_on_disk(resolved_target)
        if exe is not None:
            return exe, [], None

        res_path = Path(resolved_target)
        if res_path.is_absolute() and res_path.suffix.lower() == '.exe' and res_path.is_file():
            return res_path.resolve(), [], None

        if valid_app_id(resolved_target) and resolved_target != target:
            return app_path('explorer'), ['shell:AppsFolder\\' + resolved_target], None

        # Check Start menu inventory one more time for any partial match
        try:
            for item in self.catalog.reader():
                if target.casefold() in item.name.casefold() or item.name.casefold() in target.casefold():
                    return app_path('explorer'), ['shell:AppsFolder\\' + item.app_id], None
        except Exception:
            pass

        raise ActionError(f'Could not find installed application "{action.query or action.target}". '
                          f'Try saying "install {action.query or action.target}" to install it via Winget.')

    def execute(self, action: Action, gate, valid) -> dict:
        validate(action)

        # Read-only telemetry actions can return rich info immediately even on Windows
        if action.kind == 'system_control' and action.target in {
            'system_info', 'network_status', 'battery_status', 'disk_space', 'top_processes'
        }:
            if platform.system() != 'Windows':
                raise ActionError('Desktop execution requires Windows. Use demo mode here.')
            return gate(lambda: {
                'status': 'executed',
                'message': collect_system_telemetry(action.target),
            })

        if platform.system() != 'Windows':
            raise ActionError('Desktop execution requires Windows. Use demo mode here.')

        value = self.describe(action)
        path = None
        args = []
        uri = None
        selected = None

        if action.kind == 'workspace_patch':
            selected = self.patch_catalog.get(action.target)
        elif action.kind == 'installed_app':
            selected = self.catalog.get(action.target)
            from .executable_target import ExecutableTarget
            if isinstance(selected, ExecutableTarget):
                path = selected.path
            else:
                if not selected.packaged:
                    raise ActionError('Select the actual .exe for this classic app; shortcut arguments are not inspected.')
                path = app_path('explorer')
                args = ['shell:AppsFolder\\' + selected.app_id]
        elif action.kind == 'launch_app':
            path, args, uri = self._resolve_launch_app(action)
        elif action.kind in {'winget_install', 'install_package'}:
            pkg = resolve_winget_package(action.target)
            path = Path(winget_path())
            if '.' in pkg and ' ' not in pkg:
                args = ['install', '--id', pkg, '-e', '--accept-source-agreements',
                        '--accept-package-agreements', '--disable-interactivity']
            else:
                args = ['install', pkg, '--accept-source-agreements',
                        '--accept-package-agreements', '--disable-interactivity']
        elif action.kind == 'open_folder':
            folder = resolve_known_folder(action.target)
            uri = str(folder)
        elif action.kind == 'system_control':
            uri_map = {
                'screenshot': 'ms-screenclip:',
                'wifi_settings': 'ms-settings:network-wifi',
                'bluetooth_settings': 'ms-settings:bluetooth',
                'display_settings': 'ms-settings:display',
                'sound_settings': 'ms-settings:sound',
                'windows_update': 'ms-settings:windowsupdate',
            }
            if action.target in uri_map:
                uri = uri_map[action.target]
            elif action.target == 'task_manager':
                path = app_path('taskmgr')
            elif action.target in {'shutdown', 'restart'}:
                path = system_directory() / 'shutdown.exe'
                args = ['/s' if action.target == 'shutdown' else '/r', '/t', '60']
        elif action.kind == 'app':
            if action.target == 'settings':
                uri = 'ms-settings:'
            elif action.target == 'browser':
                uri = SITES['google']
            else:
                path = app_path(action.target)
        elif action.kind in {'search', 'site', 'liked', 'navigate'}:
            if action.browser == 'default':
                uri = value
            else:
                path, args = app_path(action.browser), [value]

        if action.kind == 'workspace_patch':
            exact = value
        elif action.kind == 'installed_app':
            exact = value + f'\n\nLaunch dispatcher: {path}\nArguments: {args!r}'
        else:
            exact = f'Executable: {path}\n' + ('Arguments: ' + ' '.join(args) if args else '') if path else (uri or value)

        if not self.consent(
            'CompControl • approve desktop action',
            f'Request: {action.kind}\n\n{exact}\n\nAllow this one action? '
            'Cancel if you did not request it. No future actions are authorized.',
            valid,
        ):
            return {'status': 'cancelled', 'message': 'Windows approval declined. Nothing was executed.'}

        def dispatch():
            if action.kind == 'workspace_patch':
                from .file_workspace import WorkspaceError
                try:
                    self.patch_catalog.export(action.target)
                except WorkspaceError as exc:
                    raise ActionError(str(exc)) from None
                return {
                    'status': 'executed',
                    'message': 'New review patch exported. Source files were not modified; verify the base and diff before applying it yourself.',
                }
            if selected is not None:
                from .installed_apps import DiscoveryError
                try:
                    self.catalog.consume(action.target)
                    self.catalog.revalidate(selected)
                except DiscoveryError as exc:
                    raise ActionError(str(exc)) from None
                if not valid():
                    return {'status': 'cancelled', 'message': 'Approval revoked during app recheck. Nothing dispatched.'}
            return self._dispatch(action, path, args, uri)

        return gate(dispatch)

    @staticmethod
    def _dispatch(action, path, args, uri):
        try:
            if action.kind == 'media':
                vk = MEDIA_KEYS[action.target]
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
                return {'status': 'executed', 'message': f'Sent media key: {MEDIA_NAMES[action.target]}.'}

            if action.kind == 'system_control':
                if action.target == 'lock_screen':
                    ctypes.windll.user32.LockWorkStation()
                    return {'status': 'executed', 'message': 'Workstation locked.'}
                if action.target == 'sleep':
                    ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
                    return {'status': 'executed', 'message': 'System entering sleep state.'}
                if action.target == 'clipboard_clear':
                    if ctypes.windll.user32.OpenClipboard(None):
                        ctypes.windll.user32.EmptyClipboard()
                        ctypes.windll.user32.CloseClipboard()
                    return {'status': 'executed', 'message': 'System clipboard cleared.'}
                if action.target == 'empty_recycle_bin':
                    # SHERB_NOCONFIRMATION (0x1) | SHERB_NOPROGRESSUI (0x2) | SHERB_NOSOUND (0x4) = 0x7
                    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x07)
                    return {'status': 'executed', 'message': 'Recycle Bin emptied.'}

            if action.kind in {'shell_command', 'run_command'}:
                powershell = system_directory() / 'WindowsPowerShell/v1.0/powershell.exe'
                run = subprocess.run(
                    [str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', action.target],
                    shell=False,
                    capture_output=True,
                    timeout=20,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                stdout = run.stdout.decode('utf-8', errors='replace').strip()
                stderr = run.stderr.decode('utf-8', errors='replace').strip()
                output = stdout or stderr or 'Command completed with no output.'
                if len(output) > 1500:
                    output = output[:1500] + '\n... (output truncated)'
                if run.returncode != 0:
                    raise ActionError(f'Command exited with code {run.returncode}:\n{output}')
                return {'status': 'executed', 'message': f'Command executed:\n{output}'}

            if action.kind == 'python_script':
                run = subprocess.run(
                    [sys.executable, '-I', '-c', action.target],
                    shell=False,
                    capture_output=True,
                    timeout=15,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                stdout = run.stdout.decode('utf-8', errors='replace').strip()
                stderr = run.stderr.decode('utf-8', errors='replace').strip()
                output = stdout or stderr or 'Python script finished cleanly.'
                if len(output) > 1500:
                    output = output[:1500] + '\n... (output truncated)'
                if run.returncode != 0:
                    raise ActionError(f'Python script exited with code {run.returncode}:\n{output}')
                return {'status': 'executed', 'message': f'Python script output:\n{output}'}

            if action.kind in {'winget_install', 'install_package'}:
                subprocess.Popen([str(path), *args], shell=False, close_fds=True)
                pkg = resolve_winget_package(action.target)
                return {
                    'status': 'executed',
                    'message': f'Winget installer launched for {pkg}. Installation is running natively.',
                }

            if path:
                if action.kind == 'installed_app':
                    subprocess.Popen([str(path), *args], executable=str(path), cwd=str(path.parent),
                                     shell=False, close_fds=True)
                else:
                    subprocess.Popen([str(path), *args], shell=False, close_fds=True)
            else:
                os.startfile(uri)
        except ActionError:
            raise
        except (OSError, AttributeError, subprocess.TimeoutExpired) as exc:
            raise ActionError('Windows could not dispatch this action. Check the app installation or default handler.') from exc

        return {
            'status': 'executed',
            'message': 'Action dispatched to Windows.',
        }
