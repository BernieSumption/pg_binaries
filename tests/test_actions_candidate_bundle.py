import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile


SPEC = importlib.util.spec_from_file_location(
    "actions_candidate_bundle", Path(__file__).resolve().parents[1] / "tools" / "actions_candidate_bundle.py")
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class ActionsCandidateBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def zip_file(self, members, name="bundle.zip"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for path, data in members:
                archive.writestr(path, data)
        result = self.root / name
        result.write_bytes(buffer.getvalue())
        return result

    def test_extracts_verified_archive_pairs_and_verification_records(self):
        pg = "postgresql-15.10-linux-x86_64.tar.gz"
        extension = "pgvector-0.8.0-postgresql-15.10-linux-x86_64.tar.gz"
        files = {pg: b"postgres bytes", extension: b"extension bytes",
                 "postgresql.json": b'{"verified": true}',
                 "pgvector.json": b'{"verified": true}'}
        members = [("bundle/" + name, content) for name, content in files.items()]
        for name in (pg, extension):
            content = files[name]
            members.append(("bundle/" + name + ".sha256",
                            f"{hashlib.sha256(content).hexdigest()}  {name}\n".encode()))
        zip_path = self.zip_file(members)
        allowlist = ["bundle/" + name for name in files]
        allowlist.extend("bundle/" + name + ".sha256" for name in (pg, extension))
        output = bundle.extract_bundle(zip_path, allowlist, self.root / "out",
                                       archive_paths=["bundle/" + pg, "bundle/" + extension])
        self.assertEqual(set(output), set(allowlist))
        self.assertEqual(output["bundle/" + pg].read_bytes(), files[pg])
        self.assertEqual(output["bundle/postgresql.json"].read_bytes(), files["postgresql.json"])

    def test_rejects_dot_and_aliases_that_resolve_to_one_member(self):
        zip_path = self.zip_file([("bundle/file", b"content")])
        with self.assertRaisesRegex(bundle.BundleError, "unsafe"):
            bundle.extract_bundle(zip_path, ["."], self.root / "dot")
        with self.assertRaisesRegex(bundle.BundleError, "same ZIP member"):
            bundle.extract_bundle(zip_path, ["bundle/file", "file"], self.root / "aliases")
        self.assertFalse((self.root / "aliases" / "bundle" / "file").exists())

    def test_rejects_duplicate_and_unsafe_zip_paths_without_outputs(self):
        cases = [([("one/file", b"1"), ("one/file", b"2")], "duplicate"),
                 ([("../escape", b"x"), ("safe", b"y")], "unsafe")]
        for members, expected in cases:
            with self.subTest(expected=expected):
                zip_path = self.zip_file(members, expected + ".zip")
                output = self.root / (expected + "-out")
                with self.assertRaisesRegex(bundle.BundleError, expected):
                    bundle.extract_bundle(zip_path, ["safe"], output)
                self.assertFalse((output / "safe").exists())

    def test_rejects_mismatched_sidecar_without_partial_output(self):
        name = "pgvector.tar.gz"
        zip_path = self.zip_file([(name, b"archive"), (name + ".sha256", ("0" * 64 + "  " + name).encode())])
        output = self.root / "out"
        with self.assertRaisesRegex(bundle.BundleError, "sidecar checksum"):
            bundle.extract_bundle(zip_path, [name, name + ".sha256"], output, archive_paths=[name])
        self.assertFalse((output / name).exists())
        self.assertFalse((output / (name + ".sha256")).exists())

    def test_preserves_existing_destination_on_failure(self):
        zip_path = self.zip_file([("record.json", b"new")])
        output = self.root / "out"
        output.mkdir()
        existing = output / "record.json"
        existing.write_bytes(b"original")
        with self.assertRaisesRegex(bundle.BundleError, "already exists"):
            bundle.extract_bundle(zip_path, ["record.json"], output)
        self.assertEqual(existing.read_bytes(), b"original")

    def test_enforces_total_size_bound_without_partial_output(self):
        zip_path = self.zip_file([("first", b"1234"), ("second", b"5678")])
        output = self.root / "out"
        with self.assertRaisesRegex(bundle.BundleError, "total size"):
            bundle.extract_bundle(zip_path, ["first", "second"], output, max_total_bytes=7)
        self.assertFalse((output / "first").exists())
        self.assertFalse((output / "second").exists())

    def test_resolves_unique_basename_but_rejects_ambiguous_basename(self):
        zip_path = self.zip_file([("only/location/record.json", b"ok")])
        result = bundle.extract_bundle(zip_path, ["record.json"], self.root / "unique")
        self.assertEqual(result["record.json"].read_bytes(), b"ok")
        ambiguous = self.zip_file([("left/record.json", b"1"), ("right/record.json", b"2")], "ambiguous.zip")
        with self.assertRaisesRegex(bundle.BundleError, "ambiguous"):
            bundle.extract_bundle(ambiguous, ["record.json"], self.root / "ambiguous")

    def test_download_rejects_invalid_github_identity_before_network(self):
        digest = "sha256:" + "0" * 64
        for repository, artifact_id in (("owner/../other", "42"), ("owner/repo", "0")):
            with self.subTest(repository=repository, artifact_id=artifact_id):
                with self.assertRaises(bundle.BundleError):
                    bundle.download_and_extract_bundle(
                        repository, artifact_id, digest, ["record.json"], self.root / "invalid")


if __name__ == "__main__":
    unittest.main()
