#!/usr/bin/env bash
set -euo pipefail

pg_version=18.6
extension_version=3.7.0
extension_sql_version=3.7
pgroot=/opt/postgresql
mkdir -p /work/source /work/package /out
cd /work/source

# This feasibility path builds PostgreSQL from its official 18.6 source because
# no matching core archive is present. The pilot does not claim archive reuse.
curl -fL --retry 3 -o postgresql.tar.gz \
  "https://ftp.postgresql.org/pub/source/v${pg_version}/postgresql-${pg_version}.tar.gz"
curl -fL --retry 3 -o postgresql.tar.gz.sha256 \
  "https://ftp.postgresql.org/pub/source/v${pg_version}/postgresql-${pg_version}.tar.gz.sha256"
expected=$(awk -v name="postgresql-${pg_version}.tar.gz" '$2 == name {print $1}' postgresql.tar.gz.sha256)
test -n "$expected"
printf '%s  %s\n' "$expected" postgresql.tar.gz | sha256sum -c -
tar -xzf postgresql.tar.gz
cd "postgresql-${pg_version}"
./configure --prefix="$pgroot" --without-icu --without-readline --without-zlib
make -s -j8
make -s install

export PATH="$pgroot/bin:$PATH"
cd /work/source
git clone --depth 1 --branch "v${extension_version}" \
  https://github.com/postgis/address_standardizer.git address_standardizer
cd address_standardizer
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" address_standardizer.control)" = "$extension_sql_version"
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" address_standardizer_data_us.control)" = "$extension_sql_version"
make -s PG_CONFIG="$pgroot/bin/pg_config" -j2
make -s PG_CONFIG="$pgroot/bin/pg_config" install

mkdir -p /work/package/address_standardizer/{lib,share/extension}
cp "$pgroot"/lib/address_standardizer*.so /work/package/address_standardizer/lib/
cp "$pgroot"/share/extension/address_standardizer*.control \
  "$pgroot"/share/extension/address_standardizer*.sql \
  /work/package/address_standardizer/share/extension/
python3 /usr/local/bin/license_pointer.py write /work/package/address_standardizer address_standardizer
cat > /work/package/metadata.json <<EOF
{
  "purpose": "feasibility-pilot",
  "postgresql_version": "${pg_version}",
  "extension_version": "${extension_version}",
  "extension_sql_version": "${extension_sql_version}",
  "sql_names": ["address_standardizer", "address_standardizer_data_us"],
  "postgresql_source": "https://ftp.postgresql.org/pub/source/v${pg_version}/postgresql-${pg_version}.tar.gz",
  "extension_source": "https://github.com/postgis/address_standardizer.git",
  "extension_ref": "v${extension_version}",
  "runtime_dependency": "PCRE2 supplied by the disposable Ubuntu build container"
}
EOF

useradd -m postgres
mkdir -p /work/data /work/socket
chown postgres:postgres /work/data /work/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /work/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -o '-k /work/socket -p 55432 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 \
  -h /work/socket -p 55432 -d postgres -f /work/probe.sql | tee /out/probe-output.txt
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m fast -w stop
trap - EXIT
cp /work/source/postgresql.tar.gz.sha256 /out/postgresql-source.sha256
git -C /work/source/address_standardizer rev-parse HEAD > /out/address-standardizer-commit.txt
cd /work/package
tar -czf /out/address-standardizer-3.7.0-postgresql-18.6-linux-x86_64-pilot.tar.gz \
  address_standardizer metadata.json
cd /out
sha256sum address-standardizer-3.7.0-postgresql-18.6-linux-x86_64-pilot.tar.gz \
  > address-standardizer-3.7.0-postgresql-18.6-linux-x86_64-pilot.tar.gz.sha256
