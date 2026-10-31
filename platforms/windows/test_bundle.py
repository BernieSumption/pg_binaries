from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from platforms.windows.bundle import bundle


class ClosureTests(unittest.TestCase):
    def test_copies_only_transitive_non_system_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix, provider = root / 'postgresql', root / 'provider'
            (prefix / 'lib').mkdir(parents=True)
            provider.mkdir()
            (prefix / 'lib/extension.dll').write_bytes(b'extension')
            for name in ('first.dll', 'second.dll', 'unused.dll'):
                (provider / name).write_bytes(name.encode())
            imports = {'extension.dll': ['FIRST.dll', 'kernel32.dll'], 'first.dll': ['second.dll'], 'second.dll': []}
            with patch('platforms.windows.bundle.inspect', side_effect=lambda path, _: imports[path.name]):
                self.assertEqual(bundle(prefix, [provider]), ['first.dll', 'second.dll'])
            self.assertFalse((prefix / 'bin/unused.dll').exists())

    def test_missing_import_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary)
            (prefix / 'extension.dll').write_bytes(b'extension')
            with patch('platforms.windows.bundle.inspect', return_value=['missing.dll']):
                with self.assertRaisesRegex(ValueError, 'unresolved non-system import'):
                    bundle(prefix, [])

    def test_conflicting_providers_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = root / 'postgresql'
            prefix.mkdir()
            (prefix / 'extension.dll').write_bytes(b'extension')
            providers = [root / 'one', root / 'two']
            for index, provider in enumerate(providers):
                provider.mkdir()
                (provider / 'dependency.dll').write_bytes(str(index).encode())
            with patch('platforms.windows.bundle.inspect', return_value=['dependency.dll']):
                with self.assertRaisesRegex(ValueError, 'conflicting providers'):
                    bundle(prefix, providers)

    def test_reuses_postgresql_dlls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix, postgres = root / 'payload', root / 'postgresql'
            prefix.mkdir()
            (postgres / 'bin').mkdir(parents=True)
            (prefix / 'extension.dll').write_bytes(b'extension')
            (postgres / 'bin/libpq.dll').write_bytes(b'libpq')
            with patch('platforms.windows.bundle.inspect', return_value=['libpq.dll']):
                self.assertEqual(bundle(prefix, [], postgres=postgres), [])
