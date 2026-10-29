import unittest
from unittest.mock import patch

from build import ROOT, main, release_module


class ReleaseDispatchTests(unittest.TestCase):
    def test_dispatches_each_target_to_its_platform_verifier(self) -> None:
        self.assertEqual(release_module("linux-arm64"), "verification.linux.release")
        self.assertEqual(release_module("macos-arm64"), "verification.macos.release")
        self.assertEqual(release_module("macos-x86_64"), "verification.macos.release")

    def test_each_extension_target_uses_one_package_entry_point(self) -> None:
        for target in ("macos-arm64", "macos-x86_64", "linux-arm64", "linux-x86_64"):
            with self.subTest(target=target), patch("sys.argv", ["build.py", "--target", target,
                    "extension-build", "pgvector", "/pg", "/out"]), patch("build.run_recipe") as recipe:
                main()
                path, arguments, selected = recipe.call_args.args
                self.assertEqual(path, ROOT / "packages/pgvector/build.sh")
                self.assertEqual(arguments[:2], target.split("-", 1))
                self.assertEqual(arguments[-2:], ["/pg", "/out"])
                self.assertEqual(selected, target)

    def test_postgresql_uses_one_entry_point(self) -> None:
        with patch("sys.argv", ["build.py", "--target", "linux-arm64",
                "postgresql-package", "/pg", "/deps", "/out"]), patch("build.run_recipe") as recipe:
            main()
            path, arguments, selected = recipe.call_args.args
            self.assertEqual(path, ROOT / "packages/postgresql/build.sh")
            self.assertEqual(arguments, ["linux", "arm64", "package", "/pg", "/deps", "/out"])
            self.assertEqual(selected, "linux-arm64")


if __name__ == "__main__":
    unittest.main()
