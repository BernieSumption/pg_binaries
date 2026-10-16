import hashlib
import json
import tempfile
import unittest

from tools.local_publication_dry_run import DryRunError, LocalPublicationStore


class LocalPublicationDryRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalPublicationStore(self.temp.name)
        self.old_tag = "catalog-20261016-1"
        self.new_tag = "catalog-20261017-1"
        self.old_url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{self.old_tag}/old.tar.gz"
        self.new_url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{self.new_tag}/new.tar.gz"
        self.old_bytes, self.new_bytes = b"older archive", b"new archive"
        self.old_inventory = self.inventory(self.old_url, self.old_bytes)
        self.store.seed_release(self.old_tag, self.old_inventory, {"old.tar.gz": self.old_bytes})
        self.store.current_path.parent.mkdir(parents=True)
        self.store.current_path.write_text(json.dumps(self.old_inventory), encoding="utf-8")
        self.candidate = {
            "schema_version": 1,
            "postgresql": {
                "15.1": {"downloads": {"linux-x86_64": {
                    "url": self.old_url, "sha256": self.digest(self.old_bytes)}}},
                "16.1": {"downloads": {"linux-x86_64": {
                    "url": self.new_url, "sha256": self.digest(self.new_bytes)}}},
            },
            "extensions": {},
        }

    @staticmethod
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    def inventory(self, url, data):
        return {"schema_version": 1, "postgresql": {"15.1": {
            "downloads": {"linux-x86_64": {"url": url, "sha256": self.digest(data)}}}},
            "extensions": {}}

    def test_stages_verifies_promotes_then_retrieves_old_and_new_urls_locally(self):
        self.store.promote(self.new_tag, self.candidate, {self.new_url: self.new_bytes})
        self.assertEqual(self.store.current_inventory(), self.candidate)
        self.assertEqual(self.store.retrieve(self.old_url), self.old_bytes)
        self.assertEqual(self.store.retrieve(self.new_url), self.new_bytes)
        self.assertEqual(self.store.retrieve_current_references(), {
            self.old_url: self.old_bytes, self.new_url: self.new_bytes})
        release = self.store.releases / self.new_tag
        self.assertEqual((release / "new.tar.gz").read_bytes(), self.new_bytes)
        self.assertEqual(json.loads((release / "inventory.json").read_text()), self.candidate)

    def test_failure_after_staging_or_verification_preserves_current(self):
        for failure in ("after_stage", "after_verify"):
            with self.subTest(failure=failure):
                with self.assertRaises(DryRunError):
                    self.store.promote(self.new_tag, self.candidate,
                                       {self.new_url: self.new_bytes}, fail_at=failure)
                self.assertEqual(self.store.current_inventory(), self.old_inventory)
                self.assertFalse((self.store.releases / self.new_tag).exists())

    def test_failure_after_release_creation_preserves_current_inventory(self):
        with self.assertRaisesRegex(DryRunError, "before current inventory switch"):
            self.store.promote(self.new_tag, self.candidate,
                               {self.new_url: self.new_bytes}, fail_at="before_current_switch")
        self.assertEqual(self.store.current_inventory(), self.old_inventory)
        self.assertEqual(self.store.retrieve(self.new_url), self.new_bytes)

    def test_missing_retained_archive_and_checksum_mismatch_block_switch(self):
        (self.store.releases / self.old_tag / "old.tar.gz").unlink()
        with self.assertRaisesRegex(DryRunError, "unavailable"):
            self.store.promote(self.new_tag, self.candidate, {self.new_url: self.new_bytes})
        self.assertEqual(self.store.current_inventory(), self.old_inventory)

        (self.store.releases / self.old_tag / "old.tar.gz").write_bytes(b"wrong bytes")
        with self.assertRaisesRegex(DryRunError, "checksum mismatch"):
            self.store.promote(self.new_tag, self.candidate, {self.new_url: self.new_bytes})
        self.assertEqual(self.store.current_inventory(), self.old_inventory)

    def test_new_assets_must_match_tag_and_candidate_references(self):
        with self.assertRaisesRegex(DryRunError, "exactly match"):
            self.store.promote(self.new_tag, self.candidate, {})
        with self.assertRaisesRegex(DryRunError, "does not use candidate tag"):
            self.store.promote(self.new_tag, self.candidate, {self.old_url: self.old_bytes})
        self.assertEqual(self.store.current_inventory(), self.old_inventory)


if __name__ == "__main__":
    unittest.main()
