import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
        self.assertEqual(result["architecture"], selection["platform"].split("-", 1)[1])
        self.assertEqual(result["runner"], tool.RUNNERS[selection["platform"]])
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

    def test_resolves_declared_hypopg_macos_arm64_and_windows_groups(self):
        for platform, runner in (("macos-arm64", "macos-15"), ("windows-x86_64", "windows-2022")):
            with self.subTest(platform=platform):
                result = tool.resolve(ROOT, {
                    "project": "HypoPG",
                    "version": "1.4.3",
                    "platform": platform,
                    "postgresql_major": 17,
                })
                self.assertEqual(result["platform"], platform)
                self.assertEqual(result["architecture"], platform.split("-", 1)[1])
                self.assertEqual(result["runner"], runner)
                self.assertEqual(result["postgresql_major"], 17)
                self.assertEqual(result["closure_ids"][-1], result["group_id"])

    def test_resolves_linux_x86_64_pgvector_17_11_from_the_queue(self):
        result = tool.resolve(ROOT, {
            "project": "pgvector", "version": "0.8.7", "platform": "linux-x86_64",
            "postgresql_major": 17,
        })
        self.assertEqual(result["postgresql_version"], "17.11")
        self.assertEqual(result["architecture"], "x86_64")
        self.assertEqual(len(result["closure_ids"]), 2)
        self.assertTrue(result["closure_ids"][0].startswith("build-core:"))

    def test_resolves_pgvector_by_exact_postgresql_release(self):
        result = tool.resolve(ROOT, {
            "project": "pgvector", "version": "0.8.7", "platform": "linux-x86_64",
            "postgresql_version": "17.11",
        })
        self.assertEqual(result["postgresql_version"], "17.11")
        self.assertEqual(result["postgresql_major"], 17)

    def test_cli_accepts_exact_postgresql_release(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = tool.main([
                "--root", str(ROOT), "--project", "pgvector", "--version", "0.8.7",
                "--platform", "linux-x86_64", "--postgresql-version", "17.11",
            ])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["postgresql_version"], "17.11")

    def test_linux_selected_trial_uses_planned_extension_and_selected_postgresql_outputs(self):
        workflow = (ROOT / ".github/workflows/pgvector-linux-selected-trial.yml").read_text()
        self.assertIn("REQUESTED_POSTGRESQL_VERSION: ${{ inputs.postgresql_version }}", workflow)
        self.assertIn("--postgresql-version \"$pg_version\"", workflow)
        self.assertIn("PG_VERSION: ${{ steps.target.outputs.postgresql_version }}", workflow)
        self.assertIn("PGVECTOR_VERSION: ${{ steps.target.outputs.version }}", workflow)
        self.assertNotIn("0.8.7", workflow)
        self.assertNotIn('test "$PG_VERSION" = 17.11', workflow)

    def test_rejects_undeclared_platform_architecture_and_malformed_selection(self):
        selection = {"project": "NoSuchExtension", "version": "3.6.4", "platform": "macos-x86_64",
                     "postgresql_major": 17}
        with self.assertRaisesRegex(ValueError, "found 0"):
            tool.resolve(ROOT, selection)
        for platform in ("freebsd-x86_64", "macos-riscv64", "windows-arm64"):
            with self.subTest(platform=platform), self.assertRaisesRegex(ValueError, "declared platform"):
                tool.resolve(ROOT, {**selection, "platform": platform})
        with self.assertRaisesRegex(ValueError, "exactly"):
            tool.resolve(ROOT, {**selection, "extra": True})
        with self.assertRaisesRegex(ValueError, "exactly"):
            tool.resolve(ROOT, {"project": "HypoPG", "version": "1.4.3", "platform": "macos-arm64"})

    def test_cli_resolves_direct_macos_and_windows_targets(self):
        for platform, runner in (("macos-arm64", "macos-15"), ("windows-x86_64", "windows-2022")):
            with self.subTest(platform=platform):
                output = io.StringIO()
                with redirect_stdout(output):
                    status = tool.main([
                        "--root", str(ROOT), "--project", "HypoPG", "--version", "1.4.3",
                        "--platform", platform, "--postgresql-major", "17",
                    ])
                result = json.loads(output.getvalue())
                self.assertEqual(status, 0)
                self.assertEqual(result["platform"], platform)
                self.assertEqual(result["runner"], runner)

    def test_cli_keeps_json_selection_path(self):
        selection = json.loads((ROOT / "support/selected-extension-work.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            selection_path = Path(directory) / "selection.json"
            selection_path.write_text(json.dumps(selection))
            output = io.StringIO()
            with redirect_stdout(output):
                status = tool.main(["--root", str(ROOT), "--selection", str(selection_path)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["group_id"], tool.resolve(ROOT, selection)["group_id"])

    def test_cli_requires_exactly_one_complete_selection_form(self):
        direct = ["--project", "HypoPG", "--version", "1.4.3", "--platform", "macos-arm64",
                  "--postgresql-major", "17"]
        invalid_args = (
            ["--project", "HypoPG"],
            ["--selection", "selection.json", *direct],
            ["--version", "1.4.3", "--platform", "macos-arm64", "--postgresql-major", "17"],
            ["--project", "HypoPG", "--version", "1.4.3", "--platform", "macos-arm64",
             "--postgresql-major", "17", "--postgresql-version", "17.11"],
        )
        for argv in invalid_args:
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    tool.main(argv)
                self.assertEqual(error.exception.code, 2)

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
