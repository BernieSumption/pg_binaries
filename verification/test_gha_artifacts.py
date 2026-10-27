import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verification import gha_artifacts as artifacts
from verification.records import selected_inputs


class RunSelectionTests(unittest.TestCase):
    def test_later_successful_component_replaces_earlier_one(self) -> None:
        target = "macos-arm64"
        components = ["postgresql", "pgvector", "hypopg"]
        listings = {
            10: {artifacts.artifact_name(target, component) for component in components},
            11: {artifacts.artifact_name(target, "pgvector")},
            12: set(),
        }
        with patch.object(artifacts, "run_artifacts", side_effect=listings.get):
            selected = artifacts.choose_runs([10, 11, 12], target, components)
        self.assertEqual(selected, {"postgresql": 10, "pgvector": 11, "hypopg": 10})

    def test_missing_component_stops_selection(self) -> None:
        with patch.object(artifacts, "run_artifacts", return_value=set()):
            with self.assertRaisesRegex(artifacts.SelectionError, "pgvector"):
                artifacts.choose_runs([10], "macos-arm64", ["pgvector"])

    def test_downloaded_records_must_match_postgresql(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = "macos-arm64"
            selected = {"postgresql": 10, "pgvector": 11}
            for component in selected:
                destination = root / "downloads" / component
                destination.mkdir(parents=True)
                archive = destination / artifacts.archive_name(target, component)
                archive.write_bytes(component.encode("ascii"))
                record = {
                    "schema_version": 1,
                    "component": component,
                    "target": target,
                    "git_revision": "0" * 40,
                    "archive": {"filename": archive.name, "sha256": artifacts.sha256(archive)},
                }
                record["sources"], record["build_inputs"] = selected_inputs(
                    artifacts.SUPPORT, target, component)
                if component == "postgresql":
                    development = destination / "postgresql-development-18.6-macos-arm64.tar.gz"
                    development.write_bytes(b"development")
                    record["development_archive"] = {
                        "filename": development.name, "sha256": artifacts.sha256(development)}
                else:
                    record["postgresql_archive"] = {"sha256": "0" * 64}
                (destination / "record.json").write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(artifacts.SelectionError, "different PostgreSQL archive"):
                artifacts.inspect_downloads(selected, target, root)
            postgres_archive = root / "downloads/postgresql" / artifacts.archive_name(target, "postgresql")
            record_path = root / "downloads/pgvector/record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["postgresql_archive"]["sha256"] = artifacts.sha256(postgres_archive)
            record_path.write_text(json.dumps(record), encoding="utf-8")
            manifest = artifacts.inspect_downloads(selected, target, root)
            self.assertEqual(manifest["components"]["pgvector"]["origin_run"], 11)
            record["sources"][0]["sha256"] = "0" * 64
            record_path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(artifacts.SelectionError, "different selected sources"):
                artifacts.inspect_downloads(selected, target, root)


if __name__ == "__main__":
    unittest.main()
