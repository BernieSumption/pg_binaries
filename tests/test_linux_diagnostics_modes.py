import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/linux/diagnostics-in-container.sh"


class LinuxDiagnosticsModeTests(unittest.TestCase):
    def test_core_only_does_not_require_vector_inputs(self):
        architecture = "x86_64"
        with tempfile.TemporaryDirectory() as temporary:
            archives = Path(temporary)
            archive = archives / f"postgresql-18.6-linux-{architecture}.tar.gz"
            archive.write_bytes(b"placeholder archive")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            (archives / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n")
            symbols = archives / "debug-symbols"
            symbols.mkdir()
            (symbols / "index.json").write_text(json.dumps({"files": []}))
            fake_bin = archives / "bin"
            fake_bin.mkdir()
            uname = fake_bin / "uname"
            uname.write_text("#!/bin/sh\nprintf '%s\\n' x86_64\n")
            uname.chmod(0o755)

            result = subprocess.run(
                ["bash", str(SCRIPT), str(archives), "18.6", architecture],
                env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}", "PG_DIAGNOSTICS_MODE": "core-only"},
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Missing diagnostic input:", result.stderr)
        self.assertNotIn("pgvector-", result.stderr)

    def test_paired_mode_still_requires_vector_inputs(self):
        architecture = "x86_64"
        with tempfile.TemporaryDirectory() as temporary:
            archives = Path(temporary)
            archive = archives / f"postgresql-18.6-linux-{architecture}.tar.gz"
            archive.write_bytes(b"placeholder archive")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            (archives / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n")
            symbols = archives / "debug-symbols"
            symbols.mkdir()
            (symbols / "index.json").write_text(json.dumps({"files": []}))
            fake_bin = archives / "bin"
            fake_bin.mkdir()
            uname = fake_bin / "uname"
            uname.write_text("#!/bin/sh\nprintf '%s\\n' x86_64\n")
            uname.chmod(0o755)

            result = subprocess.run(
                ["bash", str(SCRIPT), str(archives), "18.6", architecture],
                env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"},
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Missing diagnostic input:", result.stderr)
        self.assertIn("pgvector-", result.stderr)


if __name__ == "__main__":
    unittest.main()
