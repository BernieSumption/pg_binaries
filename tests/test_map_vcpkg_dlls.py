import json
from pathlib import Path
import tempfile
import unittest

from tools.map_vcpkg_dlls import map_bundled_dlls


class VcpkgDllMappingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.installed = self.root / "installed" / "x64-windows"
        self.info = self.root / "installed" / "vcpkg" / "info"
        self.dll_dir = self.root / "bundle" / "bin"
        self.info.mkdir(parents=True)
        self.dll_dir.mkdir(parents=True)
        self._add_package("icu", "74.2", "0", ["bin/icuuc74.dll"])

    def tearDown(self):
        self.temp.cleanup()

    def _add_package(self, port, version, port_version, files):
        status = self.root / "installed" / "vcpkg" / "status"
        status.parent.mkdir(parents=True, exist_ok=True)
        existing = status.read_text(encoding="utf-8") if status.exists() else ""
        status.write_text(existing + (
            f"Package: {port}\nVersion: {version}\nPort-Version: {port_version}\n"
            "Architecture: x64-windows\nStatus: install ok installed\n\n"
        ), encoding="utf-8")
        (self.info / f"{port}_x64-windows.list").write_text("\n".join(files) + "\n", encoding="utf-8")
        notice = self.installed / "share" / port / "copyright"
        notice.parent.mkdir(parents=True, exist_ok=True)
        notice.write_text(f"Copyright notice for {port}\n", encoding="utf-8")

    def test_maps_owned_dll_with_resolved_package_and_notice_hash(self):
        dll = self.dll_dir / "icuuc74.dll"
        dll.write_bytes(b"icu runtime")
        result = map_bundled_dlls(self.installed, self.dll_dir)
        self.assertEqual(result["schema_version"], 1)
        item = result["components"][0]
        self.assertEqual(item["dll"], "icuuc74.dll")
        self.assertEqual(len(item["dll_sha256"]), 64)
        self.assertEqual(item["port"], "icu")
        self.assertEqual(item["triplet"], "x64-windows")
        self.assertEqual(item["version"], "74.2")
        self.assertEqual(item["port_version"], "0")
        self.assertEqual(item["copyright_file"], "share/icu/copyright")
        self.assertEqual(len(item["copyright_sha256"]), 64)

    def test_output_order_is_stable(self):
        self._add_package("zlib", "1.3.1", "0", ["bin/zlib1.dll"])
        (self.dll_dir / "zlib1.dll").write_bytes(b"zlib")
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        report = map_bundled_dlls(self.installed, self.dll_dir)
        self.assertEqual([entry["dll"] for entry in report["components"]], ["icuuc74.dll", "zlib1.dll"])
        self.assertEqual(json.dumps(report), json.dumps(map_bundled_dlls(self.installed, self.dll_dir)))

    def test_accepts_versioned_installed_info_filename(self):
        owner_list = self.info / "icu_74.2#0_x64-windows.list"
        (self.info / "icu_x64-windows.list").rename(owner_list)
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        self.assertEqual(map_bundled_dlls(self.installed, self.dll_dir)["components"][0]["port"], "icu")

    def test_accepts_triplet_prefixed_owner_path_and_dash_port_version(self):
        owner_list = self.info / "icu_74.2-0_x64-windows.list"
        (self.info / "icu_x64-windows.list").rename(owner_list)
        owner_list.write_text("x64-windows/bin/icuuc74.dll\n", encoding="utf-8")
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        self.assertEqual(map_bundled_dlls(self.installed, self.dll_dir)["components"][0]["port"], "icu")

    def test_accepts_matching_feature_status_paragraph(self):
        status = self.root / "installed" / "vcpkg" / "status"
        status.write_text(status.read_text(encoding="utf-8") + (
            "Package: icu\nFeature: tools\nVersion: 74.2\nPort-Version: 0\n"
            "Architecture: x64-windows\nStatus: install ok installed\n\n"
        ), encoding="utf-8")
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        self.assertEqual(map_bundled_dlls(self.installed, self.dll_dir)["components"][0]["port"], "icu")

    def test_defaults_omitted_port_version_to_zero(self):
        status = self.root / "installed" / "vcpkg" / "status"
        status.write_text(
            "Package: icu\nVersion: 74.2\nArchitecture: x64-windows\n"
            "Status: install ok installed\n\n", encoding="utf-8")
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        item = map_bundled_dlls(self.installed, self.dll_dir)["components"][0]
        self.assertEqual(item["port_version"], "0")

    def test_accepts_each_vcpkg_version_field(self):
        status = self.root / "installed" / "vcpkg" / "status"
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        for field in ("Version", "Version-String", "Version-Date", "Version-Semver"):
            with self.subTest(field=field):
                status.write_text(
                    f"Package: icu\n{field}: 74.2\nPort-Version: 0\n"
                    "Architecture: x64-windows\nStatus: install ok installed\n\n",
                    encoding="utf-8")
                item = map_bundled_dlls(self.installed, self.dll_dir)["components"][0]
                self.assertEqual(item["version"], "74.2")

    def test_accepts_matching_duplicate_vcpkg_version_fields(self):
        status = self.root / "installed" / "vcpkg" / "status"
        status.write_text(
            "Package: icu\nVersion: 74.2\nVersion-Date: 74.2\n"
            "Port-Version: 0\nArchitecture: x64-windows\nStatus: install ok installed\n\n",
            encoding="utf-8")
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        item = map_bundled_dlls(self.installed, self.dll_dir)["components"][0]
        self.assertEqual(item["version"], "74.2")

    def test_rejects_conflicting_vcpkg_version_fields(self):
        status = self.root / "installed" / "vcpkg" / "status"
        status.write_text(
            "Package: icu\nVersion: 74.2\nVersion-Date: 2026-10-18\n"
            "Port-Version: 0\nArchitecture: x64-windows\nStatus: install ok installed\n\n",
            encoding="utf-8")
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        with self.assertRaisesRegex(ValueError, "one unambiguous version"):
            map_bundled_dlls(self.installed, self.dll_dir)

    def test_rejects_unowned_dll(self):
        (self.dll_dir / "other.dll").write_bytes(b"unknown")
        with self.assertRaisesRegex(ValueError, "exactly one vcpkg owner.*found 0"):
            map_bundled_dlls(self.installed, self.dll_dir)

    def test_rejects_ambiguous_dll_ownership(self):
        self._add_package("icu-data", "74.2", "0", ["bin/icuuc74.dll"])
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        with self.assertRaisesRegex(ValueError, "exactly one vcpkg owner.*found 2"):
            map_bundled_dlls(self.installed, self.dll_dir)

    def test_rejects_missing_package_version_fields(self):
        status = self.root / "installed" / "vcpkg" / "status"
        status.write_text("Package: icu\nArchitecture: x64-windows\nStatus: install ok installed\n", encoding="utf-8")
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        with self.assertRaisesRegex(ValueError, "one unambiguous version"):
            map_bundled_dlls(self.installed, self.dll_dir)

    def test_rejects_missing_notice(self):
        (self.installed / "share/icu/copyright").unlink()
        (self.dll_dir / "icuuc74.dll").write_bytes(b"icu")
        with self.assertRaisesRegex(ValueError, "copyright notice is missing"):
            map_bundled_dlls(self.installed, self.dll_dir)

    def test_rejects_case_insensitive_duplicate_bundle_names(self):
        (self.dll_dir / "icuuc74.dll").write_bytes(b"one")
        nested = self.dll_dir / "nested"
        nested.mkdir()
        (nested / "icuuc74.dll").write_bytes(b"two")
        with self.assertRaisesRegex(ValueError, "duplicate bundled DLL basename"):
            map_bundled_dlls(self.installed, self.dll_dir)


if __name__ == "__main__":
    unittest.main()
