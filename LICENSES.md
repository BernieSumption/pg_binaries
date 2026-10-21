# Licences

This file records licence declarations for PostgreSQL, selected extensions, separately bundled dependency libraries and data. A project's own entry covers dependencies it compiles into its binary. Source and declaration links identify the upstream project and the files used by the build. Build evidence and the policy for applying declarations are in [policies/licenses.md](policies/licenses.md).

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
- pg_jsonschema — Apache-2.0. [Source and `LICENSE`](https://github.com/supabase/pg_jsonschema/tree/v0.3.4).

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
- PCRE2 — BSD-3-Clause WITH PCRE2-exception. [Source and licence declaration](https://github.com/PCRE2Project/pcre2/blob/pcre2-10.48/LICENCE.md).
- GDAL — MIT-style terms. [GDAL licence declaration](https://gdal.org/en/stable/license.html); [source release](https://download.osgeo.org/gdal/3.13.3/gdal-3.13.3.tar.gz).
- HDF5 — BSD-3-Clause. [Source](https://github.com/HDFGroup/hdf5); [`LICENSE` declaration](https://github.com/HDFGroup/hdf5/blob/develop/LICENSE).
- libaec and its SZIP-compatible `libsz` library — BSD-2-Clause. [Source](https://github.com/Deutsches-Klimarechenzentrum/libaec); [`LICENSE.txt` declaration](https://github.com/Deutsches-Klimarechenzentrum/libaec/blob/main/LICENSE.txt).
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
- LZ4 — BSD-2-Clause. [Source](https://github.com/lz4/lz4); [`lib/LICENSE`](https://github.com/lz4/lz4/blob/v1.10.0/lib/LICENSE).
- OpenSSL — Apache-2.0. [Source](https://github.com/openssl/openssl); [`LICENSE.txt`](https://github.com/openssl/openssl/blob/openssl-3.5.8/LICENSE.txt).
- Zstandard — BSD-3-Clause for the bundled library. [Source](https://github.com/facebook/zstd); [`LICENSE`](https://github.com/facebook/zstd/blob/v1.5.7/LICENSE).
- GNU C Library (glibc) — LGPL-2.1-or-later for the library, with file-specific GPL-2.0 and GFDL terms declared by the Ubuntu package. [Source](https://sourceware.org/glibc/); [Ubuntu `libc6` package declaration](https://packages.ubuntu.com/jammy/libc6).
- GCC runtime libraries (`libgcc`, `libgfortran`, `libquadmath` and `libstdc++`) — GPL-3.0-or-later WITH GCC Runtime Library Exception 3.1, as declared by Ubuntu's `gcc-12-base` copyright file. [Source](https://gcc.gnu.org/); [Ubuntu `gcc-12-base` package declaration](https://packages.ubuntu.com/jammy/gcc-12-base).
- musl — MIT and file-specific permissive or public-domain terms, as declared by Ubuntu. [Source](https://musl.libc.org/); [Ubuntu `musl` package declaration](https://packages.ubuntu.com/jammy/musl).
- util-linux libuuid — BSD-3-Clause, LGPL-2.1-or-later and public-domain terms for the shipped library files, as declared by Ubuntu. [Source](https://github.com/util-linux/util-linux); [Ubuntu `libuuid1` package declaration](https://packages.ubuntu.com/jammy/libuuid1).
- ARPACK-NG — BSD-3-Clause. [Source and `COPYING`](https://github.com/opencollab/arpack-ng/blob/master/COPYING).
- Reference BLAS and LAPACK — modified BSD licence. [LAPACK source and licence declaration](https://github.com/Reference-LAPACK/lapack); [Ubuntu Jammy `libblas3` package](https://packages.ubuntu.com/jammy/libblas3) identifies the shipped BLAS as the reference implementation.
- e2fsprogs libcom_err — human-approved MIT-style terms. [Project notice](https://github.com/tytso/e2fsprogs/blob/master/NOTICE); [C source-file licence declaration](https://github.com/tytso/e2fsprogs/blob/master/lib/et/et_name.c).
- FYBA — MIT. The source declares the MIT licence in its [README](https://github.com/kartverket/fyba#license); the Ubuntu Jammy package identifies the FYBA source package for these libraries ([`libfyba0`](https://packages.ubuntu.com/jammy/libfyba0)).
- keyutils library — LGPL. The [source project](https://kernel.googlesource.com/pub/scm/linux/kernel/git/dhowells/keyutils/) distinguishes the library's [`LICENCE.LGPL`](https://github.com/yugabyte/libkeyutils/blob/master/LICENCE.LGPL) from the GPL-licensed tools.
- JBIG-KIT — GNU GPL. [Source and licence declaration](https://github.com/nu774/jbigkit).
- p11-kit — BSD-3-Clause. [Source and `COPYING`](https://github.com/p11-glue/p11-kit/blob/master/COPYING).
- libtirpc — BSD-3-Clause. [Source and `COPYING`](https://github.com/alisw/libtirpc/blob/master/COPYING).
- GNU libtasn1 — LGPL-2.1-or-later for the library. [Source and licence declaration](https://github.com/gnutls/libtasn1/blob/master/README.md).
- GNU libunistring — LGPL-3.0-or-later OR GPL-2.0-or-later for the library and headers. [Source and licence declaration](https://github.com/gnu-mirror-unofficial/libunistring/blob/master/README).
- libssh — LGPL-2.1-or-later. [Source and licence declaration](https://github.com/canonical/libssh).
- librtmp — LGPL-2.1-or-later for the library. [Source and licence declaration](https://github.com/mstorsjo/rtmpdump/blob/master/librtmp/rtmp.h).
- AOM — BSD-3-Clause. [Source and `LICENSE`](https://aomedia.googlesource.com/aom/+/refs/heads/main/LICENSE).
- Armadillo — Apache-2.0. [Source and `LICENSE.txt`](https://gitlab.com/conradsnicta/armadillo-code/-/blob/14.2.x/LICENSE.txt).
- Blosc — BSD-3-Clause. [Source and `LICENSE.txt`](https://github.com/Blosc/c-blosc/blob/main/LICENSE.txt).
- Brotli — MIT. [Source and `LICENSE`](https://github.com/google/brotli/blob/master/LICENSE).
- bzip2 — bzip2 licence. [Source and `LICENSE`](https://gitlab.com/bzip2/bzip2/-/blob/bzip2-1.0.8/LICENSE).
- CFITSIO — ISC, as declared by the upstream [source package specification](https://github.com/HEASARC/cfitsio/blob/develop/cfitsio.spec); [source and licence file](https://github.com/HEASARC/cfitsio/tree/develop/licenses).
- CharLS — BSD-3-Clause. [Source and `LICENSE`](https://github.com/team-charls/charls/blob/main/LICENSE).
- dav1d — BSD-2-Clause. [Source and `COPYING`](https://code.videolan.org/videolan/dav1d/-/blob/master/COPYING).
- libde265 — LGPL-3.0-or-later. [Source and `COPYING`](https://github.com/strukturag/libde265/blob/master/COPYING).
- Expat — MIT. [Source and `COPYING`](https://github.com/libexpat/libexpat/blob/master/expat/COPYING).
- libffi — MIT. [Source and `LICENSE`](https://github.com/libffi/libffi/blob/master/LICENSE).
- Fontconfig — MIT. [Source and licence declaration](https://gitlab.freedesktop.org/fontconfig/fontconfig/-/blob/main/COPYING).
- FreeType — FTL (FreeType licence) OR GPL-2.0-or-later. [Source and licence declarations](https://gitlab.freedesktop.org/freetype/freetype/-/blob/master/docs/FTL.TXT).
- FreeXL — MPL-1.1. [Source and `COPYING`](https://www.gaia-gis.it/fossil/freexl/file?name=COPYING).
- libgeotiff — MIT. [Source and `LICENSE`](https://github.com/OSGeo/libgeotiff/blob/master/LICENSE).
- giflib — MIT. [Source and `COPYING`](https://sourceforge.net/p/giflib/code/ci/master/tree/COPYING).
- GnuTLS — LGPL-2.1-or-later for the library. [Source and licence declaration](https://gitlab.com/gnutls/gnutls/-/blob/master/COPYING).
- HDF4 — BSD-style licence. [Source and `COPYING`](https://github.com/HDFGroup/hdf4/blob/master/COPYING).
- libheif — LGPL-3.0-or-later. [Source and `COPYING`](https://github.com/strukturag/libheif/blob/master/COPYING).
- libidn2 — LGPL-3.0-or-later OR GPL-2.0-or-later for the library. [Source and licence declaration](https://gitlab.com/gnu-libidn/libidn2/-/blob/master/COPYING).
- libkml — BSD-3-Clause. [Source and licence declaration](https://github.com/libkml/libkml/blob/master/COPYING).
- Little CMS — MIT. [Source and `LICENSE`](https://github.com/mm2/Little-CMS/blob/master/LICENSE).
- OpenLDAP — OpenLDAP Public License. [Source and licence declaration](https://www.openldap.org/software/release/license.html).
- GNU libtool — LGPL-2.1-or-later for libltdl. [Source and `COPYING.LIB`](https://git.savannah.gnu.org/cgit/libtool.git/tree/COPYING.LIB).
- minizip — zlib licence. [Source and licence declaration](https://github.com/madler/zlib/tree/develop/contrib/minizip).
- MySQL client library — GPL-2.0 with the FOSS License Exception. [Source and licence declaration](https://github.com/mysql/mysql-server/blob/8.0/LICENSE).
- Nettle, including its hogweed library — LGPL-3.0-or-later OR GPL-2.0-or-later. [Source and licence declaration](https://git.lysator.liu.se/nettle/nettle/-/blob/master/COPYING.LESSERv3).
- Mozilla NSPR — MPL-2.0. [Source and `LICENSE`](https://github.com/nss-dev/nspr/blob/master/LICENSE).
- Mozilla NSS — MPL-2.0. [Source and `LICENSE`](https://github.com/nss-dev/nss/blob/main/LICENSE).
- NUMA library — LGPL-2.1-or-later. [Source and `COPYING`](https://github.com/numactl/numactl/blob/master/COPYING).
- unixODBC — LGPL-2.1-or-later for the libraries. [Source and licence declaration](https://github.com/lurcher/unixODBC/blob/master/COPYING).
- OGDI — MIT. [Source and `LICENSE`](https://github.com/libogdi/ogdi/blob/master/LICENSE).
- OpenJPEG — BSD-2-Clause. [Source and `LICENSE`](https://github.com/uclouvain/openjpeg/blob/master/LICENSE).
- libpng — libpng licence. [Source and licence declaration](http://www.libpng.org/pub/png/src/libpng-LICENSE.txt).
- Poppler — GPL-2.0-or-later. [Source and `COPYING`](https://gitlab.freedesktop.org/poppler/poppler/-/blob/master/COPYING).
- Qhull — Qhull licence. [Source and licence declaration](https://github.com/qhull/qhull/blob/master/COPYING.txt).
- librttopo — GPL-2.0-or-later. [Source and `COPYING`](https://git.osgeo.org/gitea/rttopo/librttopo/src/branch/master/COPYING).
- Cyrus SASL — BSD-style licence. [Source and `COPYING`](https://github.com/cyrusimap/cyrus-sasl/blob/master/COPYING).
- Snappy — BSD-3-Clause. [Source and `COPYING`](https://github.com/google/snappy/blob/main/COPYING).
- SpatiaLite — MPL-1.1. [Source and licence declaration](https://www.gaia-gis.it/fossil/libspatialite/file?name=COPYING).
- SuperLU — BSD-3-Clause. [Source and `License.txt`](https://github.com/xiaoyeli/superlu/blob/master/License.txt).
- uriparser — BSD-3-Clause. [Source and `COPYING`](https://github.com/uriparser/uriparser/blob/main/COPYING).
- x265 — GPL-2.0-or-later. [Source and `COPYING`](https://bitbucket.org/multicoreware/x265_git/src/master/COPYING).
- Xerces-C++ — Apache-2.0. [Source and `LICENSE`](https://github.com/apache/xerces-cpp/blob/master/LICENSE).
- Microsoft Visual C++ runtime — human-reviewed redistributable component under Microsoft's [Visual Studio 2022 licence terms](https://visualstudio.microsoft.com/license-terms/) and [Visual C++ runtime redistribution list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution#visual-c-runtime-files). The [licence policy](policies/licenses.md#microsoft-visual-c-runtime) records the approval. Microsoft does not publish its source under an open-source licence.

## Windows runtime dependencies

The Windows PostGIS trial archive's runtime owner report identifies these separately copied libraries. The MSYS2 package pages declare the licences for the packages used to supply them.

- Abseil — Apache-2.0. [Source and `LICENSE`](https://github.com/abseil/abseil-cpp/blob/master/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-abseil-cpp).
- Apache Arrow and Parquet — Apache-2.0. [Source and `LICENSE.txt`](https://github.com/apache/arrow/blob/main/LICENSE.txt); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-arrow).
- Crypto++ — Boost Software License 1.0. [Source and licence declaration](https://github.com/weidai11/cryptopp/blob/master/License.txt); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-crypto%2B%2B).
- gettext runtime (`libintl`) — LGPL-2.1-or-later. [Source and `intl/COPYING.LIB`](https://github.com/autotools-mirror/gettext/blob/master/gettext-runtime/intl/COPYING.LIB); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-gettext-runtime).
- GLib — LGPL-2.1-or-later. [Source and `COPYING`](https://gitlab.gnome.org/GNOME/glib/-/blob/main/COPYING); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-glib2).
- Graphite2 — LGPL-2.1-or-later, GPL-2.0-or-later, or MPL-1.1, as offered by upstream. [Source and licence declaration](https://github.com/silnrsi/graphite/blob/master/COPYING); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-graphite2).
- HarfBuzz — MIT. [Source and `COPYING`](https://github.com/harfbuzz/harfbuzz/blob/main/COPYING); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-harfbuzz).
- Highway — Apache-2.0. [Source and `LICENSE`](https://github.com/google/highway/blob/master/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-highway).
- Imath — BSD-3-Clause. [Source and `LICENSE.md`](https://github.com/AcademySoftwareFoundation/Imath/blob/main/LICENSE.md); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-imath).
- Kvazaar — BSD-3-Clause. [Source and `COPYING`](https://github.com/ultravideo/kvazaar/blob/master/COPYING); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-kvazaar).
- libarchive — BSD-2-Clause. [Source and `COPYING`](https://github.com/libarchive/libarchive/blob/master/COPYING); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-libarchive).
- libb2 — CC0-1.0 or MIT. [Source and licence declarations](https://github.com/BLAKE2/libb2/tree/master); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-libb2).
- GCC OpenMP runtime (`libgomp`) — GPL-3.0-or-later WITH GCC Runtime Library Exception 3.1. [Source and licence declaration](https://gcc.gnu.org/git/?p=gcc.git;a=blob;f=COPYING.RUNTIME); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-libgomp).
- JPEG XL — BSD-3-Clause. [Source and `LICENSE`](https://github.com/libjxl/libjxl/blob/main/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-libjxl).
- MariaDB Connector/C — LGPL-2.1-or-later. [Source and `COPYING.LIB`](https://github.com/mariadb-corporation/mariadb-connector-c/blob/3.4/COPYING.LIB); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-libmariadbclient).
- OpenBLAS — BSD-3-Clause. [Source and `LICENSE`](https://github.com/OpenMathLib/OpenBLAS/blob/develop/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-openblas).
- OpenEXR — BSD-3-Clause. [Source and `LICENSE.md`](https://github.com/AcademySoftwareFoundation/openexr/blob/main/LICENSE.md); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-openexr).
- OpenH264 — BSD-2-Clause. [Source and `LICENSE`](https://github.com/cisco/openh264/blob/master/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-openh264).
- OpenJPH — BSD-2-Clause. [Source and `LICENSE`](https://github.com/aous72/OpenJPH/blob/master/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-openjph).
- PoDoFo — LGPL-2.0-or-later and GPL-2.0-or-later, as declared for the MSYS2 package. [Source](https://github.com/podofo/podofo); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-podofo).
- rav1e — BSD-2-Clause. [Source and `LICENSE`](https://github.com/xiph/rav1e/blob/master/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-rav1e).
- RE2 — BSD-3-Clause. [Source and `LICENSE`](https://github.com/google/re2/blob/main/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-re2).
- simdjson — Apache-2.0. [Source and `LICENSE`](https://github.com/simdjson/simdjson/blob/master/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-simdjson).
- SVT-AV1 — BSD-3-Clause. [Source and `LICENSE.md`](https://gitlab.com/AOMediaCodec/SVT-AV1/-/blob/master/LICENSE.md); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-svt-av1).
- Thrift — Apache-2.0. [Source and `LICENSE`](https://github.com/apache/thrift/blob/master/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-thrift).
- utf8proc — MIT. [Source and `LICENSE.md`](https://github.com/JuliaStrings/utf8proc/blob/master/LICENSE.md); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-libutf8proc).
- MinGW-w64 winpthreads — MIT and BSD-3-Clause for the library components. [Source and `COPYING`](https://github.com/mingw-w64/mingw-w64/tree/master/mingw-w64-libraries/winpthreads); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-libwinpthread).
- libzip — BSD-3-Clause. [Source and `LICENSE`](https://github.com/nih-at/libzip/blob/main/LICENSE); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-libzip).
- nghttp3 — MIT. [Source and `COPYING`](https://github.com/ngtcp2/nghttp3/blob/main/COPYING); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-nghttp3).
- ngtcp2 — MIT. [Source and `COPYING`](https://github.com/ngtcp2/ngtcp2/blob/main/COPYING); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-ngtcp2).
- zlib-ng — zlib licence. [Source and `LICENSE.md`](https://github.com/zlib-ng/zlib-ng/blob/develop/LICENSE.md); [MSYS2 package declaration](https://packages.msys2.org/package/mingw-w64-x86_64-zlib-ng).
- x264 — GPL-2.0. [Source](https://code.videolan.org/videolan/x264); [upstream licence declaration](https://x264.org/licensing/); [MSYS2 `libx264` package](https://packages.msys2.org/package/mingw-w64-x86_64-libx264).

## Incomplete dependency inventory

The [selected Linux PostGIS owner report](support/evidence/postgis-publication-39618831130/x86_64/18.6/runtime-package-owners.txt) identifies the 114 libraries bundled with that archive; their projects are listed above. Compare selected macOS and Windows archives with this list before treating it as complete across the support matrix. The [macOS conda trial report](support/evidence/postgis-conda-archive-39602429364/README.md) and [Windows trial report](support/evidence/postgis-windows-publication-39646973668/runtime-package-owners.txt) provide starting points.
