#!/usr/bin/env bash
set -euo pipefail
pg_version=18.6
postgis_version=3.6.4
pg_archive="postgresql-${pg_version}-linux-x86_64.tar.gz"
postgis_archive="postgis-${postgis_version}-postgresql-${pg_version}-linux-x86_64.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/prefix /work/source /work/stage/postgis/{lib,share/extension,LICENSES} /out
tar -xzf "$pg_archive" -C /work/prefix
mv /work/prefix/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = 'PostgreSQL 18.6'
export PATH="$pgroot/bin:$PATH"
cd /work/source
curl -fL --retry 3 -o postgis.tar.gz "https://download.osgeo.org/postgis/source/postgis-${postgis_version}.tar.gz"
tar -xzf postgis.tar.gz
cd "postgis-${postgis_version}"
./configure --with-pgconfig="$pgroot/bin/pg_config" --with-sfcgal=/usr/bin/sfcgal-config
make -j 4
touch /work/install-marker
make install

# Identify every file installed into the exact PostgreSQL prefix.
stage=/work/stage/postgis
find "$pgroot/lib" -maxdepth 1 -type f -newer /work/install-marker -print -exec cp -v {} "$stage/lib/" \;
find "$pgroot/share/extension" -maxdepth 1 \( -type f -o -type l \) -newer /work/install-marker -print -exec cp -av {} "$stage/share/extension/" \;
mkdir -p "$stage/bin"
find "$pgroot/bin" -maxdepth 1 -type f -newer /work/install-marker -print -exec cp -v {} "$stage/bin/" \;
find /usr/local/bin -maxdepth 1 -type f -newer /work/install-marker -print -exec cp -v {} "$stage/bin/" \;
cp COPYING "$stage/LICENSES/PostGIS.txt"
mkdir -p "$stage/lib/runtime" "$stage/share"
cp -a /usr/share/proj "$stage/share/proj"
cp -a /usr/share/gdal "$stage/share/gdal"
cp /usr/share/doc/proj-data/copyright "$stage/LICENSES/proj-data.copyright"
cp /usr/share/doc/gdal-data/copyright "$stage/LICENSES/gdal-data.copyright"
# Bundle the ELF dependency closure, excluding the glibc ABI supplied by the
# supported Linux host. SFCGAL and GDAL pull in a substantial C++ stack.
for pass in 1 2 3 4; do
  while IFS= read -r -d '' elf; do
    if ! file -b "$elf" | grep -q ELF; then continue; fi
    while read -r library path; do
      [[ -f "$path" ]] || continue
      case "$library" in
        linux-vdso*|ld-linux*|libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|libresolv.so*|libnss_*) continue ;;
      esac
      case "$path" in "$pgroot"/lib/*|"$stage"/lib/*) continue ;; esac
      dest="$stage/lib/runtime/$library"
      if [[ ! -e "$dest" ]]; then
        cp -L "$path" "$dest"
        resolved=$(readlink -f "$path")
        package=$(dpkg-query -S "$path" "$resolved" 2>/dev/null | head -1 | cut -d: -f1 || true)
        if [[ -z "$package" ]]; then
          package=$(dpkg-query -S "*/$(basename "$resolved")" 2>/dev/null | head -1 | cut -d: -f1 || true)
        fi
        if [[ -z "$package" || ! -f "/usr/share/doc/$package/copyright" ]]; then
          echo "No package copyright found for $library ($path)" >&2
          exit 1
        fi
        cp "/usr/share/doc/$package/copyright" "$stage/LICENSES/${package}.copyright"
      fi
    done < <(ldd "$elf" 2>/dev/null | awk '$2 == "=>" && $3 ~ /^\// {print $1, $3}')
  done < <(find "$stage/lib" "$stage/bin" -type f -print0)
done
while IFS= read -r -d '' elf; do
  if ! file -b "$elf" | grep -q ELF; then continue; fi
  case "$elf" in
    "$stage/lib/runtime/"*) rpath='$ORIGIN' ;;
    "$stage/bin/"*) rpath='$ORIGIN/../lib:$ORIGIN/../lib/runtime' ;;
    *) rpath='$ORIGIN:$ORIGIN/runtime' ;;
  esac
  patchelf --set-rpath "$rpath" "$elf"
done < <(find "$stage/lib" "$stage/bin" -type f -print0)
cat > "$stage/manifest.json" <<EOF
{"schema_version":1,"component":"postgis","version":"${postgis_version}","postgresql_version":"${pg_version}","platform":"linux","architecture":"x86_64","pilot":true,"runtime_environment":{"PROJ_LIB":"share/proj","PROJ_DATA":"share/proj","GDAL_DATA":"share/gdal"}}
EOF

# Test installed extensions against the extracted PostgreSQL archive. Runtime
# library and data closure is recorded separately; this phase tests function.
useradd -m postgres
mkdir -p /work/data /work/socket
chown postgres:postgres /work/data /work/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /work/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -o '-k /work/socket -p 55432 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /work/socket -p 55432 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m fast -w stop
trap - EXIT
cd /work/stage
tar -czf "/out/$postgis_archive" postgis
cd /out
sha256sum "$postgis_archive" > "$postgis_archive.sha256"
du -sh /work/stage/postgis "$stage/lib/runtime" "$stage/share/proj" "$stage/share/gdal"
