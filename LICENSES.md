# Licences

This file identifies the declared terms for PostgreSQL, the selected extension projects and dependencies copied into the distribution. Source archives and checksums for the selected project releases are recorded in `support.json`. Dependencies added to packaged archives are added here when their recipes are implemented.

## PostgreSQL and extension projects

- PostgreSQL — PostgreSQL License. [Source and `COPYRIGHT`](https://github.com/postgres/postgres/blob/REL_18_6/COPYRIGHT).
- pgvector — PostgreSQL License. [Source and `LICENSE`](https://github.com/pgvector/pgvector/blob/v0.8.7/LICENSE).
- PostGIS — GPL-2.0-or-later. [Source and `COPYING`](https://github.com/postgis/postgis/blob/3.6.4/COPYING).
- PostGIS TIGER Geocoder — GPL-2.0, declared in `META.json` and `COPYING` in the [2025.2 source archive](https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz).
- Address Standardizer — MIT-style terms. [Source and `COPYING`](https://github.com/postgis/address_standardizer/blob/v3.7.0/COPYING). Its US data files have no separate declared terms in this release.
- HypoPG — PostgreSQL License. [Source and `LICENSE`](https://github.com/HypoPG/hypopg/blob/1.4.4/LICENSE).
- pgcollection — Apache-2.0. [Source and `LICENSE`](https://github.com/aws/pgcollection/blob/v2.1.3/LICENSE); the source also contains a [`NOTICE`](https://github.com/aws/pgcollection/blob/v2.1.3/NOTICE).
- pg_ivm — PostgreSQL-style licence. [Source and `LICENSE`](https://github.com/sraoss/pg_ivm/blob/v1.17/LICENSE).
- pgAudit — PostgreSQL licence. [Source and `LICENSE`](https://github.com/pgaudit/pgaudit/blob/18.0/LICENSE).
- pgTAP — PostgreSQL-style permissive terms. [Source and licence declaration](https://github.com/theory/pgtap/blob/v1.3.4/README.md#copyright-and-license).
- pg_jsonschema — Apache-2.0. [Source and `LICENSE`](https://github.com/supabase/pg_jsonschema/blob/v0.3.4/LICENSE).

## PostgreSQL build dependencies

- OpenSSL — Apache-2.0. [Source and `LICENSE.txt`](https://github.com/openssl/openssl/blob/openssl-3.5.8/LICENSE.txt); [Conda-forge package](https://anaconda.org/conda-forge/openssl).
- ICU4C — Unicode License v3. [Source and `LICENSE`](https://github.com/unicode-org/icu/blob/release-78.3/LICENSE); [Conda-forge package](https://anaconda.org/conda-forge/icu).
- LZ4 — BSD-2-Clause. [Source and `lib/LICENSE`](https://github.com/lz4/lz4/blob/v1.10.0/lib/LICENSE); [Conda-forge package](https://anaconda.org/conda-forge/lz4-c).
- Zstandard — BSD-3-Clause for the bundled library. [Source and `LICENSE`](https://github.com/facebook/zstd/blob/v1.5.7/LICENSE); [Conda-forge package](https://anaconda.org/conda-forge/zstd).
- libxml2 — terms declared in its `Copyright` file. [Source and `Copyright`](https://gitlab.gnome.org/GNOME/libxml2/-/blob/master/Copyright); [Conda-forge package](https://anaconda.org/conda-forge/libxml2-16).
- libxslt — terms declared in its `Copyright` file. [Source and `Copyright`](https://gitlab.gnome.org/GNOME/libxslt/-/blob/master/Copyright).

## Extension build dependencies

- PCRE2 — BSD-3-Clause with the PCRE2 exception. [Source and `LICENCE.md`](https://github.com/PCRE2Project/pcre2/blob/pcre2-10.48/LICENCE.md); [Conda-forge package](https://anaconda.org/conda-forge/pcre2).

## PostGIS runtime dependencies

The PostGIS archive includes libraries and data from the projects below. Each linked conda-forge record declares its licence and links to the project source. The exact binary packages are selected in [the macOS ARM64 lock file](packages/postgis/macos-arm64/conda-lock.txt).

- Blosc — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/blosc).
- bzip2 — bzip2 licence, approved for the bundled library. [Source and licence](https://gitlab.com/bzip2/bzip2/-/blob/bzip2-1.0.8/LICENSE); [Conda-forge record](https://anaconda.org/conda-forge/bzip2).
- FreeXL — MPL-1.1. [Conda-forge record](https://anaconda.org/conda-forge/freexl).
- GDAL — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libgdal-core).
- GEOS — LGPL-2.1-only. [Conda-forge record](https://anaconda.org/conda-forge/geos).
- giflib — MIT. [Conda-forge record](https://anaconda.org/conda-forge/giflib).
- GMP — GPL-2.0-or-later OR LGPL-3.0-or-later. [Conda-forge record](https://anaconda.org/conda-forge/gmp).
- json-c — MIT. [Conda-forge record](https://anaconda.org/conda-forge/json-c).
- Kerberos 5 — MIT. [Conda-forge record](https://anaconda.org/conda-forge/krb5).
- LERC — Apache-2.0. [Conda-forge record](https://anaconda.org/conda-forge/lerc).
- libarchive — BSD-2-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libarchive).
- Boost — BSL-1.0. [Conda-forge record](https://anaconda.org/conda-forge/libboost).
- Brotli — MIT. [Conda-forge records](https://anaconda.org/conda-forge/libbrotlicommon) for its common, decoder and encoder libraries.
- curl — curl licence. [Conda-forge record](https://anaconda.org/conda-forge/libcurl).
- LLVM libc++ and OpenMP — Apache-2.0 WITH LLVM-exception. [libc++](https://anaconda.org/conda-forge/libcxx) and [OpenMP](https://anaconda.org/conda-forge/llvm-openmp) conda-forge records.
- libdeflate — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libdeflate).
- Expat — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libexpat).
- Highway — Apache-2.0 OR BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libhwy).
- GNU libiconv — LGPL-2.1-only. [Conda-forge record](https://anaconda.org/conda-forge/libiconv).
- libjpeg-turbo — Independent JPEG Group licence and BSD-3-Clause and Zlib; its IJG terms are approved for the bundled library. [Source and IJG licence](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/README.ijg); [Conda-forge record](https://anaconda.org/conda-forge/libjpeg-turbo).
- JPEG XL — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libjxl).
- libkml — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libkml).
- xz/liblzma — 0BSD. [Conda-forge record](https://anaconda.org/conda-forge/liblzma).
- nghttp2 — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libnghttp2).
- libpng — zlib-acknowledgement. [Conda-forge record](https://anaconda.org/conda-forge/libpng).
- libpsl — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libpsl).
- librttopo — GPL-2.0-or-later. [Conda-forge record](https://anaconda.org/conda-forge/librttopo).
- libspatialite — MPL-1.1. [Conda-forge record](https://anaconda.org/conda-forge/libspatialite).
- SQLite — public-domain blessing, approved for the bundled runtime. [Source and declaration](https://www.sqlite.org/copyright.html); [Conda-forge record](https://anaconda.org/conda-forge/libsqlite).
- libssh2 — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libssh2).
- libtiff — HPND. [Conda-forge record](https://anaconda.org/conda-forge/libtiff).
- libwebp — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libwebp-base).
- zlib — Zlib. [Conda-forge record](https://anaconda.org/conda-forge/libzlib).
- LZO — GPL-2.0-or-later. [Conda-forge record](https://anaconda.org/conda-forge/lzo).
- minizip — Zlib. [Conda-forge record](https://anaconda.org/conda-forge/minizip).
- MPFR — LGPL-3.0-only. [Conda-forge record](https://anaconda.org/conda-forge/mpfr).
- muparser — MIT. [Conda-forge record](https://anaconda.org/conda-forge/muparser).
- PROJ — MIT. [Conda-forge record](https://anaconda.org/conda-forge/proj).
- protobuf-c — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/protobuf-c).
- SFCGAL — LGPL-2.0-or-later upstream; this build uses CGAL and is distributed under GPL-3.0-or-later. [Pinned source](https://gitlab.com/SFCGAL/SFCGAL/-/tree/137203dae01faab4a1287934f9457e925e3b4383) and [licence explanation](https://www.osgeo.org/projects/sfcgal/).
- Snappy — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/snappy).
- uriparser — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/uriparser).
- Xerces-C — Apache-2.0. [Conda-forge record](https://anaconda.org/conda-forge/xerces-c).
