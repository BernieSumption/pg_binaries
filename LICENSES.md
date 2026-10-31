# Licences

This file identifies the declared terms for PostgreSQL, the selected extension projects and dependencies copied into the distribution. Source archives and checksums are recorded in each package's `build.json`. Build tools listed separately below are not included in the downloads.

Windows PostgreSQL dependency sources and patches come from the [pinned vcpkg ports](https://github.com/microsoft/vcpkg/tree/9e593bb18ea69cc5095e012465dcd675a822ed0d/ports), selected by `packages/postgresql/internal/vcpkg-commit.txt`.

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

## Build tools

- PatchELF — GPL-3.0-or-later. Used to prepare Linux PostGIS libraries; the tool is not redistributed. [Source and licence declaration](https://github.com/NixOS/patchelf/blob/0.18.0/README.md).

## PostgreSQL build dependencies

- OpenSSL — Apache-2.0. [Source and `LICENSE.txt`](https://github.com/openssl/openssl/blob/openssl-3.5.8/LICENSE.txt); [Conda-forge package](https://anaconda.org/conda-forge/openssl); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libssl3).
- ICU4C — Unicode License v3. [Source and `LICENSE`](https://github.com/unicode-org/icu/blob/release-78.3/LICENSE); [Conda-forge package](https://anaconda.org/conda-forge/icu); [Ubuntu Jammy ICU 70 package](https://packages.ubuntu.com/jammy/libicu70).
- LZ4 — BSD-2-Clause. [Source and `lib/LICENSE`](https://github.com/lz4/lz4/blob/v1.10.0/lib/LICENSE); [Conda-forge package](https://anaconda.org/conda-forge/lz4-c); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/liblz4-1).
- Zstandard — BSD-3-Clause for the bundled library. [Source and `LICENSE`](https://github.com/facebook/zstd/blob/v1.5.7/LICENSE); [Conda-forge package](https://anaconda.org/conda-forge/zstd); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libzstd1).
- libxml2 — terms declared in its `Copyright` file. [Source and `Copyright`](https://gitlab.gnome.org/GNOME/libxml2/-/blob/master/Copyright); [Conda-forge package](https://anaconda.org/conda-forge/libxml2-16); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libxml2).
- libxslt — terms declared in its `Copyright` file. [Source and `Copyright`](https://gitlab.gnome.org/GNOME/libxslt/-/blob/master/Copyright); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libxslt1.1).
- GNU C Library — LGPL-2.1-or-later for the copied runtime libraries and loader. [Source and licence](https://sourceware.org/glibc/); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libc6).
- musl libc — MIT for the static Linux launcher. [Source and copyright declaration](https://git.musl-libc.org/cgit/musl/tree/COPYRIGHT); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/musl-dev).
- Microsoft Visual C++ runtime — Microsoft licence terms for the listed, unmodified runtime DLLs. [Visual Studio 2022 licence terms](https://visualstudio.microsoft.com/license-terms/); [redistributable-file list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution#visual-c-runtime-files).
- GNU Compiler Collection runtime libraries (`libgcc_s`, `libstdc++` and `libgfortran`) — GPL-3.0-or-later WITH GCC Runtime Library Exception 3.1. [Source and terms](https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html); [Ubuntu Jammy `libgcc-s1`](https://packages.ubuntu.com/jammy/libgcc-s1), [`libstdc++6`](https://packages.ubuntu.com/jammy/libstdc++6) and [`libgfortran5`](https://packages.ubuntu.com/jammy/libgfortran5).

## Extension build dependencies

- PCRE2 — BSD-3-Clause with the PCRE2 exception. [Source and `LICENCE.md`](https://github.com/PCRE2Project/pcre2/blob/pcre2-10.48/LICENCE.md); [Conda-forge package](https://anaconda.org/conda-forge/pcre2); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libpcre2-8-0).

## PostGIS runtime dependencies

The PostGIS archives include libraries and data from the projects below. Conda-forge records document the macOS ARM64 packages in [the lock file](packages/postgis/internal/macos-arm64/conda-lock.txt); Ubuntu Jammy package links document the Linux ARM64 provider packages and their copyright declarations.

- Blosc — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/blosc); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libblosc1).
- bzip2 — bzip2 licence, approved for the bundled library. [Source and licence](https://gitlab.com/bzip2/bzip2/-/blob/bzip2-1.0.8/LICENSE); [Conda-forge record](https://anaconda.org/conda-forge/bzip2); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libbz2-1.0).
- FreeXL — MPL-1.1. [Conda-forge record](https://anaconda.org/conda-forge/freexl); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libfreexl1).
- GDAL — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libgdal-core); [Ubuntu Jammy runtime and data packages](https://packages.ubuntu.com/jammy/libgdal30) and [`gdal-data`](https://packages.ubuntu.com/jammy/gdal-data).
- GEOS — LGPL-2.1-only. [Conda-forge record](https://anaconda.org/conda-forge/geos); [Ubuntu Jammy packages](https://packages.ubuntu.com/jammy/libgeos3.10.2) and [`libgeos-c1v5`](https://packages.ubuntu.com/jammy/libgeos-c1v5).
- giflib — MIT. [Conda-forge record](https://anaconda.org/conda-forge/giflib); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libgif7).
- GMP — GPL-2.0-or-later OR LGPL-3.0-or-later. [Conda-forge record](https://anaconda.org/conda-forge/gmp); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libgmp10).
- json-c — MIT. [Conda-forge record](https://anaconda.org/conda-forge/json-c); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libjson-c5).
- Kerberos 5 — MIT. [Conda-forge record](https://anaconda.org/conda-forge/krb5); Ubuntu Jammy packages [`libkrb5-3`](https://packages.ubuntu.com/jammy/libkrb5-3), [`libgssapi-krb5-2`](https://packages.ubuntu.com/jammy/libgssapi-krb5-2) and [`libkrb5support0`](https://packages.ubuntu.com/jammy/libkrb5support0).
- LERC — Apache-2.0. [Conda-forge record](https://anaconda.org/conda-forge/lerc).
- libarchive — BSD-2-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libarchive).
- Boost — BSL-1.0. [Conda-forge record](https://anaconda.org/conda-forge/libboost); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libboost-serialization1.74.0).
- Brotli — MIT. [Conda-forge records](https://anaconda.org/conda-forge/libbrotlicommon) for its common, decoder and encoder libraries; [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libbrotli1).
- curl — curl licence. [Conda-forge record](https://anaconda.org/conda-forge/libcurl); [Ubuntu Jammy packages](https://packages.ubuntu.com/jammy/libcurl4) and [`libcurl3-gnutls`](https://packages.ubuntu.com/jammy/libcurl3-gnutls).
- LLVM libc++ and OpenMP — Apache-2.0 WITH LLVM-exception. [libc++](https://anaconda.org/conda-forge/libcxx) and [OpenMP](https://anaconda.org/conda-forge/llvm-openmp) conda-forge records.
- libdeflate — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libdeflate); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libdeflate0).
- Expat — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libexpat); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libexpat1).
- Highway — Apache-2.0 OR BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libhwy).
- GNU libiconv — LGPL-2.1-only. [Conda-forge record](https://anaconda.org/conda-forge/libiconv).
- libjpeg-turbo — Independent JPEG Group licence and BSD-3-Clause and Zlib; its IJG terms are approved for the bundled library. [Source and IJG licence](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/README.ijg); [Conda-forge record](https://anaconda.org/conda-forge/libjpeg-turbo); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libjpeg-turbo8).
- JPEG XL — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libjxl).
- libkml — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libkml); [Ubuntu Jammy packages](https://packages.ubuntu.com/jammy/libkmlbase1), [`libkmldom1`](https://packages.ubuntu.com/jammy/libkmldom1) and [`libkmlengine1`](https://packages.ubuntu.com/jammy/libkmlengine1).
- xz/liblzma — 0BSD. [Conda-forge record](https://anaconda.org/conda-forge/liblzma); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/liblzma5).
- nghttp2 — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libnghttp2); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libnghttp2-14).
- libpng — zlib-acknowledgement. [Conda-forge record](https://anaconda.org/conda-forge/libpng); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libpng16-16).
- libpsl — MIT. [Conda-forge record](https://anaconda.org/conda-forge/libpsl); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libpsl5).
- librttopo — GPL-2.0-or-later. [Conda-forge record](https://anaconda.org/conda-forge/librttopo); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/librttopo1).
- libspatialite — MPL-1.1. [Conda-forge record](https://anaconda.org/conda-forge/libspatialite); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libspatialite7).
- SQLite — public-domain blessing, approved for the bundled runtime. [Source and declaration](https://www.sqlite.org/copyright.html); [Conda-forge record](https://anaconda.org/conda-forge/libsqlite); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libsqlite3-0).
- libssh2 — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libssh2).
- libtiff — HPND. [Conda-forge record](https://anaconda.org/conda-forge/libtiff); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libtiff5).
- libwebp — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/libwebp-base); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libwebp7).
- zlib — Zlib. [Conda-forge record](https://anaconda.org/conda-forge/libzlib); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/zlib1g).
- LZO — GPL-2.0-or-later. [Conda-forge record](https://anaconda.org/conda-forge/lzo).
- minizip — Zlib. [Conda-forge record](https://anaconda.org/conda-forge/minizip); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libminizip1).
- MPFR — LGPL-3.0-only. [Conda-forge record](https://anaconda.org/conda-forge/mpfr); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libmpfr6).
- muparser — MIT. [Conda-forge record](https://anaconda.org/conda-forge/muparser).
- PROJ — MIT. [Conda-forge record](https://anaconda.org/conda-forge/proj); [Ubuntu Jammy runtime and data packages](https://packages.ubuntu.com/jammy/libproj22) and [`proj-data`](https://packages.ubuntu.com/jammy/proj-data).
- protobuf-c — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/protobuf-c); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libprotobuf-c1).
- SFCGAL — LGPL-2.0-or-later upstream; this build uses CGAL and is distributed under GPL-3.0-or-later. [Pinned source](https://gitlab.com/SFCGAL/SFCGAL/-/tree/137203dae01faab4a1287934f9457e925e3b4383), [licence explanation](https://www.osgeo.org/projects/sfcgal/) and [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libsfcgal1).
- Snappy — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/snappy); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libsnappy1v5).
- uriparser — BSD-3-Clause. [Conda-forge record](https://anaconda.org/conda-forge/uriparser); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/liburiparser1).
- Xerces-C — Apache-2.0. [Conda-forge record](https://anaconda.org/conda-forge/xerces-c); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libxerces-c3.2).

The Linux ARM64 PostGIS archive also contains the projects below. Ubuntu package links point to Jammy package records with copyright declarations.

- SuperLU — BSD-3-Clause. [Source and licence declaration](https://github.com/xiaoyeli/superlu); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libsuperlu5).
- LAPACK and BLAS — BSD-3-Clause. [Source and licence](https://github.com/Reference-LAPACK/lapack); [Ubuntu Jammy packages](https://packages.ubuntu.com/jammy/liblapack3) and [`libblas3`](https://packages.ubuntu.com/jammy/libblas3).
- ARPACK — BSD-3-Clause. [Source](https://github.com/opencollab/arpack-ng); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libarpack2).
- Armadillo — Apache-2.0. [Source and licence declaration](https://arma.sourceforge.net/faq.html); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libarmadillo10).
- libaec — BSD-2-Clause. [Source](https://gitlab.dkrz.de/k202009/libaec); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libaec0).
- Nettle — LGPL-3.0-or-later OR GPL-2.0-or-later. [Source](https://git.lysator.liu.se/nettle/nettle); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libnettle8).
- GnuTLS — LGPL-2.1-or-later for the main library. [Source](https://gitlab.com/gnutls/gnutls); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libgnutls30).
- NSPR — MPL-2.0. [Source](https://github.com/nss-dev/nspr); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libnspr4).
- NSS — MPL-2.0, with BSD, Zlib and MIT components. [Source](https://github.com/nss-dev/nss); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libnss3).
- GNU Libtool (`libltdl`) — GPL-2.0-or-later with the generated-configuration exception. [Source and licence](https://git.savannah.gnu.org/cgit/libtool.git/tree/COPYING); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libltdl7).
- HDF5 — BSD-3-Clause for the runtime library. [Source and licence](https://github.com/HDFGroup/hdf5/blob/develop/COPYING); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libhdf5-103-1).
- Poppler — GPL-2.0-or-later OR GPL-3.0-or-later. [Source](https://gitlab.freedesktop.org/poppler/poppler); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libpoppler118).
- libtirpc — BSD-3-Clause. [Source](https://sourceforge.net/projects/libtirpc/); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libtirpc3).
- unixODBC — LGPL-2.1-or-later for the shared library. [Source](https://github.com/lurcher/unixODBC); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libodbc2).
- MySQL client — GPL-2.0-or-later. [Source](https://github.com/mysql/mysql-server); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libmysqlclient21).
- NetCDF-C — BSD-3-Clause. [Source](https://github.com/Unidata/netcdf-c); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libnetcdf19).
- GeoTIFF — MIT for the core library. [Source](https://github.com/OSGeo/libgeotiff); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libgeotiff5).
- CharLS — BSD-3-Clause. [Source](https://github.com/team-charls/charls); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libcharls2).
- FYBA — MIT for the core library; the package also contains GPL-2.0-or-later files. [Source](https://github.com/kartverket/fyba); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libfyba0).
- Alliance for Open Media codec (AOM) — BSD-2-Clause, with BSD-3-Clause files. [Source](https://aomedia.googlesource.com/aom/); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libaom3).
- dav1d — BSD-2-Clause. [Source](https://code.videolan.org/videolan/dav1d); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libdav1d5).
- libde265 — LGPL-3.0-or-later for the shared library. [Source](https://github.com/strukturag/libde265); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libde265-0).
- libheif — LGPL-3.0-or-later for the shared library. [Source](https://github.com/strukturag/libheif); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libheif1).
- GNU Libidn2 — LGPL-3.0-or-later OR GPL-2.0-or-later. [Source](https://gitlab.com/libidn/libidn2); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libidn2-0).
- jbigkit — GPL-2.0-or-later. [Source](https://www.cl.cam.ac.uk/~mgk25/jbigkit/); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libjbig0).
- Little CMS — MIT for the shared library. [Source](https://github.com/mm2/Little-CMS); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/liblcms2-2).
- p11-kit — BSD-3-Clause. [Source](https://github.com/p11-glue/p11-kit); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libp11-kit0).
- OpenJPEG — BSD-2-Clause. [Source](https://github.com/uclouvain/openjpeg); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libopenjp2-7).
- OpenLDAP — OpenLDAP Public License 2.8. [Source and licence](https://www.openldap.org/software/release/license.html); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libldap-2.5-0).
- GNU libtasn1 — LGPL-2.1-or-later for the shared library. [Source and licence](https://gitlab.com/gnutls/libtasn1); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libtasn1-6).
- GNU libunistring — LGPL-3.0-or-later OR GPL-2.0-or-later. [Source](https://www.gnu.org/software/libunistring/); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libunistring2).
- Cyrus SASL — BSD-4-Clause. [Source](https://github.com/cyrusimap/cyrus-sasl); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libsasl2-2); [SPDX declaration](https://spdx.org/licenses/BSD-4-Clause.html); [FSF free-software listing](https://www.gnu.org/licenses/license-list.html#OriginalBSD); [Debian licence listing](https://www.debian.org/legal/licenses/). The Ubuntu copyright declaration applies BSD-4-Clause to the shared library.
- NUMA library — LGPL-2.1-or-later. [Source](https://github.com/numactl/numactl); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libnuma1).
- keyutils — LGPL-2.0-or-later for the shared library. [Source](https://git.kernel.org/pub/scm/linux/kernel/git/dhowells/keyutils.git); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libkeyutils1).
- librtmp — LGPL-2.1-or-later. [Source](https://git.ffmpeg.org/rtmpdump); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/librtmp1).
- libffi — MIT. [Source](https://github.com/libffi/libffi); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libffi8).
- HDF4 — BSD-style terms. [Source](https://github.com/HDFGroup/hdf4); [Ubuntu Jammy source package and copyright](https://packages.ubuntu.com/source/jammy/hdf4).
- OGDI — MIT-style terms. [Source](https://github.com/libogdi/ogdi); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libogdi4.1).
- libssh — LGPL-2.1-or-later with the OpenSSL exception. [Source and licence](https://git.libssh.org/projects/libssh.git/tree/COPYING); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libssh-4).
- libcom_err — MIT-style terms for the `lib/et` source files, approved for the bundled library. [Source and notice](https://github.com/tytso/e2fsprogs/blob/master/lib/et/et_name.c); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libcom-err2).
- Qhull — Qhull licence, approved for the bundled runtime library. [Source and licence](https://github.com/qhull/qhull/blob/master/COPYING.txt); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libqhull-r8.0).
- CFITSIO — CFITSIO License, accepted under the MIT-style rule. [Source and licence declaration](https://heasarc.gsfc.nasa.gov/docs/software/fitsio/c/f_user/node9.html); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libcfitsio9); [SPDX declaration](https://spdx.org/licenses/CFITSIO.html).
- FreeType — GPL-2.0-only, selected from the upstream licence options for this distribution. The Ubuntu Jammy copyright file declares FTL for its packaged source. [Source and licence options](https://freetype.org/license); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libfreetype6).
- util-linux `libuuid` — BSD-3-Clause for `libuuid` source files. [Source](https://github.com/util-linux/util-linux/tree/master/libuuid); [Ubuntu Jammy package](https://packages.ubuntu.com/jammy/libuuid1).
