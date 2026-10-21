#!/usr/bin/env bash
set -euo pipefail

core_archive=${1:?usage: cross-install-probe.sh CORE_ARCHIVE OUTPUT_ROOT}
output_root=${2:?usage: cross-install-probe.sh CORE_ARCHIVE OUTPUT_ROOT}
mkdir -p "$output_root"
output_root=$(cd "$output_root" && pwd)
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

# Build PostGIS with a matching MinGW PostgreSQL development installation.
bash "$(dirname "$0")/build-and-probe.sh" "$output_root/mingw"

exec > >(tee "$output_root/cross-install.log") 2>&1
set -x
test "${MSYSTEM:-}" = MINGW64
mkdir -p "$output_root/selected"
tar -xzf "$core_archive" -C "$output_root/selected"
selected="$output_root/selected/postgresql"
mingw="$output_root/mingw/postgresql"
source_root="$output_root/mingw/source"
netcdf="$output_root/mingw/netcdf-no-ros3"
test -s "$netcdf/bin/libnetcdf.dll"
test "$("$selected/bin/pg_config.exe" --version)" = 'PostgreSQL 18.6'
test "$("$mingw/bin/pg_config.exe" --version)" = 'PostgreSQL 18.6'

shopt -s nullglob
modules=("$mingw"/lib/postgis*.dll "$mingw"/lib/rtpostgis*.dll)
sql=("$mingw"/share/extension/postgis*.sql "$mingw"/share/extension/postgis*.control)
test "${#modules[@]}" -gt 0
test "${#sql[@]}" -gt 0
cp "${modules[@]}" "$selected/lib/"
cp "${sql[@]}" "$selected/share/extension/"

# This is a module-load experiment. Runtime dependency packaging is a later gate.
export PATH="$netcdf/bin:$selected/bin:$mingw/bin:$mingw/lib:/mingw64/bin:$PATH"
work="$output_root/selected-cluster"
mkdir -p "$work"
"$selected/bin/initdb.exe" -D "$work/data" --no-locale -E UTF8 -U postgres
finish() { "$selected/bin/pg_ctl.exe" -D "$work/data" -m immediate stop || true; }
trap finish EXIT
if ! "$selected/bin/pg_ctl.exe" -D "$work/data" -l "$work/server.log" -o "-p 55439 -h 127.0.0.1" start; then
  if test -f "$work/server.log"; then
    cat "$work/server.log" >&2
  else
    printf 'PostgreSQL server log was not created: %s/server.log\n' "$work" >&2
  fi
  exit 1
fi
"$selected/bin/createdb.exe" -h 127.0.0.1 -p 55439 postgis_probe
"$selected/bin/psql.exe" -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55439 -d postgis_probe \
  -f "$repo_root/scripts/postgis/probe.sql" \
  -c "CREATE TABLE cross_install_probe (id integer PRIMARY KEY, shape geometry(Point, 4326))" \
  -c "INSERT INTO cross_install_probe VALUES (1, ST_SetSRID(ST_MakePoint(1, 2), 4326))" \
  -c 'SELECT id, ST_AsText(shape) FROM cross_install_probe'

package_root="$output_root/package/postgis"
mkdir -p "$package_root/bin" "$package_root/lib" "$package_root/share/extension" "$package_root/share/gdal" "$package_root/share/proj"
cp "${modules[@]}" "$package_root/lib/"
cp "${sql[@]}" "$package_root/share/extension/"
for data_dir in gdal proj sfcgal; do
  if test -d "/mingw64/share/$data_dir"; then
    mkdir -p "$package_root/share/$data_dir"
    cp -a "/mingw64/share/$data_dir/." "$package_root/share/$data_dir/"
  fi
done

module_basenames="$output_root/package/postgis-module-names.txt"
printf '%s\n' "${modules[@]##*/}" | sort -fu > "$module_basenames"
for module in "${modules[@]}"; do
  report="$output_root/package/$(basename "$module").json"
  resolved="$output_root/package/$(basename "$module").modules.json"
  if ! python "$repo_root/experiments/postgis-windows-abi-trial/diagnose-imports.py" \
    --root "$module" \
    --search-directory "$selected/bin" \
    --search-directory "$selected/lib" \
    --search-directory "$netcdf/bin" \
    --search-directory "$mingw/bin" \
    --search-directory "$mingw/lib" \
    --search-directory /mingw64/bin \
    --search-directory /mingw64/lib \
    --search-directory /usr/bin \
    --output "$report" --modules-output "$resolved"; then
    printf 'ERROR: unable to resolve runtime closure for %s\n' "$module" >&2
    exit 1
  fi
  python - "$report" <<'PY'
import json, sys
from pathlib import Path
report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
findings = report["missing_symbols"] + report["unresolved_dlls"] + report["objdump_errors"]
if findings:
    print(json.dumps(findings, indent=2))
    raise SystemExit("PostGIS module runtime resolution failed")
PY
  python - "$resolved" "$package_root/bin" "$module_basenames" "$selected/bin" <<'PY'
import filecmp, json, shutil, sys
from pathlib import Path
resolved_path, destination, roots_path, selected_bin = map(Path, sys.argv[1:])
roots = {line.casefold() for line in roots_path.read_text().splitlines()}
core_dlls = {path.name.casefold() for path in selected_bin.glob('*.dll')}
destination.mkdir(parents=True, exist_ok=True)
for source_text in json.loads(resolved_path.read_text(encoding="utf-8")):
    source = Path(source_text)
    if source.suffix.casefold() == ".dll" and source.name.casefold() not in roots | core_dlls:
        target = destination / source.name
        if target.exists() and not filecmp.cmp(source, target, shallow=False):
            raise SystemExit(f'conflicting runtime DLLs: {target}')
        if not target.exists():
            shutil.copy2(source, target)
PY
done
selected_sha=$(sha256sum "$core_archive" | cut -d' ' -f1)
postgis_sha=$(sha256sum "$source_root/postgis-3.6.4.tar.gz" | cut -d' ' -f1)
python - "$package_root/metadata.json" "$selected_sha" "$postgis_sha" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({
    "schema_version": 1,
    "purpose": "non-publication-relocation-trial",
    "project": "PostGIS",
    "version": "3.6.4",
    "postgresql_version": "18.6",
    "platform": "windows",
    "architecture": "x86_64",
    "sql_names": ["postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology"],
    "core_archive_sha256": sys.argv[2],
    "source_sha256": sys.argv[3],
    "runtime_layout": "bin contains the recursive MinGW DLL closure; share contains GDAL/PROJ/SFCGAL data",
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
python "$repo_root/tools/license_pointer.py" write "$package_root" postgis
archive="$output_root/postgis-3.6.4-postgresql-18.6-windows-x86_64-trial.tar.gz"
tar -czf "$archive" -C "$output_root/package" postgis
python "$repo_root/tools/license_pointer.py" verify "$archive" postgis
(cd "$output_root" && sha256sum "${archive##*/}" > "${archive##*/}.sha256")
printf 'Created relocatable trial archive: %s\n' "$archive"
