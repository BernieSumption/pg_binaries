#!/usr/bin/env bash
set -euo pipefail

output=${1:?usage: inspect.sh OUTPUT_DIRECTORY}
mkdir -p "$output"
output=$(cd "$output" && pwd)
prefix="$RUNNER_TEMP/conda-postgis-spatial-arm64-env"

test "$(uname -s)" = Darwin
test "$(uname -m)" = arm64
command -v micromamba >/dev/null

micromamba create --yes --prefix "$prefix" --channel conda-forge \
  geos proj gdal >"$output/resolve.log" 2>&1
micromamba list --prefix "$prefix" --explicit >"$output/explicit-packages.txt"
micromamba list --prefix "$prefix" --json >"$output/packages.json"

python3 - "$prefix" "$output" <<'PY'
from pathlib import Path
import json
import re
import subprocess
import sys

prefix, output = map(Path, sys.argv[1:])
report = []
failures = []

def run(*args):
    return subprocess.run(args, text=True, capture_output=True)

for binary in sorted(prefix.rglob("*")):
    if not binary.is_file() or binary.is_symlink():
        continue
    archs = run("lipo", "-archs", str(binary))
    if archs.returncode:
        continue
    header = run("otool", "-hv", str(binary))
    if header.returncode:
        continue
    file_types = re.findall(r"\b(?:MH_)?(?:EXECUTE|DYLIB|BUNDLE)\b", header.stdout)
    if not file_types:
        continue
    loads = run("otool", "-l", str(binary))
    linked = run("otool", "-L", str(binary))
    if loads.returncode or linked.returncode:
        failures.append(f"unable to inspect {binary}")
        continue
    min_versions = []
    absolute_rpaths = []
    lines = loads.stdout.splitlines()
    for index, line in enumerate(lines):
        if line.strip() in {"cmd LC_BUILD_VERSION", "cmd LC_VERSION_MIN_MACOSX"}:
            block = "\n".join(lines[index:index + 7])
            match = re.search(r"(?:minos|version)\s+(\d+(?:\.\d+){1,2})", block)
            if match:
                min_versions.append(match.group(1))
        if line.strip() == "cmd LC_RPATH":
            block = "\n".join(lines[index:index + 6])
            match = re.search(r"^\s*path\s+(\S+)\s+\(offset\s+\d+\)", block, re.M)
            if match and match.group(1).startswith("/"):
                absolute_rpaths.append(match.group(1))
    dependencies = [
        line.strip().split(" ", 1)[0]
        for line in linked.stdout.splitlines()[1:]
        if line.strip()
    ]
    absolute = [
        dep for dep in dependencies
        if dep.startswith("/")
        and not dep.startswith(("/usr/lib/", "/System/Library/"))
    ]
    report.append({
        "path": str(binary.relative_to(prefix)),
        "file_types": sorted(set(file_types)),
        "architectures": archs.stdout.strip(),
        "minimum_macos_versions": min_versions,
        "absolute_lc_rpaths": absolute_rpaths,
        "dependencies": dependencies,
        "non_system_absolute_dependencies": absolute,
    })
    if not min_versions:
        failures.append(f"no macOS deployment target found: {binary}")
    for version in min_versions:
        parts = tuple(int(part) for part in version.split("."))
        parts = (parts + (0, 0, 0))[:3]
        if parts > (11, 0, 0):
            failures.append(f"deployment target exceeds 11.0: {binary}: {version}")

if not report:
    failures.append("no loadable Mach-O files found in the resolved environment")
(output / "macho-report.json").write_text(json.dumps(report, indent=2) + "\n")
(output / "inspection-findings.txt").write_text(
    "\n".join(failures) + ("\n" if failures else "No deployment-target or inspection failures found.\n")
)
if failures:
    raise SystemExit("Mach-O inspection found issues; see inspection-findings.txt")
PY
