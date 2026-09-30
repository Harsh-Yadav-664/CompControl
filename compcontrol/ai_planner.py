"""Autonomous AI intent planner with background app discovery and Exploit Shield validation."""
import json

from .actions import ActionError, resolve_winget_package, validate
from .models import (
    Action, APP_ALIASES, APP_NAMES, KNOWN_FOLDERS, MEDIA_NAMES,
    Plan, SITES, SYSTEM_CONTROLS,
)
from .planner import (
    clean, follow_up, launch_resolved_app, navigate,
    search, winget_install_plan,
)
from .providers import ProviderError

SYSTEM = '''You are CompControl (Jarvis / Friday), an autonomous Windows desktop AI agent.
Your mission is to make daily PC usage effortless by directly executing actions on the user's behalf.
Return strictly one JSON object without markdown formatting.

Supported JSON shapes:
1. Launch any application (built-in or third-party; background Start-menu discovery resolves it automatically):
   {"action":{"kind":"launch_app","target":"Visual Studio Code","query":""}}
   {"action":{"kind":"app","target":"calculator","query":""}}
2. Open Spotify Liked Songs (for ANY phrasing like "play my liked songs list", "open liked tracks", "saved songs"):
   {"action":{"kind":"liked","target":"spotify","query":""}}
3. Search the web, YouTube, Spotify, or Google Maps:
   {"action":{"kind":"search","target":"youtube","query":"Sidemen videos"}}
   {"action":{"kind":"search","target":"spotify","query":"sad Hindi songs"}}
4. Open a known website or explicit HTTPS URL:
   {"action":{"kind":"site","target":"github","query":""}}
   {"action":{"kind":"navigate","target":"https://example.org/","query":""}}
5. Install software natively via Windows Package Manager (Winget):
   {"action":{"kind":"winget_install","target":"VideoLAN.VLC","query":"VLC"}}
   {"action":{"kind":"install_package","target":"BlenderFoundation.Blender","query":"Blender"}}
6. Control media playback & volume:
   {"action":{"kind":"media","target":"play_pause","query":""}}
   (targets: play_pause, next, previous, volume_up, volume_down, mute)
7. Execute Windows system controls & hardware telemetry:
   {"action":{"kind":"system_control","target":"system_info","query":""}}
   (targets: system_info, network_status, battery_status, disk_space, top_processes, lock_screen, sleep, screenshot, task_manager, wifi_settings, bluetooth_settings, display_settings, sound_settings, windows_update, clipboard_clear, empty_recycle_bin, shutdown, restart)
8. Open user folders:
   {"action":{"kind":"open_folder","target":"downloads","query":""}}
   (targets: downloads, documents, desktop, pictures, music, videos, home, temp, appdata)
9. Run a PowerShell command or Python automation script for advanced tasks:
   {"action":{"kind":"shell_command","target":"Get-Date","query":""}}
   {"action":{"kind":"python_script","target":"import platform; print(platform.processor())","query":""}}
10. Follow-up workflows or direct conversational answers:
   {"intent":"find_app","query":"Visual Studio Code"}
   {"intent":"file_workspace","query":""}
   {"intent":"research","query":"battery recycling"}
   {"message":"A concise, helpful answer."}

Rules:
- Built-in app shortcuts: calculator, notepad, paint, explorer, settings, chrome, brave, edge, spotify, browser.
- For any other application (e.g., VS Code, Discord, Blender, VLC, Steam, Obsidian, Slack, Terminal), use kind "launch_app" with the application name in "target" (query must be ""). CompControl automatically scans the Windows Start menu and installation paths in the background to launch it directly.
- For software installation requests (e.g. "install VLC", "download Blender"), use "winget_install" or "install_package" with the Winget package ID or software name in "target".
- For "play my liked songs list", "liked playlist", "favorite tracks on spotify", ALWAYS use {"action":{"kind":"liked","target":"spotify","query":""}}, NEVER a Spotify search.
- Actions must contain exactly the keys "kind", "target", and "query" (all strings).
- Never emit encoded PowerShell (-EncodedCommand), credential-dumping commands, or unrequested destructive commands.'''


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate key')
        result[key] = value
    return result


