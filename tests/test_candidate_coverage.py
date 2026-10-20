import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "candidate_coverage", Path(__file__).resolve().parents[1] / "tools" / "candidate_coverage.py")
candidate_coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate_coverage)


class CandidateCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.support = {
            "schema_version": 1,
            "postgresql": {"minimum_major": 15},
            "version_selection_as_of": "2026-10-17",
            "os_support": {name: {"minimum_version": version} for name, version in
                           (("macos", "11.0"), ("windows", "10.0"), ("linux", "5.15"))},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"],
                                        "windows": ["x86_64"],
                                        "linux": ["x86_64", "arm64"]},
            "extensions": {"Example": {"sql_names": ["example"], "versions": {
                "1.0": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 17}}}},
        }
        self.snapshot = {"as_of": "2026-10-17", "source": "https://example.test/releases",
                         "support_status": {"as_of": "2026-10-17", "source": "https://example.test/support",
                                            "supported_majors": [15]},
                         "releases": [{"version": "15.9", "release_date": "2025-09-25"}]}
        (self.root / "support").mkdir()
        (self.root / "policies").mkdir()
        (self.root / "policies/extensions.md").write_text("## Example — include\n", encoding="utf-8")
        (self.root / "support/verification-profiles.json").write_text(json.dumps({
            "schema_version": 1, "profiles": {"publication": {
                "scope": "publication", "platforms": sorted(["macos-x86_64", "macos-arm64",
                    "windows-x86_64", "linux-x86_64", "linux-arm64"]),
                "case_ids": ["smoke"], "sources": ["tests/profile.py"]}}}), encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests/profile.py").write_text("profile source", encoding="utf-8")
        (self.root / "support.json").write_text(json.dumps(self.support), encoding="utf-8")
        (self.root / "support/postgresql-releases.json").write_text(json.dumps(self.snapshot), encoding="utf-8")
        profile = candidate_coverage._coverage.verification_profile(self.root, "publication")
        self.candidate = {"schema_version": 1, "candidate_status": "structural-draft",
                          "os_support": self.support["os_support"], "postgresql": {},
                          "extensions": {}, "verification_evidence": {}}
        self.platforms = [f"{os}-{arch}" for os, arches in self.support["platform_architectures"].items()
                          for arch in arches]
        for platform in self.platforms:
            os_name, architecture = platform.split("-", 1)
            core_sha = hashlib.sha256(platform.encode()).hexdigest()
            ext_sha = hashlib.sha256((platform + "extension").encode()).hexdigest()
            core_url = f"https://example.test/postgresql-15.9-{platform}.tar.gz"
            ext_url = f"https://example.test/example-1.0-postgresql-15.9-{platform}.tar.gz"
            self.candidate["postgresql"].setdefault("15.9", {
                "included_extensions": [], "downloads": {}})["downloads"][platform] = {
                    "url": core_url, "sha256": core_sha}
            self.candidate["extensions"].setdefault("example", {}).setdefault("1.0", {
                "requires": [], "downloads": {}})["downloads"][platform] = [{
                    "postgresql_support": {"from": "15.9", "to": "15.9"},
                    "url": ext_url, "sha256": ext_sha}]
            common = {"schema_version": 2, "profile_id": profile["profile_id"],
                      "profile_revision": profile["profile_revision"], "scope": "publication",
                      "test_cases": ["smoke"], "test_revision": "a" * 40,
                      "outcome": "passed", "platform": platform,
                      "environment": {"os": os_name, "architecture": architecture,
                          "os_version": {"macos": "12", "windows": "11", "linux": "6"}[os_name],
                          "endpoint": "current", "clean_system": True,
                          "image_id": "runner@sha256:image", "dependency_check_profile": "runtime-v1",
                          "dependency_checks_passed": True},
                      "case_results": {"smoke": "passed"}}
            core_record = dict(common, component="postgresql", version="15.9",
                               postgresql_version="15.9", sha256=core_sha)
            ext_record = dict(common, component="example", version="1.0",
                              postgresql_version="15.9", sha256=ext_sha,
                              assembled_core={"archive": f"postgresql-15.9-{platform}.tar.gz",
                                              "version": "15.9", "sha256": core_sha},
                              prerequisite_archives=[])
            self.candidate["verification_evidence"][core_url] = [core_record]
            self.candidate["verification_evidence"][ext_url] = [ext_record]
        self.candidate_path = self.root / "candidate.json"
        self.write_candidate()

    def tearDown(self):
        self.temporary.cleanup()

    def write_candidate(self):
        self.candidate_path.write_text(json.dumps(self.candidate), encoding="utf-8")

    def report(self):
        self.write_candidate()
        return candidate_coverage.report_candidate(self.root, self.candidate_path)

    def test_new_postgresql_and_extension_targets_are_reported_missing(self):
        self.support["extensions"]["Example"]["versions"]["2.0"] = {
            "postgresql_minimum_major": 15, "postgresql_maximum_major": 17}
        self.support["extensions"]["Example"]["major_first_releases"] = {
            "1": {"date": "2025-01-01", "source": "https://example.test/v1"},
            "2": {"date": "2026-01-01", "source": "https://example.test/v2"}}
        self.snapshot["support_status"]["supported_majors"].append(16)
        self.snapshot["releases"].append({"version": "16.6", "release_date": "2026-01-01"})
        self.write_candidate()
        (self.root / "support.json").write_text(json.dumps(self.support), encoding="utf-8")
        (self.root / "support/postgresql-releases.json").write_text(json.dumps(self.snapshot), encoding="utf-8")
        policy = self.root / "policies/extensions.md"
        policy.write_text("## Example — include\n", encoding="utf-8")
        report = candidate_coverage.report_candidate(self.root, self.candidate_path)
        self.assertEqual(len(report["core_without_download"]), 5)
        self.assertEqual(len(report["extension_without_download"]), 15)
        self.assertEqual(report["publication_eligibility"], "not-established-by-coverage")

    def test_inline_evidence_must_pass_and_bind_to_candidate_core(self):
        report = self.report()
        self.assertEqual(report["missing_extension"], [])
        ext_url = next(url for url in self.candidate["verification_evidence"] if "example-1.0" in url)
        good = json.loads(json.dumps(self.candidate["verification_evidence"][ext_url]))
        del self.candidate["verification_evidence"][ext_url]
        report = self.report()
        self.assertEqual(len(report["extension_awaiting_verification"]), 1)
        self.candidate["verification_evidence"][ext_url] = good
        self.candidate["verification_evidence"][ext_url][0]["assembled_core"]["sha256"] = "0" * 64
        report = self.report()
        self.assertEqual(len(report["extension_awaiting_verification"]), 1)


if __name__ == "__main__":
    unittest.main()
