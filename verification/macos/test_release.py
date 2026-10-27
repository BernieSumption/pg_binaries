from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from verification.macos import release
from verification.records import selected_inputs


class BuildRecordSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        support = json.loads((release.ROOT / "support.json").read_text(encoding="utf-8"))
        self.names = ["postgresql", *support["packages"]]
        self.args = ["release.py", str(self.root / "postgresql.tar.gz"), str(self.root / "report")]
        self.records = {}
        for name in self.names:
            archive = self.root / f"{name}.tar.gz"
            archive.write_bytes(name.encode("ascii"))
            if name != "postgresql":
                self.args.extend(["--package-archive", f"{name}={archive}"])
            record = {
                "schema_version": 1,
                "component": name,
                "target": release.TARGET,
                "git_revision": "0" * 40,
                "archive": {"filename": archive.name, "sha256": release.sha256(archive)},
            }
            record["sources"], record["build_inputs"] = selected_inputs(support, release.TARGET, name)
            self.records[name] = record
        for name in self.names[1:]:
            self.records[name]["postgresql_archive"] = {
                "sha256": self.records["postgresql"]["archive"]["sha256"]}

    def invoke(self, checks=None, origin_runs=False) -> int:
        for name, record in self.records.items():
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            self.args.extend(["--build-record", f"{name}={path}"])
        if origin_runs:
            for index, name in enumerate(self.names, start=1):
                self.args.extend(["--origin-run", f"{name}={index}"])
        with patch.object(sys, "argv", self.args), \
             patch.object(release.platform, "system", return_value="Darwin"), \
             patch.object(release.platform, "machine", return_value="arm64"), \
             patch.object(release, "builtin_controls", return_value=["citext"]), \
             patch.object(release, "verify") as verify:
            verify.return_value = checks if checks is not None else [
                {"name": "archive safety and overlap", "outcome": "passed", "reason": None}]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = release.main()
            self.assertEqual(verify.call_count, len(self.names) + 1)
            return result

    def test_complete_selection_records_all_combinations(self) -> None:
        self.assertEqual(self.invoke(), 0)
        report = json.loads((self.root / "report/verification-report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["combinations"]), len(self.names) + 1)
        self.assertEqual(report["combinations"][0]["checks"][0]["outcome"], "passed")
        self.assertEqual(report["postgresql_builtin_extensions"], ["citext"])

    def test_reads_builtin_controls_from_postgresql_archive(self) -> None:
        archive = self.root / "builtins.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            root = tarfile.TarInfo("postgresql")
            root.type = tarfile.DIRTYPE
            output.addfile(root)
            for name, payload in (
                ("postgresql/LICENCE", b"See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md"),
                ("postgresql/share/extension/citext.control", b"comment = 'citext'\n"),
                ("postgresql/share/extension/hstore.control", b"comment = 'hstore'\n"),
            ):
                entry = tarfile.TarInfo(name)
                entry.size = len(payload)
                output.addfile(entry, io.BytesIO(payload))
        self.assertEqual(release.builtin_controls(archive), ["citext", "hstore"])

    def test_rejects_extension_built_against_another_postgresql_archive(self) -> None:
        self.records[self.names[1]]["postgresql_archive"]["sha256"] = "0" * 64
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / "report").exists())

    def test_rejects_stale_build_inputs(self) -> None:
        self.records["postgresql"]["build_inputs"] = {}
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / "report").exists())

    def test_rejects_stale_source_selection(self) -> None:
        self.records[self.names[1]]["sources"][0]["sha256"] = "0" * 64
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / "report").exists())

    def test_rejects_missing_build_revision(self) -> None:
        del self.records["postgresql"]["git_revision"]
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)

    def test_failed_check_fails_combination_and_release(self) -> None:
        checks = [{"name": "SQL probes", "outcome": "failed", "reason": "probe failed"}]
        self.assertEqual(self.invoke(checks), 1)
        report = json.loads((self.root / "report/verification-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["combinations"][0]["outcome"], "failed")
        self.assertEqual(report["combinations"][0]["checks"], checks)

    def test_required_check_that_cannot_run_fails_release(self) -> None:
        checks = [{"name": "SQL probes", "outcome": "not_run", "reason": "startup failed"}]
        self.assertEqual(self.invoke(checks), 1)
        report = json.loads((self.root / "report/verification-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["combinations"][0]["outcome"], "failed")

    def test_inapplicable_check_does_not_fail_release(self) -> None:
        checks = [{"name": "PostgreSQL built-ins", "outcome": "not_applicable",
                   "reason": "covered by the PostgreSQL-only combination"}]
        self.assertEqual(self.invoke(checks), 0)

    def test_records_archive_origin_runs(self) -> None:
        self.assertEqual(self.invoke(origin_runs=True), 0)
        report = json.loads((self.root / "report/verification-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["archives"]["postgresql"]["origin_run"], 1)
        self.assertEqual(report["archives"][self.names[1]]["origin_run"], 2)

    def test_rejects_incomplete_origin_runs(self) -> None:
        self.args.extend(["--origin-run", "postgresql=1"])
        with self.assertRaises(SystemExit) as error:
            self.invoke()
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / "report").exists())


if __name__ == "__main__":
    unittest.main()
