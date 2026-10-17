#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
case "$pg_version" in
  15.19|16.15|17.11|18.6) ;;
  *)
  echo "Unsupported PostgreSQL pilot version: $pg_version" >&2
  exit 2
    ;;
esac
version=1.3.4
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
archive="pgtap-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/prefix /work/source /work/stage /out
tar -xzf "$pg_archive" -C /work/prefix
mv /work/prefix/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
export PATH="$pgroot/bin:$PATH"
cd /work/source
curl -fL --retry 3 -o pgtap.tar.gz 'https://github.com/theory/pgtap/archive/refs/tags/v1.3.4.tar.gz'
echo 'd2c951afb296a001d21785611a8e966e3f8fa3f5bfbd929396a5130c0152f314  pgtap.tar.gz' | sha256sum -c -
tar -xzf pgtap.tar.gz
cd "pgtap-${version}"
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" pgtap.control)" = "$version"
make -j 4
make install DESTDIR=/work/stage
install_root=/work/stage/opt/postgresql
mkdir -p /work/package/pgtap/share/extension /work/package/pgtap/share/doc/extension /work/package/pgtap/LICENSES
cp "$install_root/share/extension/"* /work/package/pgtap/share/extension/
cp -a "$install_root/share/doc/extension/." /work/package/pgtap/share/doc/extension/
sed -n '/^Copyright and License$/,$p' README.md | sed '1,2d' > /work/package/pgtap/LICENSES/pgTAP.txt
grep -Fxq 'Copyright (c) 2008-2025 David E. Wheeler. Some rights reserved.' /work/package/pgtap/LICENSES/pgTAP.txt
cat > /work/package/pgtap/LICENSES/pgtap-inventory.json <<EOF
{
  "schema_version": 1,
  "components": [
    {
      "component": "pgtap",
      "version": "${version}",
      "payload_paths": ["share/extension", "share/doc/extension"],
      "license_file": "pgTAP.txt",
      "license_source": "https://github.com/theory/pgtap/tree/v1.3.4",
      "redistribution_review": {
        "status": "resolved",
        "basis": "The pgTAP v1.3.4 source distribution applies the included permissive copyright notice to the project files and generated SQL and documentation payload. The notice permits redistribution with its attribution and disclaimer retained.",
        "source_obligation": "none"
      }
    }
  ]
}
EOF
cat > /work/package/metadata.json <<EOF
{"project":"pgtap","version":"${version}","sql_names":["pgtap"],"requires":[],"configuration_prerequisites":[{"type":"sql_extension","name":"plpgsql","value":"CREATE EXTENSION plpgsql"}],"runtime_prerequisites":[],"postgresql_version":"${pg_version}","platform":"linux","architecture":"${architecture}","source":{"url":"https://github.com/theory/pgtap/archive/refs/tags/v1.3.4.tar.gz","sha256":"d2c951afb296a001d21785611a8e966e3f8fa3f5bfbd929396a5130c0152f314"}}
EOF
cp -a "$install_root/share/extension/." "$pgroot/share/extension/"
useradd -m postgres
mkdir -p /work/data /work/socket
chown postgres:postgres /work/data /work/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /work/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -o '-k /work/socket -p 55432 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -A -t -v ON_ERROR_STOP=1 -h /work/socket -p 55432 -d postgres -f /work/probe.sql | tee /work/probe.out
grep -Fxq '1..4' /work/probe.out
test "$(grep -Ec '^ok [1-4]( -|$)' /work/probe.out)" -eq 4
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m fast -w stop
trap - EXIT
cd /work/package
tar -czf "/out/$archive" pgtap metadata.json
cd /out
sha256sum "$archive" > "$archive.sha256"
