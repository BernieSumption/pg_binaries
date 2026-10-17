import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from tools.local_publication_dry_run import DryRunError, LocalPublicationStore, _preflight

_PREFLIGHT_TESTS_SPEC = importlib.util.spec_from_file_location(
    "publication_preflight_fixtures", Path(__file__).with_name("test_publication_preflight.py"))
_preflight_tests = importlib.util.module_from_spec(_PREFLIGHT_TESTS_SPEC)
_PREFLIGHT_TESTS_SPEC.loader.exec_module(_preflight_tests)


class LocalPublicationDryRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalPublicationStore(self.temp.name)
        self.old_tag = "catalog-20261016-1"
        self.new_tag = "catalog-20261017-1"
        self.old_url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{self.old_tag}/old.tar.gz"
        self.new_url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{self.new_tag}/new.tar.gz"
        self.old_bytes, self.new_bytes = b"older archive", b"new archive"
        self.old_inventory = self.inventory(self.old_url, self.old_bytes)
        self.store.seed_release(self.old_tag, self.old_inventory, {"old.tar.gz": self.old_bytes})
        self.store.current_path.parent.mkdir(parents=True)
        self.store.current_path.write_text(json.dumps(self.old_inventory), encoding="utf-8")
        self.candidate = {
            "schema_version": 1,
            "postgresql": {
                "15.1": {"downloads": {"linux-x86_64": {
                    "url": self.old_url, "sha256": self.digest(self.old_bytes)}}},
                "16.1": {"downloads": {"linux-x86_64": {
                    "url": self.new_url, "sha256": self.digest(self.new_bytes)}}},
            },
            "extensions": {},
        }

    @staticmethod
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    def inventory(self, url, data):
        return {"schema_version": 1, "postgresql": {"15.1": {
            "downloads": {"linux-x86_64": {"url": url, "sha256": self.digest(data)}}}},
            "extensions": {}}

    def test_stages_verifies_promotes_then_retrieves_old_and_new_urls_locally(self):
        self.store.promote(self.new_tag, self.candidate, {self.new_url: self.new_bytes})
        self.assertEqual(self.store.current_inventory(), self.candidate)
        self.assertEqual(self.store.retrieve(self.old_url), self.old_bytes)
        self.assertEqual(self.store.retrieve(self.new_url), self.new_bytes)
        self.assertEqual(self.store.retrieve_current_references(), {
            self.old_url: self.old_bytes, self.new_url: self.new_bytes})
        release = self.store.releases / self.new_tag
        self.assertEqual((release / "new.tar.gz").read_bytes(), self.new_bytes)
        self.assertEqual(json.loads((release / "inventory.json").read_text()), self.candidate)

    def test_failure_after_staging_or_verification_preserves_current(self):
        for failure in ("after_stage", "after_verify"):
            with self.subTest(failure=failure):
                with self.assertRaises(DryRunError):
                    self.store.promote(self.new_tag, self.candidate,
                                       {self.new_url: self.new_bytes}, fail_at=failure)
                self.assertEqual(self.store.current_inventory(), self.old_inventory)
                self.assertFalse((self.store.releases / self.new_tag).exists())

    def test_failure_after_release_creation_preserves_current_inventory(self):
        with self.assertRaisesRegex(DryRunError, "before current inventory switch"):
            self.store.promote(self.new_tag, self.candidate,
                               {self.new_url: self.new_bytes}, fail_at="before_current_switch")
        self.assertEqual(self.store.current_inventory(), self.old_inventory)
        self.assertEqual(self.store.retrieve(self.new_url), self.new_bytes)

    def test_missing_retained_archive_and_checksum_mismatch_block_switch(self):
        (self.store.releases / self.old_tag / "old.tar.gz").unlink()
        with self.assertRaisesRegex(DryRunError, "unavailable"):
            self.store.promote(self.new_tag, self.candidate, {self.new_url: self.new_bytes})
        self.assertEqual(self.store.current_inventory(), self.old_inventory)

        (self.store.releases / self.old_tag / "old.tar.gz").write_bytes(b"wrong bytes")
        with self.assertRaisesRegex(DryRunError, "checksum mismatch"):
            self.store.promote(self.new_tag, self.candidate, {self.new_url: self.new_bytes})
        self.assertEqual(self.store.current_inventory(), self.old_inventory)

    def test_new_assets_must_match_tag_and_candidate_references(self):
        with self.assertRaisesRegex(DryRunError, "exactly match"):
            self.store.promote(self.new_tag, self.candidate, {})
        with self.assertRaisesRegex(DryRunError, "does not use candidate tag"):
            self.store.promote(self.new_tag, self.candidate, {self.old_url: self.old_bytes})
        self.assertEqual(self.store.current_inventory(), self.old_inventory)

    def test_preflighted_addition_replacement_retirement_and_incomplete_coverage(self):
        fixture = _preflight_tests.PublicationPreflightTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        candidate = fixture.candidate
        support, snapshot = fixture.support, fixture.snapshot
        snapshot["support_status"]["supported_majors"].append(16)
        snapshot["releases"].append({"version": "16.6", "release_date": "2025-11-01"})

        historical_tag = "catalog-20261016-9"
        historical_filename = "example-1.0-postgresql-15.9-to-16.6-linux-x86_64.tar.gz"
        historical_url = (
            f"https://github.com/BernieSumption/pg_binaries/releases/download/"
            f"{historical_tag}/{historical_filename}")
        historical_asset_url, historical_checksum = fixture._stage(
            "historical selected range", "example-1.0-postgresql-16.6-linux-x86_64.tar.gz",
            tag=historical_tag, platform="linux-x86_64", pg_version="16.6")
        historical_bytes = Path(fixture.staged.pop(historical_asset_url)["path"]).read_bytes()
        candidate["verification_evidence"].pop(historical_asset_url)

        base = {
            "schema_version": 1,
            "os_support": support["os_support"],
            "postgresql": copy.deepcopy(candidate["postgresql"]),
            "extensions": copy.deepcopy(candidate["extensions"]),
        }
        base["extensions"]["example"]["1.0"]["downloads"]["linux-x86_64"] = [{
            "postgresql_support": {"from": "15.9", "to": "16.6"},
            "url": historical_url, "sha256": historical_checksum,
        }]
        retired_url = (
            f"https://github.com/BernieSumption/pg_binaries/releases/download/"
            f"{historical_tag}/postgresql-14.9-linux-x86_64.tar.gz")
        retired_bytes = b"retired unselected PostgreSQL archive"
        base["postgresql"]["14.9"] = {"downloads": {"linux-x86_64": {
            "url": retired_url, "sha256": self.digest(retired_bytes)}}}

        def add_exact_extension(pg_version, platform, tag):
            filename = f"example-1.0-postgresql-{pg_version}-{platform}.tar.gz"
            url, checksum = fixture._stage(
                f"example-{pg_version}-{platform}", filename,
                tag=tag, platform=platform, pg_version=pg_version)
            core = candidate["postgresql"][pg_version]["downloads"][platform]
            candidate["verification_evidence"][url] = [fixture._verification_record(
                "example", "1.0", platform, pg_version, checksum, "current",
                assembled_core={"archive": f"postgresql-{pg_version}-{platform}.tar.gz",
                                "version": pg_version, "sha256": core["sha256"]})]
            candidate["extensions"]["example"]["1.0"]["downloads"].setdefault(platform, []).append({
                "postgresql_support": {"from": pg_version, "to": pg_version},
                "url": url, "sha256": checksum,
            })

        platforms = ("macos-x86_64", "macos-arm64", "windows-x86_64",
                     "linux-x86_64", "linux-arm64")
        for platform in platforms:
            fixture._add_core(candidate, "16.6", platform, f"core-16.6-{platform}")
            if platform != "linux-x86_64":
                add_exact_extension("16.6", platform, "catalog-20261017-8")
        candidate["extensions"]["example"]["1.0"]["downloads"]["linux-x86_64"].append({
            "postgresql_support": {"from": "16.6", "to": "16.6"},
            "url": historical_url, "sha256": historical_checksum,
        })

        base_refs = _preflight._asset_references(base)
        candidate_refs = _preflight._asset_references(candidate)
        new_urls = set(candidate_refs) - set(base_refs)
        new_tag = "catalog-20261017-9"
        url_mapping = {url: f"https://github.com/BernieSumption/pg_binaries/releases/download/"
                            f"{new_tag}/{url.rsplit('/', 1)[-1]}"
                       for url in new_urls}

        def rekey(value):
            if isinstance(value, dict):
                return {key: rekey(child) for key, child in value.items()}
            if isinstance(value, list):
                return [rekey(child) for child in value]
            return url_mapping.get(value, value) if isinstance(value, str) else value

        candidate = rekey(candidate)
        candidate["verification_evidence"] = {
            url_mapping.get(url, url): records
            for url, records in candidate["verification_evidence"].items()
            if url not in base_refs
        }
        new_assets = {
            url_mapping[url]: Path(asset["path"]).read_bytes()
            for url, asset in fixture.staged.items() if url in url_mapping
        }
        self.assertEqual(set(new_assets), set(url_mapping.values()))

        store = LocalPublicationStore(Path(self.temp.name) / "preflighted")
        old_assets = {}
        for url in base_refs:
            if url == historical_url:
                content = historical_bytes
            elif url == retired_url:
                content = retired_bytes
            else:
                content = Path(fixture.staged[url]["path"]).read_bytes()
            old_tag, filename = store._path_parts(url)
            old_assets.setdefault(old_tag, {})[filename] = content
        for tag, assets in old_assets.items():
            store.seed_release(tag, base, assets)
        store.current_path.parent.mkdir(parents=True, exist_ok=True)
        store.current_path.write_text(json.dumps(base), encoding="utf-8")

        exact_replacement_url = next(
            url for url in url_mapping.values()
            if url.endswith("/example-1.0-postgresql-15.9-linux-x86_64.tar.gz"))
        incomplete = copy.deepcopy(candidate)
        incomplete["extensions"]["example"]["1.0"]["downloads"]["linux-x86_64"] = [
            entry for entry in incomplete["extensions"]["example"]["1.0"]["downloads"]["linux-x86_64"]
            if entry["url"] != exact_replacement_url]
        incomplete["verification_evidence"].pop(exact_replacement_url)
        incomplete_assets = dict(new_assets)
        incomplete_assets.pop(exact_replacement_url)
        context = {"support": support, "snapshot": snapshot, "root": fixture.root}
        with self.assertRaisesRegex(DryRunError, "missing extension target example 1.0 PostgreSQL 15.9 linux-x86_64"):
            store.promote(new_tag, incomplete, incomplete_assets, preflight_context=context)
        self.assertEqual(store.current_inventory(), base)
        self.assertFalse((store.releases / new_tag).exists())

        store.promote(new_tag, candidate, new_assets, preflight_context=context)
        current_refs = store.retrieve_current_references()
        self.assertIn(historical_url, current_refs)
        self.assertNotIn(retired_url, current_refs)
        self.assertEqual(current_refs[historical_url], historical_bytes)
        self.assertEqual(store.current_inventory(), candidate)


if __name__ == "__main__":
    unittest.main()
