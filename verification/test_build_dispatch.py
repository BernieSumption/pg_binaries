import unittest

from build import release_module


class ReleaseDispatchTests(unittest.TestCase):
    def test_dispatches_each_target_to_its_platform_verifier(self) -> None:
        self.assertEqual(release_module("linux-arm64"), "verification.linux.release")
        self.assertEqual(release_module("macos-arm64"), "verification.macos.release")
        self.assertEqual(release_module("macos-x86_64"), "verification.macos.release")


if __name__ == "__main__":
    unittest.main()
