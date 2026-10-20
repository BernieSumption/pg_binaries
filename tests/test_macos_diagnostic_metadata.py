import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "macos"))
import diagnostic_metadata


class MacOSDiagnosticMetadataTests(unittest.TestCase):
    def setUp(self):
        self.core = {"build_id": "github-39415909929-1"}
        self.vector = {"build_id": "github-39415909930-1"}
        self.archive_name = "postgresql-18.6-macos-arm64.tar.gz"
        self.archive_sha256 = "a" * 64

    def test_accepts_separate_vector_identity_bound_to_exact_core_archive(self):
        self.vector["core_archive"] = {
            "basename": self.archive_name,
            "sha256": self.archive_sha256,
        }

        self.assertEqual(
            diagnostic_metadata.validate_build_ids(
                self.core, self.vector, self.archive_name, self.archive_sha256
            ),
            {"postgresql": self.core["build_id"], "pgvector": self.vector["build_id"]},
        )

    def test_rejects_separate_vector_identity_with_wrong_archive_binding(self):
        self.vector["core_archive"] = {
            "basename": self.archive_name,
            "sha256": "b" * 64,
        }

        with self.assertRaisesRegex(ValueError, "does not bind"):
            diagnostic_metadata.validate_build_ids(
                self.core, self.vector, self.archive_name, self.archive_sha256
            )

    def test_combined_archives_still_require_matching_build_ids(self):
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            diagnostic_metadata.validate_build_ids(self.core, self.vector)
        self.vector["build_id"] = self.core["build_id"]
        self.assertEqual(
            diagnostic_metadata.validate_build_ids(self.core, self.vector),
            {"postgresql": self.core["build_id"], "pgvector": self.core["build_id"]},
        )


if __name__ == "__main__":
    unittest.main()
