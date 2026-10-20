#!/usr/bin/env bash
set -euo pipefail

pg_version=${PG_VERSION:-18.6}
extension_version=${ADDRESS_STANDARDIZER_VERSION:-3.7.0}
if [[ "$extension_version" != 3.7.0 ]]; then
  echo "Address Standardizer recipe supports 3.7.0; selected $extension_version" >&2
  exit 2
fi
extension_sql_version=3.7
extension_commit=fa11ff53eb49b863d9ffff37f6afd5ff9299c581
pcre2_version=10.48
pcre2_sha256=b6c68fdf6f3ac31388b50aa89ff0fc49c00c987c16e7b5146491d12003f2c8ed
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture:$(uname -m)" in x86_64:x86_64|arm64:aarch64) ;; *) echo "Architecture mismatch" >&2; exit 2 ;; esac

core_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
archive="address-standardizer-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$core_archive.sha256"
mkdir -p /work/core /work/source /out
tar -xzf "$core_archive" -C /work/core
mv /work/core/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"

cd /work/source
curl -fL --retry 3 -o "pcre2-${pcre2_version}.tar.bz2" \
  "https://github.com/PCRE2Project/pcre2/releases/download/pcre2-${pcre2_version}/pcre2-${pcre2_version}.tar.bz2"
printf '%s  %s\n' "$pcre2_sha256" "pcre2-${pcre2_version}.tar.bz2" | sha256sum -c -
tar -xjf "pcre2-${pcre2_version}.tar.bz2"
cd "pcre2-${pcre2_version}"
./configure --prefix=/work/pcre2 --libdir=/work/pcre2/lib --enable-shared --disable-static \
  --disable-pcre2-16 --disable-pcre2-32 --enable-jit
make -s -j"$(nproc)"
make -s install
cp -a /work/pcre2/lib/libpcre2-8.so* "$pgroot/lib/"

