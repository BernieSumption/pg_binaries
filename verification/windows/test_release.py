import unittest
from unittest.mock import patch

from verification.windows import release


class ReleaseTests(unittest.TestCase):
    def test_uses_shared_release_record_and_combination_checks_for_native_or_translated_x64(self):
        with patch.object(release, 'release_main', return_value=7) as shared:
            self.assertEqual(release.main(['postgresql.tar.gz', 'report']), 7)
        self.assertEqual(shared.call_args.args, (['postgresql.tar.gz', 'report'],))
        configuration = shared.call_args.kwargs['platform_configuration']
        self.assertEqual(configuration['targets'], ('windows-x86_64',))
        self.assertEqual(configuration['system'], 'Windows')
        self.assertIn('arm64', configuration['machines']['windows-x86_64'])
        self.assertIn('amd64', configuration['machines']['windows-x86_64'])
        self.assertEqual(configuration['version_key'], 'windows_version')
