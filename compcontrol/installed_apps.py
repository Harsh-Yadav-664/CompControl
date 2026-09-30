"""Observed Windows Start-menu targets and autonomous background app resolution."""
import json
import os
import platform
import re
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .models import APP_ALIASES, APP_NAMES, EXTENDED_APPS


class DiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class InstalledApp:
    name: str
    app_id: str
    verified_packaged: bool = False

    @property
    def detail(self):
        return (f'Name: {self.name}\nWindows AppID: {self.app_id}\n'
                'Source: Windows Start menu.\n'
                'Packaged apps launch via shell:AppsFolder. Classic entries can also launch via resolved .exe.')

    @property
    def packaged(self):
        return self.verified_packaged and bool(re.fullmatch(
            r'[A-Za-z0-9][A-Za-z0-9.\-]*_[a-z0-9]{13}![A-Za-z0-9.\-]+', self.app_id))


def valid_app_id(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 512:
        return False
    if any(ord(c) < 32 or ord(c) > 126 for c in value):
        return False
    if any(c in value for c in ': /"\'`,;|&<>') or '..' in value:
        return False
    # Desktop entries may be known-folder paths; never accept a bare path/UNC.
    if '\\' in value:
        return bool(re.fullmatch(r'\{[0-9A-Fa-f-]{36}\}(?:\\[\w.()!+\-]+)+', value))
    return bool(re.fullmatch(r'[A-Za-z0-9_{][A-Za-z0-9_.{}!+\-]*', value))


def parse_inventory(raw):
    if len(raw) > 2 * 1024 * 1024:
        raise DiscoveryError('Windows app inventory exceeded the size limit.')
    try:
        data = json.loads(raw.lstrip('\ufeff'))
        if not isinstance(data, dict) or set(data) != {'Apps', 'PackagedAppIds'}:
            raise ValueError()
        rows, ids = data['Apps'], data['PackagedAppIds']
        if not isinstance(ids, list) or len(ids) > 10000 or any(not isinstance(x, str) for x in ids):
            raise ValueError()
        packaged = set(ids)
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError()
        result = set()
        from .planner import clean
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'Name', 'AppID'}:
                raise ValueError()
            name, app_id = row['Name'], row['AppID']
            if valid_app_id(app_id) and isinstance(name, str) and name and clean(name, 300) == name:
                result.add(InstalledApp(name, app_id, app_id in packaged))
        return tuple(sorted(result, key=lambda a: (a.name.casefold(), a.app_id)))
    except (ValueError, TypeError, RecursionError):
        raise DiscoveryError('Windows returned an unreadable app inventory.') from None


