import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import coverage
import emit_postgis_pilot_record as emitter

ROOT = Path(__file__).resolve().parents[1]
ENV = {'GITHUB_SHA': 'a' * 40, 'GITHUB_RUN_ID': '123',
       'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_SERVER_URL': 'https://github.com'}
OS_RELEASE = 'PRETTY_NAME="Ubuntu 24.04"\nVERSION_ID="24.04"\n'


class PostgisRecordTests(unittest.TestCase):
    def emit(self, directory, architecture, corrupt_core=False):
        root = Path(directory)
        for name in (f'postgresql-18.6-linux-{architecture}.tar.gz',
                     f'postgis-3.6.4-postgresql-18.6-linux-{architecture}.tar.gz'):
            data = name.encode()
            (root / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            if corrupt_core and name.startswith('postgresql-'):
                digest = '0' * 64
            (root / (name + '.sha256')).write_text(f'{digest}  {name}\n')
        read_text = Path.read_text
        def read(path, *args, **kwargs):
            return OS_RELEASE if str(path) == '/etc/os-release' else read_text(path, *args, **kwargs)
        with patch.dict(os.environ, ENV), patch.object(Path, 'read_text', read):
            return emitter.emit(ROOT, root, root, root / 'records',
                                'sha256:' + '1' * 64, '6.11.0-ubuntu', architecture)

    def test_records_bind_both_archives_and_matching_profile(self):
        for architecture, machine in (('x86_64', 'x86_64'), ('arm64', 'aarch64')):
            with self.subTest(architecture=architecture), tempfile.TemporaryDirectory() as directory:
                with patch.object(emitter.platform, 'machine', return_value=machine):
                    paths = self.emit(directory, architecture)
                self.assertEqual(len(paths), 4)
                for path in paths:
                    record = json.loads(path.read_text())
                    self.assertEqual(record['platform'], f'linux-{architecture}')
                    self.assertEqual(record['environment']['architecture'], architecture)
                    self.assertEqual(record['profile_id'], f'postgis-pilot-linux-{architecture}')
                    self.assertEqual(record['assembled_core']['archive'],
                                     f'postgresql-18.6-linux-{architecture}.tar.gz')
                    self.assertEqual(record['scope'], 'pilot-smoke')
                    self.assertIn(architecture, path.name)

    def test_rejects_wrong_native_runner(self):
        with patch.object(emitter.platform, 'machine', return_value='x86_64'):
            with self.assertRaisesRegex(coverage.CoverageError, 'native runner'):
                emitter.emit(ROOT, ROOT, ROOT, ROOT, 'unused', 'unused', 'arm64')

    def test_rejects_core_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(emitter.platform, 'machine', return_value='aarch64'):
                with self.assertRaisesRegex(coverage.CoverageError, 'core archive checksum mismatch'):
                    self.emit(directory, 'arm64', corrupt_core=True)
