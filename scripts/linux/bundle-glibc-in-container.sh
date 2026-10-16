#!/usr/bin/env bash
set -euo pipefail

root=${1:?usage: bundle-glibc-in-container.sh STAGED_POSTGRESQL_ROOT ARCHITECTURE RUNTIME_PACKAGE_MAP}
architecture=${2:?}
runtime_map=${3:?}
case "$architecture" in
  x86_64) triplet=x86_64-linux-gnu; loader=ld-linux-x86-64.so.2; loader_path=/lib64/$loader ;;
  arm64) triplet=aarch64-linux-gnu; loader=ld-linux-aarch64.so.1; loader_path=/lib/$loader ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac

mkdir -p "$root/lib/glibc" "$root/libexec" "$root/LICENSES"
for soname in "$loader" libc.so.6 libm.so.6 libpthread.so.0 libdl.so.2 \
               librt.so.1 libresolv.so.2 libnss_files.so.2 libnss_dns.so.2; do
  if [[ $soname == "$loader" ]]; then
    source=$loader_path
  else
    source=/lib/$triplet/$soname
  fi
  if [[ ! -f $source ]]; then
    echo "Missing glibc runtime library: $source" >&2
    exit 1
  fi
  cp -L "$source" "$root/lib/glibc/$soname"
  printf 'libc6\tlib/glibc/%s\n' "$soname" >> "$runtime_map"
done
cp /usr/share/doc/libc6/copyright "$root/LICENSES/libc6.copyright"
for name in GFDL-1.3 GPL-2 LGPL-2.1; do
  cp "/usr/share/common-licenses/$name" "$root/LICENSES/libc6-$name.txt"
done

for executable in "$root"/bin/*; do
  [[ -f $executable && ! -L $executable ]] || continue
  if [[ $(head -c 4 "$executable" | od -An -tx1 | tr -d ' \n') != 7f454c46 ]]; then
    continue
  fi
  name=${executable##*/}
  mv "$executable" "$root/libexec/$name"
  cat > "$executable" <<EOF
#!/bin/sh
set -eu
entry=\$0
case \$entry in */*) ;; *) entry=\$(command -v "\$entry") ;; esac
bin=\${entry%/*}
root=\$(CDPATH= cd "\$bin/.." && pwd -P)
exec "\$root/lib/glibc/$loader" --argv0 "\$root/bin/\${entry##*/}" \\
  --library-path "\$root/lib/glibc:\$root/lib/runtime:\$root/lib" \\
  "\$root/libexec/\${entry##*/}" "\$@"
EOF
  chmod 755 "$executable"
done
