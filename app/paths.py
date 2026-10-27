"""Separate distributable application resources from private installation data."""
import os
import stat
import sys
import tempfile
from pathlib import Path


def data_directory():
    if os.environ.get('PAF_DATA_DIR'):
        return Path(os.environ['PAF_DATA_DIR']).expanduser().resolve()
    if not getattr(sys, 'frozen', False):
        return None  # Preserve existing source-install paths and configuration.
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    return base / 'Ping_A_Friend'


def private_path(filename, legacy):
    directory = data_directory()
    return directory / filename if directory is not None else Path(legacy)


def external_environment():
    """System ping/browser helpers must not load one-file bundle libraries."""
    env = os.environ.copy()
    if getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
        original = env.get('LD_LIBRARY_PATH_ORIG')
        if original:
            env['LD_LIBRARY_PATH'] = original
        else:
            env.pop('LD_LIBRARY_PATH', None)
    return env


def private_directory(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Private application data directories must not be symlinks')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Do not chmod the working directory or a user's home for a bare filename.
    if path.resolve() not in {Path.cwd().resolve(), Path.home().resolve(), Path('/').resolve(), Path(tempfile.gettempdir()).resolve()}:
        if os.name == 'posix' and path.stat().st_uid != os.getuid():
            raise PermissionError('Private application data belongs to another user')
        path.chmod(0o700)


def private_file(path, create=False):
    path = Path(path)
    private_directory(path.parent)
    flags = os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    if create:
        flags |= os.O_CREAT
    if path.is_symlink():
        raise ValueError('Private application files must not be symlinks')
    fd = os.open(path, flags, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Private application storage must be a regular file')
        if os.name == 'posix' and info.st_uid != os.getuid():
            raise PermissionError('Private application file belongs to another user')
        if os.name == 'posix':
            os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    return path
