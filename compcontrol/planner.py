"""Fast deterministic local routing + seamless handoff to AI planner."""
import ast
import math
import operator
import re
import unicodedata
from datetime import datetime

from .models import (
    Action, APP_ALIASES, APP_NAMES, BROWSERS, KNOWN_FOLDERS,
    MEDIA_NAMES, Plan, SITES, SYSTEM_CONTROLS, WINGET_PACKAGES,
)

MAX_REQUEST = 1000
MAX_QUERY = 300
BIDI = set('\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')
HELP = (
    'Launch any installed Windows app, install software natively via Winget, '
    'control media & system settings, open folders or HTTPS links, search YouTube/Spotify/Google/Maps, '
    'or use AI for autonomous multi-step commands, shell tasks, and Python scripts.'
)


def clean(text: str, limit: int = MAX_REQUEST) -> str:
    if not isinstance(text, str) or len(text) > limit:
        raise ValueError(f'Request must be text of at most {limit} characters.')
    if any(c in BIDI or unicodedata.category(c) == 'Cc' for c in text):
        raise ValueError('Control characters and hidden direction changes are not allowed.')
    return ' '.join(text.strip().split())


def calculate(expression: str) -> str:
    """Bounded arithmetic only. No eval, calls, attributes, powers or names."""
    if len(expression) > 100:
        raise ValueError('Keep arithmetic under 100 characters.')
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
    }
    try:
        tree = ast.parse(expression, mode='eval')
        if sum(1 for _ in ast.walk(tree)) > 40:
            raise ValueError('Expression is too complex.')

        def walk(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                value = node.value
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
                value = walk(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
            elif isinstance(node, ast.BinOp) and type(node.op) in ops:
                value = ops[type(node.op)](walk(node.left), walk(node.right))
            else:
                raise ValueError('Use numbers, parentheses and + - * / // % only.')
            if not math.isfinite(value) or abs(value) > 1e15:
                raise ValueError('Result is outside the supported range.')
            return value

        return format(walk(tree.body), '.12g')
    except (SyntaxError, ZeroDivisionError, OverflowError, RecursionError) as exc:
        raise ValueError('Invalid arithmetic or division by zero.') from exc


def search(site: str, query: str, browser: str) -> Plan:
    query = clean(query, MAX_QUERY)
    if not query or query.casefold() in {'for', 'search', 'and', 'songs'}:
        return Plan('What should I search for?', 'Add a specific topic, artist or song to your request.')
    label = {'google': 'Google', 'youtube': 'YouTube', 'spotify': 'Spotify', 'maps': 'Google Maps'}[site]
    note = (
        'Opens results, not automatic playback. Choose what to play in the app.'
        if site in {'youtube', 'spotify'}
        else 'Your search terms will be sent to this website.'
    )
    return Plan(f'Search {label}', f'{note} Browser: {browser}.', (Action('search', site, query, browser),))


def launch_resolved_app(app_query: str) -> Plan:
    """Resolve an application name in the background and return a direct launch_app Plan."""
    from .installed_apps import auto_resolve_app
    app_query = clean(app_query, MAX_QUERY)
    target, display = auto_resolve_app(app_query)
    if target in APP_NAMES:
        return Plan(f'Open {APP_NAMES[target]}', 'Opens the registered Windows application.', (Action('app', target),))
    return Plan(
        f'Launch {display}',
        f'Resolved "{display}" ({target}) via background app discovery.',
        (Action('launch_app', target, query=display),),
    )


def winget_install_plan(software: str) -> Plan:
    """Create a native Winget package installation Plan."""
    from .actions import resolve_winget_package
    software = clean(software, 240).strip(' .!?')
    if not software or len(software) > 240 or not re.fullmatch(r'[A-Za-z0-9._+\- ]+', software):
        return Plan('Which software?', 'Name the package or app to install via Winget.')
    pkg = resolve_winget_package(software)
    return Plan(
        f'Install {software}',
        f'Installs {pkg} natively using Windows Package Manager (winget).',
        (Action('winget_install', pkg, query=software),),
    )


def follow_up(intent, query='', browser='default'):
    query = clean(query, MAX_QUERY)
    if intent == 'find_app':
        if query:
            return launch_resolved_app(query)
        return Plan(
            'Discover installed apps',
            'Use Discover apps to browse the Windows Start menu or type "open <app name>" to launch directly.',
            intent=intent,
            query=query,
        )
    if intent == 'file_workspace':
        return Plan(
            'Choose a project and file',
            'Use Project files. Select the project folder and exact file yourself. '
            'Preview an exact-text replacement and export a patch; originals stay unchanged.',
            intent=intent,
            query=query,
        )
    if intent == 'research':
        if not query:
            return Plan('What should I research?', 'Include a specific topic for the research draft.')
        return Plan(
            'Prepare ChatGPT research',
            'Opens ChatGPT only. In ChatGPT, select New chat, choose Deep research if your account '
            'has access, paste the draft below and review its research plan. No text is submitted '
            'and no research job is started by CompControl.\n\nDraft to copy:\n'
            'Research this topic in depth: ' + query + '. Cite primary sources, compare alternatives, '
            'and clearly separate findings from uncertainty.',
            (Action('site', 'chatgpt', browser=browser),),
        )
    raise ValueError('Unknown follow-up.')


def navigate(url, browser='default'):
    from .actions import validate_url
    validate_url(url)
    return Plan(
        'Open HTTPS destination',
        'Opens the requested HTTPS URL in your selected browser.',
        (Action('navigate', url, browser=browser),),
    )


def _is_liked_songs_intent(low: str) -> bool:
    """Match any natural phrasing for opening/playing Spotify liked/saved/favorite songs list."""
    pattern = (
        r'^(?:(?:open|launch|start)\s+spotify\s+(?:and|then)\s+)?'
        r'(?:open|play|show|start|shuffle|listen\s+to|go\s+to)\s+'
        r'(?:my\s+)?(?:spotify\s+)?'
        r'(?:liked|saved|fav(?:ou?rite)?)\s+'
        r'(?:songs?(?:\s+list|\s+playlist|\s+collection)?|tracks?(?:\s+list|\s+playlist)?|playlist|music|list|collection)'
        r'(?:\s+(?:list|playlist|collection))?'
        r'(?:\s+(?:on|in)\s+spotify)?$'
    )
    return bool(re.fullmatch(pattern, low))


def plan_request(text: str, browser: str = 'default') -> Plan:
    if browser not in BROWSERS:
        raise ValueError('Select a supported browser.')
    text = clean(text)
    text = re.sub(r'^(?:hey\s+)?(?:jarvis|friday)[,:]?\s+', '', text, flags=re.I)
    text = re.sub(r'^(?:(?:please|can you|could you|would you)\s+)+', '', text, flags=re.I)
    if 'https://' not in text:
        text = text.rstrip('?.!')
    low = text.casefold()
    if not text:
        return Plan('Ready when you are', 'Type a command or press Enter to execute.')
    if low in {'help', 'what can you do', 'commands', 'skills'}:
        return Plan('Your command toolkit', HELP)
    if low in {'time', 'what time is it', 'date', "what's the time", 'what is the date', 'today'}:
        return Plan('Right on time', datetime.now().astimezone().strftime('%A, %d %B %Y · %I:%M %p %Z'))
    match = re.fullmatch(r'(?:calculate|calc|what is)\s+([\d\s.+*/%()\-]+)', text, re.I)
    if match:
        return Plan('Calculated locally', f'{match[1]} = {calculate(match[1])}')
    # Also allow direct bare math expressions like "(2400 * .18) + 2400" if they contain an operator
    if re.fullmatch(r'[\d\s.+*/%()\-]+', text) and any(op in text for op in '+-*/%') and any(c.isdigit() for c in text):
        try:
            return Plan('Calculated locally', f'{text} = {calculate(text)}')
        except ValueError:
            pass

    media = {
        'play pause': 'play_pause', 'toggle playback': 'play_pause',
        'toggle play pause': 'play_pause', 'next track': 'next', 'next song': 'next',
        'skip song': 'next', 'previous track': 'previous', 'previous song': 'previous',
        'volume up': 'volume_up', 'volume down': 'volume_down',
        'mute': 'mute', 'toggle mute': 'mute', 'unmute': 'mute',
    }
    if low in media:
        key = media[low]
        return Plan(
            MEDIA_NAMES[key],
            'Sends one Windows media key to the active media session. '
            'Mute and play/pause are toggles; the current state is not read.',
            (Action('media', key),),
        )
    if low in {'pause music', 'play music', 'resume music'}:
        return Plan(
            'Use the playback toggle',
            'I cannot read your player state. Say “toggle playback” '
            'to send a play/pause key, or ask for a Spotify search.',
        )

    # System controls & telemetry
    sys_map = {
        'system info': 'system_info', 'system status': 'system_info', 'pc info': 'system_info',
        'pc health': 'system_info', 'hardware info': 'system_info',
        'network status': 'network_status', 'ip address': 'network_status',
        'battery': 'battery_status', 'battery status': 'battery_status',
        'disk space': 'disk_space', 'storage': 'disk_space', 'free space': 'disk_space',
        'top processes': 'top_processes', 'running processes': 'top_processes',
        'lock screen': 'lock_screen', 'lock pc': 'lock_screen', 'lock computer': 'lock_screen',
        'sleep': 'sleep', 'put pc to sleep': 'sleep',
        'screenshot': 'screenshot', 'take a screenshot': 'screenshot', 'snip': 'screenshot',
        'task manager': 'task_manager', 'open task manager': 'task_manager',
        'wifi settings': 'wifi_settings', 'open wifi settings': 'wifi_settings',
        'bluetooth settings': 'bluetooth_settings', 'open bluetooth settings': 'bluetooth_settings',
        'display settings': 'display_settings', 'open display settings': 'display_settings',
        'sound settings': 'sound_settings', 'open sound settings': 'sound_settings',
        'windows update': 'windows_update', 'check for updates': 'windows_update',
        'clear clipboard': 'clipboard_clear', 'empty recycle bin': 'empty_recycle_bin',
    }
    if low in sys_map:
        ctrl = sys_map[low]
        return Plan(SYSTEM_CONTROLS[ctrl], f'Executes Windows system control: {SYSTEM_CONTROLS[ctrl]}.', (Action('system_control', ctrl),))

    # Folder shortcuts
    folder_match = re.fullmatch(r'(?:open|show|go to) (?:my )?(downloads|documents|desktop|pictures|music|videos|temp|appdata)(?: folder)?', low)
    if folder_match:
        fk = folder_match[1]
        return Plan(f'Open {KNOWN_FOLDERS[fk]}', f'Opens your {KNOWN_FOLDERS[fk]} folder in File Explorer.', (Action('open_folder', fk),))

    match = re.fullmatch(r'(?:open|visit|download(?: from)?) (https://\S+)', text, re.I)
    if match:
        return navigate(match[1], browser)

    match = re.fullmatch(
        r'(?:download and install|install or download|winget install|install|download) (?:the )?(.+?)(?: for windows)?',
        text, re.I
    )
    if match:
        return winget_install_plan(match[1])

    match = re.fullmatch(r'(?:research|deep research|ask chatgpt to (?:do )?(?:deep )?research)(?: about| on)? (.+)', text, re.I)
    if match:
        return follow_up('research', match[1], browser)
    if low in {'project files', 'edit project file', 'preview file change', 'open project files'}:
        return follow_up('file_workspace')
    match = re.fullmatch(r'(?:find|discover) (?:installed )?app(?:s)?(?: (.+))?', text, re.I)
    if match:
        return follow_up('find_app', match[1] or '')

    # Composite: browser selection + search or liked songs
    match = re.fullmatch(r'open (?:the )?(chrome|brave|edge)(?: browser)? and (.+)', text, re.I)
    if match:
        browser, text = match[1].lower(), match[2]
        if not re.match(r'(?:search|find|google|play|open|show)\b', text, re.I):
            return Plan('One action at a time', 'After opening a browser I can search, not execute other commands.')
        low = text.casefold()

    # Liked songs detection MUST run before generic Spotify search patterns
    if _is_liked_songs_intent(low):
        return Plan(
            'Open your liked songs',
            'Opens Spotify’s liked-songs collection directly.',
            (Action('liked', 'spotify', browser=browser),),
        )

    match = re.fullmatch(r'open spotify and (?:play|search(?: for)?) (.+)', text, re.I)
    if match:
        if _is_liked_songs_intent('play ' + match[1].casefold()):
            return Plan(
                'Open your liked songs',
                'Opens Spotify’s liked-songs collection directly.',
                (Action('liked', 'spotify', browser=browser),),
            )
        return search('spotify', match[1], browser)

    match = re.fullmatch(r'(?:play|watch) (.+?) on (youtube|yt)', text, re.I)
    if match:
        return search('youtube', match[1], browser)
    match = re.fullmatch(r'(?:play|listen to) (.+?)(?: on spotify)?', text, re.I)
    if match:
        if _is_liked_songs_intent(low):
            return Plan(
                'Open your liked songs',
                'Opens Spotify’s liked-songs collection directly.',
                (Action('liked', 'spotify', browser=browser),),
            )
        return search('spotify', match[1], browser)

    # Opening a site and searching it is one navigation
    match = re.fullmatch(
        r'(?:open|launch) (?:a |the |an? new )?(youtube|yt|spotify|google|maps)'
        r'(?: tab| page| website)? (?:and|then|and then) (?:search(?: for)?|find|look for) (.+)',
        text, re.I,
    )
    if match:
        return search(match[1].lower().replace('yt', 'youtube'), match[2], browser)
    match = re.fullmatch(r'(?:look for|look up|show me) (.+?) (?:on|in) (youtube|yt|spotify|google|maps)', text, re.I)
    if match:
        return search(match[2].lower().replace('yt', 'youtube'), match[1], browser)

    for pattern in (
        r'(?:search|find)(?: on)? (youtube|yt|spotify|google|maps)(?: for)? (.+)',
        r'(youtube|yt|spotify|google|maps)(?: search)?(?: for)? (.+)',
    ):
        match = re.fullmatch(pattern, text, re.I)
        if match:
            site = match[1].lower().replace('yt', 'youtube')
            return search(site, match[2], browser)
    match = re.fullmatch(r'(?:search|find)(?: for)? (.+?) on (youtube|yt|spotify|google|maps)', text, re.I)
    if match:
        return search(match[2].lower().replace('yt', 'youtube'), match[1], browser)
    match = re.fullmatch(r'(?:search for|search|find) (.+)', text, re.I)
    if match:
        return search('google', match[1], browser)
    if low in {'search', 'search for', 'youtube', 'spotify', 'google'}:
        return Plan('Add a little more detail', 'Try “search YouTube for Sidemen videos”.')

    match = re.fullmatch(r'(?:open|launch|start) (?:the )?(.+)', text, re.I)
    if match:
        raw_target = match[1].strip()
        target = raw_target.lower()
        target = {
            'yt': 'youtube', 'youtube tab': 'youtube', 'yt tab': 'youtube',
            'file explorer': 'explorer', 'windows settings': 'settings',
            'google chrome': 'chrome', 'microsoft edge': 'edge',
            'chrome browser': 'chrome', 'brave browser': 'brave',
        }.get(target, target)
        if target in APP_NAMES:
            return Plan(
                f'Open {APP_NAMES[target]}',
                'Only the registered application will be opened.',
                (Action('app', target),),
            )
        if target in SITES:
            return Plan(
                f'Open {target.title()}',
                'Opens a fixed HTTPS destination in your selected browser.',
                (Action('site', target, browser=browser),),
            )
        if (not re.search(r'(?:\b(?:and|then|run|delete)\b|[\\/:;&|<>])', target, re.I)
                and len(raw_target) <= MAX_QUERY):
            return launch_resolved_app(raw_target)

    return Plan(
        'Let’s interpret that',
        'Routing to AI planner for natural language interpretation and autonomous execution.',
    )
