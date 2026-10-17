import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import create_linux_publication_receipt as builder
import emit_linux_publication_records as emitter


REPO = Path(__file__).resolve().parents[1]


class LinuxPublicationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "root"
        (self.root / "support").mkdir(parents=True)
        shutil.copy(REPO / "support.json", self.root / "support.json")
        (self.root / "profile-source.txt").write_text("profile fixture\n")
        self.profile_id = "publication-fixture"
        (self.root / "support" / "verification-profiles.json").write_text(json.dumps({
            "schema_version": 1,
            "profiles": {self.profile_id: {
                "scope": "publication", "platforms": ["linux-arm64", "linux-x86_64"],
                "case_ids": ["archive-suite", "diagnostics"],
                "sources": ["profile-source.txt"],
            }},
        }))
        self.archives = self.base / "archives"
        self.archives.mkdir()
        self.names = ["postgresql-18.6-linux-x86_64.tar.gz",
                      "pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz"]
        for index, name in enumerate(self.names):
            content = f"archive {index}".encode()
            digest = hashlib.sha256(content).hexdigest()
            (self.archives / name).write_bytes(content)
            (self.archives / f"{name}.sha256").write_text(f"{digest}  {name}\n")
        self.steps = self.base / "steps.json"
        self.steps.write_text(json.dumps({"archive-suite": "success", "diagnostics": "success"}))
        self.receipt_path = self.base / "receipt.json"
        self.env = {
            "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "987654",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_SERVER_URL": "https://github.com",
        }

    def tearDown(self):
        self.temp.cleanup()

    def create(self, **overrides):
        values = dict(
            root=self.root, archives_dir=self.archives, receipt_path=self.receipt_path,
            profile_id=self.profile_id, postgresql_version="18.6", architecture="x86_64",
            endpoint="current", kernel_release="6.8.0-40-generic",
            distribution="Ubuntu", distribution_version="24.04", image_id="sha256:" + "b" * 64,
            dependency_check_profile=emitter.DEPENDENCY_PROFILE,
            dependency_check_result="success", clean_system=True,
            step_results_path=self.steps, environ=self.env,
        )
        values.update(overrides)
        return builder.create(**values)

    def test_creates_receipt_with_registered_revision_case_mapping_and_archive_hashes(self):
        self.create()
        receipt = json.loads(self.receipt_path.read_text())
        profile = coverage.verification_profile(self.root, self.profile_id)
        self.assertEqual(receipt["profile_revision"], profile["profile_revision"])
        self.assertEqual(receipt["case_results"], {"archive-suite": "passed", "diagnostics": "passed"})
        self.assertEqual(receipt["ci"]["run_url"], "https://github.com/owner/repo/actions/runs/987654")
        self.assertEqual(receipt["archives"], {
            name: hashlib.sha256((self.archives / name).read_bytes()).hexdigest()
            for name in self.names
        })
        paths = emitter.emit(self.root, self.archives, self.receipt_path, self.base / "records")
        self.assertEqual(len(paths), 2)

    def test_maps_failed_and_skipped_step_outcomes(self):
        self.steps.write_text(json.dumps({"archive-suite": "failure", "diagnostics": "skipped"}))
        self.create(clean_system=False, dependency_check_result="failure")
        receipt = json.loads(self.receipt_path.read_text())
        self.assertEqual(receipt["case_results"], {"archive-suite": "failed", "diagnostics": "skipped"})

    def test_arm64_receipt_uses_arm64_archives_and_profile_platform(self):
        for name in ("postgresql-18.6-linux-arm64.tar.gz",
                     "pgvector-0.8.7-postgresql-18.6-linux-arm64.tar.gz"):
            (self.archives / name).write_bytes(name.encode())
            digest = hashlib.sha256(name.encode()).hexdigest()
            (self.archives / f"{name}.sha256").write_text(f"{digest}  {name}\n")
        self.create(architecture="arm64")
        receipt = json.loads(self.receipt_path.read_text())
        self.assertEqual(receipt["architecture"], "arm64")
        paths = emitter.emit(self.root, self.archives, self.receipt_path, self.base / "arm-records")
        self.assertEqual(len(paths), 2)
        self.assertTrue(all("linux-arm64" in path.name for path in paths))

    def test_rejects_case_set_mismatch_and_never_writes_receipt(self):
        self.steps.write_text(json.dumps({"archive-suite": "success", "extra": "success"}))
        with self.assertRaises(coverage.CoverageError):
            self.create()
        self.assertFalse(self.receipt_path.exists())

    def test_rejects_missing_github_provenance_and_bad_archive_sidecar(self):
        with self.assertRaises(coverage.CoverageError):
            self.create(environ={})
        self.assertFalse(self.receipt_path.exists())
        (self.archives / f"{self.names[0]}.sha256").write_text("0" * 64 + "  wrong.tar.gz\n")
        with self.assertRaises(coverage.CoverageError):
            self.create()
        self.assertFalse(self.receipt_path.exists())


if __name__ == "__main__":
    unittest.main()
