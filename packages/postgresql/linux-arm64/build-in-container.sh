#!/usr/bin/env bash
set -euo pipefail
version=18.6
source_url=https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.gz
source_sha256=983ee554ec53dbeb9b70797bef9fcf4e67e117e7e48ca1463cc80b3ff8e8ff3f
[[ $(uname -m) == aarch64 ]] || { echo 'Build requires Linux ARM64' >&2; exit 1; }
work=/work
root=$work/stage/postgresql
mkdir -p "$work/src" "$root"
curl --fail --location --retry 3 "$source_url" -o "$work/postgresql.tar.gz"
printf '%s  %s\n' "$source_sha256" "$work/postgresql.tar.gz" | sha256sum -c -
tar -xzf "$work/postgresql.tar.gz" -C "$work/src"
cd "$work/src/postgresql-$version"
CFLAGS='-O2 -g -march=armv8-a' ./configure --prefix=/opt/postgresql --disable-rpath \
  --with-icu --with-lz4 --with-zstd --with-ssl=openssl --with-libxml --with-libxslt \
  --with-zlib --with-uuid=e2fs --without-readline --without-libcurl --without-gssapi \
  --without-ldap --without-pam --without-bonjour --without-libnuma --without-liburing \
  --without-selinux --without-perl --without-python --without-tcl
make -j "$(nproc)" && make install
make -C contrib -j "$(nproc)" && make -C contrib install
cp -a /opt/postgresql/. "$root/"
mkdir -p "$work/stage/development/postgresql"
cp -a /opt/postgresql/. "$work/stage/development/postgresql/"
rm -rf "$root/include" "$root/lib/pgxs" "$root/bin/pg_config"
find "$root/lib" -maxdepth 1 -name '*.a' -delete
mkdir -p "$root/lib/runtime" "$root/lib/glibc" "$root/libexec"
for pass in 1 2 3; do
  while IFS= read -r -d '' elf; do
    file -b "$elf" | grep -q ELF || continue
    while read -r name path; do
      [[ -f $path ]] || continue
      case "$name" in linux-vdso*|ld-linux*|libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|libresolv.so*|libnss_*) continue ;; esac
      [[ $path == /opt/postgresql/lib/* || $path == "$root"/lib/* ]] && continue
      [[ -e $root/lib/runtime/$name ]] || cp -L "$path" "$root/lib/runtime/$name"
    done < <(ldd "$elf" 2>/dev/null | awk '$2 == "=>" && $3 ~ /^\// {print $1, $3}')
  done < <(find "$root/bin" "$root/lib" -type f -print0)
done
for soname in ld-linux-aarch64.so.1 libc.so.6 libm.so.6 libpthread.so.0 libdl.so.2 librt.so.1 libresolv.so.2 libnss_files.so.2 libnss_dns.so.2; do
  source=/lib/aarch64-linux-gnu/$soname
  [[ $soname == ld-linux-aarch64.so.1 ]] && source=/lib/ld-linux-aarch64.so.1
  [[ -f $source ]] && cp -L "$source" "$root/lib/glibc/$soname"
done
cmp /lib/ld-linux-aarch64.so.1 "$root/lib/glibc/ld-linux-aarch64.so.1"
musl-gcc -static -O2 -o "$root/bin/.pg-launcher" /usr/local/src/pg-launcher.c
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
tar -C "$work/stage" -czf /out/postgresql-18.6-linux-arm64.tar.gz postgresql
sha256sum /out/postgresql-18.6-linux-arm64.tar.gz > /out/postgresql-18.6-linux-arm64.tar.gz.sha256
tar -C "$work/stage/development" -czf /out/postgresql-development-18.6-linux-arm64.tar.gz postgresql
sha256sum /out/postgresql-development-18.6-linux-arm64.tar.gz > /out/postgresql-development-18.6-linux-arm64.tar.gz.sha256
