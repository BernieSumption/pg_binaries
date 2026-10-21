#!/usr/bin/env bash
set -euo pipefail

architecture=${1:?}
[[ $(uname -r) =~ ^5\.15\. ]] || { echo 'Expected Linux 5.15' >&2; exit 1; }
case "$architecture:$(uname -m)" in x86_64:x86_64|arm64:aarch64) ;; *) exit 1 ;; esac
. /etc/os-release
printf 'guest_os=%s\nguest_kernel=%s\nguest_architecture=%s\n' "$PRETTY_NAME" "$(uname -r)" "$architecture"
sudo mkdir /core /postgis /tiger /repo
sudo mkdir -p /repo/scripts/tiger
sudo mv /tmp/postgresql-*.tar.gz* /core/
sudo mv /tmp/postgis-3.6.4-*.tar.gz* /postgis/
sudo mv /tmp/postgis_tiger_geocoder-*.tar.gz* /tiger/
sudo cp /tmp/probe.sql /repo/scripts/tiger/probe.sql
sudo cp /tmp/support.json /repo/support.json
sudo install -m 0755 /tmp/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
sudo install -m 0755 /tmp/license_pointer.py /usr/local/bin/license_pointer.py
sudo env PG_ARCHITECTURE="$architecture" bash /tmp/verify-in-container.sh
printf 'PASS: TIGER Geocoder 2025.2 minimum-kernel archive verification\n'
