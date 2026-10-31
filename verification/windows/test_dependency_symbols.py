from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verification.windows.dependency_symbols import inspect


class IdentityTests(unittest.TestCase):
    def fixture(self, root, libraries):
        paths = {'bin/postgres.exe': b'backend', **libraries}
        for relative, content in paths.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return {'bin/postgres.exe': ['postgresql'], **{relative: [relative.split('/')[1]] for relative in libraries}}

    def run_check(self, root, owners, dependencies=None):
        dependencies = dependencies or {}
        with patch('verification.windows.dependency_symbols.imports', side_effect=lambda path: dependencies.get(path.relative_to(root).as_posix(), [])), patch('verification.windows.dependency_symbols.backend_module', side_effect=lambda path: path.name.lower().startswith('module')):
            return inspect(root, 'windows-x86_64', owners)

    def test_different_dll_names_bind_safely_despite_same_export_api(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            owners = self.fixture(root, {'lib/a/module_a.dll': b'same_function_export', 'lib/b/module_b.dll': b'same_function_export'})
            self.assertEqual(self.run_check(root, owners)['conflicts'], [])

    def test_detects_different_bytes_for_case_insensitive_dll_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            owners = self.fixture(root, {'lib/a/module_a.dll': b'a', 'lib/b/module_b.dll': b'b', 'lib/a/common.dll': b'v1', 'lib/b/COMMON.dll': b'v2'})
            details = self.run_check(root, owners, {'lib/a/module_a.dll': ['common.dll'], 'lib/b/module_b.dll': ['common.dll']})
            self.assertEqual(len(details['conflicts']), 1)
            self.assertEqual(details['conflicts'][0]['competing_identity'], 'common.dll')
            self.assertTrue(details['conflicts'][0]['libraries'][0]['consumers'])

    def test_postgresql_and_same_package_and_identical_bytes_are_excluded(self):
        for packages, contents in ((['postgresql', 'b'], [b'v1', b'v2']), (['a', 'a'], [b'v1', b'v2']), (['a', 'b'], [b'same', b'same'])):
            with self.subTest(packages=packages, contents=contents), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                owners = self.fixture(root, {'lib/a/module.dll': contents[0], 'lib/b/MODULE.dll': contents[1]})
                owners['lib/a/module.dll'] = [packages[0]]
                owners['lib/b/MODULE.dll'] = [packages[1]]
                self.assertEqual(self.run_check(root, owners)['conflicts'], [])

    def test_unloaded_helpers_do_not_create_conflicts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            owners = self.fixture(root, {'lib/a/helper.dll': b'a', 'lib/b/HELPER.dll': b'b'})
            self.assertEqual(self.run_check(root, owners)['inspected_binaries'], 1)

    def test_loaded_files_require_archive_ownership(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.fixture(root, {'lib/a/module.dll': b'a'})
            with self.assertRaisesRegex(RuntimeError, 'no archive package ownership'):
                self.run_check(root, {})

    def test_unresolved_non_system_import_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            owners = self.fixture(root, {})
            with self.assertRaisesRegex(RuntimeError, 'unresolved dependency missing.dll'):
                self.run_check(root, owners, {'bin/postgres.exe': ['missing.dll']})
