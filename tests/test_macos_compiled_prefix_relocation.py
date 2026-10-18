"""Verify macOS relocation probes hide and then restore the compiled prefix."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/macos/compiled-prefix-relocation.sh"


class CompiledPrefixRelocationTests(unittest.TestCase):
    def test_prefix_is_unavailable_during_probe_and_restored_afterward(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiled_install = root / "compiled-install"
            compiled_install.mkdir()
            marker = compiled_install / "compiled-marker"
            marker.write_text("restore check\n")
            prefix = root / "compiled-prefix"
            prefix.symlink_to(compiled_install)
            probe = root / "relocated-probe"
            probe.mkdir()
            result = subprocess.run(
                [
                    "bash", "-c",
                    'source "$1"; '
                    'macos_hide_compiled_prefix "$2" "$3"; '
                    'test ! -e "$2" && test ! -L "$2"; '
                    'test ! -e "$3" && test ! -L "$3"; '
                    'test -d "$4"; '
                    'macos_restore_compiled_prefix; '
                    'test -L "$2" && test "$(readlink "$2")" = "$3"; '
                    'test -d "$3" && test -f "$3/compiled-marker"',
                    "relocation-test", str(HELPER), str(prefix),
                    str(compiled_install), str(probe),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(prefix.is_symlink())
            self.assertEqual(os.readlink(prefix), str(compiled_install))


if __name__ == "__main__":
    unittest.main()
