#!/usr/bin/env bash
set -euo pipefail
root=$1 pg_prefix=$2 arch=$3
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
mkdir -p "$root/lib/runtime" "$root/lib/glibc" "$root/libexec"
bash "$repo/platforms/linux/bundle-runtime.sh" "$root" "$root/lib/runtime" "$pg_prefix" CORE
if [[ $arch == arm64 ]]; then
  triplet=aarch64-linux-gnu
  loader=ld-linux-aarch64.so.1
  loader_source=/lib/$loader
else
  triplet=x86_64-linux-gnu
  loader=ld-linux-x86-64.so.2
  loader_source=/lib/$triplet/$loader
fi
cp -L "$loader_source" "$root/lib/glibc/$loader"
for soname in libc.so.6 libm.so.6 libpthread.so.0 libdl.so.2 librt.so.1 libresolv.so.2 libnss_files.so.2 libnss_dns.so.2; do
  [[ ! -f /lib/$triplet/$soname ]] || cp -L "/lib/$triplet/$soname" "$root/lib/glibc/$soname"
done
musl-gcc -static -O2 -o "$root/bin/.pg-launcher" "$repo/platforms/linux/launcher.c"
for executable in "$root"/bin/*; do
  [[ -f $executable && ! -L $executable ]] || continue
  file -b "$executable" | grep -q ELF || continue
  name=${executable##*/}
  mv "$executable" "$root/libexec/$name"
  ln "$root/bin/.pg-launcher" "$executable"
done
bash "$repo/platforms/linux/relocate-runtime.sh" "$root" CORE
