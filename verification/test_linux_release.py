import hashlib
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

from verification.linux import release
from verification.records import selected_inputs
from build_support.metadata import load_selection, packages as package_metadata


class LinuxReleaseTests(unittest.TestCase):
    def test_verifies_each_package_postgresql_only_and_all_packages(self) -> None:
        support = load_selection(release.ROOT / "support.json")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = "linux-arm64"
            postgresql = root / f"postgresql-{target}.tar.gz"
            with tarfile.open(postgresql, "w:gz") as archive:
                control = root / "vector.control"
                control.write_text("comment = 'fixture'\n", encoding="utf-8")
                archive.add(control, "postgresql/share/extension/plpgsql.control")

            packages = {}
            records = {}
            pg_hash = hashlib.sha256(postgresql.read_bytes()).hexdigest()
            for component in ["postgresql", *package_metadata()]:
                archive_path = postgresql if component == "postgresql" else root / f"{component}.tar.gz"
                if component != "postgresql":
                    archive_path.write_bytes(f"archive:{component}".encode())
                    packages[component] = archive_path
                sources, build_inputs = selected_inputs(support, target, component)
                digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
                record = {
                    "schema_version": 1,
                    "component": component,
                    "target": target,
                    "git_revision": "0" * 40,
                    "sources": sources,
                    "build_inputs": build_inputs,
                    "archive": {"filename": archive_path.name, "sha256": digest},
                    "postgresql_version": "18.6",
                }
                if component != "postgresql":
                    record["postgresql_archive"] = {"filename": postgresql.name, "sha256": pg_hash}
                    record["postgresql_development_archive"] = {"sha256": "a" * 64}
                else:
                    record["development_archive"] = {"sha256": "a" * 64}
                record_path = root / f"{component}.json"
                record_path.write_text(json.dumps(record), encoding="utf-8")
                records[component] = record_path

            argv = [str(postgresql), str(root / "report")]
            for component, archive_path in packages.items():
                argv.extend(("--package-archive", f"{component}={archive_path}"))
            for component, record_path in records.items():
                argv.extend(("--build-record", f"{component}={record_path}"))
            for component in records:
                argv.extend(("--origin-run", f"{component}=123"))

            def fake_verify(postgres, selected, output, target):
                versions = {name: "test-sql-version" for package in selected
                            for name in package_metadata()[package]["extensions"]}
                return [{"name": "dependency symbol isolation", "outcome": "passed"}, {"name": "PostgreSQL version", "outcome": "passed", "reason": None, "version": "18.6"},
                        {"name": "SQL probes", "outcome": "passed", "reason": None, "extension_versions": versions}]

            with mock.patch.object(release.platform, "system", return_value="Linux"), \
                    mock.patch.object(release.platform, "machine", return_value="aarch64"), \
                    mock.patch.object(release, "linux_version", return_value="Ubuntu fixture"), \
                    mock.patch.object(release, "git_revision", return_value="1" * 40), \
                    mock.patch.object(release, "builtin_controls", return_value=["plpgsql"]), \
                    mock.patch.object(release, "verify", side_effect=fake_verify) as verify:
                result = release.main(argv)
                self.assertEqual(result, 0, (root / "report/verification-report.json").read_text())
                changed = json.loads(records["pgvector"].read_text())
                changed["postgresql_development_archive"]["sha256"] = "b" * 64
                records["pgvector"].write_text(json.dumps(changed))
                error_output = io.StringIO()
                with redirect_stderr(error_output), self.assertRaises(SystemExit):
                    release.main(argv)
                self.assertIn("different PostgreSQL development archive", error_output.getvalue())

            combinations = json.loads((root / "report/verification-report.json").read_text())[
                "combinations"
            ]
            expected = [*package_metadata(), "postgresql-only", "all-packages"]
            self.assertEqual([item["name"] for item in combinations], expected)
            self.assertTrue(all(item["outcome"] == "passed" for item in combinations))
            self.assertEqual(verify.call_count, len(expected))


if __name__ == "__main__":
    unittest.main()
