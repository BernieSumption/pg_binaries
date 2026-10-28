import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

from verification.linux import release
from verification.records import selected_inputs


class LinuxReleaseTests(unittest.TestCase):
    def test_verifies_each_package_postgresql_only_and_all_packages(self) -> None:
        support = json.loads((release.ROOT / "support.json").read_text(encoding="utf-8"))
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
            for component in ["postgresql", *support["packages"]]:
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
                }
                if component != "postgresql":
                    record["postgresql_archive"] = {"filename": postgresql.name, "sha256": pg_hash}
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

            with mock.patch.object(release.platform, "system", return_value="Linux"), \
                    mock.patch.object(release.platform, "machine", return_value="aarch64"), \
                    mock.patch.object(release, "linux_version", return_value="Ubuntu fixture"), \
                    mock.patch.object(release, "git_revision", return_value="1" * 40), \
                    mock.patch.object(release, "builtin_controls", return_value=["plpgsql"]), \
                    mock.patch.object(release, "verify", side_effect=lambda *_: [
                        {"name": "fixture", "outcome": "passed", "reason": None}
                    ]) as verify:
                result = release.main(argv)
                self.assertEqual(result, 0, (root / "report/verification-report.json").read_text())

            combinations = json.loads((root / "report/verification-report.json").read_text())[
                "combinations"
            ]
            expected = [*support["packages"], "postgresql-only", "all-packages"]
            self.assertEqual([item["name"] for item in combinations], expected)
            self.assertTrue(all(item["outcome"] == "passed" for item in combinations))
            self.assertEqual(verify.call_count, len(expected))


if __name__ == "__main__":
    unittest.main()
