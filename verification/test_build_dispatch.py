import unittest
from pathlib import Path
from unittest.mock import patch

from build import ROOT, main, release_module


class ReleaseDispatchTests(unittest.TestCase):
    def test_dispatches_each_target_to_its_platform_verifier(self) -> None:
        self.assertEqual(release_module("linux-arm64"), "verification.linux.release")
        self.assertEqual(release_module("macos-arm64"), "verification.macos.release")
        self.assertEqual(release_module("macos-x86_64"), "verification.macos.release")

    def test_each_extension_target_uses_shared_preparation(self) -> None:
        for target in ("macos-arm64", "macos-x86_64", "linux-arm64", "linux-x86_64"):
            with self.subTest(target=target), patch("sys.argv", ["build.py", "--target", target,
                    "extension-build", "pgvector", "/development.tar.gz", "/out"]), patch("build_support.extensions.build_extension") as build:
                main()
                build.assert_called_once_with("pgvector", target, "/development.tar.gz", "/out", None, None)

    def test_postgresql_uses_one_entry_point(self) -> None:
        with patch("sys.argv", ["build.py", "--target", "linux-arm64",
                "postgresql-package", "/workspace", "/out"]), patch("build_support.postgresql.package_postgresql", return_value={}) as package:
            main()
            package.assert_called_once_with(Path("/workspace"), "linux-arm64", Path("/out"))


if __name__ == "__main__":
    unittest.main()