def discover():
    if platform.system() != 'Windows':
        raise DiscoveryError('Installed-app discovery requires Windows. No apps were scanned.')
    from .actions import system_directory
    powershell = system_directory() / 'WindowsPowerShell/v1.0/powershell.exe'
    script = ("$ErrorActionPreference='Stop'; "
              '[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding; '
              '$apps = @(Get-StartApps | Select-Object Name,AppID); '
              '$ids = @(Get-AppxPackage | ForEach-Object { $pkg = $_; '
              '$manifest = Get-AppxPackageManifest -Package $pkg.PackageFullName; '
              'foreach ($app in $manifest.Package.Applications.Application) { '
              "if ($app.Id) { $pkg.PackageFamilyName + '!' + $app.Id } } }); "
              '$result = @{Apps=$apps; PackagedAppIds=$ids}; '
              'ConvertTo-Json -InputObject $result -Depth 4 -Compress')
    try:
        run = subprocess.run([str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive',
                              '-Command', script], shell=False, capture_output=True,
                             timeout=12, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if run.returncode:
            raise DiscoveryError('Start-menu discovery failed. No fallback command was run.')
        return parse_inventory(run.stdout.decode('utf-8-sig'))
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        raise DiscoveryError('Start-menu discovery failed or timed out. Try again explicitly.') from None


def find_exe_on_disk(app_key_or_name: str) -> Path | None:
    """Search known Windows installation roots for a matching executable."""
    key = app_key_or_name.strip().lower()
    key = APP_ALIASES.get(key, key)
    roots = [os.environ.get(k) for k in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA', 'APPDATA')]
    valid_roots = [Path(r) for r in roots if r and Path(r).is_absolute()]
    if key in EXTENDED_APPS:
        _, rels = EXTENDED_APPS[key]
        for root in valid_roots:
            for rel in rels:
                candidate = root / rel
                if candidate.is_file():
                    return candidate.resolve()
        if platform.system() == 'Windows':
            try:
                from .actions import system_directory
                sys_dir = system_directory()
                for rel in rels:
                    candidate = sys_dir / rel
                    if candidate.is_file():
                        return candidate.resolve()
            except Exception:
                pass
    return None


def auto_resolve_app(query: str, reader=None) -> tuple[str, str]:
    """Automatically resolve an app name using background Start-menu discovery and known paths.

    Returns (target_identifier, display_name) suitable for `Action('launch_app', target, query=display_name)`
    or `Action('app', target)` if it matches a core built-in shortcut.
    """
    if reader is None:
        reader = discover
    from .planner import clean
    cleaned = clean(query, 300).strip()
    if not cleaned:
        raise DiscoveryError('Specify an application name to launch.')
    low = cleaned.casefold()
    alias = APP_ALIASES.get(low, low)

    if alias in APP_NAMES:
        return alias, APP_NAMES[alias]

    # 1. Try background Start-menu discovery via discover()
    try:
        inventory = reader()
    except Exception:
        inventory = ()

    if inventory:
        # Exact name match first
        for app in inventory:
            if app.name.casefold() == low or app.name.casefold() == alias:
                return app.app_id, app.name
        # Substring / word match (prefer packaged apps first, then shortest name match)
        matches = [
            app for app in inventory
            if low in app.name.casefold() or alias in app.name.casefold() or app.name.casefold() in low
        ]
        if matches:
            matches.sort(key=lambda a: (not a.packaged, len(a.name), a.name.casefold()))
            best = matches[0]
            return best.app_id, best.name

    # 2. Check extended apps dictionary & disk paths
    exe_path = find_exe_on_disk(alias)
    if exe_path is not None:
        display = EXTENDED_APPS[alias][0] if alias in EXTENDED_APPS else cleaned
        return str(exe_path), display

    if alias in EXTENDED_APPS:
        display, _ = EXTENDED_APPS[alias]
        return alias, display

    # 3. Return cleaned query as a direct launch_app target so WindowsExecutor can resolve it at runtime
    return cleaned, cleaned


class AppCatalog:
    """Session-only, expiring, single-use selection handles. Inventory stays local."""
    def __init__(self, reader=discover, clock=time.monotonic, ttl=120):
        self.reader, self.clock, self.ttl = reader, clock, ttl
        self._choices = {}

    def scan(self):
        rows = self.reader()
        expires = self.clock() + self.ttl
        self._choices = {secrets.token_hex(16): (app, expires) for app in rows}
        return [(token, item[0]) for token, item in self._choices.items()]

    def add_executable(self, value):
        from .executable_target import select_executable
        target = select_executable(value)
        token = secrets.token_hex(16)
        self._choices[token] = (target, self.clock() + self.ttl)
        return token

    def get(self, token):
        item = self._choices.get(token)
        if item is None or self.clock() >= item[1]:
            raise DiscoveryError('App selection expired or changed. Discover and select it again.')
        return item[0]

    def consume(self, token):
        app = self.get(token)
        del self._choices[token]
        return app

    def revalidate(self, app):
        from .executable_target import ExecutableTarget, select_executable
        if isinstance(app, ExecutableTarget):
            if select_executable(app.path) != app:
                raise DiscoveryError('Selected executable changed. Select and approve it again.')
            return
        if not app.packaged:
            raise DiscoveryError('Classic app entries need a locally selected .exe, not an uninspected shortcut.')
        if app not in self.reader():
            raise DiscoveryError('This Windows app registration changed. Nothing was launched. Scan again.')
