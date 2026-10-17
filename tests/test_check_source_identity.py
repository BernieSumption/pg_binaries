import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_source_identity", ROOT / "tools" / "check_source_identity.py")
import sys
sys.path.insert(0, str(ROOT / "tools"))
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class CheckSourceIdentityTests(unittest.TestCase):
    def test_accepts_pinned_formats_and_rejects_tampering(self):
        for platform in ("linux", "macos", "windows"):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                core_path = Path(temp) / "manifest.json"
                vector_path = Path(temp) / "metadata.json"
                archive_format = "tar.gz" if platform == "windows" else "tar.bz2"
                core = {"source_archive": checker.source_archive("postgresql", "18.6", archive_format)}
                if platform == "windows":
                    core["source_sha256"] = core["source_archive"]["sha256"]
                vector = {"source_archive": checker.source_archive("pgvector", "0.8.7", "tar.gz")}
                core_path.write_text(json.dumps(core))
                vector_path.write_text(json.dumps(vector))
                checker.check(ROOT, platform, "18.6", core_path, vector_path)
                vector["source_archive"]["sha256"] = "0" * 64
                vector_path.write_text(json.dumps(vector))
                with self.assertRaisesRegex(ValueError, "pgvector"):
                    checker.check(ROOT, platform, "18.6", core_path, vector_path)
                vector_path.write_text("{}")
                with self.assertRaisesRegex(ValueError, "pgvector"):
                    checker.check(ROOT, platform, "18.6", core_path, vector_path)
                vector_path.write_text(json.dumps({"source_archive": checker.source_archive("pgvector", "0.8.7", "tar.gz")}))
                core["source_archive"]["url"] = "https://example.test/wrong.tar.gz"
                core_path.write_text(json.dumps(core))
                with self.assertRaisesRegex(ValueError, "PostgreSQL"):
                    checker.check(ROOT, platform, "18.6", core_path, vector_path)
                if platform == "windows":
                    core["source_archive"] = checker.source_archive("postgresql", "18.6", "tar.gz")
                    core["source_sha256"] = "0" * 64
                    core_path.write_text(json.dumps(core))
                    with self.assertRaisesRegex(ValueError, "legacy"):
                        checker.check(ROOT, platform, "18.6", core_path, vector_path)


if __name__ == "__main__":
    unittest.main()
