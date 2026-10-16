#!/usr/bin/env bash
set -euo pipefail

pg_version=${1:?usage: qemu-kernel-515-guest-full.sh PG_VERSION ARCHITECTURE}
architecture=${2:?}
[[ $(uname -r) =~ ^5\.15\. ]] || {
  echo "Expected Linux 5.15, got $(uname -r)" >&2
  exit 1
}
test -d /tmp/tests
test -f /tmp/check_elf_dependencies.py
test -f /tmp/verify-in-container.sh
sudo ln -s /tmp /out
sudo ln -s /tmp/tests /tests
sudo install -m 0755 /tmp/check_elf_dependencies.py /usr/local/bin/check-elf-dependencies
sudo env PG_VERSION="$pg_version" PG_ARCHITECTURE="$architecture" \
  bash /tmp/verify-in-container.sh
