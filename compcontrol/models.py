"""Shared immutable command contracts. No OS access lives here."""
from dataclasses import asdict, dataclass

APP_NAMES = {
    'calculator': 'Calculator', 'notepad': 'Notepad', 'paint': 'Paint',
    'explorer': 'File Explorer', 'settings': 'Windows Settings',
    'chrome': 'Google Chrome', 'brave': 'Brave', 'edge': 'Microsoft Edge',
    'spotify': 'Spotify', 'browser': 'Default browser',
}
SITES = {
    'google': 'https://www.google.com/', 'youtube': 'https://www.youtube.com/',
    'spotify': 'https://open.spotify.com/', 'github': 'https://github.com/',
    'gmail': 'https://mail.google.com/', 'maps': 'https://maps.google.com/',
    'chatgpt': 'https://chatgpt.com/',
}
BROWSERS = {'default', 'chrome', 'brave', 'edge'}
MEDIA_KEYS = {'play_pause': 0xB3, 'next': 0xB0, 'previous': 0xB1,
              'volume_up': 0xAF, 'volume_down': 0xAE, 'mute': 0xAD}
MEDIA_NAMES = {'play_pause': 'Toggle play / pause', 'next': 'Next track',
               'previous': 'Previous track', 'volume_up': 'Volume up one step',
               'volume_down': 'Volume down one step', 'mute': 'Toggle mute'}


@dataclass(frozen=True)
class Action:
    kind: str
    target: str
    query: str = ''
    browser: str = 'default'

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Plan:
    title: str
    message: str
    actions: tuple[Action, ...] = ()
    intent: str = ''
    query: str = ''

    def to_dict(self):
        return {'title': self.title, 'message': self.message,
                'actions': [a.to_dict() for a in self.actions],
                'intent': self.intent, 'query': self.query}
