import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from verification.publication_preflight import PreflightError, check
from verification.inventory import RELEASE_BASE, make_inventory
from build_support.metadata import load_selection
from verification.records import selected_inputs


class PublicationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.support_path = self.root / "support.json"
        self.support_path.write_text(json.dumps({"targets": {"macos-arm64": {"minimum_os_version": "11.0"}}}))
        for package, project in (("postgresql", "PostgreSQL"), ("pgvector", "pgvector")):
            folder = self.root / "packages" / package
            folder.mkdir(parents=True)
            metadata = {"sources": {package: {"project": project, "url": "https://example.com/source.tar.gz", "sha256": "a" * 64}}}
            if package == "pgvector":
                metadata["extensions"] = {"vector": {}}
                (folder / "probes").mkdir()
                (folder / "probes/vector.sql").write_text("SELECT 1;")
            (folder / "build.json").write_text(json.dumps(metadata))
            (folder / "build.sh").write_text("#!/bin/sh\n")
        self.support = load_selection(self.support_path)
        self.licences_path = self.root / "LICENSES.md"
        self.licences_path.write_text("# Licences\n\n- PostgreSQL — PostgreSQL License.\n- pgvector — PostgreSQL License.\n")
        self.paths = {}
        archives = {}
        components = {}
        build_records = {}
        for name in ("postgresql", "pgvector"):
            filename = (f"postgresql-18.6-macos-arm64.tar.gz" if name == "postgresql"
                        else f"{name}-postgresql-18.6-macos-arm64.tar.gz")
            path = self.root / filename
            with tarfile.open(path, "w:gz") as output:
                directory = tarfile.TarInfo("postgresql")
                directory.type = tarfile.DIRTYPE
                output.addfile(directory)
                payload = b"See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md"
                licence = tarfile.TarInfo("postgresql/LICENCE")
                licence.size = len(payload)
                output.addfile(licence, io.BytesIO(payload))
                control_name = "citext" if name == "postgresql" else "vector"
                control = tarfile.TarInfo(f"postgresql/share/extension/{control_name}.control")
                control.size = 1
                output.addfile(control, io.BytesIO(b"x"))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            archives[name] = {"filename": path.name, "sha256": digest,
                              "origin_run": 7 if name == "postgresql" else 8}
            components[name] = {"archive": str(path), "sha256": digest,
                                "origin_run": archives[name]["origin_run"]}
            sources, inputs = selected_inputs(self.support, "macos-arm64", name, root=self.root)
            build_records[name] = {"component": name, "target": "macos-arm64", "postgresql_version": "18.6",
                                   "archive": {"filename": path.name, "sha256": digest},
                                   "sources": sources, "build_inputs": inputs}
        build_records["pgvector"]["postgresql_archive"] = dict(build_records["postgresql"]["archive"])
        self.paths = {name: self.root / f"{name}.tar.gz" for name in archives}
        report = {"target": "macos-arm64", "archives": archives,
                  "build_records": build_records,
                  "postgresql_version": "18.6", "extension_versions": {"vector": "0.8.7"},
                  "combinations": [{"name": name, "outcome": "passed"}
                                   for name in ("postgresql-only", "pgvector", "all-packages")],
                  "postgresql_builtin_extensions": ["citext"]}
        selection = {"target": "macos-arm64", "components": components}
        self.report_path, self.selection_path = self.root / "report.json", self.root / "selection.json"
        self.report_path.write_text(json.dumps(report))
        self.selection_path.write_text(json.dumps(selection))
        self.inventory = make_inventory([self.report_path], "candidate", self.support,
                                        today="2026-01-01", suffix="abcd1234")
        self.inventory_path = self.root / "inventory.json"
        self.save_inventory()

    def save_inventory(self):
        self.inventory_path.write_text(json.dumps(self.inventory))

    def test_passes_complete_local_preflight(self):
        count = check(self.inventory_path,
                      [("macos-arm64", self.selection_path, self.report_path)], self.support_path)
        self.assertEqual(count, 1)

    def test_rejects_missing_project_licence_entry(self):
        self.licences_path.write_text("# Licences\n\n- PostgreSQL — PostgreSQL License.\n")
        with self.assertRaisesRegex(PreflightError, "missing licence entries.*pgvector"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_sources_changed_after_verification(self):
        path = self.root / "packages/pgvector/build.json"
        metadata = json.loads(path.read_text())
        metadata["sources"]["pgvector"]["sha256"] = "b" * 64
        path.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(PreflightError, "differs from current sources or build inputs"):
            check(self.inventory_path, [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_private_lock_changed_after_verification(self):
        internal = self.root / "packages/pgvector/internal"
        internal.mkdir()
        lock = internal / "dependency.lock"
        lock.write_text("original locked dependency\n")
        report = json.loads(self.report_path.read_text())
        _, inputs = selected_inputs(self.support, "macos-arm64", "pgvector", root=self.root)
        report["build_records"]["pgvector"]["build_inputs"] = inputs
        self.report_path.write_text(json.dumps(report))
        self.assertEqual(check(self.inventory_path, [("macos-arm64", self.selection_path, self.report_path)], self.support_path), 1)
        lock.write_text("different locked dependency\n")
        with self.assertRaisesRegex(PreflightError, "differs from current sources or build inputs"):
            check(self.inventory_path, [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_missing_embedded_build_records(self):
        report = json.loads(self.report_path.read_text())
        del report["build_records"]["pgvector"]
        self.report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(PreflightError, "build records must include every component"):
            check(self.inventory_path, [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_build_record_for_other_archive_or_version(self):
        original = self.report_path.read_text()
        for field, value in (("archive", {"filename": "wrong.tar.gz", "sha256": "0" * 64}), ("postgresql_version", "18.5")):
            report = json.loads(original)
            report["build_records"]["postgresql"][field] = value
            self.report_path.write_text(json.dumps(report))
            with self.subTest(field=field), self.assertRaises(PreflightError):
                check(self.inventory_path, [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_local_origins(self):
        selection = json.loads(self.selection_path.read_text())
        selection["components"]["pgvector"]["origin_run"] = None
        self.selection_path.write_text(json.dumps(selection))
        with self.assertRaisesRegex(PreflightError, "selection and report disagree"):
            check(self.inventory_path, [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_accepts_renamed_development_archive_with_same_bytes(self):
        report = json.loads(self.report_path.read_text())
        report["build_records"]["postgresql"]["development_archive"] = {
            "filename": "postgresql-development-18.6-macos-arm64.tar.gz", "sha256": "a" * 64}
        report["build_records"]["pgvector"]["postgresql_development_archive"] = {
            "filename": "development.tar.gz", "sha256": "a" * 64}
        self.report_path.write_text(json.dumps(report))
        self.assertEqual(check(self.inventory_path, [("macos-arm64", self.selection_path, self.report_path)], self.support_path), 1)

    def test_rejects_different_or_invalid_development_archive_hash(self):
        original = self.report_path.read_text()
        for digest in ("b" * 64, None, "invalid", 1):
            report = json.loads(original)
            report["build_records"]["postgresql"]["development_archive"] = {
                "filename": "postgresql-development-18.6-macos-arm64.tar.gz", "sha256": "a" * 64}
            report["build_records"]["pgvector"]["postgresql_development_archive"] = {
                "filename": "development.tar.gz", "sha256": digest}
            self.report_path.write_text(json.dumps(report))
            with self.subTest(digest=digest), self.assertRaisesRegex(PreflightError, "different PostgreSQL development archive"):
                check(self.inventory_path, [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_missing_copied_dependency_licence_entry(self):
        path = self.root / "packages/postgresql/build.json"
        metadata = json.loads(path.read_text())
        metadata["sources"]["icu"] = {"project": "ICU4C", "url": "https://example.com/icu.tar.gz", "sha256": "b" * 64}
        path.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(PreflightError, "missing licence entries.*ICU4C"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_wrong_inventory_sha(self):
        self.inventory["packages"]["pgvector"]["downloads"]["macos-arm64"]["sha256"] = "0" * 64
        self.save_inventory()
        with self.assertRaisesRegex(PreflightError, "does not match"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_wrong_extension_package_mapping(self):
        self.inventory["extensions"]["vector"]["package"] = "postgresql"
        self.save_inventory()
        with self.assertRaisesRegex(PreflightError, "do not match verification report"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_download_url_for_other_bytes(self):
        self.inventory["packages"]["pgvector"]["downloads"]["macos-arm64"]["url"] = (
            f"{RELEASE_BASE}/candidate/other.tar.gz")
        self.save_inventory()
        with self.assertRaisesRegex(PreflightError, "download does not match"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_wrong_declared_metadata(self):
        self.inventory["extensions"]["vector"]["version"] = "wrong"
        self.save_inventory()
        with self.assertRaisesRegex(PreflightError, "extensions"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_different_release_tags(self):
        download = self.inventory["packages"]["pgvector"]["downloads"]["macos-arm64"]
        download["url"] = download["url"].replace("/candidate/", "/other/")
        self.save_inventory()
        with self.assertRaisesRegex(PreflightError, "one shared release tag"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_invalid_inventory_version(self):
        self.inventory["inventory_version"] = "18.6-not-a-date-abcd1234"
        self.save_inventory()
        with self.assertRaisesRegex(PreflightError, "inventory_version"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)


if __name__ == "__main__":
    unittest.main()
