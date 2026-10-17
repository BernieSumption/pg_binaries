import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
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
            "extensions": {"Example": {"sql_names": ["example"], "requires": [], "versions": {
                "1.0": {"postgresql_minimum_major": 15}}}},
        }
        self.snapshot = {
            "as_of": "2026-01-01", "source": "https://example.test/releases",
            "releases": [{"version": "15.9", "release_date": "2025-09-25"}],
        }
        profile_source = self.root / "tests" / "preflight_profile.py"
        profile_source.parent.mkdir(parents=True)
        profile_source.write_text("preflight verification cases", encoding="utf-8")
        profile_platforms = sorted(f"{os_name}-{arch}"
                                   for os_name, arches in self.support["platform_architectures"].items()
                                   for arch in arches)
        profile_registry = {"schema_version": 1, "profiles": {"preflight-publication": {
            "scope": "publication", "platforms": profile_platforms,
            "case_ids": ["candidate-smoke"], "sources": ["tests/preflight_profile.py"]}}}
        profile_path = self.root / "support" / "verification-profiles.json"
        profile_path.parent.mkdir()
        profile_path.write_text(json.dumps(profile_registry), encoding="utf-8")
        self.base = {"schema_version": 1, "postgresql": {}, "extensions": {}}
        self.candidate = {"schema_version": 1, "os_support": self.support["os_support"],
                          "candidate_status": "structural-draft",
                          "postgresql": {}, "extensions": {}, "verification_evidence": {}}
        self.staged = {}
        for os_name, architectures in self.support["platform_architectures"].items():
            for arch in architectures:
                platform = f"{os_name}-{arch}"
                self._add_core(self.candidate, "15.9", platform, f"core-{platform}")
                self._add_extension(platform, f"extension-{platform}")

    def _add_core(self, inventory, version, platform, content, *, tag="catalog-20261016-1"):
        filename = f"postgresql-{version}-{platform}.tar.gz"
        path = self.root / filename
        with tarfile.open(path, "w:gz") as archive:
            payload = b"comment = 'built in'\n"
            member = tarfile.TarInfo("postgresql/share/extension/example.control")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
            os_name, architecture = platform.split("-", 1)
            manifest = json.dumps({
                "schema_version": 1, "component": "postgresql", "version": version,
                "postgresql_version": version, "platform": os_name,
                "architecture": architecture, "included_extensions": ["example"],
            }).encode()
            member = tarfile.TarInfo("postgresql/manifest.json")
            member.size = len(manifest)
            archive.addfile(member, io.BytesIO(manifest))
            self._licence_members(archive, "postgresql", "share/extension")
        payload = path.read_bytes()
        checksum = hashlib.sha256(payload).hexdigest()
        url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{tag}/{filename}"
        self.staged[url] = {"path": str(path), "sha256": checksum}
        inventory.setdefault("verification_evidence", {})[url] = [
            self._verification_record("postgresql", version, platform, version, checksum, endpoint)
            for endpoint in ("minimum", "current")]
        entry = inventory["postgresql"].setdefault(version, {"included_extensions": ["example"], "downloads": {}})
        entry["included_extensions"] = ["example"]
        entry["downloads"][platform] = {
            "url": url, "sha256": checksum,
        }

    def _add_extension(self, platform, content):
        url, checksum = self._stage(content, f"example-1.0-postgresql-15.9-{platform}.tar.gz", platform=platform)
        core = self.candidate["postgresql"]["15.9"]["downloads"][platform]
        self.candidate["verification_evidence"][url] = [
            self._verification_record(
                "example", "1.0", platform, "15.9", checksum, endpoint,
                assembled_core={"archive": f"postgresql-15.9-{platform}.tar.gz",
                                "version": "15.9", "sha256": core["sha256"]})
            for endpoint in ("minimum", "current")]
        self.candidate["extensions"].setdefault("example", {}).setdefault("1.0", {
            "requires": [], "downloads": {}})["downloads"][platform] = [{
                "postgresql_support": {"from": "15.9", "to": "15.9"},
                "url": url, "sha256": checksum,
            }]

    def _verification_record(self, component, version, platform, pg_version, checksum, endpoint,
                             assembled_core=None):
        profile = publication_preflight._coverage.verification_profile(self.root, "preflight-publication")
        os_name, architecture = platform.split("-", 1)
        record = {
            "schema_version": 2, "scope": "publication", "profile_id": "preflight-publication",
            "profile_revision": profile["profile_revision"], "outcome": "passed",
            "sha256": checksum, "component": component, "version": version,
            "platform": platform, "postgresql_version": pg_version,
            "test_revision": "a" * 40, "test_cases": profile["case_ids"],
            "case_results": {case: "passed" for case in profile["case_ids"]},
            "environment": {
                "os": os_name, "architecture": architecture,
                "os_version": "1" if endpoint == "minimum" else "2",
                "clean_system": True, "endpoint": endpoint,
                "image_id": "ubuntu@sha256:image", "dependency_check_profile": "fixture-v1",
                "dependency_checks_passed": True,
            },
        }
        if assembled_core is not None:
            record["assembled_core"] = assembled_core
        return record

    def _stage(self, content, filename, tag="catalog-20261016-2", platform="linux-x86_64"):
        path = self.root / filename
        with tarfile.open(path, "w:gz") as archive:
            payload = content.encode("utf-8")
            member = tarfile.TarInfo("example/lib/example.so")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
            os_name, architecture = platform.split("-", 1)
            metadata = json.dumps({"project": "example", "version": "1.0",
                                   "platform": os_name, "architecture": architecture,
                                   "sql_names": ["example"], "requires": [],
                                   "configuration_prerequisites": [],
                                   "runtime_prerequisites": []}).encode()
            member = tarfile.TarInfo("metadata.json")
            member.size = len(metadata)
            archive.addfile(member, io.BytesIO(metadata))
            self._licence_members(archive, "example", "lib")
        payload = path.read_bytes()
        checksum = hashlib.sha256(payload).hexdigest()
        url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{tag}/{filename}"
        self.staged[url] = {"path": str(path), "sha256": checksum}
        self.candidate["verification_evidence"][url] = [{"sha256": checksum}]
        return url, checksum

    def _licence_members(self, archive, root, payload_path):
        inventory = {"schema_version": 1, "components": [{
            "component": root, "version": "1.0", "payload_paths": [payload_path],
            "license_file": "COPYING", "redistribution_review": {
                "status": "resolved", "basis": "Fixture permissive licence reviewed",
                "source_obligation": "none"}}]}
        for name, data in {"inventory.json": json.dumps(inventory).encode(),
                           "COPYING": b"Fixture licence text"}.items():
            member = tarfile.TarInfo(f"{root}/LICENSES/{name}")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))

    def _rewrite_extension(self, transform, url=None):
        if url is None:
            url = next(url for url in self.staged if "example-1.0-postgresql-15.9-linux-x86_64" in url)
        path = Path(self.staged[url]["path"])
        with tarfile.open(path, "r:gz") as archive:
            contents = {m.name: archive.extractfile(m).read() for m in archive.getmembers()}
        transform(contents)
        with tarfile.open(path, "w:gz") as archive:
            for name, data in contents.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        self.staged[url]["sha256"] = checksum
        for record in self.candidate["verification_evidence"][url]:
            record["sha256"] = checksum
        self.candidate["extensions"]["example"]["1.0"]["downloads"]["linux-x86_64"][0]["sha256"] = checksum

    def _rewrite_core(self, transform):
        url = next(url for url in self.staged if "postgresql-15.9-linux-x86_64" in url)
        path = Path(self.staged[url]["path"])
        with tarfile.open(path, "r:gz") as archive:
            contents = {m.name: archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
        transform(contents)
        with tarfile.open(path, "w:gz") as archive:
            for name, data in contents.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        self.staged[url]["sha256"] = checksum
        self.candidate["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["sha256"] = checksum
        for record in self.candidate["verification_evidence"][url]:
            record["sha256"] = checksum
        extension_url = next(url for url in self.staged if "example-1.0-postgresql-15.9-linux-x86_64" in url)
        for record in self.candidate["verification_evidence"][extension_url]:
            record["assembled_core"]["sha256"] = checksum

    def _rewrite_core_manifest(self, transform):
        def rewrite(contents):
            name = "postgresql/manifest.json"
            manifest = json.loads(contents[name])
            transform(manifest)
            contents[name] = json.dumps(manifest).encode()
        self._rewrite_core(rewrite)

    def _review(self, **changes):
        def transform(contents):
            name = "example/LICENSES/inventory.json"
            inventory = json.loads(contents[name])
            inventory["components"][0]["redistribution_review"] = changes
            contents[name] = json.dumps(inventory).encode()
        self._rewrite_extension(transform)

    def test_rejects_provenance_without_resolved_review(self):
        self._review(status="pending", basis="Source URL known", source_obligation="none",
                     source_urls=["https://example.test/source.tar.gz"])
        with self.assertRaisesRegex(publication_preflight.PreflightError, "resolved redistribution_review"):
            self.check()

    def test_raw_source_provenance_does_not_satisfy_source_links(self):
        self._review(status="resolved", basis="Review recorded", source_obligation="source-links",
                     source_urls=["https://example.test/source.tar.gz"],
                     source_url="https://example.test/source.tar.gz")
        with self.assertRaisesRegex(publication_preflight.PreflightError, "requires source_links"):
            self.check()

    def test_requires_source_obligation_disposition(self):
        self._review(status="resolved", basis="Reviewed")
        with self.assertRaisesRegex(publication_preflight.PreflightError, "source_obligation"):
            self.check()

    def test_source_links_require_explicit_public_links(self):
        for links in ([], ["file:///source"], ["https://user:secret@example.test/source"]):
            with self.subTest(links=links):
                self._review(status="resolved", basis="Reviewed source delivery", source_obligation="source-links",
                             source_links=links)
                with self.assertRaises(publication_preflight.PreflightError):
                    self.check()
        self._review(status="resolved", basis="Reviewed exact corresponding source",
                     source_obligation="source-links", source_links=["https://example.test/source.tar.gz"])
        self.assertEqual(self.check()["redistribution_review_status"], "declarations-checked")

    def test_source_offer_requires_included_nonempty_regular_file(self):
        self._review(status="resolved", basis="Written offer reviewed", source_obligation="source-offer",
                     source_offer_file="offer.txt")
        with self.assertRaisesRegex(publication_preflight.PreflightError, "licence evidence file"):
            self.check()
        self._rewrite_extension(lambda contents: contents.update({"example/LICENSES/offer.txt": b"Offer text"}))
        self.check()

    def test_rejects_absent_inventory_or_licence_text(self):
        url = next(url for url in self.staged if "example-1.0-postgresql-15.9-macos-x86_64" in url)
        self._rewrite_extension(lambda contents: contents.pop("example/LICENSES/inventory.json"), url)
        with self.assertRaises(publication_preflight.PreflightError):
            self.check()

    def test_rejects_absent_licence_text(self):
        url = next(url for url in self.staged if "example-1.0-postgresql-15.9-macos-arm64" in url)
        self._rewrite_extension(lambda contents: contents.pop("example/LICENSES/COPYING"), url)
        with self.assertRaises(publication_preflight.PreflightError):
            self.check()

    def _assert_invalid_licence_inventory(self, mutate):
        def transform(contents):
            name = "example/LICENSES/inventory.json"
            inventory = json.loads(contents[name])
            mutate(inventory)
            contents[name] = json.dumps(inventory).encode()
        self._rewrite_extension(transform)
        with self.assertRaises(publication_preflight.PreflightError):
            self.check()

    def test_rejects_invalid_licence_inventory_schema_version(self):
        self._assert_invalid_licence_inventory(lambda inventory: inventory.update(schema_version=2))

    def test_rejects_empty_licence_inventory_components(self):
        self._assert_invalid_licence_inventory(lambda inventory: inventory.update(components=[]))

    def test_rejects_licence_component_without_version(self):
        self._assert_invalid_licence_inventory(lambda inventory: inventory["components"][0].pop("version"))

    def test_rejects_unmapped_licence_payload(self):
        self._assert_invalid_licence_inventory(
            lambda inventory: inventory["components"][0].update(payload_paths=["missing/lib"]))

    def test_rejects_missing_additional_licence_file(self):
        self._assert_invalid_licence_inventory(
            lambda inventory: inventory["components"][0].update(additional_license_files=["missing.txt"]))

    def test_rejects_traversal_in_evidence_path(self):
        self._review(status="resolved", basis="Reviewed", source_obligation="source-offer",
                     source_offer_file="../offer.txt")
        with self.assertRaisesRegex(publication_preflight.PreflightError, "invalid licence inventory path"):
            self.check()

    def check(self, candidate=None, base=None, staged=None):
        return publication_preflight.preflight_candidate(
            base if base is not None else self.base,
            candidate if candidate is not None else self.candidate,
            self.support, self.snapshot,
            staged if staged is not None else self.staged, root=self.root)

    def _rename_new_url(self, old_url, filename):
        tag = old_url.rsplit("/", 1)[0]
        new_url = f"{tag}/{filename}"
        self.staged[new_url] = self.staged.pop(old_url)
        self.candidate["verification_evidence"][new_url] = self.candidate["verification_evidence"].pop(old_url)
        for component in (self.candidate["postgresql"], self.candidate["extensions"]):
            def replace(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key == "url" and child == old_url:
                            value[key] = new_url
                        else:
                            replace(child)
                elif isinstance(value, list):
                    for child in value:
                        replace(child)
            replace(component)

    def _run_cli(self, candidate=None):
        documents = {
            "base.json": self.base,
            "candidate.json": candidate if candidate is not None else self.candidate,
            "support.json": self.support,
            "snapshot.json": self.snapshot,
            "staged.json": self.staged,
        }
        paths = {}
        for filename, document in documents.items():
            path = self.root / filename
            path.write_text(json.dumps(document), encoding="utf-8")
            paths[filename] = path
        script = Path(__file__).resolve().parents[1] / "tools" / "publication_preflight.py"
        return subprocess.run(
            [sys.executable, str(script), "--base-inventory", str(paths["base.json"]),
             "--candidate-inventory", str(paths["candidate.json"]),
             "--support", str(paths["support.json"]),
             "--release-snapshot", str(paths["snapshot.json"]),
             "--staged-assets", str(paths["staged.json"]), "--root", str(self.root)],
            capture_output=True, text=True, check=False)

    def test_cli_outputs_json_success_report(self):
        result = self._run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.check())
        self.assertEqual(result.stderr, "")

    def test_cli_returns_nonzero_and_error_for_failed_preflight(self):
        candidate = dict(self.candidate, candidate_status="pending")
        result = self._run_cli(candidate)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("candidate_status 'structural-draft'", result.stderr)

    def test_passes_with_matching_local_files_and_complete_coverage(self):
        report = self.check()
        self.assertEqual(report["preflight_status"], "passed")
        self.assertEqual(report["new_asset_count"], 10)
        self.assertEqual(report["postgresql_target_count"], 5)
        self.assertEqual(report["extension_target_count"], 5)
        self.assertNotIn("release_eligible", report)

    def test_rejects_new_core_filename_for_different_target(self):
        old_url = next(url for url in self.staged if "postgresql-15.9-linux-x86_64" in url)
        self._rename_new_url(old_url, "postgresql-15.9-linux-mips.tar.gz")
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "PostgreSQL archive filename does not match candidate target"):
            self.check()

    def test_rejects_new_extension_filename_outside_claimed_pg_range(self):
        old_url = next(url for url in self.staged if "example-1.0-postgresql-15.9-linux-x86_64" in url)
        self._rename_new_url(old_url, "example-1.0-postgresql-16.0-linux-x86_64.tar.gz")
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "extension archive PostgreSQL target does not match candidate range"):
            self.check()

    def test_accepts_one_project_archive_for_multiple_sql_names(self):
        self.support["extensions"]["Example"]["sql_names"].append("example_aux")
        for platform, records in self.candidate["extensions"]["example"]["1.0"]["downloads"].items():
            for record in records:
                self.candidate["extensions"].setdefault("example_aux", {}).setdefault("1.0", {
                    "requires": [], "downloads": {}})["downloads"][platform] = [dict(record)]
        for url, records in self.candidate["verification_evidence"].items():
            if "example-" in url:
                records.extend([dict(record, component="example_aux") for record in records])
        for url, asset in self.staged.items():
            if "example-" not in url:
                continue
            with tarfile.open(asset["path"], "r:gz") as archive:
                contents = {m.name: archive.extractfile(m).read() for m in archive.getmembers()}
            metadata = json.loads(contents["metadata.json"])
            metadata["sql_names"] = ["example", "example_aux"]
            contents["metadata.json"] = json.dumps(metadata).encode()
            with tarfile.open(asset["path"], "w:gz") as archive:
                for name, data in contents.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            checksum = hashlib.sha256(Path(asset["path"]).read_bytes()).hexdigest()
            asset["sha256"] = checksum
            for record in self.candidate["verification_evidence"][url]:
                record["sha256"] = checksum
            for sql_name in ("example", "example_aux"):
                for records in self.candidate["extensions"][sql_name]["1.0"]["downloads"].values():
                    for record in records:
                        if record["url"] == url:
                            record["sha256"] = checksum
        self.assertEqual(self.check()["extension_target_count"], 10)

    def _rewrite_metadata(self, transform):
        def rewrite(contents):
            metadata = json.loads(contents["metadata.json"])
            transform(metadata)
            contents["metadata.json"] = json.dumps(metadata).encode()
        self._rewrite_extension(rewrite)

    def test_rejects_missing_extension_metadata(self):
        self._rewrite_extension(lambda contents: contents.pop("metadata.json"))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "requires a regular metadata.json"):
            self.check()

    def test_rejects_malformed_extension_metadata_json(self):
        self._rewrite_extension(lambda contents: contents.update({"metadata.json": b"{"}))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "cannot read staged extension metadata"):
            self.check()

    def test_rejects_wrong_extension_metadata_sql_names(self):
        self._rewrite_metadata(lambda metadata: metadata.update(sql_names=["other"]))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "sql_names do not match support"):
            self.check()

    def test_rejects_wrong_extension_metadata_requires(self):
        self._rewrite_metadata(lambda metadata: metadata.update(requires=["other-project"]))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "requires does not match candidate"):
            self.check()

    def test_requires_configuration_prerequisites_array(self):
        self._rewrite_metadata(lambda metadata: metadata.pop("configuration_prerequisites"))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "requires configuration_prerequisites list"):
            self.check()

    def test_configuration_prerequisites_must_be_array(self):
        self._rewrite_metadata(lambda metadata: metadata.update(configuration_prerequisites={}))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "requires configuration_prerequisites list"):
            self.check()

    def test_requires_runtime_prerequisites_array(self):
        self._rewrite_metadata(lambda metadata: metadata.pop("runtime_prerequisites"))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "requires runtime_prerequisites list"):
            self.check()

    def test_runtime_prerequisites_must_be_array(self):
        self._rewrite_metadata(lambda metadata: metadata.update(runtime_prerequisites="none"))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "requires runtime_prerequisites list"):
            self.check()

    def test_rejects_extension_metadata_version_mismatch(self):
        self._rewrite_metadata(lambda metadata: metadata.update(version="2.0"))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "project or version"):
            self.check()

    def test_rejects_missing_extension_metadata_platform(self):
        self._rewrite_metadata(lambda metadata: metadata.pop("platform"))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "platform does not match candidate"):
            self.check()

    def test_rejects_missing_extension_metadata_architecture(self):
        self._rewrite_metadata(lambda metadata: metadata.pop("architecture"))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "platform does not match candidate"):
            self.check()

    def test_rejects_extension_archive_extra_root(self):
        self._rewrite_extension(lambda contents: contents.update({"other/file": b"unsafe root"}))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "only the project payload root"):
            self.check()

    def test_verification_evidence_is_required_and_bound_to_candidate_checksum(self):
        url = next(iter(self.candidate["verification_evidence"]))
        original_evidence = self.candidate["verification_evidence"][url]
        del self.candidate["verification_evidence"][url]
        with self.assertRaisesRegex(publication_preflight.PreflightError, "no verification evidence"):
            self.check()

        self.candidate["verification_evidence"][url] = original_evidence
        self.candidate["verification_evidence"][url][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(publication_preflight.PreflightError, "verification record checksum"):
            self.check()

    def test_rejects_checksum_only_verification_evidence(self):
        url = next(iter(self.candidate["verification_evidence"]))
        checksum = self.candidate["verification_evidence"][url][0]["sha256"]
        self.candidate["verification_evidence"][url] = [{"sha256": checksum}]
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "requires passed current-profile publication verification"):
            self.check()

    def test_rejects_extension_verification_bound_to_wrong_core(self):
        url = next(url for url in self.staged if "example-1.0-postgresql-15.9-linux-x86_64" in url)
        self.candidate["verification_evidence"][url][0]["assembled_core"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "requires passed current-profile publication verification"):
            self.check()

    def test_rejects_core_without_both_os_endpoint_records(self):
        url = next(url for url in self.staged if "postgresql-15.9-linux-x86_64" in url)
        self.candidate["verification_evidence"][url] = self.candidate["verification_evidence"][url][:1]
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "requires passed current-profile publication verification"):
            self.check()

    def test_rejects_stale_publication_profile(self):
        url = next(url for url in self.staged if "postgresql-15.9-linux-x86_64" in url)
        self.candidate["verification_evidence"][url][0]["profile_revision"] = "0" * 64
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "requires passed current-profile publication verification"):
            self.check()

    def test_rejects_failed_publication_record(self):
        url = next(url for url in self.staged if "postgresql-15.9-linux-x86_64" in url)
        record = self.candidate["verification_evidence"][url][0]
        record["outcome"] = "failed"
        record["case_results"]["candidate-smoke"] = "failed"
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "requires passed current-profile publication verification"):
            self.check()

    def test_rejects_staged_file_with_wrong_bytes(self):
        url = next(iter(self.staged))
        Path(self.staged[url]["path"]).write_text("different bytes", encoding="utf-8")
        with self.assertRaisesRegex(publication_preflight.PreflightError, "bytes do not match"):
            self.check()

    def test_rejects_included_extensions_that_do_not_match_archive_controls(self):
        self.candidate["postgresql"]["15.9"]["included_extensions"] = ["wrong"]
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "do not match staged archive controls"):
            self.check()

    def test_rejects_postgresql_archive_without_manifest(self):
        self._rewrite_core(lambda contents: contents.pop("postgresql/manifest.json"))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "requires a regular manifest.json"):
            self.check()

    def test_rejects_postgresql_manifest_target_mismatch(self):
        self._rewrite_core_manifest(lambda manifest: manifest.update(architecture="arm64"))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "manifest target does not match candidate"):
            self.check()

    def test_rejects_postgresql_manifest_builtin_mismatch(self):
        self._rewrite_core_manifest(lambda manifest: manifest.update(included_extensions=["other"]))
        with self.assertRaisesRegex(publication_preflight.PreflightError, "manifest included_extensions"):
            self.check()

    def test_rejects_postgresql_archive_without_control_files(self):
        url = next(url for url in self.staged if "postgresql-15.9-linux-x86_64" in url)
        path = Path(self.staged[url]["path"])
        with tarfile.open(path, "w:gz") as archive:
            payload = b"no extension controls"
            member = tarfile.TarInfo("postgresql/README")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        self.staged[url]["sha256"] = checksum
        for record in self.candidate["verification_evidence"][url]:
            record["sha256"] = checksum
        self.candidate["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["sha256"] = checksum
        extension_url = next(url for url in self.staged if "example-1.0-postgresql-15.9-linux-x86_64" in url)
        for record in self.candidate["verification_evidence"][extension_url]:
            record["assembled_core"]["sha256"] = checksum
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "missing or duplicate PostgreSQL extension controls"):
            self.check()

    def test_rejects_malformed_postgresql_control_filename(self):
        url = next(url for url in self.staged if "postgresql-15.9-linux-x86_64" in url)
        path = Path(self.staged[url]["path"])
        with tarfile.open(path, "w:gz") as archive:
            payload = b"comment = 'built in'\n"
            member = tarfile.TarInfo("postgresql/share/extension/bad name.control")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        self.staged[url]["sha256"] = checksum
        for record in self.candidate["verification_evidence"][url]:
            record["sha256"] = checksum
        self.candidate["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["sha256"] = checksum
        extension_url = next(url for url in self.staged if "example-1.0-postgresql-15.9-linux-x86_64" in url)
        for record in self.candidate["verification_evidence"][extension_url]:
            record["assembled_core"]["sha256"] = checksum
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "malformed PostgreSQL extension control"):
            self.check()

    def test_rejects_decoy_control_outside_postgresql_root(self):
        url = next(url for url in self.staged if "postgresql-15.9-linux-x86_64" in url)
        path = Path(self.staged[url]["path"])
        with tarfile.open(path, "w:gz") as archive:
            payload = b"comment = 'built in'\n"
            member = tarfile.TarInfo("other/share/extension/example.control")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        self.staged[url]["sha256"] = checksum
        for record in self.candidate["verification_evidence"][url]:
            record["sha256"] = checksum
        self.candidate["postgresql"]["15.9"]["downloads"]["linux-x86_64"]["sha256"] = checksum
        extension_url = next(url for url in self.staged if "example-1.0-postgresql-15.9-linux-x86_64" in url)
        for record in self.candidate["verification_evidence"][extension_url]:
            record["assembled_core"]["sha256"] = checksum
        with self.assertRaisesRegex(publication_preflight.PreflightError,
                                    "outside postgresql/share/extension"):
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
        url, checksum = self._stage("untracked", "untracked.tar.gz")
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
        old_url = next(url for url in self.staged if "postgresql-15.9-linux-x86_64" in url)
        asset = self.staged.pop(old_url)
        mutable_url = "https://github.com/BernieSumption/pg_binaries/releases/latest/download/archive.tar.gz"
        self.staged[mutable_url] = asset
        self.candidate["verification_evidence"][mutable_url] = self.candidate["verification_evidence"].pop(old_url)
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
