import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from packages.postgresql.probes.environment import clean_environment, connection
from packages.postgresql.probes.builtins import expected_extensions
from verification.runtime import archive_contents


class WindowsEnvironmentTests(unittest.TestCase):
    def test_environment_excludes_builders_path_and_retains_windows_process_support(self):
        with patch.dict(os.environ, {'PATH': 'C:/developer/bin', 'SystemRoot': 'C:/Windows', 'TEMP': 'C:/Temp'}, clear=True):
            environment = clean_environment(Path('C:/distribution/bin'), windows=True)
        self.assertEqual(environment['PATH'], 'C:/distribution/bin')
        self.assertEqual(environment['SystemRoot'], 'C:/Windows')
        self.assertEqual(environment['TEMP'], 'C:/Temp')
        self.assertNotIn('C:/developer', str(environment))

    def test_connection_uses_loopback_ephemeral_port(self):
        with patch('packages.postgresql.probes.environment.socket.socket') as socket_factory:
            listener = socket_factory.return_value.__enter__.return_value
            listener.getsockname.return_value = ('127.0.0.1', 49152)
            environment, settings = connection(Path('C:/distribution/bin'), Path('unused'), windows=True)
            listener.bind.assert_called_once_with(('127.0.0.1', 0))
        self.assertEqual(environment['PGHOST'], '127.0.0.1')
        self.assertGreater(int(environment['PGPORT']), 0)
        self.assertIn(f"port = {environment['PGPORT']}", settings)
        self.assertNotIn('unix_socket', settings)

    def test_windows_builtin_selection_excludes_only_uuid_ossp(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / 'source.tar.gz'
            with tarfile.open(archive_path, 'w:gz') as archive:
                for name in ('uuid-ossp', 'xml2', 'pgcrypto'):
                    entry = tarfile.TarInfo(f'postgresql/contrib/{name}/{name}.control')
                    entry.size = 1
                    archive.addfile(entry, io.BytesIO(b'x'))
            self.assertEqual(expected_extensions(archive_path, windows=True), {'xml2', 'pgcrypto'})
            self.assertEqual(expected_extensions(archive_path, windows=False), {'uuid-ossp', 'xml2', 'pgcrypto'})

    def test_windows_archive_requires_exe_tools_without_unix_execute_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / 'postgresql.tar.gz'
            with tarfile.open(archive_path, 'w:gz') as archive:
                directory = tarfile.TarInfo('postgresql')
                directory.type = tarfile.DIRTYPE
                directory.mode = 0o755
                archive.addfile(directory)
                licence = tarfile.TarInfo('postgresql/LICENCE')
                licence.size = 1
                archive.addfile(licence, io.BytesIO(b'x'))
                for name in ('initdb', 'pg_ctl', 'psql', 'pg_dump', 'pg_restore'):
                    entry = tarfile.TarInfo(f'postgresql/bin/{name}.exe')
                    entry.mode = 0o644
                    entry.size = 1
                    archive.addfile(entry, io.BytesIO(b'x'))
            archive_contents(archive_path, {}, 'windows-x86_64')
            with self.assertRaisesRegex(RuntimeError, 'missing or non-executable'):
                archive_contents(archive_path, {}, 'linux-x86_64')


class SourceTLSFixtureTests(unittest.TestCase):
    def test_reads_only_named_public_upstream_tls_identities(self):
        from packages.postgresql.probes.tls import source_certificates
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path, destination = root / 'source.tar.gz', root / 'certs'
            destination.mkdir()
            names = ('server-cn-only+server_ca.crt', 'server-cn-only.key', 'client+client_ca.crt', 'client.key', 'root_ca.crt', 'root+client_ca.crt')
            with tarfile.open(archive_path, 'w:gz') as archive:
                for name in names:
                    entry = tarfile.TarInfo(f'postgresql/src/test/ssl/ssl/{name}')
                    payload = name.encode()
                    entry.size = len(payload)
                    archive.addfile(entry, io.BytesIO(payload))
            source_certificates(archive_path, destination)
            self.assertEqual((destination / 'server.crt').read_text(), 'server-cn-only+server_ca.crt')
            self.assertEqual((destination / 'client.crt').read_text(), 'client+client_ca.crt')
            self.assertEqual((destination / 'server-ca.crt').read_text(), 'root+client_ca.crt')
            self.assertEqual(len(list(destination.iterdir())), 6)


class WindowsArchiveIdentityTests(unittest.TestCase):
    def test_rejects_windows_reserved_and_ambiguous_names(self):
        from verification.archive import ArchiveError, Entry
        from verification.windows.archive import validate_paths
        for name in ('file:stream', 'NUL.dll', 'trailing.', 'trailing ', 'wild?card'):
            with self.subTest(name=name), self.assertRaises(ArchiveError):
                validate_paths({'postgresql/bin/' + name: Entry('file', 0o644, b'bytes')})
        with self.assertRaisesRegex(ArchiveError, 'case-insensitive'):
            validate_paths({'postgresql/bin/Name.dll': Entry('file', 0o644, b'one'),
                            'postgresql/bin/name.DLL': Entry('file', 0o644, b'two')})
