import importlib.util
import contextlib
import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dispatch_plan", ROOT / "tools/dispatch_plan.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class DispatchPlanTests(unittest.TestCase):
    @staticmethod
    def synthetic_queue(status="needed"):
        target = {"project": "Example", "version": "1.0", "platform": "linux-x86_64",
                  "postgresql_version": "18.6", "postgresql_major": 18}
        items = [
            {"id": "z-prerequisite", "kind": "build-core", "status": status, "depends_on": []},
            {"id": "a-target-build", "kind": "build-extension", **target,
             "status": status, "depends_on": ["z-prerequisite"]},
            {"id": "m-target-verify", "kind": "verify-extension", **target,
             "status": status, "depends_on": ["a-target-build"]},
        ]
        return {"work_items": items, "unresolved_prerequisites": []}

    def test_union_uses_topological_order_when_prerequisite_sorts_after_target(self):
        queue = self.synthetic_queue()
        with patch.object(tool.extension_work_queue, "build_queue", return_value=queue):
            result = tool.resolve(ROOT, {"project": "Example", "version": "1.0",
                                         "postgresql_version": "18.6", "platform": "linux-x86_64"})
        self.assertEqual([item["id"] for item in result["work_items"]],
                         ["z-prerequisite", "a-target-build", "m-target-verify"])

    def test_complete_target_is_noop_unless_retry_is_requested(self):
        queue = self.synthetic_queue(status="complete")
        request = {"project": "Example", "version": "1.0", "postgresql_version": "18.6",
                   "platform": "linux-x86_64"}
        with patch.object(tool.extension_work_queue, "build_queue", return_value=queue):
            ordinary = tool.resolve(ROOT, request)
            retry = tool.resolve(ROOT, {**request, "retry": True})
        self.assertFalse(ordinary["should_dispatch"])
        self.assertTrue(retry["should_dispatch"])
        self.assertTrue(all(item["status"] == "complete" for item in retry["work_items"]))

    def fixture_root(self):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        support = {
            "schema_version": 1, "version_selection_as_of": "2026-10-17",
            "postgresql": {"minimum_major": 15},
            "os_support": {name: {"minimum_version": "1"} for name in ("macos", "windows", "linux")},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"],
                                       "linux": ["x86_64", "arm64"]},
            "extensions": {
                "PostGIS": {"sql_names": ["postgis"], "requires": [], "versions": {
                    "3.6.4": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 18}}},
                "PostGIS TIGER Geocoder": {"sql_names": ["postgis_tiger_geocoder"],
                    "requires": ["PostGIS"], "requires_versions": {"PostGIS": {"minimum_version": "3.6"}},
                    "versions": {"2025.2": {"postgresql_minimum_major": 16, "postgresql_maximum_major": 18}}},
                "HypoPG": {"sql_names": ["hypopg"], "requires": [], "versions": {
                    "1.4.3": {"postgresql_minimum_major": 15}}},
            },
        }
        (root / "support.json").write_text(json.dumps(support))
        policy = root / "policies/extensions.md"
        policy.parent.mkdir()
        policy.write_text("## PostGIS — include\n## PostGIS TIGER Geocoder — include\n## HypoPG — include\n")
        releases = {"as_of": "2026-10-17", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-10-17",
                                       "supported_majors": [15, 16, 17, 18]},
                    "releases": [{"version": version, "release_date": "2026-08-13"}
                                 for version in ("15.19", "16.15", "17.11", "18.6")]}
        snapshot = root / "support/postgresql-releases.json"
        snapshot.parent.mkdir()
        snapshot.write_text(json.dumps(releases))
        (root / "inventory.json").write_text(json.dumps({"postgresql": {}, "extensions": {}}))
        return directory, root

    @staticmethod
    def input_identity(component):
        payload = {"schema_version": 1, "component": component, "target": "test",
                   "upstream_sources": {"source": "a"}, "dependencies": {"builder_image": "b"},
                   "build_configuration": {"recipe": "c"}, "recipes": {}}
        payload["sha256"] = hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        return payload

    def candidate_fixture(self, root, *, mismatch=False):
        cache = root / "cache"
        cache.mkdir()
        target = {"project": "HypoPG", "version": "1.4.3", "platform": "linux-x86_64",
                  "postgresql_version": "17.11", "postgresql_major": 17}
        core_identity = self.input_identity("postgresql")
        extension_identity = self.input_identity("hypopg")
        expected = {
            ("postgresql", "17.11", "linux-x86_64"): core_identity,
            ("HypoPG", "1.4.3", "linux-x86_64", 17): extension_identity,
        }
        rows = []
        archive_data = {}
        members = (
            ("postgresql-17.11-linux-x86_64.tar.gz", "postgresql/manifest.json",
             {"schema_version": 1, "component": "postgresql", "version": "17.11",
              "postgresql_version": "17.11", "platform": "linux", "architecture": "x86_64",
              "build_inputs": core_identity}, "postgresql", "17.11"),
            ("hypopg-1.4.3-postgresql-17.11-linux-x86_64.tar.gz", "metadata.json",
             {"project": "hypopg", "version": "1.4.3", "sql_names": ["hypopg"],
              "postgresql_version": "17.11", "platform": "linux", "architecture": "x86_64",
              "build_inputs": extension_identity}, "HypoPG", "1.4.3"),
        )
        for basename, member_name, metadata, project, version in members:
            path = cache / basename
            with tarfile.open(path, "w:gz") as archive:
                payload = json.dumps(metadata).encode()
                member = tarfile.TarInfo(member_name)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            archive_data[basename] = digest
            row = {"component": "postgresql" if project == "postgresql" else "extension",
                   "project": project, "version": version, "platform": "linux-x86_64",
                   "postgresql_version": "17.11", "path": str(path), "sha256": digest,
                   "source": {"provider": "github-actions", "run_id": "123456",
                              "artifact_name": f"candidate-{basename}",
                              "expires_at": "2099-01-01T00:00:00Z"}}
            rows.append(row)

        manifest = root / "cache/candidates.json"
        manifest.write_text(json.dumps({"schema_version": 1, "archives": rows}))
        if mismatch:
            changed = self.input_identity("hypopg")
            changed["build_configuration"]["recipe"] = "changed"
            changed["sha256"] = hashlib.sha256(json.dumps(
                {key: value for key, value in changed.items() if key != "sha256"},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            expected[("HypoPG", "1.4.3", "linux-x86_64", 17)] = changed

        self.write_hypopg_records(root, archive_data)
        return manifest, expected, {key: target[key] for key in
                                    ("project", "version", "postgresql_version", "platform")}

    @staticmethod
    def write_hypopg_records(root, archive_data):
        profile_dir = root / "support"
        profile_dir.mkdir(exist_ok=True)
        source = root / "tests/fixture.sql"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("select 1;\n")
        profiles = {"schema_version": 1, "profiles": {
            profile_id: {"scope": "publication", "platforms": ["linux-x86_64"],
                         "case_ids": ["archive-assembly"], "sources": ["tests/fixture.sql"]}
            for profile_id in ("core-current", "hypopg-current")}}
        (profile_dir / "verification-profiles.json").write_text(json.dumps(profiles))
        revision = "a" * 40
        rows = []
        for component, version, profile_id, digest in (
                ("postgresql", "17.11", "core-current", archive_data[
                    "postgresql-17.11-linux-x86_64.tar.gz"]),
                ("hypopg", "1.4.3", "hypopg-current", archive_data[
                    "hypopg-1.4.3-postgresql-17.11-linux-x86_64.tar.gz"])):
            profile = tool.extension_work_queue.coverage.verification_profile(root, profile_id)
            row = {"schema_version": 2, "scope": "publication", "profile_id": profile_id,
                   "profile_revision": profile["profile_revision"], "outcome": "passed",
                   "case_results": {"archive-assembly": "passed"}, "sha256": digest,
                   "component": component, "version": version, "platform": "linux-x86_64",
                   "postgresql_version": "17.11", "test_revision": revision,
                   "test_cases": ["archive-assembly"],
                   "environment": {"os": "linux", "architecture": "x86_64", "os_version": "1.0",
                                   "clean_system": True, "endpoint": "current", "image_id": "test-image",
                                   "dependency_check_profile": "test", "dependency_checks_passed": True}}
            if component != "postgresql":
                row["project"] = "HypoPG"
                row["assembled_core"] = {"archive": "postgresql-17.11-linux-x86_64.tar.gz",
                                          "version": "17.11",
                                          "sha256": archive_data["postgresql-17.11-linux-x86_64.tar.gz"]}
                row["prerequisite_archives"] = []
            rows.append(row)
        verification = root / "support/verification"
        verification.mkdir(parents=True, exist_ok=True)
        for index, row in enumerate(rows):
            (verification / f"record-{index}.json").write_text(json.dumps(row))

    def test_matching_candidate_queue_is_noop_and_is_passed_to_queue(self):
        temp, root = self.fixture_root()
        manifest, expected, request = self.candidate_fixture(root)
        result = tool.resolve(root, request, manifest, expected)
        self.assertFalse(result["should_dispatch"])
        self.assertTrue(result["work_items"])
        self.assertTrue(all(item["status"] == "complete" for item in result["work_items"]))
        temp.cleanup()

    def test_candidate_identity_mismatch_or_absent_manifest_keeps_dispatch_needed(self):
        temp, root = self.fixture_root()
        manifest, expected, request = self.candidate_fixture(root, mismatch=True)
        mismatch = tool.resolve(root, request, manifest, expected)
        self.assertTrue(mismatch["should_dispatch"])
        self.assertTrue(any(item["status"] == "needed" for item in mismatch["work_items"]))
        absent = tool.resolve(root, request)
        self.assertTrue(absent["should_dispatch"])
        self.assertTrue(any(item["status"] == "needed" for item in absent["work_items"]))
        temp.cleanup()

    def test_hypopg_checked_overlay_reuses_repository_core_record_by_sha256(self):
        temp, root = self.fixture_root()
        manifest, _expected, request = self.candidate_fixture(root)
        verification = root / "support/verification"
        records = list(verification.glob("record-*.json"))
        core_record = next(path for path in records
                           if json.loads(path.read_text())["component"] == "postgresql")
        extension_record_path = next(path for path in records if path != core_record)
        extension_record = json.loads(extension_record_path.read_text())
        extension_record_path.unlink()

        rows = json.loads(manifest.read_text())["archives"]
        candidates = [{key: row[key] for key in
                       ("component", "project", "version", "platform", "postgresql_version", "sha256")
                       if key in row} for row in rows]
        overlay = {"schema_version": 1, "candidate_archives": candidates,
                   "verification_records": [{**extension_record,
                                              "_record_file": "checked-extension-record",
                                              "_profile_current": True}]}

        result = tool.resolve(root, request, checked_overlay=overlay)
        self.assertFalse(result["should_dispatch"])
        self.assertEqual(next(item for item in result["work_items"]
                              if item["kind"] == "verify-core")["status"], "complete")
        self.assertEqual(next(item for item in result["work_items"]
                              if item["kind"] == "verify-extension")["status"], "complete")

        current_core = json.loads(core_record.read_text())
        current_core["sha256"] = "0" * 64
        core_record.write_text(json.dumps(current_core))
        result = tool.resolve(root, request, checked_overlay=overlay)
        core_verification = next(item for item in result["work_items"]
                                 if item["kind"] == "verify-core")
        self.assertEqual(core_verification["status"], "needed")
        self.assertEqual(next(item for item in result["work_items"]
                              if item["kind"] == "verify-extension")["status"], "complete")
        self.assertTrue(result["should_dispatch"])
        temp.cleanup()

    def test_cli_loads_candidate_manifest_and_expected_build_inputs(self):
        temp, root = self.fixture_root()
        manifest, expected, request = self.candidate_fixture(root)
        request_path = root / "request.json"
        request_path.write_text(json.dumps(request))
        inputs_path = root / "expected-build-inputs.json"
        entries = []
        for key, identity in expected.items():
            if key[0] == "postgresql":
                component, version, platform = key
                entry = {"component": component, "version": version, "platform": platform,
                         "identity": identity}
            else:
                project, version, platform, major = key
                entry = {"project": project, "version": version, "platform": platform,
                         "postgresql_major": major, "identity": identity}
            entries.append(entry)
        inputs_path.write_text(json.dumps({"schema_version": 1, "entries": entries}))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = tool.main(["--root", str(root), "--request", str(request_path),
                              "--candidate-manifest", str(manifest),
                              "--expected-build-inputs", str(inputs_path)])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(output.getvalue())["should_dispatch"])
        temp.cleanup()

    def test_selects_one_declared_target_and_its_prerequisites(self):
        temp, root = self.fixture_root()
        request = {"project": "PostGIS TIGER Geocoder", "version": "2025.2",
                   "postgresql_version": "18.6", "platform": "linux-x86_64"}
        result = tool.resolve(root, request)
        self.assertEqual(result["target"]["project"], request["project"])
        self.assertFalse(result["retry"])
        self.assertEqual(result["runner"], "ubuntu-24.04")
        kinds = [item["kind"] for item in result["work_items"]]
        self.assertIn("build-core", kinds)
        self.assertIn("build-extension", kinds)
        self.assertIn("verify-extension", kinds)
        self.assertTrue(any(item.get("project") == "PostGIS" for item in result["work_items"]))
        ids = {item["id"] for item in result["work_items"]}
        self.assertTrue(all(set(item.get("depends_on", [])) <= ids for item in result["work_items"]))
        temp.cleanup()

    def test_retry_is_explicit_and_does_not_add_run_or_asset_pins(self):
        temp, root = self.fixture_root()
        request = {"project": "HypoPG", "version": "1.4.3", "postgresql_version": "17.11",
                   "platform": "windows-x86_64", "retry": True}
        result = tool.resolve(root, request)
        self.assertTrue(result["retry"])
        self.assertFalse({"run_id", "asset_id", "asset_url"} & set(result))
        temp.cleanup()

    def test_rejects_undeclared_malformed_and_multi_target_requests(self):
        temp, root = self.fixture_root()
        base = {"project": "HypoPG", "version": "1.4.3", "postgresql_version": "17.11",
                "platform": "linux-x86_64"}
        for update in ({"version": "999"}, {"postgresql_version": "17"},
                       {"platform": "linux-mips"}, {"retry": "yes"}, {"extra_target": {}}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                tool.resolve(root, {**base, **update})
        temp.cleanup()

    def test_hypothetical_new_postgresql_and_extension_selections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, source = self.fixture_root()
            shutil.copytree(source, root, dirs_exist_ok=True)
            fixture.cleanup()
            support_path = root / "support.json"
            support = json.loads(support_path.read_text())
            support["extensions"]["Example"] = {
                "sql_names": ["example"], "requires": [],
                "versions": {"1.0": {"postgresql_minimum_major": 19}},
            }
            support_path.write_text(json.dumps(support))
            policy = root / "policies/extensions.md"
            policy.write_text(policy.read_text() + "\n## Example — include\n")
            snapshot_path = root / "support/postgresql-releases.json"
            snapshot = json.loads(snapshot_path.read_text())
            snapshot["support_status"]["supported_majors"].append(19)
            release = dict(snapshot["releases"][-1])
            release["version"] = "19.1"
            release["source_archives"] = {}
            snapshot["releases"].append(release)
            support["postgresql"]["minimum_major"] = 15
            snapshot_path.write_text(json.dumps(snapshot))
            result = tool.resolve(root, {"project": "Example", "version": "1.0",
                                         "postgresql_version": "19.1", "platform": "linux-x86_64"})
            self.assertEqual(result["target"]["postgresql_version"], "19.1")
            self.assertEqual(result["target"]["project"], "Example")


if __name__ == "__main__":
    unittest.main()
