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
            (payload / "lib/module.so").write_bytes(b"\x7fELFmodule")
            (dependencies / "liba.so").write_bytes(b"\x7fELFa")
            (dependencies / "libb.so").write_bytes(b"\x7fELFb")
            (payload / "lib/schema.sql").write_text("SELECT 1;")
            (tools / "ldd").write_text('''#!/bin/sh
case "$1" in
  */schema.sql) echo 'bad.so => /no-such-library (0x123)' ;;
  */module.so) printf '  liba.so => %s/liba.so (0x123)\\n' "$TEST_DEPS" ;;
  */liba.so) printf '  libb.so => %s/libb.so (0x456)\\n' "$TEST_DEPS" ;;
esac
''')
            for tool in tools.iterdir():
                tool.chmod(0o755)
            environment = {**os.environ, "PATH": str(tools) + ":" + os.environ["PATH"], "TEST_DEPS": str(dependencies)}
            subprocess.run(["bash", str(SCRIPT), str(payload), str(payload / "lib/runtime"),
                            str(root / "postgresql"), "EXTENSION"], check=True, env=environment)
            self.assertEqual((payload / "lib/runtime/liba.so").read_bytes(), b"\x7fELFa")
            self.assertEqual((payload / "lib/runtime/libb.so").read_bytes(), b"\x7fELFb")

    def test_only_elf_files_are_relocated_in_each_mode(self):
        for mode in ("CORE", "EXTENSION", "POSTGIS"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                payload, tools = root / "payload", root / "tools"
                (payload / "lib").mkdir(parents=True)
                (payload / "libexec").mkdir()
                tools.mkdir()
                (payload / "lib/module.so").write_bytes(b"\x7fELFmodule")
                (payload / "lib/schema.sql").write_text("SELECT 1;")
                (tools / "patchelf").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_LOG"\n')
                (tools / "realpath").write_text('#!/bin/sh\necho .\n')
                for tool in tools.iterdir():
                    tool.chmod(0o755)
                log = root / "patched.txt"
                environment = {**os.environ, "PATH": str(tools) + ":" + os.environ["PATH"], "TEST_LOG": str(log)}
                command = ["bash", str(SCRIPT.with_name("relocate-runtime.sh")), str(payload), mode]
                if mode == "EXTENSION":
                    command.append("example-deps")
                subprocess.run(command, check=True, env=environment)
                contents = log.read_text()
                self.assertIn("module.so", contents)
                self.assertNotIn("schema.sql", contents)
                if mode == "EXTENSION":
                    self.assertIn("example-deps", contents)
