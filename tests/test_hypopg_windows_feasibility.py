import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HypoPGWindowsFeasibilityTests(unittest.TestCase):
    def test_workflow_is_manual_and_uses_the_shared_pinned_core(self):
        workflow = (ROOT / ".github/workflows/hypopg-windows-feasibility.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("windows-2022", workflow)
        self.assertIn("tools/windows_core_pin.py --github-output", workflow)
        self.assertIn("windows-postgresql-18.6-pilot", workflow)
        self.assertIn("hypopg-windows-x86-64-feasibility-${{ github.run_id }}", workflow)

    def test_script_derives_sources_and_checks_the_relocated_archive(self):
        script = (ROOT / "scripts/hypopg/windows-feasibility.ps1").read_text()
        linux_builder = (ROOT / "scripts/hypopg/build-in-container.sh").read_text()
        source_hash = re.search(r"\$sourceSha256 = '([0-9a-f]{64})'", script).group(1)
        self.assertEqual(source_hash, "498a961d88cf37057fd9e98027d06fe805c8959d51895c3d9b94c9eb4e14f706")
        self.assertIn("MODULE_big\\s*=\\s*hypopg", script)
        self.assertIn("OBJS\\s*=\\s*", script)
        self.assertIn("clang-cl.exe", script)
        self.assertIn("postgres.lib", script)
        self.assertNotIn("Makefile.win", script)
        self.assertIn("--pkglibdir", script)
        self.assertIn("--sharedir", script)
        self.assertIn("$pythonExe = (Get-Command 'python.exe'", script)
        self.assertIn("$dumpbinExe = Join-Path (Split-Path $clExe -Parent) 'dumpbin.exe'", script)
        self.assertIn("& $pythonExe (Join-Path $repo 'tools/check_pe_dependencies.py')", script)
        self.assertNotIn("Get-Command cl.exe).Source", script)
        self.assertIn("Move-Item $pgRoot $moved", script)
        self.assertIn("probe.sql", script)
        self.assertIn("check_pe_dependencies.py", script)
        self.assertIn("check_extension_redistribution.py", script)
        self.assertIn(source_hash, linux_builder)
        self.assertIn("release_eligible = $false", script)

    def test_upstream_makefile_fixture_keeps_nested_sources_and_root_sql_layout(self):
        script = (ROOT / "scripts/hypopg/windows-feasibility.ps1").read_text()
        makefile = """EXTENSION = hypopg
MODULE_big = hypopg
OBJS = hypopg.o \\
       hypopg_index.o \\
       import/hypopg_import.o \\
       import/hypopg_import_index.o
DATA = $(wildcard *--*.sql)
"""
        logical = re.sub(r"\\\r?\n[ \t]*", " ", makefile)
        match = re.search(r"(?m)^OBJS\s*=\s*([^\r\n]+)", logical)
        self.assertIsNotNone(match)
        objects = match.group(1).split()
        self.assertEqual(objects, [
            "hypopg.o", "hypopg_index.o", "import/hypopg_import.o",
            "import/hypopg_import_index.o",
        ])
        self.assertIn("hypopg--*.sql", script)
        self.assertNotIn("sql/hypopg--*.sql", script)
        self.assertIn("$moduleDir = Join-Path $pgRoot $moduleRelative", script)
        self.assertIn("Join-Path (Join-Path $extensionRoot $moduleRelative) 'hypopg.dll'", script)


if __name__ == "__main__":
    unittest.main()
