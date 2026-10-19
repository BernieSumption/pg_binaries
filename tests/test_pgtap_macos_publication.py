"""Tests for target-pinned pgTAP macOS publication evidence."""

import hashlib
import json
from pathlib import Path
import shutil
import shutil
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import emit_pgtap_macos_publication as emitter
import import_pgtap_macos_publication as importer
from pgtap_macos_target import base_target, load_target_config


TARGET_CONFIGS = sorted((ROOT / "tools/pgtap_macos_pins").glob("*.json"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PublicationFixture:
    def __init__(self, original_config):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "repo"
        self.core = base / "core"
        self.output = base / "output"
        for path in (self.root, self.core, self.output):
            path.mkdir()
        config_rel = original_config.relative_to(ROOT)
        self.config = self.root / config_rel
        self.core_archive = self.core / load_target_config(original_config).core_basename
        self.core_archive.write_bytes(b"fixed test core bytes for all target configurations")
        self.core_sha256 = digest(self.core_archive)

        registry = json.loads((ROOT / "support/verification-profiles.json").read_text())
        original_target = load_target_config(original_config)
        profile = registry["profiles"][original_target.profile_id]
        for relative in profile["sources"]:
            source = ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        self.config.parent.mkdir(parents=True, exist_ok=True)
        value = json.loads(original_config.read_text())
        value["core_archive"]["sha256"] = self.core_sha256
        self.config.write_text(json.dumps(value, indent=2) + "\n")
        for relative in ("support.json", "support/postgresql-releases.json", "support/verification-profiles.json"):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        self.target = load_target_config(self.config)
        self.extension = self.output / self.target.extension_basename
        self._write_extension(self.target)
        self._sidecar(self.core_archive)
        self._sidecar(self.extension)
        self._write_reports()
        self.environ = {
            "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "12345678901",
            "GITHUB_REPOSITORY": "BernieSumption/pg_binaries",
            "GITHUB_SERVER_URL": "https://github.com",
        }

    def close(self):
        self.temp.cleanup()

    def _sidecar(self, path):
        path.with_name(path.name + ".sha256").write_text(f"{digest(path)}  {path.name}\n")

    def _write_extension(self, target):
        metadata = {
            "project": "pgtap", "version": target.pgtap_version, "sql_names": ["pgtap"],
            "postgresql_version": target.postgresql_version, "platform": "macos",
            "architecture": target.architecture,
            "source": {"url": target.source_url, "sha256": target.source_sha256},
            "core_archive": {"basename": target.core_basename, "sha256": target.core_sha256},
        }
        metadata_path = self.output / "metadata.json"
        metadata_path.write_text(json.dumps(metadata))
        with tarfile.open(self.extension, "w:gz") as archive:
            archive.add(metadata_path, arcname="metadata.json")

    def _write_reports(self):
        hashes = {self.core_archive.name: digest(self.core_archive),
                  self.extension.name: digest(self.extension)}
        (self.output / "static-analysis.json").write_text(json.dumps({
            "passed": True, "architecture": self.target.architecture,
            "inspected_files": ["bin/postgres"], "archives": hashes,
        }))
        (self.output / "probe-output.txt").write_text("1..4\nok 1\nok 2\nok 3\nok 4\n")
        (self.output / "build-log.txt").write_text("PASS feasibility probe\n")

    def emit(self, outcomes=None):
        return emitter.emit(
            self.root, self.core, self.output, self.output,
            outcomes or {"archive-suite": "success", "static-analysis": "success"},
            "15.7.9", "macos15/test-image", self.config,
            {**self.environ, "GITHUB_RUN_ID": "12345678901"},
        )

    def import_record(self):
        return importer.import_run(self.root, self.core, self.output,
                                  self.environ["GITHUB_RUN_ID"], self.config)


class PgtapMacOSPublicationTests(unittest.TestCase):
    def test_base_target_identifies_selected_core_without_a_run_pin(self):
        for architecture in ("arm64", "x86_64"):
            with self.subTest(architecture=architecture):
                target = base_target("19.1", architecture)
                self.assertEqual(target["postgresql_version"], "19.1")
                self.assertEqual(target["platform"], f"macos-{architecture}")
                self.assertEqual(target["core_archive"], {
                    "basename": f"postgresql-19.1-macos-{architecture}.tar.gz"})

    def test_selected_profiles_do_not_include_historical_pin_fixtures(self):
        registry = json.loads((ROOT / "support/verification-profiles.json").read_text())
        for config in TARGET_CONFIGS:
            target = load_target_config(config)
            sources = registry["profiles"][target.profile_id]["sources"]
            with self.subTest(profile=target.profile_id):
                self.assertFalse(any("pgtap_macos_pins" in source for source in sources))

    def test_target_pins_match_passed_current_core_records(self):
        self.assertEqual(len(TARGET_CONFIGS), 8)
        for config in TARGET_CONFIGS:
            target = load_target_config(config)
            record_path = (ROOT / "support/verification" /
                           f"postgresql-{target.postgresql_version}-{target.platform}-current-"
                           f"{target.core_run_id}.json")
            record = json.loads(record_path.read_text())
            with self.subTest(target=target.profile_id):
                self.assertEqual(record["outcome"], "passed")
                self.assertEqual(record["sha256"], target.core_sha256)
                self.assertEqual(record["ci"]["run_id"], target.core_run_id)

    def test_all_targets_emit_and_import_archive_bound_records(self):
        for config in TARGET_CONFIGS:
            with self.subTest(config=config.name):
                fixture = PublicationFixture(config)
                self.addCleanup(fixture.close)
                paths = fixture.emit()
                record = json.loads(paths[-1].read_text())
                self.assertEqual(record["profile_id"], fixture.target.profile_id)
                self.assertEqual(record["platform"], fixture.target.platform)
                self.assertEqual(record["postgresql_version"], fixture.target.postgresql_version)
                self.assertEqual(record["assembled_core"]["sha256"], fixture.core_sha256)
                receipt = json.loads((fixture.output / "publication/current-receipt.json").read_text())
                self.assertEqual(receipt["archives"][fixture.core_archive.name], fixture.core_sha256)
                retained = fixture.import_record()
                self.assertTrue(any(item.startswith("support/verification/") for item in retained))
                evidence = (fixture.root / "support/evidence" /
                            f"pgtap-macos-publication-{fixture.environ['GITHUB_RUN_ID']}" /
                            fixture.target.architecture)
                self.assertTrue((evidence / "attempt.json").is_file())
                self.assertTrue((evidence / "current-receipt.json").is_file())

    def test_emitter_and_importer_reject_core_bytes_outside_target_pin(self):
        fixture = PublicationFixture(TARGET_CONFIGS[0])
        self.addCleanup(fixture.close)
        fixture.emit()
        fixture.core_archive.write_bytes(b"changed core bytes")
        fixture._sidecar(fixture.core_archive)
        fixture._write_reports()
        with self.assertRaisesRegex(Exception, "does not match the target config pin"):
            fixture.import_record()

        second = PublicationFixture(TARGET_CONFIGS[1])
        self.addCleanup(second.close)
        second.core_archive.write_bytes(b"changed core bytes")
        second._sidecar(second.core_archive)
        second._write_reports()
        with self.assertRaisesRegex(Exception, "does not match the selected successful build"):
            second.emit()

    def test_extension_metadata_cannot_be_reused_for_another_target(self):
        fixture = PublicationFixture(TARGET_CONFIGS[0])
        self.addCleanup(fixture.close)
        other_config = TARGET_CONFIGS[-1]
        other = load_target_config(other_config)
        with self.assertRaisesRegex(Exception, "pinned publication target"):
            emitter._archive_metadata(fixture.extension, other)

    def test_inconsistent_profile_architecture_config_is_rejected(self):
        value = json.loads(TARGET_CONFIGS[0].read_text())
        value["profile_id"] = load_target_config(TARGET_CONFIGS[-1]).profile_id
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target.json"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "profile or archive identity"):
                load_target_config(path)

    def test_target_parser_accepts_a_new_postgresql_release_selected_upstream(self):
        value = json.loads(TARGET_CONFIGS[0].read_text())
        value["postgresql_version"] = "19.1"
        value["profile_id"] = f'pgtap-publication-{value["platform"]}-19.1'
        value["core_archive"]["basename"] = f'postgresql-19.1-{value["platform"]}.tar.gz'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target.json"
            path.write_text(json.dumps(value))
            self.assertEqual(load_target_config(path).postgresql_version, "19.1")

    def test_unrelated_profile_addition_does_not_change_pgtap_revision(self):
        for config in TARGET_CONFIGS:
            target = load_target_config(config)
            profile_id = target.profile_id
            registry = json.loads((ROOT / "support/verification-profiles.json").read_text())
            profile = registry["profiles"][profile_id]
            self.assertNotIn("support/verification-profiles.json", profile["sources"])
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for relative in profile["sources"]:
                    source = ROOT / relative
                    destination = root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
                registry_path = root / "support/verification-profiles.json"
                registry_path.parent.mkdir(parents=True, exist_ok=True)
                registry_path.write_text(json.dumps(registry))
                revision = emitter.coverage.verification_profile(root, profile_id)["profile_revision"]
                registry["profiles"]["unrelated-publication-profile"] = {
                    "scope": "publication", "platforms": [target.platform],
                    "case_ids": ["unrelated"], "sources": ["support.json"],
                }
                registry_path.write_text(json.dumps(registry))
                self.assertEqual(
                    emitter.coverage.verification_profile(root, profile_id)["profile_revision"],
                    revision,
                )


if __name__ == "__main__":
    unittest.main()
