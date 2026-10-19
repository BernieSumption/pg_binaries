import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "linux_changed_profiles_core", ROOT / "tools/linux_changed_profiles.py")
selector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(selector)


class LinuxCoreOnlyPublicationTests(unittest.TestCase):
    def test_core_targets_cover_declared_releases_and_linux_architectures(self):
        targets = selector.core_targets(None, ROOT)
        releases = json.loads((ROOT / "support/postgresql-releases.json").read_text())["releases"]
        support = json.loads((ROOT / "support.json").read_text())
        expected = {(release["version"], f"linux-{arch}")
                    for release in releases for arch in support["platform_architectures"]["linux"]}
        self.assertEqual({(item["postgresql_version"], item["platform"]) for item in targets}, expected)
        self.assertTrue(all(item["project"] == "PostgreSQL" for item in targets))

    def test_targeted_core_selection_is_independent_of_extension_support(self):
        target = selector.core_targets(None, ROOT, postgresql_version="18.6", architecture="arm64")
        self.assertEqual(target, [{"project": "PostgreSQL", "postgresql_version": "18.6",
                                   "platform": "linux-arm64"}])

    def test_github_output_routes_manual_core_target_away_from_extensions(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            self.assertEqual(selector.main(["--current-root", str(ROOT), "--project", "PostgreSQL",
                                            "--postgresql-version", "18.6", "--architecture", "arm64",
                                            "--github-output", str(output)]), 0)
            values = dict(line.split("=", 1) for line in output.read_text().splitlines())
            self.assertEqual(json.loads(values["targets"]), [])
            self.assertEqual(json.loads(values["core_targets"]), [{
                "project": "PostgreSQL", "postgresql_version": "18.6", "platform": "linux-arm64"}])

    def test_core_profiles_have_only_core_publication_cases_and_existing_sources(self):
        profiles = json.loads((ROOT / "support/verification-profiles.json").read_text())["profiles"]
        core_profiles = {name: value for name, value in profiles.items()
                         if name.startswith("postgresql-publication-linux-")}
        self.assertEqual(len(core_profiles), 8)
        for name, profile in core_profiles.items():
            self.assertEqual(profile["case_ids"], ["archive-suite", "diagnostics", "no-host-userspace"])
            self.assertTrue(all((ROOT / source).is_file() for source in profile["sources"]), name)

    def test_workflow_runs_core_route_and_requires_all_final_checks(self):
        workflow = (ROOT / ".github/workflows/postgresql-linux-selected-publication.yml").read_text()
        for text in ("PG_VERIFY_MODE=core-only", "PG_DIAGNOSTICS_MODE=core-only",
                     "--publication-mode core-only", "verify-no-host-userspace.sh",
                     "tools/create_linux_symbols.py", "tools/import_linux_publication_run.py",
                     "Require every core publication check"):
            self.assertIn(text, workflow)
        self.assertNotIn("PGVECTOR_VERSION", workflow)


if __name__ == "__main__":
    unittest.main()
