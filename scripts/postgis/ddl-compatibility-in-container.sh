#!/usr/bin/env bash
set -euo pipefail

pg_version=17.11
pg_archive="postgresql-${pg_version}-linux-x86_64.tar.gz"
cd /core
sha256sum -c "$pg_archive.sha256"
mkdir -p /opt /work/source /work/run /out
trap 'chmod -R a+rX /out' EXIT
tar -xzf "$pg_archive" -C /opt
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
export PATH="$pgroot/bin:$PATH"
export PROJ_LIB=/usr/share/proj PROJ_DATA=/usr/share/proj GDAL_DATA=/usr/share/gdal
useradd -m postgres
chown postgres:postgres /work/run

declare -A source_sha256=(
  [3.4.6]=294dd4c778a9181be91e4ab305eec53c82ff57a9b7ac7a820fa1a89200436796
  [3.5.7]=af9ab591854d52a0d1115f90b797ef1cd60d01b85a11ff813073689e332272ff
  [3.6.4]=ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6
)
for version in 3.4.6 3.5.7 3.6.4; do
  cd /work/source
  curl -fL --retry 3 -o "postgis-${version}.tar.gz" \
    "https://download.osgeo.org/postgis/source/postgis-${version}.tar.gz"
  printf '%s  %s\n' "${source_sha256[$version]}" "postgis-${version}.tar.gz" | sha256sum -c -
  sha256sum "postgis-${version}.tar.gz" >> /out/source-sha256.txt
  tar -xzf "postgis-${version}.tar.gz"
  cd "postgis-${version}"
  ./configure --with-pgconfig="$pgroot/bin/pg_config" --with-sfcgal=/usr/bin/sfcgal-config
  make -j 4
  make install

  data="/work/run/data-${version}"
  socket="/work/run/socket-${version}"
  mkdir -p "$data" "$socket"
  chown postgres:postgres "$data" "$socket"
  runuser -u postgres -- "$pgroot/bin/initdb" -D "$data" \
    --encoding=UTF8 --locale=C --no-instructions > "/out/initdb-${version}.log"
  runuser -u postgres -- "$pgroot/bin/pg_ctl" -D "$data" \
    -l "$data/server.log" \
    -o "-k $socket -p 55437 -h ''" -w start
  trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D "$data" -m immediate stop >/dev/null 2>&1 || true; chmod -R a+rX /out' EXIT

  case "$version" in
    3.4.6) fixtures=(3.4.6) ;;
    3.5.7) fixtures=(3.4.6 3.5.7) ;;
    3.6.4) fixtures=(3.5.7) ;;
  esac
  for authored in "${fixtures[@]}"; do
    database="ddl_${authored//./_}"
    runuser -u postgres -- "$pgroot/bin/createdb" \
      -h "$socket" -p 55437 "$database"
    runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 \
      -h "$socket" -p 55437 -d "$database" \
      -v "installed_version=$version" \
      -f "/repo/scripts/postgis/ddl-${authored}.sql" \
      > "/out/${authored}-on-${version}.log" 2>&1
    echo "PASS: PostGIS ${authored} DDL on ${version} / PostgreSQL ${pg_version}"
  done
  runuser -u postgres -- "$pgroot/bin/pg_ctl" -D "$data" -m fast -w stop
  cp "$data/server.log" "/out/server-${version}.log"
  trap 'chmod -R a+rX /out' EXIT
done

sha256sum /core/"$pg_archive" /repo/scripts/postgis/ddl-3.4.6.sql \
  /repo/scripts/postgis/ddl-3.5.7.sql > /out/input-sha256.txt
printf '%s\n' \
  'PostGIS 3.4.6 DDL passed on 3.4.6 and 3.5.7; PostGIS 3.5.7 DDL passed on 3.5.7 and 3.6.4, all on PostgreSQL 17.11 Linux x86-64.' \
  > /out/result.txt
