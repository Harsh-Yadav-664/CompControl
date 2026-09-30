"""Shared immutable command contracts and autonomous capability definitions. No OS access lives here."""
from dataclasses import asdict, dataclass

APP_NAMES = {
    'calculator': 'Calculator', 'notepad': 'Notepad', 'paint': 'Paint',
    'explorer': 'File Explorer', 'settings': 'Windows Settings',
    'chrome': 'Google Chrome', 'brave': 'Brave', 'edge': 'Microsoft Edge',
    'spotify': 'Spotify', 'browser': 'Default browser',
}

EXTENDED_APPS = {
    'vscode': ('Visual Studio Code', ('Microsoft VS Code/Code.exe', 'Programs/Microsoft VS Code/Code.exe')),
    'cursor': ('Cursor', ('Programs/cursor/Cursor.exe', 'cursor/Cursor.exe')),
    'discord': ('Discord', ('Discord/Update.exe', 'Discord/Discord.exe')),
    'slack': ('Slack', ('slack/slack.exe', 'Programs/slack/slack.exe')),
    'vlc': ('VLC Media Player', ('VideoLAN/VLC/vlc.exe',)),
    'blender': ('Blender', ('Blender Foundation/Blender/blender.exe',)),
    'obs': ('OBS Studio', ('obs-studio/bin/64bit/obs64.exe',)),
    'steam': ('Steam', ('Steam/steam.exe',)),
    'zoom': ('Zoom', ('Zoom/bin/Zoom.exe',)),
    'notion': ('Notion', ('Programs/Notion/Notion.exe',)),
    'obsidian': ('Obsidian', ('Programs/Obsidian/Obsidian.exe', 'Obsidian/Obsidian.exe')),
    'postman': ('Postman', ('Postman/Postman.exe',)),
    'firefox': ('Mozilla Firefox', ('Mozilla Firefox/firefox.exe',)),
    '7zip': ('7-Zip', ('7-Zip/7zFM.exe',)),
    'gitbash': ('Git Bash', ('Git/git-bash.exe',)),
    'docker': ('Docker Desktop', ('Docker/Docker/Docker Desktop.exe',)),
    'telegram': ('Telegram Desktop', ('Telegram Desktop/Telegram.exe',)),
    'whatsapp': ('WhatsApp', ('WhatsApp/WhatsApp.exe',)),
    'notepad++': ('Notepad++', ('Notepad++/notepad++.exe',)),
    'qbittorrent': ('qBittorrent', ('qBittorrent/qbittorrent.exe',)),
    'gimp': ('GIMP', ('GIMP 2/bin/gimp-2.10.exe',)),
    'audacity': ('Audacity', ('Audacity/Audacity.exe',)),
    'handbrake': ('HandBrake', ('HandBrake/HandBrake.exe',)),
    'everything': ('Everything', ('Everything/Everything.exe',)),
    'powertoys': ('PowerToys', ('PowerToys/PowerToys.exe',)),
    'taskmgr': ('Task Manager', ('taskmgr.exe',)),
    'control': ('Control Panel', ('control.exe',)),
    'snippingtool': ('Snipping Tool', ('SnippingTool.exe',)),
    'terminal': ('Windows Terminal', ('Microsoft/WindowsApps/wt.exe',)),
    'powershell': ('Windows PowerShell', ('WindowsPowerShell/v1.0/powershell.exe',)),
}

APP_ALIASES = {
    'vs code': 'vscode', 'visual studio code': 'vscode', 'code': 'vscode',
    'vlc media player': 'vlc', 'vlc player': 'vlc',
    'obs studio': 'obs', 'mozilla firefox': 'firefox',
    '7-zip': '7zip', '7z': '7zip', 'git bash': 'gitbash',
    'docker desktop': 'docker', 'telegram desktop': 'telegram',
    'task manager': 'taskmgr', 'control panel': 'control',
    'snipping tool': 'snippingtool', 'windows terminal': 'terminal',
    'wt': 'terminal', 'calc': 'calculator',
    'file explorer': 'explorer', 'windows explorer': 'explorer',
    'windows settings': 'settings', 'system settings': 'settings',
    'google chrome': 'chrome', 'chrome browser': 'chrome',
    'microsoft edge': 'edge', 'edge browser': 'edge',
    'brave browser': 'brave', 'default browser': 'browser',
}

