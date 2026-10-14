#!/usr/bin/env bash
set -euo pipefail
pg_archive=postgresql-18.6-linux-x86_64.tar.gz
postgis_archive=postgis-3.6.4-postgresql-18.6-linux-x86_64.tar.gz
cd /input
sha256sum -c "$pg_archive.sha256"
cd /out
sha256sum -c "$postgis_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/extension /tmp/data /tmp/socket
tar -xzf "/input/$pg_archive" -C /tmp/first
tar -xzf "/out/$postgis_archive" -C /tmp/extension
python3 - <<'PY'
import json
with open('/tmp/extension/postgis/manifest.json') as f:
    m = json.load(f)
assert (m['schema_version'], m['component'], m['version'], m['postgresql_version'],
        m['platform'], m['architecture']) == (1, 'postgis', '3.6.4', '18.6', 'linux', 'x86_64'), m
PY
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
extroot=/tmp/extension/postgis
while IFS= read -r -d '' library; do
  existing="$pgroot/lib/${library#"$extroot/lib/"}"
  if [[ -e "$existing" ]] && ! cmp -s "$library" "$existing"; then
    echo "Library collision with different bytes: ${library#"$extroot/lib/"}" >&2
    exit 1
  fi
done < <(find "$extroot/lib" -type f -print0)
cp -a --update=none "$extroot/lib/." "$pgroot/lib/"
cp -a "$extroot/share/extension/." "$pgroot/share/extension/"
cp -a "$extroot/bin/." "$pgroot/bin/"
cp -a "$extroot/share/proj" "$extroot/share/gdal" "$pgroot/share/"
test -s "$extroot/LICENSES/proj-data.copyright"
test -s "$extroot/LICENSES/gdal-data.copyright"
for loader in shp2pgsql raster2pgsql; do
  if ldd "$pgroot/bin/$loader" | grep -q 'not found'; then
    echo "Missing dynamic dependency for $loader" >&2
    exit 1
  fi
  "$pgroot/bin/$loader" -? > "/tmp/$loader.help" 2>&1 || true
  grep -qi 'usage' "/tmp/$loader.help"
done
export PROJ_LIB="$pgroot/share/proj" PROJ_DATA="$pgroot/share/proj" GDAL_DATA="$pgroot/share/gdal"
useradd -m postgres
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -l /tmp/data/server.log -o '-k /tmp/socket -p 55433 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55433 -d postgres -f /work/probe.sql
if grep -Eq 'proj_create|proj\.db|ERROR:.*PROJ' /tmp/data/server.log; then
  cat /tmp/data/server.log >&2
  echo 'PROJ runtime data error in server log' >&2
  exit 1
fi
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
echo 'PASS: relocated PostgreSQL and PostGIS archives on clean Ubuntu 24.04'
