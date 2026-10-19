import json
from pathlib import Path
import tempfile
import unittest

from tools.collection_macos_target import load_target


ROOT = Path(__file__).resolve().parents[1]


class CollectionMacosTargetTests(unittest.TestCase):
    def test_all_declared_targets_are_resolver_inputs(self):
        for path in sorted((ROOT / "tools/collection_macos_targets").glob("*.json")):
            with self.subTest(target=path.name):
                target = load_target(path)
                self.assertEqual(target.core_sha256, None)
                self.assertEqual(target.profile_id, f"collection-publication-macos-{target.architecture}-{target.postgresql_version}")
                self.assertEqual(target.extension_basename("1.1.1").split("-")[1], "1.1.1")

    def test_resolved_identity_requires_all_core_provenance(self):
        source = ROOT / "tools/collection_macos_targets/18.6-arm64.json"
        value = json.loads(source.read_text())
        value["core_archive"].update({"sha256": "a" * 64, "run_id": "123", "build_id": "github-123-1", "source_revision": "b" * 40})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target.json"
            path.write_text(json.dumps(value))
            self.assertEqual(load_target(path, require_resolved=True).core_run_id, "123")
            value["core_archive"].pop("sha256")
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "base or resolved"):
                load_target(path)

    def test_target_rejects_source_hash_or_profile_drift(self):
        value = json.loads((ROOT / "tools/collection_macos_targets/18.6-arm64.json").read_text())
        value["sources"]["2.1.3"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target.json"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "source hashes"):
                load_target(path)

    def test_build_recipe_requires_resolved_identity_and_packages_both_releases(self):
        recipe = (ROOT / "scripts/collection/build-macos.sh").read_text()
        self.assertIn("load_target(sys.argv[1], require_resolved=True)", recipe)
        self.assertIn('build_one 1.1.1 "$source_1_1_1"', recipe)
        self.assertIn('build_one 2.1.3 "$source_2_1_3"', recipe)
        for version in ("1.1.1", "2.1.3"):
            self.assertIn(f'"{version}":"', recipe)
        self.assertIn('"core_archive":{"basename":core_name,"sha256":core_sha256}', recipe)
        self.assertIn('shasum -a 256 "$archive"', recipe)
        self.assertIn("check_extension_redistribution.py", recipe)

    def test_verifier_checks_relocation_sql_and_final_archive_report_identity(self):
        verifier = (ROOT / "scripts/collection/verify-macos.sh").read_text()
        self.assertIn("usage: verify-macos.sh CORE_ARCHIVE_DIRECTORY BOTH_COLLECTION_ARCHIVES RESOLVED_TARGET_JSON OUTPUT_DIRECTORY", verifier)
        self.assertIn('for version in 1.1.1 2.1.3; do', verifier)
        self.assertIn('mv "$pgroot" "$work/moved/$version/postgresql"', verifier)
        self.assertIn('cp -a "$extroot/." "$pgroot/"', verifier)
        self.assertIn('scripts/macos/static_analysis.py', verifier)
        self.assertIn('scripts/collection/probe.sql', verifier)
        self.assertIn("integer-key collection sparse lookup/count failed", verifier)
        self.assertIn('actual != expected', verifier)
        self.assertIn('report.get("passed") is not True', verifier)


if __name__ == "__main__":
    unittest.main()
