#!/usr/bin/env bash
set -euo pipefail
architecture=${1:?}
pg_version=${2:?}
[[ $pg_version =~ ^[0-9]+\.[0-9]+$ ]] || { echo "Unsupported PostgreSQL version format: $pg_version" >&2; exit 2; }
[[ $(uname -r) =~ ^5\.15\. ]] || { echo 'Expected Linux 5.15' >&2; exit 1; }
case "$architecture:$(uname -m)" in x86_64:x86_64|arm64:aarch64) ;; *) exit 1 ;; esac
. /etc/os-release
printf 'guest_os=%s\nguest_kernel=%s\nguest_architecture=%s\npostgresql_version=%s\n' "$PRETTY_NAME" "$(uname -r)" "$architecture" "$pg_version"
sudo mkdir /input /out /work
sudo mv /tmp/postgresql-*.tar.gz* /input/
sudo mv /tmp/postgis-*.tar.gz* /out/
sudo cp /tmp/probe.sql /tmp/support.json /work/
sudo install -m 0755 /tmp/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
sudo install -m 0755 /tmp/check_postgis_license_inventory.py /usr/local/bin/check-postgis-license-inventory
sudo env PG_ARCHITECTURE="$architecture" PG_VERSION="$pg_version" bash /tmp/verify-in-container.sh
printf 'PASS: PostGIS 3.6.4 minimum-kernel archive verification\n'
