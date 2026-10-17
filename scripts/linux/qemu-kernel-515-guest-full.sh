#!/usr/bin/env bash
set -euo pipefail

pg_version=${1:?usage: qemu-kernel-515-guest-full.sh PG_VERSION ARCHITECTURE}
architecture=${2:?}
[[ $(uname -r) =~ ^5\.15\. ]] || {
  echo "Expected Linux 5.15, got $(uname -r)" >&2
  exit 1
}
printf 'guest_os='; . /etc/os-release; printf '%s\n' "$PRETTY_NAME"
printf 'guest_kernel=%s\n' "$(uname -r)"
test -d /tmp/tests
test -f /tmp/check_elf_dependencies.py
test -f /tmp/stage_extension_archive.py
test -f /tmp/verify-in-container.sh
test -f /tmp/check_source_identity.py
test -f /tmp/source_archive.py
test -f /tmp/support.json
test -f /tmp/postgresql-releases.json
sudo ln -s /tmp /out
sudo ln -s /tmp/tests /tests
sudo install -m 0755 /tmp/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
sudo install -m 0755 /tmp/stage_extension_archive.py /usr/local/bin/stage-extension-archive
sudo install -d /verification/tools /verification/support
sudo install -m 0644 /tmp/check_source_identity.py /tmp/source_archive.py /verification/tools/
sudo install -m 0644 /tmp/support.json /verification/support.json
sudo install -m 0644 /tmp/postgresql-releases.json /verification/support/postgresql-releases.json
sudo env PG_VERSION="$pg_version" PG_ARCHITECTURE="$architecture" \
  bash /tmp/verify-in-container.sh
