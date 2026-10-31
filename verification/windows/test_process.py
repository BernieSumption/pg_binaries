import os
import subprocess
import unittest
from unittest.mock import patch

from packages.postgresql.probes import process


class PgCtlCaptureTests(unittest.TestCase):
    def test_captures_control_output_without_pipe_eof_when_descendant_retains_handles(self):
        retained = []
        def exited_client(arguments, **options):
            self.assertNotIn('capture_output', options)
            for name, content in (('stdout', b'server started\r\n'), ('stderr', b'warning\r\n')):
                stream = options[name]
                retained.append(os.dup(stream.fileno()))
                stream.write(content)
                stream.flush()
            return subprocess.CompletedProcess(arguments, 0)
        try:
            with patch.object(process.sys, 'platform', 'win32'), patch.object(process.subprocess, 'run', side_effect=exited_client):
                result = process.run([r'C:\distribution\bin\pg_ctl.exe', 'start'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, 'server started\n')
            self.assertEqual(result.stderr, 'warning\n')
            for descriptor in retained:
                os.fstat(descriptor)
        finally:
            for descriptor in retained:
                os.close(descriptor)

    def test_preserves_binary_output_and_error_details(self):
        def failed_client(arguments, **options):
            options['stdout'].write(b'partial output')
            options['stderr'].write(b'start failed')
            return subprocess.CompletedProcess(arguments, 7)
        with patch.object(process.sys, 'platform', 'win32'), patch.object(process.subprocess, 'run', side_effect=failed_client):
            with self.assertRaises(subprocess.CalledProcessError) as raised:
                process.run(['pg_ctl.exe', 'start'], capture_output=True, check=True)
        self.assertEqual(raised.exception.returncode, 7)
        self.assertEqual(raised.exception.stdout, b'partial output')
        self.assertEqual(raised.exception.stderr, b'start failed')

    def test_other_commands_and_platforms_keep_standard_subprocess_capture(self):
        for platform, command in (('win32', 'initdb.exe'), ('linux', 'pg_ctl'), ('darwin', 'pg_ctl')):
            with self.subTest(platform=platform, command=command), patch.object(process.sys, 'platform', platform), patch.object(process.subprocess, 'run') as standard:
                expected = standard.return_value
                result = process.run([command, '--version'], capture_output=True, text=True, env={'PATH': 'distribution'})
                self.assertIs(result, expected)
                standard.assert_called_once_with([command, '--version'], capture_output=True, text=True, env={'PATH': 'distribution'})