def parse_proposal(raw, browser='default'):
    """Validate and convert an AI JSON proposal into an executable Plan."""
    try:
        if type(raw) is not str or len(raw) > 12000:
            raise ValueError()
        data = json.loads(
            raw,
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        if type(data) is not dict:
            raise ValueError()

        if set(data) == {'intent', 'query'}:
            if data['intent'] not in {'find_app', 'file_workspace', 'research'}:
                raise ValueError()
            return follow_up(data['intent'], data['query'], browser)

        if set(data) == {'message'}:
            message = clean(data['message'], 2000)
            if not message:
                raise ValueError()
            return Plan('AI response · no action proposed', message)

        if set(data) != {'action'} or type(data['action']) is not dict:
            raise ValueError()

        item = data['action']
        if set(item) != {'kind', 'target', 'query'} or any(type(v) is not str for v in item.values()):
            raise ValueError()

        kind = item['kind']
        target = item['target']
        query = item['query']

        if kind in {'installed_app', 'workspace_patch'}:
            raise ValueError()  # Local picker handles cannot be forged by model output.

        # If the model used 'app' for an app outside APP_NAMES, upgrade it to background 'launch_app'
        # as long as query is empty and target is a clean app name (not a raw file path or command).
        if kind == 'app' and target not in APP_NAMES:
            alias = APP_ALIASES.get(target.strip().lower(), target.strip().lower())
            if alias in APP_NAMES and not query:
                target = alias
            elif (not query and target.strip() and len(target) <= 200
                  and not any(c in target for c in '\\/:;&|<>`$')
                  and target.strip().lower() not in {'cmd', 'powershell', 'bash', 'sh', 'wscript', 'cscript'}):
                return launch_resolved_app(target)

        if kind == 'launch_app':
            if query and clean(query, 300) != query:
                raise ValueError()
            return launch_resolved_app(target)

        if kind in {'winget_install', 'install_package'}:
            pkg = resolve_winget_package(clean(target, 240))
            action = Action('winget_install', pkg, query=clean(query, 300) if query else '', browser='default')
            validate(action)
            label = query or target
            return Plan(
                f'Install {label}',
                f'Installs {pkg} natively via Windows Package Manager (winget).',
                (action,),
            )

        if kind in {'shell_command', 'run_command'}:
            action = Action('shell_command', clean(target, 500), query=clean(query, 300) if query else '', browser='default')
            validate(action)
            return Plan(
                'Run PowerShell command',
                f'Executes validated command: {action.target}',
                (action,),
            )

        if kind == 'python_script':
            action = Action('python_script', target.strip(), query=clean(query, 300) if query else '', browser='default')
            validate(action)
            return Plan(
                'Run Python automation script',
                'Executes isolated Python snippet.',
                (action,),
            )

        if kind == 'system_control':
            action = Action('system_control', target, query='', browser='default')
            validate(action)
            return Plan(
                SYSTEM_CONTROLS[target],
                f'Executes Windows system control: {SYSTEM_CONTROLS[target]}.',
                (action,),
            )

        if kind == 'open_folder':
            action = Action('open_folder', target.lower(), query='', browser='default')
            validate(action)
            return Plan(
                f'Open {KNOWN_FOLDERS[action.target]}',
                f'Opens your {KNOWN_FOLDERS[action.target]} folder in File Explorer.',
                (action,),
            )

        non_browser_kinds = {'app', 'media', 'winget_install', 'install_package',
                             'shell_command', 'run_command', 'python_script',
                             'system_control', 'open_folder', 'launch_app'}
        action = Action(kind, target, query, browser='default' if kind in non_browser_kinds else browser)
        validate(action)

        if action.kind == 'navigate':
            return navigate(action.target, browser)
        if action.kind == 'search':
            return search(action.target, action.query, action.browser)
        if action.kind == 'app':
            return Plan(
                'Open ' + APP_NAMES[action.target],
                'Opens only the registered Windows application.',
                (action,),
            )
        if action.kind == 'site':
            return Plan(
                'Open ' + action.target.title(),
                'Opens the fixed website: ' + SITES[action.target],
                (action,),
            )
        if action.kind == 'liked':
            return Plan(
                'Open your liked songs',
                'Opens Spotify’s liked-songs collection directly.',
                (action,),
            )
        return Plan(
            MEDIA_NAMES[action.target],
            'Sends one Windows media key. Playback and mute are toggles; current state is not read.',
            (action,),
        )
    except (ValueError, TypeError, KeyError, RecursionError, ActionError):
        raise ProviderError(
            'AI returned an unsupported or malformed proposal. Nothing was approved. '
            'Try rephrasing or using a local shortcut.'
        ) from None
