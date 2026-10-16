import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "publication_preflight", Path(__file__).resolve().parents[1] / "tools" / "publication_preflight.py")
publication_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publication_preflight)


class PublicationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.support = {
            "schema_version": 1,
            "postgresql": {"minimum_major": 15, "stable_release_cutoff": "2025-09-25"},
            "os_support": {name: {"minimum_version": "1"}
                           for name in ("macos", "windows", "linux")},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"], "linux": ["x86_64", "arm64"]},
            "extensions": {"Example": {"sql_names": ["example"], "versions": {
                "1.0": {"postgresql_minimum_major": 15}}}},
        }
        self.snapshot = {
            "as_of": "2026-01-01", "source": "https://example.test/releases",
            "releases": [{"version": "15.9", "release_date": "2025-09-25"}],
        }
        self.base = {"schema_version": 1, "postgresql": {}, "extensions": {}}
        self.candidate = {"schema_version": 1, "os_support": self.support["os_support"],
                          "candidate_status": "structural-draft",
                          "postgresql": {}, "extensions": {}}
        self.staged = {}
        for os_name, architectures in self.support["platform_architectures"].items():
            for arch in architectures:
                platform = f"{os_name}-{arch}"
                self._add_core(self.candidate, "15.9", platform, f"core-{platform}")
                self._add_extension(platform, f"extension-{platform}")

    def _add_core(self, inventory, version, platform, content, *, tag="catalog-20261016-1"):
        url, checksum = self._stage(content, f"pg-{platform}-{version}.tar.gz", tag)
        inventory["postgresql"].setdefault(version, {"downloads": {}})["downloads"][platform] = {
            "url": url, "sha256": checksum,
        }

    def _add_extension(self, platform, content):
        url, checksum = self._stage(content, f"example-{platform}-1.0.tar.gz")
        self.candidate["extensions"].setdefault("example", {}).setdefault("1.0", {
            "downloads": {}})["downloads"][platform] = [{
                "postgresql_support": {"from": "15.0", "to": "15.9"},
                "url": url, "sha256": checksum,
            }]

    def _stage(self, content, filename, tag="catalog-20261016-2"):
        path = self.root / filename
        payload = content.encode("utf-8")
        path.write_bytes(payload)
        checksum = hashlib.sha256(payload).hexdigest()
        url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{tag}/{filename}"
        self.staged[url] = {"path": str(path), "sha256": checksum}
        return url, checksum

    def check(self, candidate=None, base=None, staged=None):
        return publication_preflight.preflight_candidate(
            base if base is not None else self.base,
            candidate if candidate is not None else self.candidate,
            self.support, self.snapshot,
            staged if staged is not None else self.staged)

    def test_passes_with_matching_local_files_and_complete_coverage(self):
        report = self.check()
        self.assertEqual(report["preflight_status"], "passed")
        self.assertEqual(report["new_asset_count"], 10)
        self.assertEqual(report["postgresql_target_count"], 5)
        self.assertEqual(report["extension_target_count"], 5)
        self.assertNotIn("release_eligible", report)

    def test_rejects_staged_file_with_wrong_bytes(self):
        url = next(iter(self.staged))
        Path(self.staged[url]["path"]).write_text("different bytes", encoding="utf-8")
        with self.assertRaisesRegex(publication_preflight.PreflightError, "bytes do not match"):
            self.check()

    def test_rejects_changed_retained_checksum(self):
        url = "https://example.test/old/pg.tgz"
        checksum = "a" * 64
        self.base["postgresql"]["14.9"] = {"downloads": {"linux-x86_64": {
            "url": url, "sha256": checksum}}}
        self.candidate["postgresql"]["14.9"] = {"downloads": {"linux-x86_64": {
            "url": url, "sha256": "b" * 64}}}
        with self.assertRaisesRegex(publication_preflight.PreflightError, "retained URL checksum changed"):
            self.check()

    def test_rejects_dropped_base_url(self):
        url = "https://example.test/old/pg.tgz"
        self.base["postgresql"]["14.9"] = {"downloads": {"linux-x86_64": {
            "url": url, "sha256": "a" * 64}}}
        with self.assertRaisesRegex(publication_preflight.PreflightError, "dropped retained URL"):
            self.check()

    def test_rejects_candidate_reference_without_staged_or_base_asset(self):
        url, checksum = self._stage("untracked", "pg-linux-x86_64-15.9.tar.gz")
        del self.staged[url]
        self.candidate["postgresql"]["15.9"]["downloads"]["linux-x86_64"] = {
            "url": url, "sha256": checksum,
        }
        with self.assertRaisesRegex(publication_preflight.PreflightError, "no staged asset"):
            self.check()

    def test_rejects_unreferenced_staged_asset(self):
        self._stage("orphan", "orphan.tar.gz")
        with self.assertRaisesRegex(publication_preflight.PreflightError, "not referenced by candidate"):
            self.check()

    def test_rejects_non_immutable_new_url(self):
        old_url = next(url for url in self.staged if "pg-linux-x86_64-15.9" in url)
        asset = self.staged.pop(old_url)
        mutable_url = "https://github.com/BernieSumption/pg_binaries/releases/latest/download/archive.tar.gz"
        self.staged[mutable_url] = asset
        self.candidate["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["url"] = mutable_url
        with self.assertRaisesRegex(publication_preflight.PreflightError, "not an immutable catalog"):
            self.check()

    def test_rejects_incomplete_declared_coverage(self):
        del self.candidate["postgresql"]["15.9"]["downloads"]["windows-x86_64"]
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "missing PostgreSQL target 15.9 windows-x86_64"):
            self.check()

    def test_rejects_non_structural_candidate(self):
        with self.assertRaisesRegex(publication_preflight.PreflightError, "structural-draft"):
            self.check(candidate={"postgresql": {}, "extensions": {}})

    def test_rejects_candidate_with_wrong_schema_or_os_minima(self):
        with self.assertRaisesRegex(publication_preflight.PreflightError, "schema_version must be 1"):
            self.check(candidate=dict(self.candidate, schema_version=2))
        candidate = dict(self.candidate, os_support={"linux": {"minimum_version": "1"}})
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "os_support does not match declared OS minima"):
            self.check(candidate=candidate)


if __name__ == "__main__":
    unittest.main()
