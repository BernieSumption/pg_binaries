"""Native tool names and a clean environment shared by PostgreSQL probes."""

import getpass
import os
from pathlib import Path
import socket
import tempfile
import uuid


def executable(bin_dir, name):
    return Path(bin_dir) / (name + '.exe' if os.name == 'nt' else name)


def _probe_scratch_directory(parent, prefix):
    parent = Path(parent)
    if os.name == 'nt':
        # PostgreSQL's restricted child process needs inherited Windows ACLs.
        path = parent / f'{prefix}{uuid.uuid4().hex[:12]}'
        path.mkdir()
        return path
    return Path(tempfile.mkdtemp(prefix=prefix, dir=parent))


def clean_environment(bin_dir, *, windows=None):
    windows = os.name == 'nt' if windows is None else windows
    environment = {'HOME': str(Path.home()), 'LANG': os.environ.get('LANG', 'en_US.UTF-8')}
    if windows:
        for name in ('SystemRoot', 'SystemDrive', 'TEMP', 'TMP', 'USERPROFILE'):
            if name in os.environ:
                environment[name] = os.environ[name]
        if 'SystemRoot' in environment:
            environment['COMSPEC'] = str(Path(environment['SystemRoot']) / 'System32/cmd.exe')
        environment['PATH'] = str(bin_dir)
    else:
        environment['PATH'] = os.pathsep.join((str(bin_dir), '/usr/bin', '/bin', '/usr/sbin', '/sbin'))
        if 'TMPDIR' in os.environ:
            environment['TMPDIR'] = os.environ['TMPDIR']
    return environment


def connection(bin_dir, socket_directory, *, windows=None):
    windows = os.name == 'nt' if windows is None else windows
    environment = clean_environment(bin_dir, windows=windows)
    environment['PGUSER'] = getpass.getuser()
    if windows:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        environment.update(PGHOST='127.0.0.1', PGPORT=str(port))
        settings = f"\nlisten_addresses = '127.0.0.1'\nport = {port}\n"
    else:
        environment.update(PGHOST=str(socket_directory), PGPORT='5432')
        settings = f"\nunix_socket_directories = '{socket_directory}'\nlisten_addresses = ''\n"
    return environment, settings
