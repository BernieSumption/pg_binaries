import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import check_elf_dependencies as checker


class ElfInspectionTests(unittest.TestCase):
    def inspect(self, machine, program, dynamic):
        outputs = {"-hW": f"  Machine:                           {machine}\n",
                   "-lW": program, "-dW": dynamic}

        def run(command, **kwargs):
            option = next(arg for arg in command if arg in outputs)
            return subprocess.CompletedProcess(command, 0, outputs[option], "")

        with patch.object(checker.subprocess, "run", side_effect=run):
            return checker.inspect_elf(Path("fixture"))

    def test_reads_architecture_interpreter_and_both_search_path_tags(self):
        result = self.inspect(
            "AArch64",
            "[Requesting program interpreter: /lib/ld-linux-aarch64.so.1]\n",
            " 0x000000000000000f (RPATH)              Library rpath: [$ORIGIN/../lib]\n"
            " 0x000000000000001d (RUNPATH)            Library runpath: [$ORIGIN/plugins:/opt/host]\n",
        )
        self.assertEqual(result, ("arm64", "/lib/ld-linux-aarch64.so.1",
                                  ["$ORIGIN/../lib", "$ORIGIN/plugins", "/opt/host"]))

    def test_rejects_unknown_machine(self):
        with self.assertRaisesRegex(ValueError, "unsupported or unrecognized"):
            self.inspect("RISC-V", "", "")

    def test_accepts_origin_path_resolving_inside_installation(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp).resolve()
            binary = prefix / "bin/tool"
            binary.parent.mkdir()
            checker.validate_paths(binary, prefix, "x86_64", None, ["$ORIGIN/../lib"])

    def test_rejects_absolute_and_escaping_search_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp).resolve()
            binary = prefix / "bin/tool"
            binary.parent.mkdir()
            for search_path in ("/opt/host/lib", "$ORIGIN/../../../outside", "$ORIGINsuffix"):
                with self.subTest(search_path=search_path), self.assertRaises(ValueError):
                    checker.validate_paths(binary, prefix, "x86_64", None, [search_path])

    def test_rejects_wrong_or_missing_bundled_interpreter(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp).resolve()
            (prefix / "lib/glibc").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "forbidden ELF interpreter"):
                checker.validate_paths(Path(temp) / "bin/tool", prefix, "x86_64",
                                       "/lib/ld-linux-aarch64.so.1", [])
            with self.assertRaisesRegex(ValueError, "no bundled loader"):
                checker.validate_paths(Path(temp) / "bin/tool", prefix, "x86_64",
                                       "/lib64/ld-linux-x86-64.so.2", [])


if __name__ == "__main__":
    unittest.main()