WINGET_PACKAGES = {
    'vlc': 'VideoLAN.VLC',
    'vlc media player': 'VideoLAN.VLC',
    'blender': 'BlenderFoundation.Blender',
    'vscode': 'Microsoft.VisualStudioCode',
    'vs code': 'Microsoft.VisualStudioCode',
    'visual studio code': 'Microsoft.VisualStudioCode',
    'discord': 'Discord.Discord',
    'spotify': 'Spotify.Spotify',
    'chrome': 'Google.Chrome',
    'google chrome': 'Google.Chrome',
    'brave': 'Brave.Brave',
    'brave browser': 'Brave.Brave',
    'firefox': 'Mozilla.Firefox',
    'mozilla firefox': 'Mozilla.Firefox',
    '7zip': '7zip.7zip',
    '7-zip': '7zip.7zip',
    'git': 'Git.Git',
    'nodejs': 'OpenJS.NodeJS.LTS',
    'node.js': 'OpenJS.NodeJS.LTS',
    'node': 'OpenJS.NodeJS.LTS',
    'python': 'Python.Python.3.12',
    'obs': 'OBSProject.OBSStudio',
    'obs studio': 'OBSProject.OBSStudio',
    'steam': 'Valve.Steam',
    'zoom': 'Zoom.Zoom',
    'slack': 'SlackTechnologies.Slack',
    'notion': 'Notion.Notion',
    'obsidian': 'Obsidian.Obsidian',
    'postman': 'Postman.Postman',
    'docker': 'Docker.DockerDesktop',
    'docker desktop': 'Docker.DockerDesktop',
    'powertoys': 'Microsoft.PowerToys',
    'everything': 'voidtools.Everything',
    'cursor': 'Anysphere.Cursor',
    'notepad++': 'Notepad++.Notepad++',
    'qbittorrent': 'qBittorrent.qBittorrent',
    'telegram': 'Telegram.TelegramDesktop',
    'whatsapp': 'WhatsApp.WhatsApp',
    'gimp': 'GIMP.GIMP',
    'audacity': 'Audacity.Audacity',
    'handbrake': 'HandBrake.HandBrake',
    'winrar': 'RARLab.WinRAR',
    'putty': 'PuTTY.PuTTY',
    'wireshark': 'WiresharkFoundation.Wireshark',
    'windirstat': 'WinDirStat.WinDirStat',
}

SITES = {
    'google': 'https://www.google.com/', 'youtube': 'https://www.youtube.com/',
    'spotify': 'https://open.spotify.com/', 'github': 'https://github.com/',
    'gmail': 'https://mail.google.com/', 'maps': 'https://maps.google.com/',
    'chatgpt': 'https://chatgpt.com/', 'claude': 'https://claude.ai/',
    'perplexity': 'https://www.perplexity.ai/', 'reddit': 'https://www.reddit.com/',
    'twitter': 'https://x.com/', 'x': 'https://x.com/',
    'linkedin': 'https://www.linkedin.com/', 'netflix': 'https://www.netflix.com/',
    'whatsapp': 'https://web.whatsapp.com/', 'stackoverflow': 'https://stackoverflow.com/',
    'drive': 'https://drive.google.com/',
}

BROWSERS = {'default', 'chrome', 'brave', 'edge'}

MEDIA_KEYS = {
    'play_pause': 0xB3, 'next': 0xB0, 'previous': 0xB1,
    'volume_up': 0xAF, 'volume_down': 0xAE, 'mute': 0xAD,
}
MEDIA_NAMES = {
    'play_pause': 'Toggle play / pause', 'next': 'Next track',
    'previous': 'Previous track', 'volume_up': 'Volume up one step',
    'volume_down': 'Volume down one step', 'mute': 'Toggle mute',
}

SYSTEM_CONTROLS = {
    'system_info': 'System & hardware telemetry',
    'network_status': 'Network & IP status',
    'battery_status': 'Battery & power status',
    'disk_space': 'Disk storage usage',
    'top_processes': 'Active processes overview',
    'lock_screen': 'Lock Windows workstation',
    'sleep': 'Put PC to sleep',
    'screenshot': 'Open Windows Snipping overlay',
    'task_manager': 'Open Task Manager',
    'wifi_settings': 'Open Wi-Fi & Network Settings',
    'bluetooth_settings': 'Open Bluetooth & Devices Settings',
    'display_settings': 'Open Display Settings',
    'sound_settings': 'Open Sound Settings',
    'windows_update': 'Open Windows Update',
    'clipboard_clear': 'Clear system clipboard',
    'empty_recycle_bin': 'Empty Recycle Bin',
    'shutdown': 'Shut down PC (60s grace timer)',
    'restart': 'Restart PC (60s grace timer)',
}

KNOWN_FOLDERS = {
    'downloads': 'Downloads',
    'documents': 'Documents',
    'desktop': 'Desktop',
    'pictures': 'Pictures',
    'music': 'Music',
    'videos': 'Videos',
    'home': 'User Profile Home',
    'temp': 'Temporary Files',
    'appdata': 'Local AppData',
}

ACTION_KINDS = {
    'app', 'launch_app', 'installed_app', 'search', 'site', 'navigate',
    'liked', 'media', 'winget_install', 'install_package', 'shell_command',
    'run_command', 'python_script', 'system_control', 'open_folder',
    'workspace_patch',
}


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
        return {
            'title': self.title,
            'message': self.message,
            'actions': [a.to_dict() for a in self.actions],
            'intent': self.intent,
            'query': self.query,
        }