cd /work/source
git init -q address_standardizer
git -C address_standardizer remote add origin https://github.com/postgis/address_standardizer.git
git -C address_standardizer fetch --depth 1 origin refs/tags/v3.7.0
git -C address_standardizer checkout --detach FETCH_HEAD
test "$(git -C address_standardizer rev-parse HEAD)" = "$extension_commit"
cd address_standardizer
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" address_standardizer.control)" = "$extension_sql_version"
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" address_standardizer_data_us.control)" = "$extension_sql_version"
pkglibdir=$("$pgroot/bin/pg_config" --pkglibdir)
sharedir=$("$pgroot/bin/pg_config" --sharedir)
pkglib_rel=${pkglibdir#"$pgroot"/}
test "$pkglib_rel" != "$pkglibdir"
lib_rel=$(realpath --relative-to="$pkglibdir" "$pgroot/lib")
module_rpath='\$$ORIGIN'
expected_module_rpath='$ORIGIN'
if [[ $lib_rel != . ]]; then
  module_rpath+="/$lib_rel"
  expected_module_rpath+="/$lib_rel"
fi
make -s PG_CONFIG="$pgroot/bin/pg_config" \
  PG_CPPFLAGS="-I/work/pcre2/include -DAS_VERSION=\\\"3.7\\\" -DPCRE_VERSION=2" \
  PG_LDFLAGS="-L/work/pcre2/lib -Wl,-rpath,$module_rpath" -j"$(nproc)"
make -s PG_CONFIG="$pgroot/bin/pg_config" \
  PG_CPPFLAGS="-I/work/pcre2/include -DAS_VERSION=\\\"3.7\\\" -DPCRE_VERSION=2" \
  PG_LDFLAGS="-L/work/pcre2/lib -Wl,-rpath,$module_rpath" install

test -s "$pkglibdir/address_standardizer.so"
readelf -dW "$pkglibdir/address_standardizer.so" | grep -Fq "[$expected_module_rpath]"
test -s "$sharedir/extension/address_standardizer.control"
test -s "$sharedir/extension/address_standardizer_data_us.control"
test -s "$sharedir/extension/address_standardizer_data_us--${extension_sql_version}.sql"
package=/work/package/address_standardizer
mkdir -p "$package/$pkglib_rel" "$package/share/extension" "$package/lib" "$package/LICENSES"
cp "$pkglibdir/address_standardizer.so" "$package/$pkglib_rel/"
cp "$sharedir/extension/address_standardizer"* "$package/share/extension/"
cp -a "$pgroot/lib"/libpcre2-8.so* "$package/lib/"
cp "COPYING" "$package/LICENSES/Address-Standardizer.txt"
cp "/work/source/pcre2-${pcre2_version}/LICENCE.md" "$package/LICENSES/PCRE2.txt"
cp "/work/source/pcre2-${pcre2_version}/deps/sljit/LICENSE" "$package/LICENSES/SLJIT.txt"
cp "COPYING" /out/Address-Standardizer-COPYING.txt
cp "/work/source/pcre2-${pcre2_version}/LICENCE.md" /out/PCRE2-LICENCE.md
cp "/work/source/pcre2-${pcre2_version}/deps/sljit/LICENSE" /out/SLJIT-LICENSE.txt

cat > "$package/LICENSES/license-inventory.json" <<EOF
{
  "schema_version": 1,
  "components": [
    {"component": "Address Standardizer", "version": "${extension_version}", "payload_paths": ["${pkglib_rel}/address_standardizer.so", "share/extension"], "license_file": "Address-Standardizer.txt", "license_source": "https://github.com/postgis/address_standardizer/blob/v3.7.0/COPYING", "source_url": "https://github.com/postgis/address_standardizer/tree/v3.7.0", "source_commit": "${extension_commit}", "redistribution_review": {"status": "resolved", "basis": "Address Standardizer 3.7.0 uses the upstream MIT-style COPYING permission terms. The archive includes the complete copyright and permission notice. Under the repository-licence rule, those terms also cover its data files without separate terms. No source delivery is required for this binary distribution.", "source_obligation": "none"}},
    {"component": "PCRE2", "version": "${pcre2_version}", "payload_paths": ["lib/libpcre2-8.so"], "license_file": "PCRE2.txt", "additional_license_files": ["SLJIT.txt"], "license_source": "https://github.com/PCRE2Project/pcre2/blob/pcre2-${pcre2_version}/LICENCE.md", "additional_license_sources": ["https://github.com/PCRE2Project/pcre2/blob/pcre2-${pcre2_version}/deps/sljit/LICENSE"], "source_url": "https://github.com/PCRE2Project/pcre2/releases/download/pcre2-${pcre2_version}/pcre2-${pcre2_version}.tar.bz2", "source_sha256": "${pcre2_sha256}", "redistribution_review": {"status": "resolved", "basis": "PCRE2 10.48 uses BSD-3-Clause WITH PCRE2-exception; its enabled JIT includes bundled SLJIT under a separate two-clause BSD licence. The archive includes both complete licence notices, conditions and disclaimers and must not use the Cambridge or contributor names for endorsement. Neither licence requires source delivery for this binary distribution.", "source_obligation": "none"}}
  ]
}
EOF
cat > /work/package/metadata.json <<EOF
{"project":"Address Standardizer","version":"${extension_version}","sql_names":["address_standardizer","address_standardizer_data_us"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[],"postgresql_version":"${pg_version}","platform":"linux","architecture":"${architecture}","payload_paths":["address_standardizer/${pkglib_rel}/address_standardizer.so","address_standardizer/lib/libpcre2-8.so","address_standardizer/share/extension","address_standardizer/LICENSES"],"source":{"url":"https://github.com/postgis/address_standardizer/tree/v3.7.0","commit":"${extension_commit}"},"dependencies":[{"name":"PCRE2","version":"${pcre2_version}","sha256":"${pcre2_sha256}"}],"license_inventory":"address_standardizer/LICENSES/license-inventory.json"}
EOF
cp -a "$package/$pkglib_rel/address_standardizer.so" "$pkglibdir/"
cp -a "$package/share/extension/." "$sharedir/extension/"
git -C /work/source/address_standardizer rev-parse HEAD > /out/address-standardizer-commit.txt
printf 'address_standardizer_source_commit=%s\n' "$extension_commit" > /out/build-evidence.txt
printf 'pcre2_source_sha256=%s\n' "$pcre2_sha256" >> /out/build-evidence.txt
printf 'postgresql_version=%s\narchitecture=%s\n' "$pg_version" "$architecture" >> /out/build-evidence.txt

tar -C /work/package -czf "/out/$archive" address_standardizer metadata.json
cd /out
sha256sum "$archive" > "$archive.sha256"
