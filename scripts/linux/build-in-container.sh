#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
core_only=${CORE_ONLY:-0}
case "$core_only" in 0|1) ;; *) echo "CORE_ONLY must be 0 or 1: $core_only" >&2; exit 2 ;; esac
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
case "$architecture:$(uname -m)" in
  x86_64:x86_64|arm64:aarch64) ;;
  *) echo "Build container architecture does not match $architecture: $(uname -m)" >&2; exit 2 ;;
esac
if [[ ! $pg_version =~ ^[1-9][0-9]*\.[0-9]+$ ]]; then
  echo "Invalid PostgreSQL release: $pg_version" >&2
  exit 2
fi
vector_version=0.8.7
pg_source_url=${PG_SOURCE_URL:?PG_SOURCE_URL is required}
pg_source_sha256=${PG_SOURCE_SHA256:?PG_SOURCE_SHA256 is required}
if [[ $core_only == 0 ]]; then
  vector_source_url=${VECTOR_SOURCE_URL:?VECTOR_SOURCE_URL is required}
  vector_source_sha256=${VECTOR_SOURCE_SHA256:?VECTOR_SOURCE_SHA256 is required}
fi
build_id=${BUILD_ID:?BUILD_ID is required}
source_revision=${SOURCE_REVISION:?SOURCE_REVISION is required}
builder_image_id=${BUILDER_IMAGE_ID:?BUILDER_IMAGE_ID is required}
base_image_digest=${BASE_IMAGE_DIGEST:?BASE_IMAGE_DIGEST is required}
builder_packages_sha256=$(dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' | LC_ALL=C sort | sha256sum | awk '{print $1}')
if [[ ! $build_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ || ! $source_revision =~ ^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$ || ! $builder_image_id =~ ^sha256:[0-9a-f]{64}$ || ! $base_image_digest =~ ^sha256:[0-9a-f]{64}$ || ! $builder_packages_sha256 =~ ^[0-9a-f]{64}$ ]]; then
  echo "Invalid Linux build provenance" >&2
  exit 2
fi
build_configuration="postgresql-${pg_version};builder=ubuntu-22.04;configure=icu,lz4,zstd,openssl,libxml,libxslt,zlib,uuid-e2fs,no-readline,no-rpath;cflags=-O2,-g;runtime=bundled-glibc-static-musl-launcher"
if [[ $core_only == 0 ]]; then
  build_configuration="postgresql-${pg_version};pgvector-${vector_version};builder=ubuntu-22.04;configure=icu,lz4,zstd,openssl,libxml,libxslt,zlib,uuid-e2fs,no-readline,no-rpath;cflags=-O2,-g;pgvector-optflags=empty;runtime=bundled-glibc-static-musl-launcher"
fi
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
vector_archive="pgvector-${vector_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
if [[ $core_only == 1 ]]; then
  rm -f "/out/$vector_archive" "/out/$vector_archive.sha256"
  rm -rf /out/debug-symbols
fi
mkdir -p /work/src /work/stage/postgresql /out
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
if [[ $core_only == 0 ]]; then
  mkdir -p /work/stage/pgvector
  curl -fL --retry 3 -o pgvector.tar.gz "$vector_source_url"
  printf '%s  %s\n' "$vector_source_sha256" pgvector.tar.gz | sha256sum -c -
  tar -xf pgvector.tar.gz
  cd "pgvector-${vector_version}"
  make -j "$(nproc)" PG_CONFIG=/opt/postgresql/bin/pg_config OPTFLAGS=
  make install PG_CONFIG=/opt/postgresql/bin/pg_config OPTFLAGS=
fi
cp -a /opt/postgresql/. /work/stage/postgresql/
# The extension is delivered separately and must not be silently bundled.
if [[ $core_only == 0 ]]; then
  mkdir -p /work/stage/pgvector/lib /work/stage/pgvector/share/extension
  mv /work/stage/postgresql/lib/vector.so /work/stage/pgvector/lib/
  mv /work/stage/postgresql/share/extension/vector* /work/stage/pgvector/share/extension/
fi
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

python3 /usr/local/bin/license-pointer write "$root" postgresql

cat > "$root/manifest.json" <<EOF
{"schema_version":1,"component":"postgresql","version":"${pg_version}","postgresql_version":"${pg_version}","platform":"linux","architecture":"${architecture}","build_id":"${build_id}","source_revision":"${source_revision}","source_archive":{"url":"${pg_source_url}","sha256":"${pg_source_sha256}"},"build_configuration":"${build_configuration}","builder_image_id":"${builder_image_id}","builder_inputs":{"base_image":"ubuntu:22.04","base_image_digest":"${base_image_digest}","packages_sha256":"${builder_packages_sha256}"},"bundled_glibc_version":"$(dpkg-query -W -f='${Version}' libc6)","included_extensions":${builtins},"capabilities":{"icu":true,"libc_collations":true,"lz4":true,"zstd":true}}
EOF

if [[ $core_only == 0 ]]; then
cat > /work/stage/metadata.json <<EOF
{"project":"pgvector","version":"${vector_version}","sql_names":["vector"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[],"build_id":"${build_id}","source_revision":"${source_revision}","source_archive":{"url":"${vector_source_url}","sha256":"${vector_source_sha256}"},"build_configuration":"${build_configuration}","builder_image_id":"${builder_image_id}","platform":"linux","architecture":"${architecture}"}
EOF
python3 /usr/local/bin/license-pointer write /work/stage/pgvector pgvector
fi
cd /work/stage
tar -czf "/out/$pg_archive" postgresql
if [[ $core_only == 0 ]]; then
  tar -czf "/out/$vector_archive" pgvector metadata.json
fi
cd /out
sha256sum "$pg_archive" > "$pg_archive.sha256"
if [[ $core_only == 0 ]]; then
  sha256sum "$vector_archive" > "$vector_archive.sha256"
  python3 /usr/local/bin/create-linux-symbols \
    "$pg_archive" "$vector_archive" --output-dir /out/debug-symbols
else
  python3 /usr/local/bin/create-linux-symbols \
    "$pg_archive" --output-dir /out/debug-symbols
fi
