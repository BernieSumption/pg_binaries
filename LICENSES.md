# Licences

This file records licence declarations for projects whose code or data is included in the selected PostgreSQL and extension archives. Source and declaration links identify the upstream project and the files used by the build. Build evidence and the policy for applying declarations are in [policies/licenses.md](policies/licenses.md).

## PostgreSQL

- PostgreSQL — PostgreSQL License. [Source repository and `COPYRIGHT` declaration](https://github.com/postgres/postgres/blob/master/COPYRIGHT); selected release archives are listed in [support/postgresql-releases.json](support/postgresql-releases.json).

## Extensions

- Address Standardizer — MIT-style terms. [Source](https://github.com/postgis/address_standardizer/tree/v3.7.0); [`COPYING` declaration](https://github.com/postgis/address_standardizer/blob/v3.7.0/COPYING). The repository licence also applies to its US data files under the policy above.
- pgvector — PostgreSQL License. [Source](https://github.com/pgvector/pgvector/tree/v0.8.7); [`LICENSE`](https://github.com/pgvector/pgvector/blob/v0.8.7/LICENSE).
- PostGIS — GPL-2.0-or-later. [Source and `COPYING`](https://github.com/postgis/postgis/blob/3.6.4/COPYING); the selected build uses the corresponding [OSGeo source release](https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz).
- PostGIS TIGER Geocoder — GPL-2.0, declared in `META.json` and `COPYING` in its separate [2025.2 source archive](https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz); [source project](https://gitea.osgeo.org/postgis/postgis_tiger_geocoder).
- HypoPG — PostgreSQL License. [Source](https://github.com/HypoPG/hypopg/tree/1.4.3); [`LICENSE`](https://github.com/HypoPG/hypopg/blob/1.4.3/LICENSE).
- collection (pgcollection) — Apache-2.0. [Source and `LICENSE`](https://github.com/aws/pgcollection/blob/v2.1.3/LICENSE); the selected source also contains [`NOTICE`](https://github.com/aws/pgcollection/blob/v2.1.3/NOTICE).
- pg_cron — PostgreSQL License. [Source and `LICENSE`](https://github.com/citusdata/pg_cron/blob/v1.6.8/LICENSE).
- pg_ivm — PostgreSQL-style licence. [Source and `LICENSE`](https://github.com/sraoss/pg_ivm/blob/v1.16/LICENSE).
- pgAudit — PostgreSQL licence, as stated by its upstream [`LICENSE`](https://github.com/pgaudit/pgaudit/blob/18.0/LICENSE); [source](https://github.com/pgaudit/pgaudit/tree/18.0).
- pgTAP — PostgreSQL-style permissive terms, declared in the [v1.3.4 `README.md` “Copyright and License” section](https://github.com/theory/pgtap/blob/v1.3.4/README.md#copyright-and-license), which the build copies from the [source project](https://github.com/theory/pgtap/tree/v1.3.4).
- pg_jsonschema — Apache-2.0. [Source and `LICENSE`](https://github.com/supabase/pg_jsonschema/tree/v0.3.4). Its build statically links a target-filtered Cargo dependency closure; see the incomplete dependencies section below.

## Directly identified bundled dependencies

- Boost — BSL-1.0. [Source and licence declaration](https://github.com/boostorg/boost/blob/develop/LICENSE_1_0.txt); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/b/boost.rb).
- GEOS — LGPL-2.1-or-later. [Source and `COPYING`](https://github.com/libgeos/geos/blob/main/COPYING); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/g/geos.rb).
- GMP — LGPL-3.0-or-later OR GPL-2.0-or-later. [Source and licence declaration](https://gmplib.org/manual/Copying); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/g/gmp.rb).
- IJG JPEG library — IJG licence. [Source and licence declaration](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/README.ijg); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/lib/libjpeg-turbo.rb).
- JSON-C — MIT. [Source and `COPYING`](https://github.com/json-c/json-c/blob/master/COPYING); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/j/json-c.rb).
- libiconv — LGPL-2.1-or-later with the libiconv linking exception. [Source and licence declaration](https://git.savannah.gnu.org/cgit/libiconv.git/tree/COPYING.LIB); [vcpkg port](https://github.com/microsoft/vcpkg/blob/9e593bb18ea69cc5095e012465dcd675a822ed0d/ports/libiconv/portfile.cmake).
- libtiff — libtiff licence. [Source and licence declaration](https://gitlab.com/libtiff/libtiff/-/blob/master/COPYRIGHT); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/lib/libtiff.rb).
- MPFR — LGPL-3.0-or-later. [Source and `COPYING.LESSER`](https://gitlab.inria.fr/mpfr/mpfr/-/blob/master/COPYING.LESSER); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/m/mpfr.rb).
- protobuf-c — BSD-2-Clause. [Source and licence declaration](https://github.com/protobuf-c/protobuf-c/blob/master/LICENSE); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/p/protobuf-c.rb).
- SFCGAL — LGPL-2.0-or-later. [Source and licence declaration](https://github.com/Oslandia/SFCGAL/blob/master/COPYING); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/s/sfcgal.rb).
- WebP — BSD-3-Clause. [Source and `COPYING`](https://chromium.googlesource.com/webm/libwebp/+/refs/heads/main/COPYING); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/w/webp.rb).
- XZ Utils — 0BSD for library code, with GPL-2.0-or-later also applying to other source components. [Source and licence declarations](https://github.com/tukaani-project/xz/blob/master/COPYING); [Homebrew formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/x/xz.rb).
- zlib — zlib licence. [Source and licence declaration](https://github.com/madler/zlib/blob/develop/README); [vcpkg port](https://github.com/microsoft/vcpkg/blob/9e593bb18ea69cc5095e012465dcd675a822ed0d/ports/zlib/portfile.cmake).
- PCRE2 — BSD-3-Clause WITH PCRE2-exception. Its enabled JIT includes separately licensed SLJIT under 2-clause BSD. [PCRE2 declaration](https://github.com/PCRE2Project/pcre2/blob/pcre2-10.48/LICENCE.md); [SLJIT declaration](https://github.com/PCRE2Project/pcre2/blob/pcre2-10.48/deps/sljit/LICENSE).
- GDAL — MIT-style terms. [GDAL licence declaration](https://gdal.org/en/stable/license.html); [source release](https://download.osgeo.org/gdal/3.13.3/gdal-3.13.3.tar.gz).
- HDF5 — BSD-3-Clause. [Source](https://github.com/HDFGroup/hdf5); [`LICENSE` declaration](https://github.com/HDFGroup/hdf5/blob/develop/LICENSE).
- libaec — BSD-2-Clause. [Source](https://github.com/Deutsches-Klimarechenzentrum/libaec); [`LICENSE.txt` declaration](https://github.com/Deutsches-Klimarechenzentrum/libaec/blob/main/LICENSE.txt).
- NetCDF-C — BSD-3-Clause. [Source](https://github.com/Unidata/netcdf-c/tree/v4.10.1); [`COPYRIGHT` declaration](https://github.com/Unidata/netcdf-c/blob/v4.10.1/COPYRIGHT).
- PROJ — MIT. [Source and `COPYING`](https://github.com/OSGeo/PROJ/blob/master/COPYING).
- PROJ-data — per-file terms, recorded in upstream [`README.DATA`](https://github.com/OSGeo/PROJ-data/blob/master/README.DATA) and `copyright_and_licenses.csv`; the build retains the applicable licence texts.
- ICU4C — Unicode License v3. [Source](https://github.com/unicode-org/icu); [`LICENSE`](https://github.com/unicode-org/icu/blob/release-78-1/LICENSE).
- MIT Kerberos (krb5) — MIT. [Source](https://github.com/krb5/krb5); [`NOTICE` declaration](https://github.com/krb5/krb5/blob/master/NOTICE); [conda-forge package recipe](https://github.com/conda-forge/krb5-feedstock/blob/main/recipe/meta.yaml).
- LERC — Apache-2.0. [Source](https://github.com/Esri/lerc); [`LICENSE`](https://github.com/Esri/lerc/blob/master/LICENSE); [conda-forge package recipe](https://github.com/conda-forge/lerc-feedstock/blob/main/recipe/meta.yaml).
- curl / libcurl — curl licence. [Source](https://github.com/curl/curl); [copyright and licence declaration](https://curl.se/docs/copyright.html); [conda-forge package recipe](https://github.com/conda-forge/libcurl-feedstock/blob/main/recipe/meta.yaml).
- libc++ — Apache-2.0 WITH LLVM-exception, as declared by the conda-forge package. [Source and licence declaration](https://github.com/llvm/llvm-project/blob/main/libcxx/LICENSE.TXT); [conda-forge package recipe](https://github.com/conda-forge/libcxx-feedstock/blob/main/recipe/meta.yaml).
- libdeflate — MIT. [Source and `COPYING`](https://github.com/ebiggers/libdeflate/blob/master/COPYING); [conda-forge package recipe](https://github.com/conda-forge/libdeflate-feedstock/blob/main/recipe/meta.yaml).
- nghttp2 — MIT. [Source and `COPYING`](https://github.com/nghttp2/nghttp2/blob/master/COPYING); [conda-forge package recipe](https://github.com/conda-forge/nghttp2-feedstock/blob/main/recipe/meta.yaml).
- libpsl — MIT. [Source and `COPYING`](https://github.com/rockdaboot/libpsl/blob/master/COPYING); [conda-forge package recipe](https://github.com/conda-forge/libpsl-feedstock/blob/main/recipe/meta.yaml).
- SQLite — SQLite blessing (the project dedicates its code to the public domain). [Source and declaration](https://sqlite.org/copyright.html); [conda-forge package recipe](https://github.com/conda-forge/sqlite-feedstock/blob/main/recipe/meta.yaml).
- libssh2 — BSD-3-Clause. [Source and `COPYING`](https://github.com/libssh2/libssh2/blob/master/COPYING); [conda-forge package recipe](https://github.com/conda-forge/libssh2-feedstock/blob/main/recipe/meta.yaml).
- libxml2 — licence terms declared in its `Copyright` file. [Source](https://gitlab.gnome.org/GNOME/libxml2); [`Copyright`](https://gitlab.gnome.org/GNOME/libxml2/-/blob/master/Copyright).
- libxslt — licence terms declared in its `Copyright` file. [Source](https://gitlab.gnome.org/GNOME/libxslt); [`Copyright`](https://gitlab.gnome.org/GNOME/libxslt/-/blob/master/Copyright).
- LZ4 — BSD-2-Clause. [Source](https://github.com/lz4/lz4); [`lib/LICENSE`](https://github.com/lz4/lz4/blob/v1.10.0/lib/LICENSE). The bundled xxHash code has a separate [BSD-2-Clause notice](https://github.com/lz4/lz4/blob/v1.10.0/lib/xxhash.c).
- OpenSSL — Apache-2.0. [Source](https://github.com/openssl/openssl); [`LICENSE.txt`](https://github.com/openssl/openssl/blob/openssl-3.5.8/LICENSE.txt).
- Zstandard — BSD-3-Clause for the bundled library. [Source](https://github.com/facebook/zstd); [`LICENSE`](https://github.com/facebook/zstd/blob/v1.5.7/LICENSE). Bundled divsufsort code has a separate [MIT-style notice](https://github.com/facebook/zstd/blob/v1.5.7/lib/dictBuilder/divsufsort.c).
- GNU C Library (glibc) — LGPL-2.1-or-later for the library, with file-specific GPL-2.0 and GFDL terms declared by the Ubuntu package. [Source](https://sourceware.org/glibc/); [Ubuntu `libc6` package declaration](https://packages.ubuntu.com/jammy/libc6).
- GCC runtime libraries (`libgcc` and `libstdc++`) — GPL-3.0-or-later WITH GCC Runtime Library Exception 3.1, as declared by Ubuntu's `gcc-12-base` copyright file. [Source](https://gcc.gnu.org/); [Ubuntu `gcc-12-base` package declaration](https://packages.ubuntu.com/jammy/gcc-12-base).
- musl — MIT and file-specific permissive or public-domain terms, as declared by Ubuntu. [Source](https://musl.libc.org/); [Ubuntu `musl` package declaration](https://packages.ubuntu.com/jammy/musl).
- util-linux libuuid — BSD-3-Clause, LGPL-2.1-or-later and public-domain terms for the shipped library files, as declared by Ubuntu. [Source](https://github.com/util-linux/util-linux); [Ubuntu `libuuid1` package declaration](https://packages.ubuntu.com/jammy/libuuid1).
- uthash — BSD-1-Clause. The selected collection source [vendors uthash](https://github.com/aws/pgcollection/tree/v2.1.3/include/uthash) with its [licence declaration](https://github.com/aws/pgcollection/blob/v2.1.3/include/uthash/LICENSE).
- Microsoft Visual C++ runtime — human-reviewed redistributable component under Microsoft's [Visual Studio 2022 licence terms](https://visualstudio.microsoft.com/license-terms/) and [Visual C++ runtime redistribution list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution#visual-c-runtime-files). The [licence policy](policies/licenses.md#microsoft-visual-c-runtime) records the approval. Microsoft does not publish its source under an open-source licence.

## Cargo dependencies of pg_jsonschema

The following project entries come from the target-filtered shipped dependency set recorded for the selected Linux x86-64 PostgreSQL 15.19 archive. Other selected targets still need comparison for additional crates. The linked crates.io page supplies the project licence declaration; the repository link identifies its source.

- ahash — MIT OR Apache-2.0. [Source](https://github.com/tkaitchuck/ahash); [licence declaration](https://crates.io/crates/ahash).
- aho-corasick — Unlicense OR MIT. [Source](https://github.com/BurntSushi/aho-corasick); [licence declaration](https://crates.io/crates/aho-corasick).
- allocator-api2 — MIT OR Apache-2.0. [Source](https://github.com/zakarumych/allocator-api2); [licence declaration](https://crates.io/crates/allocator-api2).
- bit-set — Apache-2.0 OR MIT. [Source](https://github.com/contain-rs/bit-set); [licence declaration](https://crates.io/crates/bit-set).
- bit-vec — Apache-2.0 OR MIT. [Source](https://github.com/contain-rs/bit-vec); [licence declaration](https://crates.io/crates/bit-vec).
- bitflags — MIT OR Apache-2.0. [Source](https://github.com/bitflags/bitflags); [licence declaration](https://crates.io/crates/bitflags).
- bitvec — MIT. [Source](https://github.com/bitvecto-rs/bitvec); [licence declaration](https://crates.io/crates/bitvec).
- borrow-or-share — MIT-0. [Source](https://github.com/yescallop/borrow-or-share); [licence declaration](https://crates.io/crates/borrow-or-share).
- bytecount — Apache-2.0/MIT. [Source](https://github.com/llogiq/bytecount); [licence declaration](https://crates.io/crates/bytecount).
- cee-scape — MIT OR Apache-2.0. [Source](https://github.com/pnkfelix/cee-scape); [licence declaration](https://crates.io/crates/cee-scape).
- cfg-if — MIT OR Apache-2.0. [Source](https://github.com/rust-lang/cfg-if); [licence declaration](https://crates.io/crates/cfg-if).
- convert_case — MIT. [Source](https://github.com/rutrum/convert-case); [licence declaration](https://crates.io/crates/convert_case).
- data-encoding — MIT. [Source](https://github.com/ia0/data-encoding); [licence declaration](https://crates.io/crates/data-encoding).
- email_address — MIT. [Source](https://github.com/johnstonskj/rust-email_address.git); [licence declaration](https://crates.io/crates/email_address).
- enum-map — MIT OR Apache-2.0. [Source](https://codeberg.org/xfix/enum-map); [licence declaration](https://crates.io/crates/enum-map).
- equivalent — Apache-2.0 OR MIT. [Source](https://github.com/indexmap-rs/equivalent); [licence declaration](https://crates.io/crates/equivalent).
- eyre — MIT OR Apache-2.0. [Source](https://github.com/eyre-rs/eyre); [licence declaration](https://crates.io/crates/eyre).
- fancy-regex — MIT. [Source](https://github.com/fancy-regex/fancy-regex); [licence declaration](https://crates.io/crates/fancy-regex).
- fixedbitset — MIT OR Apache-2.0. [Source](https://github.com/petgraph/fixedbitset); [licence declaration](https://crates.io/crates/fixedbitset).
- fluent-uri — MIT. [Source](https://github.com/yescallop/fluent-uri-rs); [licence declaration](https://crates.io/crates/fluent-uri).
- foldhash — Zlib. [Source](https://github.com/orlp/foldhash); [licence declaration](https://crates.io/crates/foldhash).
- fraction — MIT/Apache-2.0. [Source](https://github.com/dnsl48/fraction.git); [licence declaration](https://crates.io/crates/fraction).
- funty — MIT. [Source](https://github.com/myrrlyn/funty); [licence declaration](https://crates.io/crates/funty).
- getrandom — MIT OR Apache-2.0. [Source](https://github.com/rust-random/getrandom); [licence declaration](https://crates.io/crates/getrandom).
- half — MIT OR Apache-2.0. [Source](https://github.com/starkat99/half-rs); [licence declaration](https://crates.io/crates/half).
- hashbrown — MIT OR Apache-2.0. [Source](https://github.com/rust-lang/hashbrown); [licence declaration](https://crates.io/crates/hashbrown).
- icu_collections — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/icu_collections).
- icu_locale_core — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/icu_locale_core).
- icu_normalizer — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/icu_normalizer).
- icu_normalizer_data — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/icu_normalizer_data).
- icu_properties — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/icu_properties).
- icu_properties_data — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/icu_properties_data).
- icu_provider — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/icu_provider).
- idna — MIT OR Apache-2.0. [Source](https://github.com/servo/rust-url/); [licence declaration](https://crates.io/crates/idna).
- idna_adapter — Apache-2.0 OR MIT. [Source](https://github.com/hsivonen/idna_adapter); [licence declaration](https://crates.io/crates/idna_adapter).
- indenter — MIT OR Apache-2.0. [Source](https://github.com/yaahc/indenter); [licence declaration](https://crates.io/crates/indenter).
- indexmap — Apache-2.0 OR MIT. [Source](https://github.com/indexmap-rs/indexmap); [licence declaration](https://crates.io/crates/indexmap).
- itoa — MIT OR Apache-2.0. [Source](https://github.com/dtolnay/itoa); [licence declaration](https://crates.io/crates/itoa).
- jsonschema — MIT. [Source](https://github.com/Stranger6667/jsonschema); [licence declaration](https://crates.io/crates/jsonschema).
- lazy_static — MIT OR Apache-2.0. [Source](https://github.com/rust-lang-nursery/lazy-static.rs); [licence declaration](https://crates.io/crates/lazy_static).
- libc — MIT OR Apache-2.0. [Source](https://github.com/rust-lang/libc); [licence declaration](https://crates.io/crates/libc).
- litemap — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/litemap).
- lock_api — MIT OR Apache-2.0. [Source](https://github.com/Amanieu/parking_lot); [licence declaration](https://crates.io/crates/lock_api).
- memchr — Unlicense OR MIT. [Source](https://github.com/BurntSushi/memchr); [licence declaration](https://crates.io/crates/memchr).
- num — MIT OR Apache-2.0. [Source](https://github.com/rust-num/num); [licence declaration](https://crates.io/crates/num).
- num-bigint — MIT OR Apache-2.0. [Source](https://github.com/rust-num/num-bigint); [licence declaration](https://crates.io/crates/num-bigint).
- num-cmp — MIT/Apache-2.0. [Source](https://github.com/lifthrasiir/num-cmp); [licence declaration](https://crates.io/crates/num-cmp).
- num-complex — MIT OR Apache-2.0. [Source](https://github.com/rust-num/num-complex); [licence declaration](https://crates.io/crates/num-complex).
- num-integer — MIT OR Apache-2.0. [Source](https://github.com/rust-num/num-integer); [licence declaration](https://crates.io/crates/num-integer).
- num-iter — MIT OR Apache-2.0. [Source](https://github.com/rust-num/num-iter); [licence declaration](https://crates.io/crates/num-iter).
- num-rational — MIT OR Apache-2.0. [Source](https://github.com/rust-num/num-rational); [licence declaration](https://crates.io/crates/num-rational).
- num-traits — MIT OR Apache-2.0. [Source](https://github.com/rust-num/num-traits); [licence declaration](https://crates.io/crates/num-traits).
- once_cell — MIT OR Apache-2.0. [Source](https://github.com/matklad/once_cell); [licence declaration](https://crates.io/crates/once_cell).
- outref — MIT. [Source](https://github.com/Nugine/outref); [licence declaration](https://crates.io/crates/outref).
- parking_lot — MIT OR Apache-2.0. [Source](https://github.com/Amanieu/parking_lot); [licence declaration](https://crates.io/crates/parking_lot).
- parking_lot_core — MIT OR Apache-2.0. [Source](https://github.com/Amanieu/parking_lot); [licence declaration](https://crates.io/crates/parking_lot_core).
- percent-encoding — MIT OR Apache-2.0. [Source](https://github.com/servo/rust-url/); [licence declaration](https://crates.io/crates/percent-encoding).
- petgraph — MIT OR Apache-2.0. [Source](https://github.com/petgraph/petgraph); [licence declaration](https://crates.io/crates/petgraph).
- pgrx — MIT. [Source](https://github.com/pgcentralfoundation/pgrx/); [licence declaration](https://crates.io/crates/pgrx).
- pgrx-pg-sys — MIT. [Source](https://github.com/pgcentralfoundation/pgrx/); [licence declaration](https://crates.io/crates/pgrx-pg-sys).
- pgrx-sql-entity-graph — MIT. [Source](https://github.com/pgcentralfoundation/pgrx/); [licence declaration](https://crates.io/crates/pgrx-sql-entity-graph).
- potential_utf — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/potential_utf).
- proc-macro2 — MIT OR Apache-2.0. [Source](https://github.com/dtolnay/proc-macro2); [licence declaration](https://crates.io/crates/proc-macro2).
- quote — MIT OR Apache-2.0. [Source](https://github.com/dtolnay/quote); [licence declaration](https://crates.io/crates/quote).
- radium — MIT. [Source](https://github.com/bitvecto-rs/radium); [licence declaration](https://crates.io/crates/radium).
- ref-cast — MIT OR Apache-2.0. [Source](https://github.com/dtolnay/ref-cast); [licence declaration](https://crates.io/crates/ref-cast).
- referencing — MIT. [Source](https://github.com/Stranger6667/jsonschema); [licence declaration](https://crates.io/crates/referencing).
- regex — MIT OR Apache-2.0. [Source](https://github.com/rust-lang/regex); [licence declaration](https://crates.io/crates/regex).
- regex-automata — MIT OR Apache-2.0. [Source](https://github.com/rust-lang/regex); [licence declaration](https://crates.io/crates/regex-automata).
- regex-syntax — MIT OR Apache-2.0. [Source](https://github.com/rust-lang/regex); [licence declaration](https://crates.io/crates/regex-syntax).
- ryu — Apache-2.0 OR BSL-1.0. [Source](https://github.com/dtolnay/ryu); [licence declaration](https://crates.io/crates/ryu).
- scopeguard — MIT OR Apache-2.0. [Source](https://github.com/bluss/scopeguard); [licence declaration](https://crates.io/crates/scopeguard).
- seahash — MIT. [Source](https://gitlab.redox-os.org/redox-os/seahash); [licence declaration](https://crates.io/crates/seahash).
- serde — MIT OR Apache-2.0. [Source](https://github.com/serde-rs/serde); [licence declaration](https://crates.io/crates/serde).
- serde_cbor — MIT/Apache-2.0. [Source](https://github.com/pyfisch/cbor); [licence declaration](https://crates.io/crates/serde_cbor).
- serde_core — MIT OR Apache-2.0. [Source](https://github.com/serde-rs/serde); [licence declaration](https://crates.io/crates/serde_core).
- serde_json — MIT OR Apache-2.0. [Source](https://github.com/serde-rs/json); [licence declaration](https://crates.io/crates/serde_json).
- smallvec — MIT OR Apache-2.0. [Source](https://github.com/servo/rust-smallvec); [licence declaration](https://crates.io/crates/smallvec).
- stable_deref_trait — MIT OR Apache-2.0. [Source](https://github.com/storyyeller/stable_deref_trait); [licence declaration](https://crates.io/crates/stable_deref_trait).
- syn — MIT OR Apache-2.0. [Source](https://github.com/dtolnay/syn); [licence declaration](https://crates.io/crates/syn).
- tap — MIT. [Source](https://github.com/myrrlyn/tap); [licence declaration](https://crates.io/crates/tap).
- thiserror — MIT OR Apache-2.0. [Source](https://github.com/dtolnay/thiserror); [licence declaration](https://crates.io/crates/thiserror).
- tinystr — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/tinystr).
- unescape — MIT. [Source](https://github.com/saghm/unescape-rs); [licence declaration](https://crates.io/crates/unescape).
- unicode-general-category — Apache-2.0. [Source](https://github.com/yeslogic/unicode-general-category); [licence declaration](https://crates.io/crates/unicode-general-category).
- unicode-ident — (MIT OR Apache-2.0) AND Unicode-3.0. [Source](https://github.com/dtolnay/unicode-ident); [licence declaration](https://crates.io/crates/unicode-ident).
- unicode-segmentation — MIT OR Apache-2.0. [Source](https://github.com/unicode-rs/unicode-segmentation); [licence declaration](https://crates.io/crates/unicode-segmentation).
- utf8_iter — Apache-2.0 OR MIT. [Source](https://github.com/hsivonen/utf8_iter); [licence declaration](https://crates.io/crates/utf8_iter).
- uuid — Apache-2.0 OR MIT. [Source](https://github.com/uuid-rs/uuid); [licence declaration](https://crates.io/crates/uuid).
- uuid-simd — MIT. [Source](https://github.com/Nugine/simd); [licence declaration](https://crates.io/crates/uuid-simd).
- vsimd — MIT. [Source](https://github.com/Nugine/simd); [licence declaration](https://crates.io/crates/vsimd).
- writeable — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/writeable).
- wyz — MIT. [Source](https://github.com/myrrlyn/wyz); [licence declaration](https://crates.io/crates/wyz).
- yoke — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/yoke).
- zerocopy — BSD-2-Clause OR Apache-2.0 OR MIT. [Source](https://github.com/google/zerocopy); [licence declaration](https://crates.io/crates/zerocopy).
- zerofrom — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/zerofrom).
- zerotrie — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/zerotrie).
- zerovec — Unicode-3.0. [Source](https://github.com/unicode-org/icu4x); [licence declaration](https://crates.io/crates/zerovec).

## Incomplete dependency inventory

PostGIS archives also include additional runtime libraries from the selected platform's package provider. A [diagnostic macOS PostGIS trial](support/evidence/postgis-conda-archive-39602429364/README.md) identified GEOS, GMP, ICU4C, JSON-C, krb5, LERC, Boost, curl, libc++, libdeflate, libiconv, JPEG, XZ, nghttp2, libpsl, SQLite, libssh2, libtiff, WebP, zlib, MPFR, PROJ and Zstandard in its conda package closure, alongside GDAL, PROJ-data and SFCGAL. This trial is evidence for candidate inventory entries, not publication verification. Linux uses distribution packages. The retained evidence available for this update does not include a package-to-payload manifest for selected Linux PostGIS archives, so their additional shipped projects cannot be enumerated from it without guessing. The exact platform package closures, providers and transitive dependencies vary by archive; this list does not yet enumerate every shipped project. Windows core packages similarly include the mapped vcpkg runtime libraries; this list now identifies the missing libiconv and zlib projects, while Windows package provenance and notices remain under review.

The pg_jsonschema archive statically links Cargo crates. The list above covers the shipped crates in one selected Linux archive; compare the other selected targets for additional crates before publication. Seahash 4.1.0 declares MIT but its crate package omits the licence text; the declaration decision is recorded in [policies/licenses.md](policies/licenses.md).

Complete the remaining provider-specific runtime dependencies and compare the Cargo dependency set across selected targets before treating this as an exhaustive inventory.
