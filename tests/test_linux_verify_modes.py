import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LinuxVerifyModeTests(unittest.TestCase):
    def test_core_only_mode_is_forwarded_without_a_pgvector_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            archive_dir = temp / "archives"
            archive_dir.mkdir()
            (archive_dir / "postgresql-18.6-linux-x86_64.tar.gz").write_bytes(b"archive")
            (archive_dir / "postgresql-18.6-linux-x86_64.tar.gz.sha256").write_text("sidecar\n")
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            docker_log = temp / "docker.log"
            docker = fake_bin / "docker"
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\n')
            docker.chmod(0o755)
            environment = os.environ.copy()
            environment.update({
                "PATH": f"{fake_bin}:{environment['PATH']}",
                "DOCKER_LOG": str(docker_log),
                "PG_VERIFY_MODE": "core-only",
                "PG_VERSION": "18.6",
                "PG_ARCHITECTURE": "x86_64",
            })
            subprocess.run(
                [str(ROOT / "scripts/linux/verify.sh"), str(archive_dir)],
                cwd=ROOT, env=environment, check=True, capture_output=True, text=True,
            )
            calls = docker_log.read_text().splitlines()
            self.assertEqual(len(calls), 2)
            self.assertIn("PG_VERIFY_MODE=core-only", calls[1])
            self.assertNotIn("pgvector-", "\n".join(calls))

if __name__ == "__main__":
    unittest.main()
