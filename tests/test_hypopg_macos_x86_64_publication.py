"""Focused tests for Intel HypoPG macOS publication evidence."""

import hashlib
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import emit_hypopg_macos_x86_64_publication as emitter
import import_hypopg_macos_x86_64_publication as importer
from test_emit_hypopg_macos_publication import fixture_target

_POINTER_SPEC = importlib.util.spec_from_file_location(
    "license_pointer", Path(__file__).resolve().parents[1] / "tools" / "license_pointer.py")
license_pointer = importlib.util.module_from_spec(_POINTER_SPEC)
_POINTER_SPEC.loader.exec_module(license_pointer)


class HypoPGMacOSIntelPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "repo"
        self.core = base / "core"
        self.output = base / "output"
        for path in (self.root, self.core, self.output):
            path.mkdir()
        registry = json.loads(Path("support/verification-profiles.json").read_text())
        profile = registry["profiles"][emitter.PROFILE_ID]
        for relative in profile["sources"]:
            source = Path(relative)
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        for relative in ("support.json", "support/postgresql-releases.json", "support/verification-profiles.json"):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(relative, destination)

        self.core_name = f"postgresql-{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz"
        self.extension_name = (f"hypopg-{emitter.HYPOPG_VERSION}-postgresql-"
                               f"{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz")
        self.core_archive = self.core / self.core_name
        self.core_archive.write_bytes(b"fixture Intel core bytes")
        self.core_digest = self.digest(self.core_archive)
        self.target = replace(fixture_target(emitter.PG_VERSION, emitter.ARCHITECTURE),
                              core_sha256=self.core_digest)
        self.extension = self.output / self.extension_name
        self._make_extension()
        self.environ = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "12345678901",
                        "GITHUB_REPOSITORY": "BernieSumption/pg_binaries",
                        "GITHUB_SERVER_URL": "https://github.com"}

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _sidecar(self, path):
        path.with_name(path.name + ".sha256").write_text(f"{self.digest(path)}  {path.name}\n")

    def _make_extension(self):
        metadata = {
            "project": "hypopg", "version": emitter.HYPOPG_VERSION,
            "sql_names": ["hypopg"], "postgresql_version": emitter.PG_VERSION,
            "platform": "macos", "architecture": emitter.ARCHITECTURE,
            "source": {"url": emitter.SOURCE_URL, "sha256": emitter.SOURCE_SHA256},
            "core_archive": {"basename": self.core_name, "sha256": self.core_digest},
        }
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "hypopg"
            (package / "lib").mkdir(parents=True)
            (package / "lib/hypopg.dylib").write_bytes(b"Intel Mach-O fixture")
            license_pointer.write_pointer(package, "hypopg")
            metadata_path = Path(temporary) / "metadata.json"
            metadata_path.write_text(json.dumps(metadata))
            with tarfile.open(self.extension, "w:gz") as archive:
                archive.add(package, arcname="hypopg")
                archive.add(metadata_path, arcname="metadata.json")
        self._sidecar(self.core_archive)
        self._sidecar(self.extension)
        digests = {self.core_name: self.digest(self.core_archive),
                   self.extension_name: self.digest(self.extension)}
        (self.output / "static-analysis.json").write_text(json.dumps({
            "passed": True, "architecture": emitter.ARCHITECTURE,
            "inspected_files": ["hypopg/lib/hypopg.dylib"], "archives": digests,
        }))
        (self.output / "probe-output.txt").write_text(
            "18\npostgres_major_matches\nt\nhypothetical_index_created\nt\n"
            "Index Scan using btree_hypo_probe_id\n0\n")

    def emit(self):
        return emitter.emit(self.root, self.core, self.output, self.output,
                            {"archive-suite": "success", "static-analysis": "success"},
                            "15.7.9", "macos15/20261018.1", self.environ, target=self.target)

    def test_adapter_selects_intel_profile_without_loading_a_core_pin(self):
        import emit_hypopg_macos_publication as arm64
        self.assertEqual(emitter.ARCHITECTURE, "x86_64")
        self.assertEqual(emitter.PROFILE_ID, "hypopg-publication-macos-x86_64-18.6")
        self.assertFalse(hasattr(emitter, "PIN"))
        self.assertNotIn("hypopg_macos_pins", Path("tools/emit_hypopg_macos_x86_64_publication.py").read_text())
        self.assertNotIn("CORE_SHA256", Path("tools/import_hypopg_macos_x86_64_publication.py").read_text())
        self.assertEqual(arm64.ARCHITECTURE, "arm64")
        self.assertEqual(arm64.PROFILE_ID, "hypopg-publication-macos-arm64-18.6")

    def test_selected_workflow_uses_intel_target_and_shared_verification_path(self):
        from hypopg_macos_target import base_target
        target = base_target("18.6", "x86_64")
        self.assertEqual((target["postgresql_version"], target["architecture"]), ("18.6", "x86_64"))
        self.assertEqual(target["core_archive"], {"basename": "postgresql-18.6-macos-x86_64.tar.gz"})
        workflow = Path(".github/workflows/hypopg-macos-x86_64-selected-publication.yml").read_text()
        self.assertIn("runs-on: macos-15-intel", workflow)
        self.assertIn("--platform macos-x86_64", workflow)
        self.assertIn("tools/hypopg_macos_target.py", workflow)
        self.assertIn("--postgresql-version \"$POSTGRESQL_VERSION\" --architecture x86_64", workflow)
        self.assertIn('--output "$RUNNER_TEMP/hypopg-base-target.json"', workflow)
        self.assertIn('resolve-core.sh "$RUNNER_TEMP/hypopg-base-target.json"', workflow)
        self.assertNotIn("hypopg_macos_pins", workflow)
        self.assertIn("scripts/macos/resolve-core.sh", workflow)
        self.assertIn("tools/emit_hypopg_macos_x86_64_publication.py", workflow)
        self.assertIn("tools/import_hypopg_macos_x86_64_publication.py", workflow)
        self.assertIn("support/verification/hypopg-1.4.3-postgresql-${{ needs.select.outputs.postgresql_version }}-macos-x86_64-current-${{ github.run_id }}.json", workflow)
        self.assertNotIn("macos-arm64", workflow)

    def test_profile_tracks_selected_workflow_inputs(self):
        profile = json.loads(Path("support/verification-profiles.json").read_text())["profiles"][emitter.PROFILE_ID]
        sources = set(profile["sources"])
        self.assertTrue({
            ".github/workflows/hypopg-macos-x86_64-selected-publication.yml",
            "tools/hypopg_macos_target.py",
            "scripts/macos/core-prefix.sh",
            "scripts/hypopg/verify-macos-publication.sh",
            "tools/emit_hypopg_macos_x86_64_publication.py",
            "tools/import_hypopg_macos_x86_64_publication.py",
        } <= sources)
        self.assertFalse(any("hypopg_macos_pins" in source for source in sources))
        self.assertNotIn("scripts/macos/resolve-core.sh", sources)
        self.assertNotIn("tools/macos_core_target_config.py", sources)
        self.assertNotIn(".github/workflows/hypopg-macos-x86_64-publication.yml", sources)
        self.assertNotIn("scripts/hypopg/macos-x86_64-feasibility.sh", sources)

    def test_emits_and_imports_archive_bound_intel_record(self):
        legacy = emitter.implementation
        original = (legacy.PROFILE_ID, legacy.ARCHITECTURE, legacy.PLATFORM)
        paths = self.emit()
        self.assertEqual((legacy.PROFILE_ID, legacy.ARCHITECTURE, legacy.PLATFORM), original)
        record = json.loads(paths[-1].read_text())
        self.assertEqual(record["platform"], "macos-x86_64")
        self.assertEqual(record["assembled_core"]["sha256"], self.core_digest)
        retained = importer.import_run(self.root, self.core, self.output, "12345678901", self.target)
        self.assertTrue(any(path.startswith("support/verification/") for path in retained))
        evidence = self.root / "support/evidence/hypopg-macos-publication-12345678901/x86_64/18.6"
        self.assertTrue((evidence / "current-receipt.json").is_file())
        self.assertTrue((evidence / "probe-output.txt").is_file())

    def test_rejects_artifact_that_does_not_match_resolved_intel_core(self):
        self.emit()
        self.core_archive.write_bytes(b"changed Intel core bytes")
        self._sidecar(self.core_archive)
        with self.assertRaisesRegex(Exception, "selected passed build"):
            emitter.emit(self.root, self.core, self.output, self.output,
                         {"archive-suite": "success", "static-analysis": "success"},
                         "15.7.9", "macos15/20261018.1", self.environ, target=self.target)


if __name__ == "__main__":
    unittest.main()
