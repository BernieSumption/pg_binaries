import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pgvector_plan_evidence as evidence


class PgvectorPlanEvidenceTests(unittest.TestCase):
    def test_checked_candidate_record_carries_producer_archives_and_plan(self):
        request = {"project": "pgvector", "version": "0.8.7",
                   "postgresql_version": "17.11", "platform": "linux-x86_64", "retry": False}
        manifest = {
            "target": {"pgvector_version": "0.8.7", "postgresql_version": "17.11",
                       "platform": "linux-x86_64"},
            "source": {"run_id": "123", "artifact_id": "456",
                       "artifact_name": "pgvector-linux-selected-17.11-123",
                       "artifact_zip_digest": "sha256:" + "a" * 64},
            "sha256": {"postgresql-17.11-linux-x86_64.tar.gz": "b" * 64,
                       "pgvector-0.8.7-postgresql-17.11-linux-x86_64.tar.gz": "c" * 64,
                       "debug-symbols/a.debug": "d" * 64},
        }
        plan = {"should_dispatch": False, "target": request, "work_items": []}
        result = evidence.build_evidence(
            request, manifest, plan, retrieval_outcome="retrieved",
            validation_outcome="passed", dispatch_outcome="checked_candidate", exit_code=0)
        self.assertEqual(result["candidate"]["source"], manifest["source"])
        self.assertEqual(result["candidate"]["archive_sha256"], {
            "postgresql-17.11-linux-x86_64.tar.gz": "b" * 64,
            "pgvector-0.8.7-postgresql-17.11-linux-x86_64.tar.gz": "c" * 64,
        })
        self.assertEqual(result["candidate"]["validation_outcome"], "passed")
        self.assertEqual(result["dispatch"]["plan"], plan)

    def test_fallback_record_keeps_plan_and_failure_without_candidate_identity(self):
        request = {"project": "pgvector", "version": "0.8.7",
                   "postgresql_version": "17.11", "platform": "linux-x86_64", "retry": False}
        plan = {"should_dispatch": True, "target": request, "work_items": [{"id": "build"}]}
        result = evidence.build_evidence(
            request, dispatch_plan=plan, retrieval_outcome="failed",
            validation_outcome="not_attempted", dispatch_outcome="fallback", exit_code=0,
            errors={"retrieval": "no eligible candidate", "validation": None, "dispatch": None})
        self.assertEqual(result["candidate"]["source"], {})
        self.assertEqual(result["candidate"]["archive_sha256"], {})
        self.assertEqual(result["dispatch"]["plan"], plan)
        self.assertEqual(result["errors"]["retrieval"], "no eligible candidate")


if __name__ == "__main__":
    unittest.main()
