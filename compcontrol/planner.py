"""Offline deterministic routing. This module cannot call providers or execute tools."""
import ast
import math
import operator
import re
import unicodedata
from datetime import datetime

from .models import Action, APP_NAMES, BROWSERS, MEDIA_NAMES, Plan, SITES

MAX_REQUEST = 1000
MAX_QUERY = 300
BIDI = set('\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')
HELP = ('Open Calculator, Notepad, Paint, File Explorer, Settings, Chrome or Brave. '
        'Search Google, YouTube, Spotify or Maps. Open Spotify liked songs. '
        'Control media keys, check the time, or calculate 18 * 25. '
        'Every desktop action is previewed first. No shell, file edits or automatic playback selection.')


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
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
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
    note = ('Opens results, not automatic playback. Choose what to play in the app.'
            if site in {'youtube', 'spotify'} else 'Your search terms will be sent to this website.')
    return Plan(f'Search {label}', f'{note} Browser: {browser}.', (Action('search', site, query, browser),))


def plan_request(text: str, browser: str = 'default') -> Plan:
    if browser not in BROWSERS:
        raise ValueError('Select a supported browser.')
    text = clean(text)
    text = re.sub(r'^(?:hey\s+)?(?:jarvis|friday)[,:]?\s+', '', text, flags=re.I)
    text = re.sub(r'^(?:please|can you|could you)\s+', '', text, flags=re.I)
    text = text.rstrip('?.!')
    low = text.casefold()
    if not text:
        return Plan('Ready when you are', 'Type a request or choose a shortcut.')
    if low in {'help', 'what can you do', 'commands', 'skills'}:
        return Plan('Your command toolkit', HELP)
    if low in {'time', 'what time is it', 'date', "what's the time", 'what is the date', 'today'}:
        return Plan('Right on time', datetime.now().astimezone().strftime('%A, %d %B %Y · %I:%M %p %Z'))
    match = re.fullmatch(r'(?:calculate|calc|what is)\s+([\d\s.+*/%()\-]+)', text, re.I)
    if match:
        return Plan('Calculated locally', f'{match[1]} = {calculate(match[1])}')

    media = {'play pause': 'play_pause', 'toggle playback': 'play_pause',
             'toggle play pause': 'play_pause', 'next track': 'next', 'next song': 'next',
             'skip song': 'next', 'previous track': 'previous', 'previous song': 'previous',
             'volume up': 'volume_up', 'volume down': 'volume_down',
             'mute': 'mute', 'toggle mute': 'mute'}
    if low in media:
        key = media[low]
        return Plan(MEDIA_NAMES[key], 'Sends one Windows media key to the active media session. '
                    'Mute and play/pause are toggles; the current state is not read.', (Action('media', key),))
    if low in {'pause music', 'play music', 'resume music'}:
        return Plan('Use the playback toggle', 'I cannot read your player state. Say “toggle playback” '
                    'to send a play/pause key, or ask for a Spotify search.')

    # Only this bounded composite is allowed: browser selection + one search.
    match = re.fullmatch(r'open (?:the )?(chrome|brave|edge)(?: browser)? and (.+)', text, re.I)
    if match:
        browser, text = match[1].lower(), match[2]
        if not re.match(r'(?:search|find|google)\b', text, re.I):
            return Plan('One action at a time', 'After opening a browser I can search, not execute other commands.')
        low = text.casefold()

    if re.fullmatch(r'(?:open spotify and )?(?:open|play|show) (?:my )?liked (?:songs|playlist)(?: on spotify)?', low):
        return Plan('Open your liked songs', 'Opens Spotify’s liked-songs page. Sign in yourself if needed. '
                    'Select Play in Spotify; I will not sign in or start a playlist automatically.',
                    (Action('liked', 'spotify', browser=browser),))
    match = re.fullmatch(r'open spotify and (?:play|search(?: for)?) (.+)', text, re.I)
    if match:
        return search('spotify', match[1], browser)
    match = re.fullmatch(r'(?:play|listen to) (.+?)(?: on spotify)?', text, re.I)
    if match:
        return search('spotify', match[1], browser)

    # Prefer site-specific search patterns before generic search. Preserve query case.
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
        target = match[1].lower()
        target = {'file explorer': 'explorer', 'windows settings': 'settings',
                  'google chrome': 'chrome', 'microsoft edge': 'edge',
                  'chrome browser': 'chrome', 'brave browser': 'brave'}.get(target, target)
        if target in APP_NAMES:
            return Plan(f'Open {APP_NAMES[target]}', 'Only the registered application will be opened.',
                        (Action('app', target),))
        if target in SITES:
            return Plan(f'Open {target.title()}', 'Opens a fixed HTTPS destination in your selected browser.',
                        (Action('site', target, browser=browser),))
    return Plan('No action taken', 'That request is outside my safe toolkit. Try “help”, a shortcut, '
                'or explicitly ask AI for a text answer. I cannot run shell commands, delete files or send messages.')
