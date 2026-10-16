import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "candidate_inventory", Path(__file__).resolve().parents[1] / "tools" / "candidate_inventory.py")
candidate_inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate_inventory)


class CandidateInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source = self.root / "tests" / "candidate_profile.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("candidate test suite", encoding="utf-8")
        registry = {"schema_version": 1, "profiles": {"candidate-test": {
            "scope": "publication", "platforms": ["linux-x86_64"],
            "case_ids": ["candidate-core", "candidate-relocation"],
            "sources": ["tests/candidate_profile.py"]}}}
        profile_path = self.root / "support" / "verification-profiles.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(json.dumps(registry), encoding="utf-8")
        self.support = {
            "schema_version": 1,
            "postgresql": {"minimum_major": 15, "stable_release_cutoff": "2025-09-25"},
            "os_support": {name: {"minimum_version": "1"} for name in ("macos", "windows", "linux")},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"], "linux": ["x86_64", "arm64"]},
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

    def tearDown(self):
        self.temporary.cleanup()

    def proposal(self, *, tag="catalog-20261016-1", filename="pg-linux-x86_64-15.9.tar.gz", sha="b" * 64,
                 version="15.9", platform="linux-x86_64"):
        url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{tag}/{filename}"
        return {"component": "postgresql", "version": version, "platform": platform,
                "tag": tag, "filename": filename, "sha256": sha, "included_extensions": ["example"],
                "verification": [self.evidence(url, sha, endpoint, version, platform)
                                 for endpoint in ("minimum", "current")]}

    def evidence(self, url, sha, endpoint, version="15.9", platform="linux-x86_64"):
        os_name, architecture = platform.split("-")
        profile_id = "candidate-test"
        profile = candidate_inventory._coverage.verification_profile(
            self.root, profile_id)
        return {"schema_version": 2, "scope": profile["scope"], "profile_id": profile_id,
                "profile_revision": profile["profile_revision"], "outcome": "passed", "url": url, "sha256": sha,
                "component": "postgresql", "version": version, "platform": platform,
                "postgresql_version": version, "test_revision": "a" * 40, "test_cases": profile["case_ids"],
                "environment": {"endpoint": endpoint, "os": os_name, "architecture": architecture,
                                "os_version": "1" if endpoint == "minimum" else "2",
                                "clean_system": True, "image_id": "ubuntu@sha256:image",
                                "dependency_check_profile": "linux-runtime-v1",
                                "dependency_checks_passed": True}}

    def test_retains_unchanged_download_and_marks_candidate(self):
        result = candidate_inventory.merge_candidate(self.old, [self.proposal()], self.support, self.snapshot,
                                                     root=self.root)
        self.assertEqual(result["candidate_status"], "structural-draft")
        self.assertEqual(result["postgresql"]["15.8"], self.old["postgresql"]["15.8"])
        self.assertEqual(result["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["sha256"], "b" * 64)
        self.assertEqual(self.old["postgresql"]["15.8"]["downloads"]["linux-x86_64"]["sha256"], "a" * 64)

    def test_correction_uses_new_url(self):
        base = {"postgresql": {"15.9": {"downloads": {"linux-x86_64": {
            "url": "https://github.com/example/releases/download/old/pg.tgz", "sha256": "a" * 64}}}},
                "extensions": {}}
        result = candidate_inventory.merge_candidate(base, [self.proposal()], self.support, self.snapshot,
                                                     root=self.root)
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
            candidate_inventory.merge_candidate(self.old, [first, second], self.support, self.snapshot,
                                                 root=self.root)

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
            candidate_inventory.merge_candidate(base, [proposal], self.support, self.snapshot,
                                                 root=self.root)

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
        result = candidate_inventory.merge_candidate(self.old, [proposal], self.support, self.snapshot,
                                                     root=self.root)
        self.assertEqual(result["candidate_status"], "structural-draft")

        restricted_support = dict(self.support, extensions={"Example": {
            "sql_names": ["example"], "versions": {"1.0": {
                "postgresql_minimum_major": 15, "postgresql_maximum_major": 15}}}})
        outside = dict(proposal, postgresql_support={"from": "15.0", "to": "16.0"})
        with self.assertRaisesRegex(candidate_inventory.CandidateError, "exceeds declared"):
            candidate_inventory.merge_candidate(self.old, [outside], restricted_support, self.snapshot,
                                                 root=self.root)

    def test_rejects_missing_evidence(self):
        proposal = self.proposal()
        proposal["verification"] = []
        with self.assertRaisesRegex(candidate_inventory.CandidateError, "missing passed"):
            candidate_inventory.merge_candidate(self.old, [proposal], self.support, self.snapshot,
                                                 root=self.root)

    def test_carries_included_extensions_and_rejects_inconsistent_platform_claims(self):
        proposal = self.proposal()
        result = candidate_inventory.merge_candidate(self.old, [proposal], self.support, self.snapshot,
                                                     root=self.root)
        self.assertEqual(result["postgresql"]["15.9"]["included_extensions"], ["example"])
        second = self.proposal(tag="catalog-20261016-3", filename="pg-linux-arm64-15.9.tar.gz",
                               platform="linux-arm64")
        second["included_extensions"] = ["different"]
        with self.assertRaisesRegex(candidate_inventory.CandidateError, "inconsistent included_extensions"):
            candidate_inventory.merge_candidate(self.old, [self.proposal(), second], self.support,
                                                 self.snapshot, root=self.root)

    def test_real_pilot_only_registry_rejects_candidate_evidence(self):
        proposal = self.proposal()
        real_root = Path(__file__).resolve().parents[1]
        profile_id = "linux-pilot-x86_64"
        profile = candidate_inventory._coverage.verification_profile(real_root, profile_id)
        for record in proposal["verification"]:
            record.update({"scope": profile["scope"], "profile_id": profile_id,
                           "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"]})
        with self.assertRaisesRegex(candidate_inventory.CandidateError, "missing passed"):
            candidate_inventory.merge_candidate(self.old, [proposal], self.support, self.snapshot,
                                                 root=real_root)
        for record in proposal["verification"]:
            record["scope"] = "publication"
        with self.assertRaisesRegex(candidate_inventory.CandidateError, "missing passed"):
            candidate_inventory.merge_candidate(self.old, [proposal], self.support, self.snapshot,
                                                 root=real_root)

    def write_cli_inputs(self, proposals):
        inputs = {"base.json": self.old, "proposed.json": proposals,
                  "support.json": self.support, "snapshot.json": self.snapshot}
        paths = {}
        for name, value in inputs.items():
            path = self.root / name
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = path
        return paths

    def run_candidate_cli(self, paths, *extra):
        script = Path(__file__).resolve().parents[1] / "tools" / "candidate_inventory.py"
        return subprocess.run(
            [sys.executable, str(script), "--base-inventory", str(paths["base.json"]),
             "--proposed-entries", str(paths["proposed.json"]), "--support", str(paths["support.json"]),
             "--release-snapshot", str(paths["snapshot.json"]), "--root", str(self.root), *extra],
            capture_output=True, text=True, check=False)

    def test_cli_writes_structural_draft_to_stdout_or_file(self):
        paths = self.write_cli_inputs([self.proposal()])
        stdout_result = self.run_candidate_cli(paths)
        self.assertEqual(stdout_result.returncode, 0, stdout_result.stderr)
        candidate = json.loads(stdout_result.stdout)
        self.assertEqual(candidate["candidate_status"], "structural-draft")

        output = self.root / "candidate.json"
        file_result = self.run_candidate_cli(paths, "--output", str(output))
        self.assertEqual(file_result.returncode, 0, file_result.stderr)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), candidate)
        self.assertEqual(file_result.stdout, "")

    def test_cli_reports_invalid_candidate_and_writes_no_output(self):
        proposal = self.proposal()
        proposal["verification"] = []
        paths = self.write_cli_inputs([proposal])
        output = self.root / "candidate.json"
        result = self.run_candidate_cli(paths, "--output", str(output))
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing passed", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
