import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "candidate_inventory", Path(__file__).resolve().parents[1] / "tools" / "candidate_inventory.py")
candidate_inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate_inventory)


class CandidateInventoryTests(unittest.TestCase):
    def setUp(self):
        self.support = {
            "schema_version": 1,
            "postgresql": {"minimum_major": 15, "stable_release_cutoff": "2025-09-25"},
            "os_support": {name: {"minimum_version": "1"} for name in ("macos", "windows", "linux")},
            "architectures": ["x86_64", "arm64"],
            "extensions": {"Example": {"sql_names": ["example"], "versions": {"1.0": {
                "postgresql_minimum_major": 15}}}},
        }
        self.snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                         "releases": [{"version": "15.9", "release_date": "2025-09-25"},
                                      {"version": "15.10", "release_date": "2025-10-01"}]}
        self.old = {"schema_version": 1, "os_support": {"linux": {"minimum_version": "1"}},
                    "postgresql": {"15.8": {"included_extensions": [], "downloads": {
                        "linux-x86_64": {"url": "https://github.com/example/releases/download/old/pg.tgz",
                                         "sha256": "a" * 64}}}}, "extensions": {}}

    def proposal(self, *, tag="catalog-20261016-1", filename="pg-linux-x86_64-15.9.tar.gz", sha="b" * 64,
                 version="15.9", platform="linux-x86_64"):
        url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{tag}/{filename}"
        return {"component": "postgresql", "version": version, "platform": platform,
                "tag": tag, "filename": filename, "sha256": sha,
                "verification": [self.evidence(url, sha, endpoint, version, platform)
                                 for endpoint in ("minimum", "current")]}

    @staticmethod
    def evidence(url, sha, endpoint, version="15.9", platform="linux-x86_64"):
        os_name, architecture = platform.split("-")
        return {"schema_version": 1, "outcome": "passed", "url": url, "sha256": sha,
                "component": "postgresql", "version": version, "platform": platform,
                "postgresql_version": version, "test_revision": "abc", "test_cases": ["smoke"],
                "environment": {"endpoint": endpoint, "os": os_name, "architecture": architecture,
                                "os_version": "1" if endpoint == "minimum" else "2",
                                "clean_system": True}}

    def test_retains_unchanged_download_and_marks_candidate(self):
        result = candidate_inventory.merge_candidate(self.old, [self.proposal()], self.support, self.snapshot)
        self.assertEqual(result["candidate_status"], "structural-draft")
        self.assertEqual(result["postgresql"]["15.8"], self.old["postgresql"]["15.8"])
        self.assertEqual(result["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["sha256"], "b" * 64)

    def test_correction_uses_new_url(self):
        base = {"postgresql": {"15.9": {"downloads": {"linux-x86_64": {
            "url": "https://github.com/example/releases/download/old/pg.tgz", "sha256": "a" * 64}}}},
                "extensions": {}}
        result = candidate_inventory.merge_candidate(base, [self.proposal()], self.support, self.snapshot)
        self.assertNotEqual(result["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["url"],
                            base["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["url"])
        self.assertEqual(base["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["sha256"], "a" * 64)

    def test_rejects_url_reused_across_proposals_even_with_same_sha(self):
        first = self.proposal()
        second = self.proposal(version="15.10")
        second["verification"] = [self.evidence(
            "https://github.com/BernieSumption/pg_binaries/releases/download/catalog-20261016-1/pg-linux-x86_64-15.9.tar.gz",
            "b" * 64, endpoint, "15.10") for endpoint in ("minimum", "current")]
        with self.assertRaisesRegex(candidate_inventory.CandidateError, "URL is reused"):
            candidate_inventory.merge_candidate(self.old, [first, second], self.support, self.snapshot)

    def test_rejects_url_already_in_base_even_when_checksum_matches(self):
        proposal = self.proposal()
        proposal["tag"] = "catalog-20261016-1"
        proposal["filename"] = "pg-linux-x86_64-15.9.tar.gz"
        proposal["verification"] = [self.evidence(
            "https://github.com/BernieSumption/pg_binaries/releases/download/catalog-20261016-1/pg-linux-x86_64-15.9.tar.gz",
            "b" * 64, endpoint) for endpoint in ("minimum", "current")]
        base = {"postgresql": {"15.9": {"downloads": {"linux-x86_64": {
            "url": "https://github.com/BernieSumption/pg_binaries/releases/download/catalog-20261016-1/pg-linux-x86_64-15.9.tar.gz",
            "sha256": "b" * 64}}}}, "extensions": {}}
        with self.assertRaisesRegex(candidate_inventory.CandidateError, "URL must be new"):
            candidate_inventory.merge_candidate(base, [proposal], self.support, self.snapshot)

    def test_extension_evidence_uses_range_endpoints_not_intermediate_releases(self):
        url = "https://github.com/BernieSumption/pg_binaries/releases/download/catalog-20261016-2/example-linux-x86_64-1.0.tar.gz"
        checksum = "d" * 64
        records = []
        for pg in ("15.0", "15.10"):
            for endpoint in ("minimum", "current"):
                evidence = self.evidence(url, checksum, endpoint, pg)
                evidence.update({"component": "example", "version": "1.0", "postgresql_version": pg})
                records.append(evidence)
        proposal = {"component": "example", "version": "1.0", "platform": "linux-x86_64",
                    "tag": "catalog-20261016-2", "filename": "example-linux-x86_64-1.0.tar.gz",
                    "sha256": checksum, "postgresql_support": {"from": "15.0", "to": "15.10"},
                    "verification": records}
        result = candidate_inventory.merge_candidate(self.old, [proposal], self.support, self.snapshot)
        self.assertEqual(result["candidate_status"], "structural-draft")

        restricted_support = dict(self.support, extensions={"Example": {
            "sql_names": ["example"], "versions": {"1.0": {
                "postgresql_minimum_major": 15, "postgresql_maximum_major": 15}}}})
        outside = dict(proposal, postgresql_support={"from": "15.0", "to": "16.0"})
        with self.assertRaisesRegex(candidate_inventory.CandidateError, "exceeds declared"):
            candidate_inventory.merge_candidate(self.old, [outside], restricted_support, self.snapshot)

    def test_rejects_missing_evidence(self):
        proposal = self.proposal()
        proposal["verification"] = []
        with self.assertRaisesRegex(candidate_inventory.CandidateError, "missing passed"):
            candidate_inventory.merge_candidate(self.old, [proposal], self.support, self.snapshot)


if __name__ == "__main__":
    unittest.main()
