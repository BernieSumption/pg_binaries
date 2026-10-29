#!/usr/bin/env bash
set -euo pipefail
[[ $# == 3 ]] || { echo "usage: $0 POSTGRESQL_PREFIX DEPENDENCY_PREFIX OUTPUT_DIR" >&2; exit 2; }
pg_prefix=$1 output_dir=$3
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
[[ $(uname -s) == Linux && $(uname -m) == aarch64 ]] || { echo 'Package requires Linux ARM64' >&2; exit 1; }
[[ -x $pg_prefix/bin/pg_config ]] || { echo 'Missing PostgreSQL pg_config' >&2; exit 1; }
pg_prefix=$(cd "$pg_prefix" && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
version=$($pg_prefix/bin/pg_config --version | sed 's/^PostgreSQL //')
work=$(mktemp -d "${TMPDIR:-/tmp}/postgresql-package.XXXXXX")
trap 'rm -rf "$work"' EXIT
root=$work/stage/postgresql
mkdir -p "$root"
cp -a "$pg_prefix"/. "$root/"
mkdir -p "$work/stage/development/postgresql"
cp -a "$pg_prefix"/. "$work/stage/development/postgresql/"
rm -rf "$root/include" "$root/lib/pgxs" "$root/bin/pg_config"
find "$root/lib" -maxdepth 1 -name '*.a' -delete
mkdir -p "$root/lib/runtime" "$root/lib/glibc" "$root/libexec"
bash "$repo/platforms/linux/bundle-runtime.sh" "$root" "$root/lib/runtime" "$pg_prefix" CORE
for soname in ld-linux-aarch64.so.1 libc.so.6 libm.so.6 libpthread.so.0 libdl.so.2 librt.so.1 libresolv.so.2 libnss_files.so.2 libnss_dns.so.2; do
  source=/lib/aarch64-linux-gnu/$soname
  [[ $soname == ld-linux-aarch64.so.1 ]] && source=/lib/ld-linux-aarch64.so.1
  [[ -f $source ]] && cp -L "$source" "$root/lib/glibc/$soname"
done
cmp /lib/ld-linux-aarch64.so.1 "$root/lib/glibc/ld-linux-aarch64.so.1"
musl-gcc -static -O2 -o "$root/bin/.pg-launcher" "$repo/platforms/linux/launcher.c"
for executable in "$root"/bin/*; do
  [[ -f $executable && ! -L $executable ]] || continue
  file -b "$executable" | grep -q ELF || continue
  name=${executable##*/}
  mv "$executable" "$root/libexec/$name"
  ln "$root/bin/.pg-launcher" "$executable"
done
while IFS= read -r -d '' elf; do
  file -b "$elf" | grep -q ELF || continue
  case "$elf" in
    "$root/libexec/"*) patchelf --set-rpath '$ORIGIN/../lib:$ORIGIN/../lib/runtime:$ORIGIN/../lib/glibc' "$elf" ;;
    "$root/lib/runtime/"*) patchelf --set-rpath '$ORIGIN:$ORIGIN/../glibc' "$elf" ;;
    *) rel=$(realpath --relative-to="$(dirname "$elf")" "$root/lib"); patchelf --set-rpath "\$ORIGIN/$rel:\$ORIGIN/$rel/runtime:\$ORIGIN/$rel/glibc" "$elf" ;;
  esac
done < <(find "$root/libexec" -type f -print0; find "$root/lib" -path "$root/lib/glibc" -prune -o -type f -print0)
printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$root/LICENCE"
find "$root" -type d -exec chmod 755 {} +
chmod 644 "$root/LICENCE"
tar -C "$work/stage" -czf "$output_dir/postgresql-$version-linux-arm64.tar.gz" postgresql
sha256sum "$output_dir/postgresql-$version-linux-arm64.tar.gz" > "$output_dir/postgresql-$version-linux-arm64.tar.gz.sha256"
tar -C "$work/stage/development" -czf "$output_dir/postgresql-development-$version-linux-arm64.tar.gz" postgresql
sha256sum "$output_dir/postgresql-development-$version-linux-arm64.tar.gz" > "$output_dir/postgresql-development-$version-linux-arm64.tar.gz.sha256"
