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
    def emit(self, directory, architecture, corrupt_core=False, minimum=False, bad_log=False,
             bad_digest=False, outcome='passed', postgresql_version='18.6',
             evidence_version=None):
        root = Path(directory)
        for name in (f'postgresql-{postgresql_version}-linux-{architecture}.tar.gz',
                     f'postgis-3.6.4-postgresql-{postgresql_version}-linux-{architecture}.tar.gz'):
            data = name.encode()
            (root / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            if corrupt_core and name.startswith('postgresql-'):
                digest = '0' * 64
            (root / (name + '.sha256')).write_text(f'{digest}  {name}\n')
        evidence = None
        if minimum:
            evidence = root / 'evidence'
            evidence.mkdir()
            pinned = emitter.ARCHITECTURES[architecture]['image_sha256']
            (evidence / 'environment.txt').write_text(
                f"test_revision={ENV['GITHUB_SHA']}\npostgresql_version={evidence_version or postgresql_version}\n"
                f"image_sha256={pinned}\n")
            success = ('PASS: PostGIS 3.6.4 minimum-kernel archive verification\n'
                       if outcome == 'passed' else '')
            (evidence / 'full-verifier.log').write_text(
                f"guest_os=Ubuntu 22.04.5 LTS\nguest_kernel={'6.8.0' if bad_log else '5.15.0-1'}\n"
                f"guest_architecture={architecture}\n"
                + success)
            checksums = ''.join(path.read_text() for path in sorted(root.glob('*.sha256')))
            if bad_digest:
                checksums = '0' * 64 + checksums[64:]
            (evidence / 'archive-checksums.sha256').write_text(checksums)
        read_text = Path.read_text
        def read(path, *args, **kwargs):
            return OS_RELEASE if str(path) == '/etc/os-release' else read_text(path, *args, **kwargs)
        with patch.dict(os.environ, ENV), patch.object(Path, 'read_text', read):
            return emitter.emit(ROOT, root, root, root / 'records',
                                'sha256:' + '1' * 64, '6.11.0-ubuntu', architecture,
                                evidence, outcome, postgresql_version)

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

    def test_non_default_postgresql_minor_binds_guest_archives_and_records(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(emitter.platform, 'machine', return_value='x86_64'):
                paths = self.emit(directory, 'x86_64', minimum=True,
                                  postgresql_version='18.7')
            self.assertEqual(len(paths), 4)
            for path in paths:
                record = json.loads(path.read_text())
                self.assertEqual(record['postgresql_version'], '18.7')
                self.assertEqual(record['assembled_core']['version'], '18.7')
                self.assertEqual(record['assembled_core']['archive'],
                                 'postgresql-18.7-linux-x86_64.tar.gz')
                self.assertIn('postgresql-18.7-linux-x86_64', path.name)

    def test_minimum_rejects_evidence_for_another_postgresql_minor(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(emitter.platform, 'machine', return_value='x86_64'):
                with self.assertRaisesRegex(coverage.CoverageError,
                                            'minimum-kernel evidence provenance mismatch'):
                    self.emit(directory, 'x86_64', minimum=True,
                              postgresql_version='18.7', evidence_version='18.6')
            self.assertFalse((Path(directory) / 'records').exists())

    def test_rejects_malformed_postgresql_version_before_archive_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(emitter.platform, 'machine', return_value='x86_64'):
                with self.assertRaisesRegex(coverage.CoverageError,
                                            'numeric major.minor'):
                    self.emit(directory, 'x86_64', postgresql_version='18.6x')

    def test_minimum_records_bind_guest_and_both_archives(self):
        for architecture, machine in (('x86_64', 'x86_64'), ('arm64', 'aarch64')):
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(emitter.platform, 'machine', return_value=machine):
                    paths = self.emit(directory, architecture, minimum=True)
                self.assertEqual(len(paths), 4)
                for path in paths:
                    record = json.loads(path.read_text())
                    self.assertEqual(record['environment']['endpoint'], 'minimum')
                    self.assertEqual(record['environment']['kernel_release'], '5.15.0-1')
                    self.assertEqual(record['profile_id'], f'postgis-minimum-kernel-{architecture}')
                    self.assertIn('-minimum-', path.name)

    def test_minimum_rejects_guest_kernel_or_archive_mismatch(self):
        for kwargs in ({'bad_log': True}, {'bad_digest': True}):
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(emitter.platform, 'machine', return_value='x86_64'):
                    with self.assertRaises(coverage.CoverageError):
                        self.emit(directory, 'x86_64', minimum=True, **kwargs)
                self.assertFalse((Path(directory) / 'records').exists())

    def test_failed_and_skipped_minimum_records_require_actual_clean_guest_identity(self):
        for outcome in ('failed', 'skipped'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                with patch.object(emitter.platform, 'machine', return_value='x86_64'):
                    paths = self.emit(directory, 'x86_64', minimum=True, outcome=outcome)
                self.assertEqual(len(paths), 4)
                for path in paths:
                    record = json.loads(path.read_text())
                    self.assertEqual(record['outcome'], outcome)
                    self.assertFalse(record['environment']['clean_system'])
                    self.assertFalse(record['environment']['dependency_checks_passed'])
                    self.assertNotIn('kernel_release', record['environment'])
                    self.assertNotIn('distribution', record['environment'])

    def test_failed_current_records_do_not_claim_dependency_checks_passed(self):
        for outcome in ('failed', 'skipped'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                with patch.object(emitter.platform, 'machine', return_value='x86_64'):
                    paths = self.emit(directory, 'x86_64', outcome=outcome)
                self.assertEqual(len(paths), 4)
                for path in paths:
                    record = json.loads(path.read_text())
                    self.assertEqual(record['outcome'], outcome)
                    self.assertFalse(record['environment']['clean_system'])
                    self.assertFalse(record['environment']['dependency_checks_passed'])

    def test_rejects_wrong_native_runner(self):
        with patch.object(emitter.platform, 'machine', return_value='x86_64'):
            with self.assertRaisesRegex(coverage.CoverageError, 'native runner'):
                emitter.emit(ROOT, ROOT, ROOT, ROOT, 'unused', 'unused', 'arm64')

    def test_rejects_core_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(emitter.platform, 'machine', return_value='aarch64'):
                with self.assertRaisesRegex(coverage.CoverageError, 'core archive checksum mismatch'):
                    self.emit(directory, 'arm64', corrupt_core=True)
