#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
if [[ ! $pg_version =~ ^(17|18)\.[0-9]+$ ]]; then
  echo "Linux pilot currently supports PostgreSQL 17 and 18 minors only: $pg_version" >&2
  exit 2
fi
vector_version=0.8.7
pg_archive="postgresql-${pg_version}-linux-x86_64.tar.gz"
vector_archive="pgvector-${vector_version}-postgresql-${pg_version}-linux-x86_64.tar.gz"
mkdir -p /work/src /work/stage/postgresql /work/stage/pgvector /out
cd /work/src
curl -fL --retry 3 -o postgresql.tar.bz2 "https://ftp.postgresql.org/pub/source/v${pg_version}/postgresql-${pg_version}.tar.bz2"
tar -xf postgresql.tar.bz2
cd "postgresql-${pg_version}"
./configure --prefix=/opt/postgresql --with-icu --with-lz4 --with-zstd \
  --with-openssl --with-libxml --with-libxslt --with-zlib --with-uuid=e2fs --without-readline
make -j "$(nproc)"
make install
make -C contrib -j "$(nproc)"
make -C contrib install
cd /work/src
curl -fL --retry 3 -o pgvector.tar.gz "https://github.com/pgvector/pgvector/archive/refs/tags/v${vector_version}.tar.gz"
tar -xf pgvector.tar.gz
cd "pgvector-${vector_version}"
make -j "$(nproc)" PG_CONFIG=/opt/postgresql/bin/pg_config OPTFLAGS=
make install PG_CONFIG=/opt/postgresql/bin/pg_config OPTFLAGS=
cp -a /opt/postgresql/. /work/stage/postgresql/
# The extension is delivered separately and must not be silently bundled.
mkdir -p /work/stage/pgvector/lib /work/stage/pgvector/share/extension /work/stage/pgvector/LICENSES
mv /work/stage/postgresql/lib/vector.so /work/stage/pgvector/lib/
mv /work/stage/postgresql/share/extension/vector* /work/stage/pgvector/share/extension/
cp LICENSE /work/stage/pgvector/LICENSES/pgvector.txt
mkdir -p /work/stage/postgresql/LICENSES
cp "/work/src/postgresql-${pg_version}/COPYRIGHT" /work/stage/postgresql/LICENSES/PostgreSQL.txt
builtins=$(python3 /usr/local/bin/discover-builtins /work/stage/postgresql)

# Copy non-glibc runtime libraries into the archive, then make every ELF file
# look for them relative to its own position. The glibc baseline is Ubuntu 22.04.
root=/work/stage/postgresql
mkdir -p "$root/lib/runtime"
for pass in 1 2 3; do
  while IFS= read -r -d '' elf; do
    if ! file -b "$elf" | grep -q ELF; then continue; fi
    while read -r library path; do
      [[ -f "$path" ]] || continue
      case "$library" in
        linux-vdso*|ld-linux*|libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|libresolv.so*|libnss_*) continue ;;
      esac
      # Libraries built by PostgreSQL are already present in the staged lib/.
      case "$path" in /opt/postgresql/lib/*|"$root"/lib/*) continue ;; esac
      dest="$root/lib/runtime/$library"
      if [[ ! -e "$dest" ]]; then
        cp -L "$path" "$dest"
        resolved=$(readlink -f "$path")
        package=$(dpkg-query -S "$path" "$resolved" 2>/dev/null | head -1 | cut -d: -f1 || true)
        if [[ -z "$package" ]]; then
          package=$(dpkg-query -S "*/$(basename "$resolved")" 2>/dev/null | head -1 | cut -d: -f1 || true)
        fi
        if [[ -z "$package" || ! -f "/usr/share/doc/$package/copyright" ]]; then
          echo "No package copyright found for bundled library $library ($path)" >&2
          exit 1
        fi
        cp "/usr/share/doc/$package/copyright" "$root/LICENSES/${package}.copyright"
      fi
    done < <(ldd "$elf" 2>/dev/null | awk '$2 == "=>" && $3 ~ /^\// {print $1, $3}')
  done < <(find "$root/bin" "$root/lib" -type f -print0)
done
while IFS= read -r -d '' elf; do
  if ! file -b "$elf" | grep -q ELF; then continue; fi
  case "$elf" in
    "$root/bin/"*) rpath='$ORIGIN/../lib:$ORIGIN/../lib/runtime' ;;
    "$root/lib/runtime/"*) rpath='$ORIGIN' ;;
    *) relative_lib=$(realpath --relative-to="$(dirname "$elf")" "$root/lib")
       rpath="\$ORIGIN/$relative_lib:\$ORIGIN/$relative_lib/runtime" ;;
  esac
  patchelf --set-rpath "$rpath" "$elf"
done < <(find "$root/bin" "$root/lib" -type f -print0)

cat > "$root/manifest.json" <<EOF
{"schema_version":1,"component":"postgresql","version":"${pg_version}","postgresql_version":"${pg_version}","platform":"linux","architecture":"x86_64","glibc_baseline":"2.35","included_extensions":${builtins},"capabilities":{"icu":true,"libc_collations":true,"lz4":true,"zstd":true}}
EOF

cat > /work/stage/metadata.json <<EOF
{"project":"pgvector","version":"${vector_version}","sql_names":["vector"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[]}
EOF
cd /work/stage
tar -czf "/out/$pg_archive" postgresql
tar -czf "/out/$vector_archive" pgvector metadata.json
cd /out
sha256sum "$pg_archive" > "$pg_archive.sha256"
sha256sum "$vector_archive" > "$vector_archive.sha256"
