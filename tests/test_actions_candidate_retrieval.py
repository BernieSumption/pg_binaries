from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import actions_candidate_discovery as discovery
import actions_candidate_retrieval as retrieval


class ActionsCandidateRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.repo = "example/project"
        self.branch = "spike"
        self.current = "999"
        self.run = {
            "id": 123, "run_attempt": 1, "repository": {"full_name": self.repo},
            "head_repository": {"full_name": self.repo}, "head_sha": "a" * 40,
            "path": ".github/workflows/producer.yml", "head_branch": self.branch,
            "event": "push", "status": "completed", "conclusion": "success",
        }

    def test_enumerates_only_allowed_successful_runs_newest_first_across_pages(self):
        older = dict(self.run, id=121)
        newer = dict(self.run, id=124)
        failed = dict(self.run, id=125, conclusion="failure")
        foreign = dict(self.run, id=126, repository={"full_name": "other/repo"})
        responses = [{"workflow_runs": [older, foreign]}, {"workflow_runs": [failed, newer]}]
        calls = []

        def gh(args):
            calls.append(args[0])
            return responses.pop(0)

        with patch.object(discovery, "_gh", side_effect=gh):
            runs = list(retrieval.enumerate_successful_runs(
                self.repo, self.branch, self.current, ["producer.yml"], max_runs=2, max_pages=2))
        self.assertEqual([run[1]["id"] for run in runs], [124, 121])
        self.assertIn("page=2", calls[1])

    def test_global_run_search_keeps_one_ten_page_budget(self):
        target = dict(self.run, id=321)
        calls = []

        def gh(args):
            endpoint = args[0]
            calls.append(endpoint)
            page = int(endpoint.rsplit("page=", 1)[1])
            rows = [dict(self.run, id=1000 - page * 100 - index,
                         path=".github/workflows/unrelated.yml") for index in range(100)]
            if page == 10:
                rows[-1] = target
            return {"workflow_runs": rows}

        with patch.object(discovery, "_gh", side_effect=gh):
            runs = list(retrieval.enumerate_successful_runs_global(
                self.repo, self.branch, self.current, ["producer.yml"],
                max_runs=100, max_pages=10))
        self.assertEqual([(workflow, run["id"]) for workflow, run in runs], [("producer.yml", 321)])
        self.assertEqual(len(calls), 10)
        self.assertIn("per_page=100&page=10", calls[-1])

    def test_finds_exact_artifact_beyond_first_artifact_page(self):
        self.run["id"] = 123
        unrelated = [{"name": f"other-{index}"} for index in range(2)]
        wanted = {"id": 44, "name": "bundle-123", "workflow_run": {
            "id": 123, "head_sha": "a" * 40, "run_attempt": 1}}
        pages = [{"artifacts": unrelated}, {"artifacts": [wanted]}]
        with patch.object(discovery, "_gh", side_effect=pages) as gh:
            found = retrieval.exact_run_artifacts(
                self.repo, self.run, "bundle-{run_id}", max_artifacts=2, max_pages=2)
        self.assertEqual(found, [wanted])
        self.assertIn("page=2", gh.call_args_list[1].args[0][0])

    def test_rejects_wrong_run_claim_and_duplicate_exact_artifacts(self):
        wrong = {"name": "bundle-123", "workflow_run": {"id": 122, "head_sha": "a" * 40}}
        with patch.object(discovery, "_gh", return_value={"artifacts": [wrong]}):
            self.assertEqual(retrieval.exact_run_artifacts(
                self.repo, self.run, "bundle-{run_id}"), [])
        duplicates = [dict(wrong, workflow_run={"id": 123, "head_sha": "a" * 40})] * 2
        with patch.object(discovery, "_gh", return_value={"artifacts": duplicates}):
            with self.assertRaisesRegex(retrieval.RetrievalError, "duplicate"):
                retrieval.exact_run_artifacts(self.repo, self.run, "bundle-{run_id}")

    def test_metadata_validation_and_pgvector_missing_claim_option(self):
        artifact = {"name": "bundle-123", "expires_at": "2099-01-01T00:00:00Z",
                    "digest": "sha256:" + "b" * 64, "size_in_bytes": 100}
        with self.assertRaisesRegex(retrieval.RetrievalError, "associated"):
            retrieval.validate_artifact_metadata(artifact, self.run)
        expiry, digest, size = retrieval.validate_artifact_metadata(
            artifact, self.run, require_run_claim=False, require_size=True)
        self.assertIsNotNone(expiry)
        self.assertEqual(digest, artifact["digest"])
        self.assertEqual(size, 100)
        artifact["size_in_bytes"] = True
        with self.assertRaisesRegex(retrieval.RetrievalError, "size is invalid"):
            retrieval.validate_artifact_metadata(artifact, self.run, require_run_claim=False)


if __name__ == "__main__":
    unittest.main()
