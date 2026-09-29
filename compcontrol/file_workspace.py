"""Local, bounded text snapshots and patch export. NEVER writes to the source.

Path/identity checks catch ordinary stale/wrong selections, not a hostile process
racing Windows directory changes. Patch application is deliberately out of scope.
"""
import difflib
import hashlib
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path

MAX_FILE = 256 * 1024


class WorkspaceError(ValueError):
    pass


def _plain(value):
    return not any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in value)


def _check_chain(path):
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise WorkspaceError('Links and Windows reparse points are not supported. Select a regular local path.')


def _root(value):
    path = Path(os.path.abspath(value))
    if not _plain(str(path)):
        raise WorkspaceError('Hidden control/direction characters in the project path are not supported.')
    if path == Path(path.anchor):
        raise WorkspaceError('Select a project folder, not an entire drive/filesystem root.')
    _check_chain(path)
    if not path.is_dir():
        raise WorkspaceError('Select an existing project directory.')
    return path.resolve(strict=True)


def _parts(relative):
    if not isinstance(relative, str) or len(relative) > 500:
        raise WorkspaceError('Select a relative file path under the project.')
    parts = relative.split('/')
    for part in parts:
        stem = part.split('.')[0].upper()
        if (not part or part in {'.', '..'} or part.endswith((' ', '.')) or part.startswith('-')
                or not _plain(part) or any(c in part for c in '\\:"<>|?*')
                or stem in {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'}
                or re.fullmatch(r'(?:COM|LPT)[1-9¹²³]', stem)):
            raise WorkspaceError('Ambiguous, reserved or unsafe file path. Select an ordinary project file.')
    return parts


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _decode(data):
    try:
        text = data.decode('utf-8')  # Preserve BOM and exact CRLF bytes.
    except UnicodeError:
        raise WorkspaceError('Only UTF-8 text files are supported for patch preview.') from None
    if '\x00' in text:
        raise WorkspaceError('Binary files are not supported.')
    lf = text.replace('\r\n', '')
    if '\r' in lf or ('\r\n' in text and '\n' in lf):
        raise WorkspaceError('Mixed or lone-CR line endings are not supported; original is unchanged.')
    return text


@dataclass(frozen=True)
class Snapshot:
    root: Path
    relative: str
    identity: tuple
    root_identity: tuple
    digest: str
    data: bytes

    @property
    def detail(self):
        return (f'Project: {ascii(str(self.root))}\nFile: {ascii(self.relative)}\n'
                f'Size: {len(self.data)} bytes\nSHA-256: {self.digest}')


def snapshot(root, relative):
    try:
        root = _root(root)
        parts = _parts(relative)
        path = root
        # Require on-disk spelling, not a case-insensitive or 8.3 alias.
        for part in parts:
            if part not in os.listdir(path):
                raise WorkspaceError('File spelling/path changed. Select the exact file again.')
            path = path / part
            _check_chain(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise WorkspaceError('Select a regular file with no hardlinks.')
        if info.st_size > MAX_FILE:
            raise WorkspaceError('Patch preview supports files up to 256 KiB.')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if _identity(before) != _identity(info):
                raise WorkspaceError('File changed during selection. Select it again.')
            data = stream.read(MAX_FILE + 1)
            after = os.fstat(stream.fileno())
        _check_chain(path)
        if (len(data) > MAX_FILE or _identity(before) != _identity(after)
                or _identity(after) != _identity(path.lstat())):
            raise WorkspaceError('File changed during reading. Select it again.')
        _decode(data)
        ri = root.stat()
        return Snapshot(root, '/'.join(parts), _identity(after), (ri.st_dev, ri.st_ino),
                        hashlib.sha256(data).hexdigest(), data)
    except WorkspaceError:
        raise
    except OSError:
        raise WorkspaceError('Could not read this project/file. Nothing was modified.') from None


def verify(original):
    current = snapshot(original.root, original.relative)
    if (current.root != original.root or current.root_identity != original.root_identity
            or current.identity != original.identity or current.digest != original.digest):
        raise WorkspaceError('Source changed since selection. Select it again and review a new patch.')


def _lines(text):
    parts = text.split('\n')
    return [p + '\n' for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


@dataclass(frozen=True)
class PatchPreview:
    source: Snapshot
    patch: bytes
    replacement_digest: str


def preview_replace(original, old, new):
    verify(original)
    if not isinstance(old, str) or not isinstance(new, str) or not old:
        raise WorkspaceError('Supply exact non-empty text to replace.')
    if any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} and c not in '\n\t'
           for c in old + new):
        raise WorkspaceError('Control and bidirectional formatting characters are not supported in edits.')
    if len(old) > MAX_FILE or len(new) > MAX_FILE or old == new:
        raise WorkspaceError('Replacement is unchanged or too large.')
    text = _decode(original.data)
    # Tk text boxes use LF. Map both fields to the selected file's newline style.
    if '\r' in old or '\r' in new or '\x00' in new:
        raise WorkspaceError('Use ordinary text with LF line breaks in the replacement fields.')
    if '\r\n' in text:
        old, new = old.replace('\n', '\r\n'), new.replace('\n', '\r\n')
    index = text.find(old)
    if index < 0:
        raise WorkspaceError('Exact text was not found. No fuzzy match or guessed edit is allowed.')
    if text.find(old, index + 1) != -1:
        raise WorkspaceError('Text matches more than once. Include more context to identify one location.')
    updated = text[:index] + new + text[index + len(old):]
    data = updated.encode('utf-8')
    if len(data) > MAX_FILE:
        raise WorkspaceError('Result exceeds the 256 KiB preview limit.')
    # Quoted/unicode filenames need Git-specific escaping. Defer those exports.
    if any(ord(c) > 126 for c in original.relative):
        raise WorkspaceError('Patch export currently needs an ASCII filename (UTF-8 content is supported).')
    pieces = []
    for line in difflib.unified_diff(_lines(text), _lines(updated),
                                     'a/' + original.relative, 'b/' + original.relative):
        pieces.append(line)
        if not line.endswith('\n'):
            pieces.append('\n\\ No newline at end of file\n')
    header = ('CompControl review patch — NOT APPLIED\n' + original.detail + '\n'
              'Patch tools do NOT verify this root or SHA-256. Verify the project and diff yourself.\n\n')
    return PatchPreview(original, (header + ''.join(pieces)).encode('utf-8'), hashlib.sha256(data).hexdigest())


def export_patch(preview, destination):
    """Create a NEW patch outside the selected project; never overwrite anything."""
    verify(preview.source)
    try:
        target = Path(os.path.abspath(destination))
        _parts(target.name)
        if target.suffix.lower() != '.patch':
            raise WorkspaceError('Export to a new .patch file.')
        _check_chain(target.parent)
        parent = target.parent.resolve(strict=True)
        if parent == preview.source.root or preview.source.root in parent.parents:
            raise WorkspaceError('Export outside the project so project files remain untouched.')
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
        fd = os.open(parent / target.name, flags, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(preview.patch)
            stream.flush()
            os.fsync(stream.fileno())
    except WorkspaceError:
        raise
    except FileExistsError:
        raise WorkspaceError('Export already exists. Choose a new filename; nothing was overwritten.') from None
    except OSError:
        raise WorkspaceError('Export failed; a partial patch may exist. Original project files are unchanged.') from None


class PatchCatalog:
    """Ephemeral native approval handles; AI cannot name or create them."""
    def __init__(self, clock=None, ttl=120):
        import time
        self.clock = clock or time.monotonic
        self.ttl = ttl
        self._items = {}

    @staticmethod
    def _check_destination(preview, destination):
        target = Path(os.path.abspath(destination))
        _parts(target.name)
        if target.suffix.lower() != '.patch':
            raise WorkspaceError('Export to a new .patch file.')
        _check_chain(target.parent)
        parent = target.parent.resolve(strict=True)
        if parent == preview.source.root or preview.source.root in parent.parents:
            raise WorkspaceError('Export outside the project so project files remain untouched.')
        if target.exists():
            raise WorkspaceError('Export already exists. Choose a new filename; nothing was overwritten.')
        return target

    def register(self, preview, destination):
        verify(preview.source)
        target = self._check_destination(preview, destination)
        import secrets
        token = secrets.token_hex(16)
        self._items[token] = (preview, target, self.clock() + self.ttl)
        return token

    def get(self, token):
        item = self._items.get(token)
        if not item or self.clock() >= item[2]:
            self._items.pop(token, None)
            raise WorkspaceError('Patch approval expired. Review and export a new patch.')
        return item[0], item[1]

    def describe(self, token):
        preview, target = self.get(token)
        return (preview.source.detail + f'\n\nNew patch file: {ascii(str(target))}\n'
                f'Patch SHA-256: {hashlib.sha256(preview.patch).hexdigest()}\n'
                'Creates a new .patch only. Never edits/applies the source. Verify diff and base before manual use.')

    def export(self, token):
        item = self._items.pop(token, None)
        if not item or self.clock() >= item[2]:
            raise WorkspaceError('Patch approval expired. Nothing was exported.')
        preview, target, _ = item
        return export_patch(preview, target)
