#!/usr/bin/env bash
set -euo pipefail

archives=${1:?usage: diagnostics-in-container.sh ARCHIVE_DIRECTORY POSTGRESQL_VERSION ARCHITECTURE [PGVECTOR_VERSION]}
pg_version=${2:?}
architecture=${3:?}
vector_version=${4:-0.8.7}
case "$architecture:$(uname -m)" in
  x86_64:x86_64|arm64:aarch64) ;;
  *) echo "Diagnostic container architecture does not match $architecture: $(uname -m)" >&2; exit 2 ;;
esac
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
vector_archive="pgvector-${vector_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
pg_sha_file="$archives/$pg_archive.sha256"
vector_sha_file="$archives/$vector_archive.sha256"
index="$archives/debug-symbols/index.json"
for file in "$archives/$pg_archive" "$archives/$vector_archive" "$pg_sha_file" "$vector_sha_file" "$index"; do
  test -s "$file" || { echo "Missing diagnostic input: $file" >&2; exit 2; }
done
(cd "$archives" && sha256sum -c "$pg_archive.sha256" "$vector_archive.sha256")
evidence=${DIAGNOSTICS_EVIDENCE_DIR:-"$archives/diagnostics"}
install=$(mktemp -d /tmp/pg-binaries-diagnostics.XXXXXX)
trap 'rm -rf "$install"' EXIT
chmod 755 "$install"
mkdir -p "$evidence/system-failure" "$evidence/postgresql-error"
tar -xzf "$archives/$pg_archive" -C "$install"
tar -xzf "$archives/$vector_archive" -C "$install"
root="$install/postgresql"
test -x "$root/bin/postgres"

useradd --create-home --shell /bin/sh diagnostic-postgres

loader_name=ld-linux-x86-64.so.2
[[ $architecture == arm64 ]] && loader_name=ld-linux-aarch64.so.1
loader="$root/lib/glibc/$loader_name"
test -s "$loader"
ldd_output=$(ldd "$root/libexec/postgres" 2>&1 || true)
ldd_version=$(ldd --version 2>&1 || true)
ldd_version=${ldd_version%%$'\n'*}
readelf_version=$(readelf --version)
readelf_version=${readelf_version%%$'\n'*}
failure_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
failure_cwd="$root"
failure_command="$root/bin/postgres --version"
rm "$loader"
set +e
system_output=$(cd "$failure_cwd" && runuser -u diagnostic-postgres -- "$root/bin/postgres" --version 2>&1)
system_status=$?
set -e
failure_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '%s\n' "$system_output" > "$evidence/system-failure/output.txt"
if [[ $system_status -eq 0 ]] || ! grep -Eqi 'loader|ld-linux|No such file|cannot open' "$evidence/system-failure/output.txt"; then
  echo "System failure did not produce the expected missing-loader diagnostic" >&2
  exit 1
fi

system_output_file="$evidence/system-failure/output.txt" \
system_command="$failure_command" system_cwd="$failure_cwd" \
system_exit="$system_status" system_start="$failure_start" system_end="$failure_end" \
system_ldd="$ldd_output" removed_loader="$loader" pg_archive_path="$archives/$pg_archive" \
vector_archive_path="$archives/$vector_archive" symbols_index="$index" \
pg_root="$root" evidence_root="$evidence" pg_version="$pg_version" architecture="$architecture" \
inspection_ldd="$ldd_version" inspection_readelf="$readelf_version" \
python3 - <<'PY'
import hashlib, json, os, platform, re, subprocess
from pathlib import Path

