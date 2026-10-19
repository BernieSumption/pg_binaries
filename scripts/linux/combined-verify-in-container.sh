#!/usr/bin/env bash
set -uo pipefail

pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture:$(uname -m)" in
  x86_64:x86_64|arm64:aarch64) ;;
  *) echo "Verifier architecture does not match $architecture: $(uname -m)" >&2; exit 2 ;;
esac
if [[ ! "$pg_version" =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Combined verifier supports PostgreSQL 15-18 selected minors: $pg_version" >&2
  exit 2
fi

results=/results
mkdir -p "$results/status" "$results/logs" "$results/static-analysis"
status="$results/status/phases.tsv"
: > "$status"
exec 9>>"$status"

# Each existing phase uses fixed scratch paths under /tmp and creates postgres.
# The image is disposable, so clear phase scratch and make that account creation repeatable.
mkdir -p /usr/local/libexec/combined
cat > /usr/local/libexec/combined/useradd <<'SHIM'
#!/bin/sh
for user do :; done
if getent passwd "$user" >/dev/null 2>&1; then
  exit 0
fi
exec /usr/sbin/useradd "$@"
SHIM
chmod +x /usr/local/libexec/combined/useradd
export PATH="/usr/local/libexec/combined:$PATH"

reset_scratch() {
  find /tmp -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
}
link_dir() {
  local path=$1 target=$2
  mkdir -p "$target"
  rm -f "$path"
  ln -s "$target" "$path"
}
run_phase() {
  local name=$1; shift
  printf '%s\trunning\n' "$name" >&9
  reset_scratch
  set +e
  "$@" 2>&1 | tee "$results/logs/$name.log"
  local code=${PIPESTATUS[0]}
  set -e
  if (( code == 0 )); then
    printf '%s\tpassed\n' "$name" >&9
  else
    printf '%s\tfailed(%s)\n' "$name" "$code" >&9
    failed=1
  fi
}

failed=0
export PG_VERSION="$pg_version" PG_ARCHITECTURE="$architecture"
core="/archives/core"
link_dir /out "$core"
link_dir /analysis "$results/static-analysis/core"
run_phase core /usr/local/bin/verify-core

export DIAGNOSTICS_EVIDENCE_DIR="$results/diagnostics"
run_phase diagnostics /usr/local/bin/verify-diagnostics "$core" "$pg_version" "$architecture"


if (( failed )); then
  echo "One or more Alpine verification phases failed; see /results/status/phases.tsv" >&2
  exit 1
fi
echo "PASS: requested Alpine verification phases completed for PostgreSQL $pg_version ($architecture)"
