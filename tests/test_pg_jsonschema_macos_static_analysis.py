import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.pg_jsonschema.check_macos_static_analysis import validate


ROOT = Path(__file__).resolve().parents[1]


class StaticAnalysisCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def check_report(self, target_name, module, mutate=None):
        target_path = ROOT / "tools" / "pg_jsonschema_macos_targets" / target_name
        target = json.loads(target_path.read_text(encoding="utf-8"))
        core = self.root / target["core_archive"]["basename"]
        extension_name = (f"pg_jsonschema-{target['pg_jsonschema_version']}-postgresql-"
                          f"{target['postgresql_version']}-{target['platform']}.tar.gz")
        extension = self.root / extension_name
        core.write_bytes(b"core archive bytes")
        extension.write_bytes(b"extension archive bytes")
        report = {
            "passed": True,
            "architecture": target["architecture"],
            "archives": [
                {"basename": core.name, "sha256": hashlib.sha256(core.read_bytes()).hexdigest()},
                {"basename": extension.name, "sha256": hashlib.sha256(extension.read_bytes()).hexdigest()},
            ],
            "inspected_files": [{"file": f"lib/{module}"}],
        }
        if mutate:
            mutate(report)
        report_path = self.root / "static-analysis.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return target_path, core, extension, report_path

    def test_accepts_postgresql_15_so_module(self):
        args = self.check_report("15.19-x86_64.json", "pg_jsonschema.so")
        validate(*args)

    def test_accepts_later_postgresql_dylib_module(self):
        args = self.check_report("18.6-arm64.json", "pg_jsonschema.dylib")
        validate(*args)

    def test_rejects_wrong_archive_digest(self):
        args = self.check_report(
            "15.19-x86_64.json", "pg_jsonschema.so",
            lambda report: report["archives"][0].update(sha256="0" * 64),
        )
        with self.assertRaisesRegex(ValueError, "final archives"):
            validate(*args)

    def test_rejects_wrong_architecture(self):
        args = self.check_report(
            "18.6-arm64.json", "pg_jsonschema.dylib",
            lambda report: report.update(architecture="x86_64"),
        )
        with self.assertRaisesRegex(ValueError, "final archives"):
            validate(*args)

    def test_rejects_wrong_module_filename(self):
        args = self.check_report("15.19-x86_64.json", "pg_jsonschema.dylib")
        with self.assertRaisesRegex(ValueError, "final archives"):
            validate(*args)


if __name__ == "__main__":
    unittest.main()
