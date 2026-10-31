from pathlib import Path
import tempfile
import unittest

from windows_collect import collect, EXTENSIONS
from windows_prepare_sdk import prepare


class WindowsPackageTests(unittest.TestCase):
    def test_collects_all_five_extensions_and_runtime_data_without_development_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk, payload, data = root / 'sdk', root / 'payload', root / 'data'
            (sdk / 'share/extension').mkdir(parents=True)
            (sdk / 'lib').mkdir()
            for name in EXTENSIONS:
                (sdk / 'share/extension' / f'{name}.control').write_text('control')
                (sdk / 'share/extension' / f'{name}--version.sql').write_text('SQL')
            for name in EXTENSIONS[:-1]:
                (sdk / 'lib' / f'{name}-3.dll').write_bytes(b'module')
            (sdk / 'lib/postgres.lib').write_bytes(b'import library')
            (sdk / 'share/extension/unrelated.control').write_text('unrelated')
            for name in ('proj', 'gdal'):
                (data / name).mkdir(parents=True)
                (data / name / 'runtime-data').write_text(name)
            collect(sdk, payload, data)
            self.assertEqual({path.stem for path in (payload / 'share/extension').glob('*.control')}, set(EXTENSIONS))
            self.assertEqual(len(list((payload / 'lib').iterdir())), 4)
            self.assertFalse((payload / 'lib/postgres.lib').exists())
            self.assertEqual((payload / 'share/proj/runtime-data').read_text(), 'proj')
            self.assertEqual((payload / 'share/gdal/runtime-data').read_text(), 'gdal')

    def test_sdk_copy_rebases_pgxs_without_mutating_cached_dependency(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            cached, private = root / 'dependencies/mingw-postgresql', root / 'postgis-sdk'
            (cached / 'lib/pgxs/src').mkdir(parents=True)
            (cached / 'lib/postgres.lib').write_bytes(b'selected MSVC import library')
            original = f'prefix = {cached}\nlibdir = {cached}/lib\n'
            (cached / 'lib/pgxs/src/Makefile.global').write_text(original)
            prepare(cached, private)
            self.assertIn(f'prefix = {private}', (private / 'lib/pgxs/src/Makefile.global').read_text())
            self.assertEqual((cached / 'lib/pgxs/src/Makefile.global').read_text(), original)
            self.assertEqual((private / 'lib/postgres.lib').read_bytes(), b'selected MSVC import library')


if __name__ == '__main__':
    unittest.main()
