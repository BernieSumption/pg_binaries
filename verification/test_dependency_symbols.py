import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from verification.dependency_symbols import Binary, conflicts, elf, inspect, macho, require_isolation


PCRE = json.loads((Path(__file__).parent / "fixtures/pcre2-overlap.json").read_text())["exports"]


class DependencySymbolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.outputs = {}
        self.owners = {}

    def add(self, name, exports=(), imports=(), needed=(), weak=(), hidden=(), references=(), package=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x7fELF")
        self.owners[name] = [package or ("postgresql" if name in ("bin/postgres", "libexec/postgres", "lib/libpq.so") else path.stem)]
        rows = []
        for symbols, binding, visibility, section in ((exports, "GLOBAL", "DEFAULT", "12"),
                                                      (imports, "GLOBAL", "DEFAULT", "UND"),
                                                      (weak, "WEAK", "DEFAULT", "12"),
                                                      (hidden, "GLOBAL", "HIDDEN", "12")):
            for symbol in symbols:
                rows.append(f"  {len(rows) + 1}: 0000000000001010 24 FUNC {binding} {visibility} {section} {symbol}")
        self.outputs["readelf", "--dyn-syms", "-W", str(path)] = "\n".join(rows)
        dynamic = "\n".join(f" 0x0000000000000001 (NEEDED) Shared library: [{name}]" for name in needed)
        dynamic += "\n 0x000000000000001d (RUNPATH) Library runpath: [$ORIGIN:$ORIGIN/deps]"
        self.outputs["readelf", "-dW", str(path)] = dynamic
        self.outputs["readelf", "-rW", str(path)] = "\n".join(f"000000002000 00000402 R_AARCH64_JUMP_SLOT 000000001010 {symbol} + 0" for symbol in references)
        return path

    def run_inspect(self):
        with patch("verification.dependency_symbols.command", side_effect=lambda *args: self.outputs[args]):
            return inspect(self.root, "linux-arm64", self.owners)

    def test_real_pcre_exports_are_found_despite_renaming_and_cli_excluded(self):
        self.add("libexec/postgres", exports=["PostgreSQL_API"])
        self.add("lib/address.so", exports=["Pg_magic_func", "pg_finfo_standardize", "standardize"],
                 imports=["pcre2_compile_8", "pcre2_match_8"], needed=["renamed-pcre248.so"])
        self.add("lib/postgis.so", exports=["Pg_magic_func", "pg_finfo_raster", "raster"],
                 imports=["pcre2_compile_8"], needed=["other-pcre239.so"])
        self.add("lib/deps/renamed-pcre248.so", exports=PCRE)
        self.add("lib/deps/other-pcre239.so", exports=PCRE)
        self.add("bin/unrelated", exports=PCRE)
        result = self.run_inspect()
        self.assertEqual(result["inspected_binaries"], 5)
        self.assertEqual(len(result["conflicts"]), 1)
        finding = result["conflicts"][0]
        self.assertEqual(finding["symbols"], ["pcre2_compile_8", "pcre2_match_8"])
        self.assertEqual(finding["libraries"][0]["consumers"], ["lib/postgis.so"])
        self.assertEqual(finding["libraries"][1]["consumers"], ["lib/address.so"])

    def test_same_soname_with_different_archive_bytes_fails(self):
        self.add("bin/postgres")
        self.add("lib/module.so", exports=["Pg_magic_func"], needed=["one.so", "two.so"])
        for name in ("one", "two"):
            path = self.add(f"lib/{name}.so", exports=[name])
            path.write_bytes(b"\x7fELF" + name.encode())
            self.outputs["readelf", "-dW", str(path)] += "\n 0x000000000000000e (SONAME) Library soname: [pcre.so]"
        self.assertEqual(self.run_inspect()["conflicts"][0]["competing_identity"], "pcre.so")

    def test_static_leak_fails_and_hidden_static_dependency_passes(self):
        self.add("bin/postgres")
        self.add("lib/address.so", exports=["Pg_magic_func", *PCRE], references=PCRE)
        self.add("lib/postgis.so", exports=["Pg_magic_func", *PCRE], references=PCRE)
        self.assertEqual(self.run_inspect()["conflicts"][0]["symbols"], PCRE)
        self.add("lib/address.so", exports=["Pg_magic_func"], hidden=PCRE)
        self.assertEqual(self.run_inspect()["conflicts"], [])

    def test_server_libpq_overlap_is_outside_extension_conflict_scope(self):
        public = ["lo_read", "lo_write"]
        aliases = ["pg_binaries_libpq_lo_read", "pg_binaries_libpq_lo_write"]
        self.add("bin/postgres", exports=public)
        self.add("lib/postgis.so", exports=["Pg_magic_func"], needed=["gdal.so"])
        self.add("lib/gdal.so", imports=public, needed=["libpq.so"])
        self.add("lib/libpq.so", exports=[*public, *aliases], references=public)
        self.assertEqual(self.run_inspect()["conflicts"], [])
        self.add("lib/libpq.so", exports=[*public, *aliases])
        self.assertEqual(self.run_inspect()["conflicts"], [])
        self.add("lib/gdal.so", imports=aliases, needed=["libpq.so"])
        self.assertEqual(self.run_inspect()["conflicts"], [])

    def test_postgres_entrypoints_weak_cpp_and_unique_symbols_are_safe(self):
        self.add("bin/postgres")
        for name in ("one", "two"):
            self.add(f"lib/{name}.so", exports=["Pg_magic_func", "pg_finfo_same_sql", "same_sql", "_PG_init", "_PG_output_plugin_init"],
                     weak=["_ZNSt6vectorIiSaIiEED1Ev"])
        self.assertEqual(self.run_inspect()["conflicts"], [])

    def test_sql_entrypoints_with_direct_c_calls_are_not_exempt(self):
        self.add("bin/postgres")
        for name in ("one", "two"):
            self.add(f"lib/{name}.so", exports=["Pg_magic_func", "pg_finfo_same_sql", "same_sql"],
                     references=["same_sql"])
        self.assertEqual(self.run_inspect()["conflicts"][0]["symbols"], ["same_sql"])

    def test_shared_dependency_reached_from_multiple_modules_is_one_provider(self):
        self.add("bin/postgres")
        for name in ("one", "two"):
            self.add(f"lib/{name}.so", exports=["Pg_magic_func"], imports=["pcre2_compile_8"], needed=["pcre.so"])
        self.add("lib/pcre.so", exports=PCRE)
        result = self.run_inspect()
        self.assertEqual(result["inspected_binaries"], 4)
        self.assertEqual(result["conflicts"], [])

    def test_distinct_versioned_abis_do_not_compete_but_unversioned_leak_does(self):
        self.add("bin/postgres")
        self.add("lib/one.so", exports=["Pg_magic_func"], imports=["curl_easy_init@CURL_OPENSSL_4"], needed=["openssl.so", "gnutls.so"])
        self.add("lib/openssl.so", exports=["curl_easy_init@@CURL_OPENSSL_4"])
        self.add("lib/gnutls.so", exports=["curl_easy_init@@CURL_GNUTLS_4"])
        self.assertEqual(self.run_inspect()["conflicts"], [])
        self.add("lib/gnutls.so", exports=["curl_easy_init"])
        self.assertEqual(self.run_inspect()["conflicts"][0]["symbols"], ["curl_easy_init"])

    def test_linker_version_nodes_and_hidden_weak_definitions_are_not_apis(self):
        path = self.add("bin/postgres")
        self.outputs["readelf", "--dyn-syms", "-W", str(path)] = """
  1: 00000000 0 OBJECT GLOBAL DEFAULT ABS OPENSSL_3.0.0
  2: 00000000 2 FUNC GLOBAL HIDDEN 12 internal
  3: 00000000 2 FUNC WEAK DEFAULT 12 weak
  4: 00000000 2 OBJECT UNIQUE DEFAULT 12 unique
  5: 00000000 2 FUNC GLOBAL DEFAULT 12 public
"""
        with patch("verification.dependency_symbols.command", side_effect=lambda *args: self.outputs[args]):
            self.assertEqual(elf(path).exports, {"public"})

    def test_missing_inspection_tool_and_unresolved_dependency_fail_closed(self):
        self.add("bin/postgres", needed=["missing.so"])
        with self.assertRaisesRegex(RuntimeError, "unresolved dependency"):
            self.run_inspect()
        with patch("verification.dependency_symbols.subprocess.run", side_effect=FileNotFoundError("readelf")):
            with self.assertRaises(FileNotFoundError):
                require_isolation(self.root, "linux-arm64", self.owners)

    def test_copy_relocation_is_dependency_storage_not_a_competing_provider(self):
        server = self.add("bin/postgres", exports=["stdout"], needed=["libc.so.6"])
        self.add("lib/libc.so.6", exports=["stdout"], references=["stdout"])
        self.outputs["readelf", "-rW", str(server)] = "000000002000 00000402 R_X86_64_COPY 000000002000 stdout@GLIBC_2.2.5 + 0"
        self.assertEqual(self.run_inspect()["conflicts"], [])

    def test_lapack_exception_requires_exact_bytes_and_records_reason(self):
        self.add("bin/postgres")
        binaries = {self.root / "bin/postgres": Binary(self.root / "bin/postgres")}
        first = self.root / "lib/postgis-deps/postgis-libblas.so.3"
        second = self.root / "lib/postgis-deps/postgis-liblapack.so.3"
        first.parent.mkdir(parents=True)
        first.write_bytes(b"blas")
        second.write_bytes(b"lapack")
        for path in (first, second):
            binaries[path] = Binary(path, exports={"lsame_", "xerbla_"}, relocations={"lsame_", "xerbla_"})
        hashes = {b"blas": "5595f2a1fe7de99f5961271fbdefb335ed82c7ead64c0cdd3990730ab5c411fa",
                  b"lapack": "4c66375ac8f1f01c8a179cba8e7a605eecc57b93691e7300ff20212e1f05d911"}
        with patch("verification.dependency_symbols.hashlib.sha256", side_effect=lambda value: SimpleNamespace(hexdigest=lambda: hashes[value])):
            result = conflicts(binaries, list(binaries), self.root, True,
                               {str(path.relative_to(self.root)): [str(path.name)] for path in binaries})
        self.assertEqual(result["conflicts"], [])
        self.assertEqual({item["symbol"] for item in result["exceptions"]}, {"lsame_", "xerbla_"})
        self.assertIn("lapack 3.10.0-2ubuntu1", result["exceptions"][0]["reason"])
        self.assertTrue(conflicts(binaries, list(binaries), self.root, True,
                                  {str(path.relative_to(self.root)): [str(path.name)] for path in binaries})["conflicts"])

    def test_unused_duplicates_and_cpp_abi_metadata_do_not_fail(self):
        self.add("bin/postgres")
        for name in ("one", "two"):
            self.add(f"lib/{name}.so", exports=["Pg_magic_func", "unused_api", "_ZTISt6vectorIiSaIiEE", "_ZGVZexample"],
                     references=["_ZTISt6vectorIiSaIiEE", "_ZGVZexample"])
        self.assertEqual(self.run_inspect()["conflicts"], [])
        self.add("lib/one.so", exports=["Pg_magic_func", "unused_api"], references=["unused_api"])
        self.assertEqual(self.run_inspect()["conflicts"][0]["symbols"], ["unused_api"])

    def test_macho_twolevel_named_binds_are_safe_dynamic_lookup_is_not(self):
        server = self.root / "postgres"
        one, two = self.root / "one", self.root / "two"
        binaries = {server: Binary(server, dependencies=[]), one: Binary(one, exports={"pcre2_compile_8"}),
                    two: Binary(two, exports={"pcre2_compile_8"})}
        owners = {"postgres": ["postgresql"], "one": ["one"], "two": ["two"]}
        result = conflicts(binaries, [server, one, two], self.root, False, owners)
        self.assertEqual(result["conflicts"], [])
        binaries[server].flat_imports.add("pcre2_compile_8")
        self.assertEqual(conflicts(binaries, [server, one, two], self.root, False, owners)["conflicts"][0]["symbols"], ["pcre2_compile_8"])

    def test_same_extension_package_is_outside_scope_for_symbols_and_identity(self):
        self.add("bin/postgres")
        self.add("lib/module.so", exports=["Pg_magic_func"], needed=["one.so", "two.so"], package="postgis")
        for name in ("one", "two"):
            path = self.add(f"lib/{name}.so", exports=["private_api"], references=["private_api"], package="postgis")
            path.write_bytes(b"\x7fELF" + name.encode())
            self.outputs["readelf", "-dW", str(path)] += "\n 0x000000000000000e (SONAME) Library soname: [private.so]"
        self.assertEqual(self.run_inspect()["conflicts"], [])
        self.owners["lib/two.so"] = ["another_extension"]
        finding = self.run_inspect()["conflicts"][0]
        self.assertEqual(finding["symbols"], ["private_api"])
        self.assertEqual(finding["competing_identity"], "private.so")

    def test_postgresql_library_does_not_mask_conflicts_between_extensions(self):
        self.add("bin/postgres", exports=["lo_read"])
        self.add("lib/libpq.so", exports=["lo_read"])
        for name in ("one", "two"):
            self.add(f"lib/{name}.so", exports=["Pg_magic_func", "lo_read"],
                     imports=["lo_read"], needed=["libpq.so"])
        findings = self.run_inspect()["conflicts"]
        self.assertEqual(len(findings), 1)
        self.assertEqual({x["path"] for x in findings[0]["libraries"]}, {"lib/one.so", "lib/two.so"})

    def test_missing_archive_ownership_fails_closed(self):
        self.add("bin/postgres")
        self.owners.clear()
        with self.assertRaisesRegex(RuntimeError, "no archive package ownership"):
            self.run_inspect()

    def test_macho_parser_retains_only_dynamic_lookup_as_global_binding(self):
        path = self.root / "module.so"
        outputs = {
            "-L": "module.so:\n @loader_path/pcre.dylib (compatibility version 1.0.0, current version 1.0.0)\n",
            "-l": "", "-hv": "MH_MAGIC_64 X86_64 BUNDLE TWOLEVEL",
            "-m": """                 (undefined) external _pcre2_compile_8 (from pcre)
                 (undefined) external _pcre2_match_8 (dynamically looked up)
0000000000001000 (__TEXT,__text) external _Pg_magic_func
0000000000001100 (__TEXT,__text) weak external _template
"""}
        with patch("verification.dependency_symbols.command", side_effect=lambda tool, *args: outputs[next(arg for arg in args if arg in outputs)]):
            binary = macho(path, "x86_64")
        self.assertEqual(binary.exports, {"Pg_magic_func"})
        self.assertEqual(binary.imports, {"pcre2_compile_8", "pcre2_match_8"})
        self.assertEqual(binary.flat_imports, {"pcre2_match_8"})
        self.assertFalse(binary.flat)


if __name__ == "__main__":
    unittest.main()
