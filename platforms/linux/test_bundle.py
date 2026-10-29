import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("bundle-runtime.sh")


class LinuxBundleTests(unittest.TestCase):
    def test_recursive_libraries_are_copied_from_paths_with_spaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = root / "payload"
            tools = root / "tools"
            dependencies = root / "private dependencies"
            (payload / "lib").mkdir(parents=True)
            tools.mkdir()
            dependencies.mkdir()
            (payload / "lib/module.so").write_text("module")
            (dependencies / "liba.so").write_text("a")
            (dependencies / "libb.so").write_text("b")
            (tools / "file").write_text('#!/bin/sh\necho ELF\n')
            (tools / "ldd").write_text('''#!/bin/sh
case "$1" in
  */module.so) printf '  liba.so => %s/liba.so (0x123)\\n' "$TEST_DEPS" ;;
  */liba.so) printf '  libb.so => %s/libb.so (0x456)\\n' "$TEST_DEPS" ;;
esac
''')
            for tool in tools.iterdir():
                tool.chmod(0o755)
            environment = {**os.environ, "PATH": str(tools) + ":" + os.environ["PATH"], "TEST_DEPS": str(dependencies)}
            subprocess.run(["bash", str(SCRIPT), str(payload), str(payload / "lib/runtime"),
                            str(root / "postgresql"), "EXTENSION"], check=True, env=environment)
            self.assertEqual((payload / "lib/runtime/liba.so").read_text(), "a")
            self.assertEqual((payload / "lib/runtime/libb.so").read_text(), "b")
