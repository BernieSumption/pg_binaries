import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))
import pgvector_candidate_bundle as candidate
import actions_candidate_discovery as discovery


class PgvectorCandidateBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repository = "example/project"
        self.version = "0.8.7"
        self.pg = "17.11"
        self.arch = "x86_64"
        self.run = {"id": 123, "run_number": 8, "run_attempt": 2,
                    "repository": {"full_name": self.repository},
                    "head_repository": {"full_name": self.repository},
                    "head_sha": "a" * 40, "path": ".github/workflows/pgvector-linux-selected-publication.yml",
                    "head_branch": "spike", "event": "push", "status": "completed", "conclusion": "success"}
        self.files = {
            f"postgresql-{self.pg}-linux-{self.arch}.tar.gz": b"core bytes",
            f"pgvector-{self.version}-postgresql-{self.pg}-linux-{self.arch}.tar.gz": b"vector bytes",
            f"postgresql-{self.pg}-linux-{self.arch}-current-123.json": b'{"verified":true}',
            f"pgvector-{self.version}-postgresql-{self.pg}-linux-{self.arch}-current-123.json": b'{"verified":true}',
        }
        self.symbols = {
            "postgresql-17.11-linux-x86_64/postgresql/lib/postgres.debug": b"core debug symbols",
            "pgvector-0.8.7-postgresql-17.11-linux-x86_64/postgresql/lib/vector.so.debug": b"vector debug symbols",
        }
        index_rows = []
        for archive_name, symbol_path, content in (
                (f"postgresql-{self.pg}-linux-{self.arch}.tar.gz", next(iter(self.symbols)),
                 next(iter(self.symbols.values()))),
                (f"pgvector-{self.version}-postgresql-{self.pg}-linux-{self.arch}.tar.gz",
                 list(self.symbols)[1], list(self.symbols.values())[1])):
            index_rows.append({"archive": archive_name,
                               "archive_sha256": hashlib.sha256(self.files[archive_name]).hexdigest(),
                               "debug_file_path": symbol_path,
                               "debug_file_sha256": hashlib.sha256(content).hexdigest(),
                               "module_path": symbol_path.removesuffix(".debug"),
                               "module_sha256": "a" * 64, "gnu_build_id": "b" * 40})
        members = []
        for name, data in self.files.items():
            location = "_temp/bundle/pilot/publication/records/" if name.endswith(".json") else "_temp/bundle/pilot/"
            members.append((location + name, data))
        for name, data in self.files.items():
            if name.endswith(".tar.gz"):
                members.append(("_temp/bundle/pilot/" + name + ".sha256",
                                f"{hashlib.sha256(data).hexdigest()}  {name}\n".encode()))
        members.append(("_temp/bundle/pilot/debug-symbols/index.json",
                        json.dumps({"schema_version": 1, "files": index_rows}).encode()))
        members.extend(("_temp/bundle/pilot/debug-symbols/" + name, data)
                       for name, data in self.symbols.items())
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in members:
                archive.writestr(name, data)
        self.zip_bytes = buffer.getvalue()
        self.zip_by_artifact = {"456": self.zip_bytes}
        self.artifact = {"id": 456, "name": "pgvector-linux-selected-17.11-123",
                         "workflow_run": {"id": 123, "head_sha": self.run["head_sha"]},
                         "expired": False, "expires_at": "2099-01-01T00:00:00Z",
                         "size_in_bytes": len(self.zip_bytes),
                         "digest": "sha256:" + hashlib.sha256(self.zip_bytes).hexdigest()}
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def fake_api(self, args):
        endpoint = args[0]
        self.calls.append(endpoint)
        if "/actions/runs?" in endpoint:
            return {"workflow_runs": [self.run]}
        if "/actions/runs/123/artifacts" in endpoint:
            return {"artifacts": [self.artifact]}
        raise AssertionError(endpoint)

    def fake_download(self, args, **kwargs):
        artifact_id = args[2].rsplit("/", 2)[-2]
        self.assertIn(artifact_id, self.zip_by_artifact)
        kwargs["stdout"].write(self.zip_by_artifact[artifact_id])
        return subprocess.CompletedProcess(args, 0, None, b"")

    def invoke(self):
        return candidate.retrieve(repository=self.repository, branch="spike", current_run_id="999",
            version=self.version, postgresql_version=self.pg, architecture=self.arch,
            output_directory=self.root / "out", manifest_path=self.root / "manifest.json")

    def test_retrieves_all_files_and_writes_machine_manifest(self):
        with patch.object(discovery, "_gh", side_effect=self.fake_api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            manifest = self.invoke()
        self.assertEqual(manifest["source"]["run_id"], "123")
        self.assertEqual(manifest["source"]["run_attempt"], 2)
        self.assertEqual(manifest["source"]["artifact_name"], self.artifact["name"])
        self.assertEqual(manifest["source"]["artifact_zip_digest"], self.artifact["digest"])
        self.assertIn("profile and build-input checks remain", manifest["eligibility"])
        written = json.loads((self.root / "manifest.json").read_text())
        self.assertEqual(written, manifest)
        for name, content in self.files.items():
            path = Path(manifest["files"][name])
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(manifest["sha256"][name], hashlib.sha256(content).hexdigest())
        for name, content in self.symbols.items():
            key = "debug-symbols/" + name
            self.assertEqual(Path(manifest["files"][key]).read_bytes(), content)
            self.assertEqual(manifest["sha256"][key], hashlib.sha256(content).hexdigest())
        self.assertIn("debug-symbols/index.json", manifest["files"])

    def test_rejects_symbol_paths_that_do_not_match_the_index(self):
        with zipfile.ZipFile(io.BytesIO(self.zip_bytes)) as source:
            members = [(item.filename, source.read(item)) for item in source.infolist()]
        members.append(("_temp/bundle/pilot/debug-symbols/orphan.debug", b"extra"))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in members:
                archive.writestr(name, data)
        archive_path = self.root / "extra.zip"
        archive_path.write_bytes(buffer.getvalue())
        with self.assertRaisesRegex(candidate.CandidateBundleError, "extra, or unsafe"):
            candidate._symbol_paths(
                archive_path, next(name for name in self.files if name.startswith("postgresql-")),
                next(name for name in self.files if name.startswith("pgvector-")),
                "_temp/bundle/pilot/" + next(name for name in self.files if name.startswith("postgresql-")),
                "_temp/bundle/pilot/" + next(name for name in self.files if name.startswith("pgvector-")))

    def test_usable_newest_candidate_stops_artifact_queries(self):
        with patch.object(discovery, "_gh", side_effect=self.fake_api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            self.invoke()
        artifact_queries = [call for call in self.calls if "/actions/runs/" in call and "/artifacts" in call]
        self.assertEqual(artifact_queries, ["repos/example/project/actions/runs/123/artifacts?per_page=100"])
        run_queries = [call for call in self.calls if "/actions/runs?" in call]
        self.assertEqual(len(run_queries), 1)
        self.assertIn("page=1", run_queries[0])

    def test_candidate_on_later_run_page_is_retrieved(self):
        unrelated = [dict(self.run, id=1000 - index, run_number=1000 - index,
                          path=".github/workflows/other.yml") for index in range(100)]

        def api(args):
            endpoint = args[0]
            self.calls.append(endpoint)
            if "/actions/runs?" in endpoint and "&page=1" in endpoint:
                return {"workflow_runs": unrelated}
            if "/actions/runs?" in endpoint and "&page=2" in endpoint:
                return {"workflow_runs": [self.run]}
            if "/actions/runs/123/artifacts" in endpoint:
                return {"artifacts": [self.artifact]}
            raise AssertionError(endpoint)

        with patch.object(discovery, "_gh", side_effect=api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            result = self.invoke()
        self.assertEqual(result["source"]["run_id"], "123")
        run_queries = [call for call in self.calls if "/actions/runs?" in call]
        self.assertEqual(len(run_queries), 2)
        self.assertIn("page=2", run_queries[1])

    def test_accepts_shared_dispatcher_producer(self):
        self.run["path"] = ".github/workflows/selected-extension-publication.yml"
        with patch.object(discovery, "_gh", side_effect=self.fake_api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            result = self.invoke()
        self.assertEqual(result["source"]["workflow"], "selected-extension-publication.yml")

    def test_fails_on_multiple_matching_runs(self):
        other = dict(self.run, id=124, run_number=9)
        other_artifact = dict(self.artifact, id=457, name="pgvector-linux-selected-17.11-124",
                              workflow_run={"id": 124, "head_sha": other["head_sha"]})
        newer_members = []
        with zipfile.ZipFile(io.BytesIO(self.zip_bytes)) as source:
            for item in source.infolist():
                name = item.filename.replace("current-123.json", "current-124.json")
                newer_members.append((name, source.read(item)))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in newer_members:
                archive.writestr(name, data)
        self.zip_by_artifact["457"] = buffer.getvalue()
        other_artifact["digest"] = "sha256:" + hashlib.sha256(self.zip_by_artifact["457"]).hexdigest()
        def api(args):
            if "/actions/runs?" in args[0]:
                return {"workflow_runs": [self.run, other]}
            return {"artifacts": [self.artifact if "/123/" in args[0] else other_artifact]}
        with patch.object(discovery, "_gh", side_effect=api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            result = self.invoke()
        self.assertEqual(result["source"]["run_id"], "124")

    def test_duplicate_exact_artifacts_within_run_are_rejected(self):
        duplicate = dict(self.artifact, id=457)
        with patch.object(discovery, "_gh", side_effect=lambda args: (
                {"workflow_runs": [self.run]} if "/actions/runs?" in args[0]
                else {"artifacts": [self.artifact, duplicate]})):
            with self.assertRaisesRegex(candidate.CandidateBundleError, "duplicate exact"):
                self.invoke()

    def test_run_id_order_is_global_across_workflows(self):
        older = dict(self.run, run_number=99)
        newer = dict(self.run, id=124, run_number=1,
                     path=".github/workflows/selected-extension-publication.yml")
        artifact = dict(self.artifact, id=457, name="pgvector-linux-selected-17.11-124",
                        workflow_run={"id": 124, "head_sha": newer["head_sha"]})
        newer_members = []
        with zipfile.ZipFile(io.BytesIO(self.zip_bytes)) as source:
            for item in source.infolist():
                newer_members.append((item.filename.replace("current-123.json", "current-124.json"),
                                      source.read(item)))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive_zip:
            for name, data in newer_members:
                archive_zip.writestr(name, data)
        self.zip_by_artifact["457"] = buffer.getvalue()
        artifact["digest"] = "sha256:" + hashlib.sha256(self.zip_by_artifact["457"]).hexdigest()

        def api(args):
            if "/actions/runs?" in args[0]:
                return {"workflow_runs": [older, newer]}
            if "/actions/runs/123/artifacts" in args[0]:
                return {"artifacts": [self.artifact]}
            if "/actions/runs/124/artifacts" in args[0]:
                return {"artifacts": [artifact]}
            raise AssertionError(args[0])

        with patch.object(discovery, "_gh", side_effect=api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            result = self.invoke()
        self.assertEqual(result["source"]["run_id"], "124")

    def test_non_list_artifact_response_is_skipped(self):
        newer = dict(self.run, id=124, run_number=9)

        def api(args):
            if "/actions/runs?" in args[0]:
                return {"workflow_runs": [newer, self.run]}
            if "/actions/runs/124/artifacts" in args[0]:
                return {"artifacts": {"unexpected": "shape"}}
            if "/actions/runs/123/artifacts" in args[0]:
                return {"artifacts": [self.artifact]}
            raise AssertionError(args[0])

        with patch.object(discovery, "_gh", side_effect=api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            result = self.invoke()
        self.assertEqual(result["source"]["run_id"], "123")

    def test_repository_runs_endpoint_handles_workflow_missing_from_default_branch(self):
        self.run["path"] = ".github/workflows/selected-extension-publication.yml"
        with patch.object(discovery, "_gh", side_effect=self.fake_api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            result = self.invoke()
        self.assertEqual(result["source"]["workflow"], "selected-extension-publication.yml")
        self.assertTrue(any("/actions/runs?branch=" in endpoint for endpoint in self.calls))
        self.assertFalse(any("/actions/workflows/" in endpoint for endpoint in self.calls))

    def test_stale_newest_artifact_falls_back_to_older_success(self):
        newer = dict(self.run, id=124, run_number=9)
        stale = dict(self.artifact, id=457, name="pgvector-linux-selected-17.11-124",
                      workflow_run={"id": 124, "head_sha": newer["head_sha"]},
                      expires_at="2000-01-01T00:00:00Z")
        def api(args):
            if "/actions/runs?" in args[0]:
                return {"workflow_runs": [newer, self.run]}
            if "/actions/runs/124/artifacts" in args[0]:
                return {"artifacts": [stale]}
            if "/actions/runs/123/artifacts" in args[0]:
                return {"artifacts": [self.artifact]}
            raise AssertionError(args[0])
        with patch.object(discovery, "_gh", side_effect=api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            result = self.invoke()
        self.assertEqual(result["source"]["run_id"], "123")

    def test_rejects_wrong_producer_or_expired_or_bad_zip_digest(self):
        cases = [("producer", {"workflow_run": {"id": 999, "head_sha": self.run["head_sha"]}}),
                 ("expired", {"expires_at": "2000-01-01T00:00:00Z"}),
                 ("digest", {"digest": "sha256:" + "0" * 64})]
        for label, changes in cases:
            with self.subTest(label=label):
                self.artifact.update(changes)
                with patch.object(discovery, "_gh", side_effect=self.fake_api):
                    if label == "producer":
                        with self.assertRaisesRegex(candidate.CandidateBundleError, "no successful eligible"):
                            self.invoke()
                    else:
                        with patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
                            with self.assertRaises(candidate.CandidateBundleError):
                                self.invoke()
                self.artifact.update({"workflow_run": {"id": 123, "head_sha": self.run["head_sha"]},
                                      "expires_at": "2099-01-01T00:00:00Z",
                                      "digest": "sha256:" + hashlib.sha256(self.zip_bytes).hexdigest()})

    def test_rejects_missing_requested_files(self):
        with zipfile.ZipFile(io.BytesIO(self.zip_bytes)) as source:
            members = [(item.filename, source.read(item)) for item in source.infolist()
                       if not item.filename.endswith("current-123.json")]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in members:
                archive.writestr(name, data)
        self.zip_bytes = buffer.getvalue()
        self.zip_by_artifact["456"] = self.zip_bytes
        self.artifact["digest"] = "sha256:" + hashlib.sha256(self.zip_bytes).hexdigest()
        with patch.object(discovery, "_gh", side_effect=self.fake_api), \
             patch.object(candidate.bundle.subprocess, "run", side_effect=self.fake_download):
            with self.assertRaisesRegex(candidate.CandidateBundleError, "absent"):
                self.invoke()


if __name__ == "__main__":
    unittest.main()
