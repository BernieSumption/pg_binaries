#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
case "$architecture:$(uname -m)" in
  x86_64:x86_64|arm64:aarch64) ;;
  *) echo "Build container architecture does not match $architecture: $(uname -m)" >&2; exit 2 ;;
esac
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Linux pilot currently supports PostgreSQL 15 through 18 minors only: $pg_version" >&2
  exit 2
fi
vector_version=0.8.7
pg_source_url=${PG_SOURCE_URL:?PG_SOURCE_URL is required}
pg_source_sha256=${PG_SOURCE_SHA256:?PG_SOURCE_SHA256 is required}
vector_source_url=${VECTOR_SOURCE_URL:?VECTOR_SOURCE_URL is required}
vector_source_sha256=${VECTOR_SOURCE_SHA256:?VECTOR_SOURCE_SHA256 is required}
build_id=${BUILD_ID:?BUILD_ID is required}
source_revision=${SOURCE_REVISION:?SOURCE_REVISION is required}
builder_image_id=${BUILDER_IMAGE_ID:?BUILDER_IMAGE_ID is required}
if [[ ! $build_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ || ! $source_revision =~ ^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$ || ! $builder_image_id =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Invalid Linux build provenance" >&2
  exit 2
fi
build_configuration="postgresql-${pg_version};pgvector-${vector_version};builder=ubuntu-22.04;configure=icu,lz4,zstd,openssl,libxml,libxslt,zlib,uuid-e2fs,no-readline,no-rpath;cflags=-O2,-g;pgvector-optflags=empty;runtime=bundled-glibc-static-musl-launcher"
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
vector_archive="pgvector-${vector_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
mkdir -p /work/src /work/stage/postgresql /work/stage/pgvector /out
cd /work/src
curl -fL --retry 3 -o postgresql.tar.bz2 "$pg_source_url"
printf '%s  %s\n' "$pg_source_sha256" postgresql.tar.bz2 | sha256sum -c -
tar -xf postgresql.tar.bz2
cd "postgresql-${pg_version}"
CFLAGS='-O2 -g' ./configure --prefix=/opt/postgresql --disable-rpath --with-icu --with-lz4 --with-zstd \
  --with-openssl --with-libxml --with-libxslt --with-zlib --with-uuid=e2fs --without-readline
make -j "$(nproc)"
make install
make -C contrib -j "$(nproc)"
make -C contrib install
cd /work/src
curl -fL --retry 3 -o pgvector.tar.gz "$vector_source_url"
printf '%s  %s\n' "$vector_source_sha256" pgvector.tar.gz | sha256sum -c -
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
cp -a /usr/share/common-licenses /work/stage/postgresql/LICENSES/common-licenses
builtins=$(python3 /usr/local/bin/discover-builtins /work/stage/postgresql)

# Copy runtime libraries into the archive, then make every ELF file look for
# them relative to its own position.
root=/work/stage/postgresql
mkdir -p "$root/lib/runtime"
: > /work/runtime-packages.tsv
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
        if [[ "$package" == libicu70 ]]; then
          package_identity=$(dpkg-query -W -f='${Version} ${source:Package} ${source:Version}' libicu70)
          read -r package_version source_package source_version <<< "$package_identity"
          if [[ "$package_version" != 70.1-2 || "$source_package" != icu || "$source_version" != 70.1-2 ]]; then
            echo "Unexpected libicu70 source identity: $package_version $source_package $source_version" >&2
            exit 1
          fi
          cp /usr/local/share/pg-binaries/icu-70.1-LICENSE.txt \
            "$root/LICENSES/libicu70-icu-70.1-LICENSE.txt"
        fi
        printf '%s\t%s\n' "$package" "lib/runtime/$library" >> /work/runtime-packages.tsv
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

bash /usr/local/bin/bundle-glibc "$root" "$architecture" /work/runtime-packages.tsv

python3 /usr/local/bin/write-linux-license-inventory \
  "$root" "$pg_version" /work/runtime-packages.tsv

cat > "$root/manifest.json" <<EOF
{"schema_version":1,"component":"postgresql","version":"${pg_version}","postgresql_version":"${pg_version}","platform":"linux","architecture":"${architecture}","build_id":"${build_id}","source_revision":"${source_revision}","source_archive":{"url":"${pg_source_url}","sha256":"${pg_source_sha256}"},"build_configuration":"${build_configuration}","builder_image_id":"${builder_image_id}","bundled_glibc_version":"$(dpkg-query -W -f='${Version}' libc6)","included_extensions":${builtins},"capabilities":{"icu":true,"libc_collations":true,"lz4":true,"zstd":true}}
EOF

cat > /work/stage/metadata.json <<EOF
{"project":"pgvector","version":"${vector_version}","sql_names":["vector"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[],"build_id":"${build_id}","source_revision":"${source_revision}","source_archive":{"url":"${vector_source_url}","sha256":"${vector_source_sha256}"},"build_configuration":"${build_configuration}","builder_image_id":"${builder_image_id}","platform":"linux","architecture":"${architecture}"}
EOF
cat > /work/stage/pgvector/LICENSES/pgvector-inventory.json <<EOF
{"schema_version":1,"components":[{"component":"pgvector","version":"${vector_version}","payload_paths":["lib/vector.so","share/extension"],"license_file":"pgvector.txt","license_source":"${vector_source_url}","source_url":"${vector_source_url}","source_sha256":"${vector_source_sha256}","redistribution_review":{"status":"resolved","basis":"The unmodified pgvector ${vector_version} source includes its PostgreSQL-style licence, permitting binary redistribution with its notice, permission and disclaimer text retained.","source_obligation":"none"}}]}
EOF
cd /work/stage
tar -czf "/out/$pg_archive" postgresql
tar -czf "/out/$vector_archive" pgvector metadata.json
cd /out
sha256sum "$pg_archive" > "$pg_archive.sha256"
sha256sum "$vector_archive" > "$vector_archive.sha256"
python3 /usr/local/bin/create-linux-symbols \
  "$pg_archive" "$vector_archive" --output-dir /out/debug-symbols
