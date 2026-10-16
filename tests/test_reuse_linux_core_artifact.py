import hashlib
import io
import json
from pathlib import Path
import tempfile
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import reuse_linux_core_artifact as reuse


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
ARCHIVE_NAME = "postgresql-18.6-linux-x86_64.tar.gz"


def artifact(record_overrides=None, archive_data=b"core archive", architecture="x86_64"):
    archive_name = f"postgresql-18.6-linux-{architecture}.tar.gz"
    profile = coverage.verification_profile(ROOT, f"linux-pilot-{architecture}")
    record = {
        "outcome": "passed",
        "component": "postgresql",
        "version": "18.6",
        "postgresql_version": "18.6",
        "platform": f"linux-{architecture}",
        "test_revision": SHA,
        "profile_id": profile["profile_id"],
        "profile_revision": profile["profile_revision"],
        "sha256": hashlib.sha256(archive_data).hexdigest(),
        "ci": {
            "run_id": 123,
            "source_revision": SHA,
            "build_revision": SHA,
            "test_revision": SHA,
        },
    }
    record.update(record_overrides or {})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zipped:
        zipped.writestr(archive_name, archive_data)
        zipped.writestr(archive_name + ".sha256", hashlib.sha256(archive_data).hexdigest() + "  " + archive_name)
        zipped.writestr(f"postgresql-18.6-linux-{architecture}-123.json", json.dumps(record))
    return output.getvalue()


class CoreReuseTests(unittest.TestCase):
    def test_extracts_only_verified_core_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            reuse.validate_and_extract(artifact(), ROOT, SHA, "18.6", 123, output)
            self.assertEqual((output / ARCHIVE_NAME).read_bytes(), b"core archive")
            self.assertTrue((output / (ARCHIVE_NAME + ".sha256")).is_file())

    def test_arm64_reuse_selects_matching_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            reuse.validate_and_extract(artifact(architecture="arm64"), ROOT, SHA,
                                       "18.6", 123, output, "arm64")
            self.assertEqual({p.name for p in output.iterdir()}, {
                "postgresql-18.6-linux-arm64.tar.gz",
                "postgresql-18.6-linux-arm64.tar.gz.sha256"})

    def test_arm64_ignores_unrelated_artifact_members(self):
        blob = io.BytesIO(artifact(architecture="arm64"))
        with zipfile.ZipFile(blob, "a") as zipped:
            zipped.writestr("postgresql-18.6-linux-arm64-minimum-123.json", "{}")
            zipped.writestr("diagnostics/server.log", "first")
            zipped.writestr("evidence/server.log", "second")
        with tempfile.TemporaryDirectory() as directory:
            reuse.validate_and_extract(blob.getvalue(), ROOT, SHA, "18.6", 123,
                                       Path(directory), "arm64")
            self.assertEqual(len(list(Path(directory).iterdir())), 2)

    def test_arm64_rejects_x86_record(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "platform"):
                reuse.validate_and_extract(artifact({"platform": "linux-x86_64"},
                                                   architecture="arm64"),
                                           ROOT, SHA, "18.6", 123, Path(directory), "arm64")

    def test_run_selection_is_architecture_specific(self):
        runs = [{"name": values[0], "path": values[1], "head_sha": SHA,
                 "conclusion": "success", "id": architecture}
                for architecture, values in reuse.TARGETS.items()]
        for architecture in reuse.TARGETS:
            self.assertEqual(reuse.select_run(runs, SHA, architecture)["id"], architecture)

    def test_rejects_different_source_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "commit"):
                reuse.validate_and_extract(
                    artifact({"test_revision": "b" * 40}), ROOT, SHA, "18.6", 123, Path(directory)
                )

    def test_rejects_wrong_platform_and_profile(self):
        for changes, expected in (({"platform": "linux-arm64"}, "platform"),
                                  ({"profile_revision": -1}, "profile")):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(ValueError, expected):
                    reuse.validate_and_extract(
                        artifact(changes), ROOT, SHA, "18.6", 123, Path(directory)
                    )

    def test_rejects_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "checksum"):
                reuse.validate_and_extract(
                    artifact({"sha256": "0" * 64}), ROOT, SHA, "18.6", 123,
                    Path(directory)
                )


if __name__ == "__main__":
    unittest.main()
