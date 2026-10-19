import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import coverage
import pgvector_candidate_records as candidate


class PgvectorCandidateRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.run_id = "123"
        self.head_sha = "a" * 40
        self.pg = "17.11"
        self.vector = "0.8.7"
        self.platform = "linux-x86_64"
        self.core_name = f"postgresql-{self.pg}-{self.platform}.tar.gz"
        self.extension_name = f"pgvector-{self.vector}-postgresql-{self.pg}-{self.platform}.tar.gz"
        self.files = {}
        self.hashes = {}
        for name, data in ((self.core_name, b"core archive bytes"),
                           (self.extension_name, b"vector archive bytes")):
            self._add(name, data)
            self._add(name + ".sha256", f"{hashlib.sha256(data).hexdigest()}  {name}\n".encode())
        profile_id = "linux-publication-current-x86_64"
        profile = coverage.verification_profile(ROOT, profile_id)
        cases = profile["case_ids"]
        core_sha = self.hashes[self.core_name]
        extension_sha = self.hashes[self.extension_name]
        common = {
            "schema_version": 2, "scope": "publication", "outcome": "passed",
            "profile_id": profile_id, "profile_revision": profile["profile_revision"],
            "test_cases": cases, "case_results": {case: "passed" for case in cases},
            "test_revision": self.head_sha,
            "environment": {"image_id": "sha256:" + "b" * 64,
                             "dependency_check_profile": "linux-runtime-v1",
                             "dependency_checks_passed": True, "clean_system": True,
                             "os": "linux", "architecture": "x86_64", "os_version": "6.17.0",
                             "endpoint": "current"},
            "platform": self.platform, "postgresql_version": self.pg,
            "ci": {"provider": "github-actions", "run_id": self.run_id,
                   "run_url": f"https://github.com/example/project/actions/runs/{self.run_id}",
                   "source_revision": self.head_sha, "build_revision": self.head_sha,
                   "test_revision": self.head_sha},
        }
        self.core_record = dict(common, component="postgresql", version=self.pg, sha256=core_sha)
        self.extension_record = dict(common, component="vector", version=self.vector, sha256=extension_sha,
                                     assembled_core={"archive": self.core_name, "version": self.pg,
                                                    "sha256": core_sha})
        self.core_record_name = f"postgresql-{self.pg}-{self.platform}-current-{self.run_id}.json"
        self.extension_record_name = (
            f"pgvector-{self.vector}-postgresql-{self.pg}-{self.platform}-current-{self.run_id}.json")
        self._add(self.core_record_name, json.dumps(self.core_record).encode())
        self._add(self.extension_record_name, json.dumps(self.extension_record).encode())
        self.manifest = {
            "schema_version": 1,
            "target": {"pgvector_version": self.vector, "postgresql_version": self.pg,
                       "platform": self.platform},
            "source": {"run_id": self.run_id, "head_sha": self.head_sha,
                       "repository": "example/project"},
            "files": self.files, "sha256": self.hashes,
        }

    def tearDown(self):
        self.temp.cleanup()

    def _add(self, name, data):
        path = self.directory / name
        path.write_bytes(data)
        self.files[name] = str(path)
        self.hashes[name] = hashlib.sha256(data).hexdigest()

    def _rewrite_record(self, kind, **changes):
        name = self.core_record_name if kind == "core" else self.extension_record_name
        record = dict(self.core_record if kind == "core" else self.extension_record)
        record.update(changes)
        self._add(name, json.dumps(record).encode())

    def test_accepts_matching_bundle_records(self):
        result = candidate.validate_candidate_records(self.manifest, ROOT)
        self.assertEqual(set(result), {"core", "extension"})

    def test_rejects_archive_sha_mismatch(self):
        self._rewrite_record("extension", sha256="0" * 64)
        with self.assertRaisesRegex(candidate.CandidateRecordError, "archive SHA-256"):
            candidate.validate_candidate_records(self.manifest, ROOT)

    def test_rejects_assembled_core_sha_mismatch(self):
        self._rewrite_record("extension", assembled_core={"archive": self.core_name,
                                                            "version": self.pg,
                                                            "sha256": "0" * 64})
        with self.assertRaisesRegex(candidate.CandidateRecordError, "assembled_core"):
            candidate.validate_candidate_records(self.manifest, ROOT)

    def test_rejects_stale_profile(self):
        self._rewrite_record("core", profile_revision="0" * 64)
        with self.assertRaisesRegex(candidate.CandidateRecordError, "current suite"):
            candidate.validate_candidate_records(self.manifest, ROOT)

    def test_rejects_wrong_run_or_source(self):
        for field, value in (("run_id", "124"), ("source_revision", "c" * 40)):
            ci = dict(self.core_record["ci"], **{field: value})
            self._rewrite_record("core", ci=ci)
            with self.subTest(field=field), self.assertRaisesRegex(
                    candidate.CandidateRecordError, "identity"):
                candidate.validate_candidate_records(self.manifest, ROOT)
            self._rewrite_record("core", ci=self.core_record["ci"])


if __name__ == "__main__":
    unittest.main()
