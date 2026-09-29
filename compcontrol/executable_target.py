"""User-selected executables, with no shortcut arguments or model-selected paths."""
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .file_workspace import _check_chain, _plain, _identity, WorkspaceError

MAX_EXE = 512 * 1024 * 1024


@dataclass(frozen=True)
class ExecutableTarget:
    path: Path
    identity: tuple
    digest: str

    @property
    def name(self):
        return self.path.name

    @property
    def app_id(self):
        return str(self.path)

    @property
    def detail(self):
        return (f'Executable: {self.path}\nSHA-256: {self.digest}\nArguments: none\n'
                'Selected locally, not inferred by AI. Signature/publisher NOT verified.\n'
                'Launching executes code with your user permissions; the app can modify files '
                'and access the network. Only select an executable you trust.')


def select_executable(value):
    try:
        path = Path(os.path.abspath(value))
        if (path.suffix.lower() != '.exe' or not _plain(str(path)) or path.name.endswith((' ', '.'))
                or ':' in path.name or str(path).startswith(('\\\\', '//'))):
            raise WorkspaceError('Select a regular local .exe, not a script, shortcut or network path.')
        _check_chain(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_EXE or info.st_nlink != 1:
            raise WorkspaceError('Executable must be a regular file without hardlinks, up to 512 MiB.')
        path = path.resolve(strict=True)
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            before = os.fstat(stream.fileno())
            if _identity(before) != _identity(info) or stream.read(2) != b'MZ':
                raise WorkspaceError('Not a recognized Windows executable or file changed during selection.')
            digest = hashlib.sha256(b'MZ')
            total = 2
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_EXE:
                    raise WorkspaceError('Executable grew beyond the size limit.')
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        _check_chain(path)
        if _identity(before) != _identity(after) or _identity(after) != _identity(path.lstat()):
            raise WorkspaceError('Executable changed during selection. Select it again.')
        return ExecutableTarget(path, _identity(after), digest.hexdigest())
    except WorkspaceError:
        raise
    except OSError:
        raise WorkspaceError('Cannot inspect the selected executable. No launch occurred.') from None