env_names = ("PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "PGHOST", "PGPORT", "PGDATA", "PG_CONFIG")
def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
def build_id(path):
    output = subprocess.run(["readelf", "-n", str(path)], check=True,
                            text=True, capture_output=True).stdout
    match = re.search(r"Build ID: ([0-9a-fA-F]+)", output)
    if not match:
        raise SystemExit(f"module or debug file has no GNU build ID: {path}")
    return match.group(1).lower()

index = json.loads(Path(os.environ["symbols_index"]).read_text())
wanted = {"postgresql/bin/.pg-launcher", "pgvector/lib/vector.so"}
entries = [row for row in index["files"] if row["module_path"] in wanted]
if {row["module_path"] for row in entries} != wanted:
    raise SystemExit("debug-symbols index lacks launcher or vector.so entry")
for row in entries:
    archive_path = os.environ["pg_archive_path"] if row["archive"].startswith("postgresql-") else os.environ["vector_archive_path"]
    expected = sha(archive_path)
    if row["archive_sha256"] != expected:
        raise SystemExit(f"debug-symbols index archive hash mismatch: {row['archive']}")
    module = Path(os.environ["pg_root"]).parent / row["module_path"]
    debug_file = Path(os.environ["symbols_index"]).parent / row["debug_file_path"]
    if (sha(module) != row["module_sha256"] or sha(debug_file) != row["debug_file_sha256"]
            or build_id(module) != row["gnu_build_id"]
            or build_id(debug_file) != row["gnu_build_id"]):
        raise SystemExit(f"module or symbol file does not match index: {row['module_path']}")

root = Path(os.environ["evidence_root"])
record = {
    "schema_version": 1,
    "failure": "missing-bundled-loader",
    "started_at_utc": os.environ["system_start"],
    "finished_at_utc": os.environ["system_end"],
    "command": os.environ["system_command"],
    "cwd": os.environ["system_cwd"],
    "exit_code": int(os.environ["system_exit"]),
    "output_file": "system-failure/output.txt",
    "lookup_environment": {name: os.environ.get(name) for name in env_names},
    "os_release": Path("/etc/os-release").read_text(),
    "machine": platform.machine(),
    "kernel_release": platform.release(),
    "run_as_user": "diagnostic-postgres",
    "ci_run_url": (os.environ.get("GITHUB_SERVER_URL", "") + "/" +
                   os.environ.get("GITHUB_REPOSITORY", "") + "/actions/runs/" +
                   os.environ.get("GITHUB_RUN_ID", "")) if os.environ.get("GITHUB_RUN_ID") else None,
    "source_revision": os.environ.get("GITHUB_SHA"),
    "inventory_revision": None,
    "postgresql_version": os.environ["pg_version"],
    "architecture": os.environ["architecture"],
    "executable_paths": {"postgres": os.environ["pg_root"] + "/bin/postgres", "postgres_payload": os.environ["pg_root"] + "/libexec/postgres", "removed_loader": os.environ["removed_loader"]},
    "ldd_libexec_postgres": os.environ["system_ldd"],
    "inspection_tool_versions": {"ldd": os.environ["inspection_ldd"], "readelf": os.environ["inspection_readelf"]},
    "archives": {os.path.basename(os.environ["pg_archive_path"]): sha(os.environ["pg_archive_path"]), os.path.basename(os.environ["vector_archive_path"]): sha(os.environ["vector_archive_path"])},
    "archive_urls": None,
    "package_metadata": {"postgresql": json.loads((Path(os.environ["pg_root"]) / "manifest.json").read_text()), "pgvector": json.loads((Path(os.environ["pg_root"]).parent / "metadata.json").read_text())},
    "gnu_build_ids_and_index_entries": entries,
}
(root / "system-failure/record.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
PY

# Keep the PostgreSQL failure independent of the deliberately damaged copy.
rm -rf "$install"
mkdir -p "$install"
chown diagnostic-postgres:diagnostic-postgres "$install"
tar -xzf "$archives/$pg_archive" -C "$install"
tar -xzf "$archives/$vector_archive" -C "$install"
root="$install/postgresql"
data="$install/data"
log="$evidence/postgresql-error/server.log"
socket="$install/socket"
mkdir -p "$socket"
chown diagnostic-postgres:diagnostic-postgres "$socket"
chown -R diagnostic-postgres:diagnostic-postgres "$evidence/postgresql-error"
if ! runuser -u diagnostic-postgres -- "$root/bin/initdb" -D "$data" --encoding=UTF8 --locale=C --no-instructions >"$evidence/postgresql-error/initdb.log" 2>&1; then
  cat "$evidence/postgresql-error/initdb.log" >&2
  exit 1
fi
runuser -u diagnostic-postgres -- "$root/bin/pg_ctl" -D "$data" \
  -o "-k $socket -p 55439 -h ''" -l "$log" -w start
pg_ctl_start_command="runuser -u diagnostic-postgres -- $root/bin/pg_ctl -D $data -o \"-k $socket -p 55439 -h ''\" -l $log -w start"
failure_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
failure_cwd="$root"
failure_command="$root/bin/psql -X -v ON_ERROR_STOP=1 -h $socket -p 55439 -d postgres -c 'SELECT 1 / 0;'"
set +e
psql_output=$(cd "$failure_cwd" && runuser -u diagnostic-postgres -- "$root/bin/psql" -X -v ON_ERROR_STOP=1 -h "$socket" -p 55439 -d postgres -c 'SELECT 1 / 0;' 2>&1)
psql_status=$?
set -e
failure_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '%s\n' "$psql_output" > "$evidence/postgresql-error/client-output.txt"
runuser -u diagnostic-postgres -- "$root/bin/pg_ctl" -D "$data" -m fast -w stop
if [[ $psql_status -eq 0 ]] || ! grep -q 'ERROR:  division by zero' "$log"; then
  echo "PostgreSQL command did not produce a server ERROR log record" >&2
  cat "$log" >&2
  exit 1
fi

postgres_output_file="$evidence/postgresql-error/client-output.txt" \
postgres_log="$log" postgres_command="$failure_command" postgres_cwd="$failure_cwd" \
postgres_exit="$psql_status" postgres_start="$failure_start" postgres_end="$failure_end" \
postgres_pg_ctl_command="$pg_ctl_start_command" pg_archive_path="$archives/$pg_archive" \
vector_archive_path="$archives/$vector_archive" symbols_index="$index" \
pg_root="$root" evidence_root="$evidence" pg_version="$pg_version" architecture="$architecture" \
inspection_ldd="$ldd_version" inspection_readelf="$readelf_version" \
python3 - <<'PY'
import hashlib, json, os, platform
from pathlib import Path
def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
env_names = ("PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "PGHOST", "PGPORT", "PGDATA", "PG_CONFIG")
index = json.loads(Path(os.environ["symbols_index"]).read_text())
wanted = {"postgresql/bin/.pg-launcher", "pgvector/lib/vector.so"}
entries = [row for row in index["files"] if row["module_path"] in wanted]
root = Path(os.environ["evidence_root"])
record = {
    "schema_version": 1,
    "failure": "postgresql-server-error",
    "started_at_utc": os.environ["postgres_start"], "finished_at_utc": os.environ["postgres_end"],
    "command": os.environ["postgres_command"], "cwd": os.environ["postgres_cwd"],
    "exit_code": int(os.environ["postgres_exit"]),
    "output_file": "postgresql-error/client-output.txt",
    "complete_server_log": "postgresql-error/server.log",
    "server_log_bytes": Path(os.environ["postgres_log"]).stat().st_size,
    "lookup_environment": {name: os.environ.get(name) for name in env_names},
    "os_release": Path("/etc/os-release").read_text(),
    "machine": platform.machine(), "kernel_release": platform.release(),
    "run_as_user": "diagnostic-postgres",
    "ci_run_url": (os.environ.get("GITHUB_SERVER_URL", "") + "/" +
                   os.environ.get("GITHUB_REPOSITORY", "") + "/actions/runs/" +
                   os.environ.get("GITHUB_RUN_ID", "")) if os.environ.get("GITHUB_RUN_ID") else None,
    "source_revision": os.environ.get("GITHUB_SHA"),
    "inventory_revision": None,
    "postgresql_version": os.environ["pg_version"], "architecture": os.environ["architecture"],
    "executable_paths": {"postgres": os.environ["pg_root"] + "/bin/postgres", "pg_ctl": os.environ["pg_root"] + "/bin/pg_ctl", "psql": os.environ["pg_root"] + "/bin/psql"},
    "server_start_command": os.environ["postgres_pg_ctl_command"],
    "inspection_tool_versions": {"ldd": os.environ["inspection_ldd"], "readelf": os.environ["inspection_readelf"]},
    "archives": {os.path.basename(os.environ["pg_archive_path"]): sha(os.environ["pg_archive_path"]), os.path.basename(os.environ["vector_archive_path"]): sha(os.environ["vector_archive_path"])},
    "archive_urls": None,
    "package_metadata": {"postgresql": json.loads((Path(os.environ["pg_root"]) / "manifest.json").read_text()), "pgvector": json.loads((Path(os.environ["pg_root"]).parent / "metadata.json").read_text())},
    "gnu_build_ids_and_index_entries": entries,
}
(root / "postgresql-error/record.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
PY
rm -rf "$install"
