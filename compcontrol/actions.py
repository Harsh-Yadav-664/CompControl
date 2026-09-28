"""The only desktop boundary. Fixed app paths and URLs, never a shell."""
import ctypes
import os
import platform
import subprocess
from pathlib import Path
from urllib.parse import quote, urlencode

from .models import Action, APP_NAMES, BROWSERS, MEDIA_KEYS, MEDIA_NAMES, SITES
from .planner import clean, MAX_QUERY


class ActionError(RuntimeError):
    pass


def validate(action: Action) -> None:
    if not isinstance(action, Action) or action.browser not in BROWSERS:
        raise ActionError('Invalid action.')
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


def destination(action: Action) -> str:
    validate(action)
    if action.kind == 'search':
        if action.target == 'spotify':
            return 'https://open.spotify.com/search/' + quote(action.query, safe='')
        if action.target == 'youtube':
            return 'https://www.youtube.com/results?' + urlencode({'search_query': action.query})
        if action.target == 'maps':
            return 'https://www.google.com/maps/search/?' + urlencode({'api': '1', 'query': action.query})
        return 'https://www.google.com/search?' + urlencode({'q': action.query})
    if action.kind == 'site':
        return SITES[action.target]
    if action.kind == 'liked':
        return 'https://open.spotify.com/collection/tracks'
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
    def __init__(self, consent=native_confirm):
        self.consent = consent

    def execute(self, action: Action, gate, valid) -> dict:
        validate(action)
        if platform.system() != 'Windows':
            raise ActionError('Desktop execution requires Windows. Use demo mode here.')
        value = destination(action)
        path = None
        args = []
        uri = None
        if action.kind == 'app':
            if action.target == 'settings':
                uri = 'ms-settings:'
            elif action.target == 'browser':
                uri = SITES['google']
            else:
                path = app_path(action.target)
        elif action.kind in {'search', 'site', 'liked'}:
            if action.browser == 'default':
                uri = value
            else:
                path, args = app_path(action.browser), [value]
        exact = f'Executable: {path}\n' + ('URL: ' + value if args else '') if path else (uri or value)
        if not self.consent('CompControl • approve desktop action',
                            f'Request: {action.kind}\n\n{exact}\n\nAllow this one action? '
                            'Cancel if you did not request it. No future actions are authorized.', valid):
            return {'status': 'cancelled', 'message': 'Windows approval declined. Nothing was executed.'}
        return gate(lambda: self._dispatch(action, path, args, uri))

    @staticmethod
    def _dispatch(action, path, args, uri):
        try:
            if action.kind == 'media':
                vk = MEDIA_KEYS[action.target]
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            elif path:
                subprocess.Popen([str(path), *args], shell=False, close_fds=True)
            else:
                os.startfile(uri)
        except (OSError, AttributeError) as exc:
            raise ActionError('Windows could not dispatch this action. Check the app installation or default handler.') from exc
        return {'status': 'executed', 'message': 'Action dispatched to Windows. '
                'App loading, sign-in and playback state are not verified.'}
