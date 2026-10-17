import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("select_extension_work", ROOT / "tools/select_extension_work.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class SelectExtensionWorkTests(unittest.TestCase):
    def test_resolves_checked_in_postgis_group(self):
        selection = json.loads((ROOT / "support/selected-extension-work.json").read_text())
        result = tool.resolve(ROOT, selection)
        self.assertTrue(result["group_id"].startswith("build-extension:"))
        self.assertEqual(result["platform"], selection["platform"])
        self.assertEqual(result["postgresql_major"], selection["postgresql_major"])
        self.assertEqual(result["postgresql_version"], "17.11")
        self.assertEqual((result["range_from"], result["range_to"]), ("17.11", "17.11"))
        self.assertEqual(result["architecture"], selection["platform"].removeprefix("linux-"))
        self.assertEqual(result["runner"], tool.RUNNERS[result["architecture"]])
        self.assertEqual(result["verification_status"], "unverified")
        self.assertEqual(result["build_postgresql_version"], result["postgresql_version"])
        self.assertEqual(len(result["closure_ids"]), 2)
        self.assertEqual(result["closure_ids"][-1], result["group_id"])
        self.assertTrue(result["closure_ids"][0].startswith("build-core:"))

    def test_rejects_undeclared_or_ambiguous_selection(self):
        selection = {"project": "PostGIS", "version": "3.6.4", "platform": "linux-x86_64",
                     "postgresql_major": 99}
        with self.assertRaisesRegex(ValueError, "found 0"):
            tool.resolve(ROOT, selection)

    def test_rejects_non_linux_and_malformed_selection(self):
        selection = {"project": "PostGIS", "version": "3.6.4", "platform": "macos-x86_64",
                     "postgresql_major": 17}
        with self.assertRaisesRegex(ValueError, "Linux"):
            tool.resolve(ROOT, selection)
        with self.assertRaisesRegex(ValueError, "exactly"):
            tool.resolve(ROOT, {**selection, "extra": True})

    def test_rejects_ambiguous_queue_match(self):
        selection = {"project": "PostGIS", "version": "3.6.4", "platform": "linux-x86_64",
                     "postgresql_major": 17}
        original = tool.extension_work_queue.build_queue
        try:
            def duplicate(root):
                queue = original(root)
                group = next(item for item in queue["work_items"] if item.get("id") == "build-extension:39e3af8b0d80a70e")
                queue["work_items"].append(dict(group, id="duplicate"))
                return queue
            tool.extension_work_queue.build_queue = duplicate
            with self.assertRaisesRegex(ValueError, "exactly one"):
                tool.resolve(ROOT, selection)
        finally:
            tool.extension_work_queue.build_queue = original


if __name__ == "__main__":
    unittest.main()
