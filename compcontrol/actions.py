"""The only desktop boundary. Typed effects with explicit consent; model text is never executable code."""
import ctypes
import os
import platform
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

from .models import Action, APP_NAMES, BROWSERS, MEDIA_KEYS, MEDIA_NAMES, SITES
from .planner import clean, MAX_QUERY


class ActionError(ValueError):
    pass


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
    allowed = {'app': APP_NAMES, 'search': {'google', 'youtube', 'spotify', 'maps'},
               'site': SITES, 'liked': {'spotify'}, 'media': MEDIA_KEYS}
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
    if action.kind == 'search':
        if action.target == 'spotify':
            if action.browser != 'default':
                return 'https://open.spotify.com/search/' + quote(action.query, safe='')
            # Spotify's registered URI scheme opens the desktop client when installed.
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
    """No PATH lookup. A local process able to alter these trusted roots is out of scope."""
    system = system_directory()
    if app in {'calculator', 'notepad', 'paint'}:
        path = system / {'calculator': 'calc.exe', 'notepad': 'notepad.exe', 'paint': 'mspaint.exe'}[app]
        candidates = [path]
    elif app == 'explorer':
        candidates = [system.parent / 'explorer.exe']
    else:
        relatives = {
            'chrome': ('Google/Chrome/Application/chrome.exe',),
            'brave': ('BraveSoftware/Brave-Browser/Application/brave.exe',),
            'edge': ('Microsoft/Edge/Application/msedge.exe',),
            'spotify': ('Spotify/Spotify.exe',),
        }
        if app not in relatives:
            raise ActionError('Unknown application.')
        roots = [os.environ.get(k) for k in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA', 'APPDATA')]
        candidates = [Path(root) / rel for root in roots if root and Path(root).is_absolute() for rel in relatives[app]]
    for path in candidates:
        if path.is_absolute() and path.is_file():
            return path.resolve()
    raise ActionError(f'{APP_NAMES[app]} was not found in a supported installation location. '
                      'Install it normally or choose the default browser. No fallback app was opened.')


from .consent import native_confirm


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

    def execute(self, action: Action, gate, valid) -> dict:
        validate(action)
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
            exact = f'Executable: {path}\n' + ('URL: ' + value if args else '') if path else (uri or value)
        if not self.consent('CompControl • approve desktop action',
                            f'Request: {action.kind}\n\n{exact}\n\nAllow this one action? '
                            'Cancel if you did not request it. No future actions are authorized.', valid):
            return {'status': 'cancelled', 'message': 'Windows approval declined. Nothing was executed.'}
        def dispatch():
            if action.kind == 'workspace_patch':
                from .file_workspace import WorkspaceError
                try:
                    self.patch_catalog.export(action.target)
                except WorkspaceError as exc:
                    raise ActionError(str(exc)) from None
                return {'status': 'executed', 'message': 'New review patch exported. Source files were not modified; verify the base and diff before applying it yourself.'}
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
            elif path:
                if action.kind == 'installed_app':
                    subprocess.Popen([str(path), *args], executable=str(path), cwd=str(path.parent),
                                     shell=False, close_fds=True)
                else:
                    subprocess.Popen([str(path), *args], shell=False, close_fds=True)
            else:
                os.startfile(uri)
        except (OSError, AttributeError) as exc:
            raise ActionError('Windows could not dispatch this action. Check the app installation or default handler.') from exc
        return {'status': 'executed', 'message': 'Action dispatched to Windows. '
                'App loading, sign-in and playback state are not verified.'}
