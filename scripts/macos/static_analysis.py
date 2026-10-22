#!/usr/bin/env python3
"""Inspect Mach-O architecture, load paths, and deployment metadata in a package."""

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys


SYSTEM_PREFIXES = ("/usr/lib/", "/System/Library/")
MINIMUM_OS = (11, 0)


def run(*args):
    return subprocess.run(args, capture_output=True, text=True)


def tool_version(tool):
    if tool in ("lipo", "otool"):
        return shutil.which(tool)
    result = run(tool, "-v")
    lines = (result.stdout or result.stderr).strip().splitlines()
    return lines[0] if lines else None


def archive_evidence(paths):
    entries = []
    names = set()
    for path in paths:
        if not path.is_file() or path.name in names:
            raise ValueError(f"missing or duplicate archive: {path}")
        names.add(path.name)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        entries.append({"basename": path.name, "sha256": digest.hexdigest()})
    return entries


def is_system(path):
    return path.startswith(SYSTEM_PREFIXES)


def commands(output):
    result = []
    current = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("cmd "):
            current = {"cmd": stripped[4:]}
            result.append(current)
        elif current is not None:
            if current["cmd"] == "LC_VERSION_MIN_MACOSX":
                match = re.match(r"version (.+?)(?: \(offset \d+\))?$", stripped)
            else:
                match = re.match(r"(?:path|minos|name) (.+?)(?: \(offset \d+\))?$", stripped)
            if match:
                current["value"] = match.group(1)
    return result


def version_tuple(value):
    match = re.match(r"^(\d+(?:\.\d+){0,2})", value)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def within(root, path):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def resolve_token(value, binary, rpaths, executables, root):
    candidates = []
    require_all = False
    if value.startswith("@loader_path/"):
        candidates = [(binary.parent / value[len("@loader_path/"):]).resolve()]
    elif value.startswith("@executable_path/"):
        contexts = executables or [binary]
        candidates = [(exe.parent / value[len("@executable_path/"):]).resolve() for exe in contexts]
        require_all = True
    elif value.startswith("@rpath/"):
        suffix = value[len("@rpath/"):]
        for rpath in rpaths:
            if rpath.startswith("@loader_path"):
                base = binary.parent / rpath.removeprefix("@loader_path").lstrip("/")
                candidates.append((base / suffix).resolve())
            elif rpath.startswith("@executable_path"):
                rest = rpath.removeprefix("@executable_path").lstrip("/")
                contexts = executables or [binary]
                candidates.extend((exe.parent / rest / suffix).resolve() for exe in contexts)
                require_all = True
            elif rpath.startswith("/"):
                candidates.append((pathlib.Path(rpath) / suffix).resolve())
    elif value.startswith("/"):
        candidates = [pathlib.Path(value).resolve()]
    resolved = [candidate for candidate in candidates if candidate.is_file() and (within(root, candidate) or is_system(str(candidate)))]
    if require_all and len(resolved) != len(candidates):
        return []
    return resolved


def inspect(root, architecture):
    root = pathlib.Path(root).resolve()
    report = {"schema_version": 1, "architecture": architecture, "minimum_os": "11.0",
              "tools": {tool: tool_version(tool) for tool in ("file", "lipo", "otool")},
              "inspected_files": [], "installation_links": [], "findings": [],
              "limits": ["Static load-command analysis cannot detect dependencies selected dynamically by application code or data-file accesses.",
                         "@rpath resolution uses declared run paths without modeling dyld run-path stack inheritance; unresolved paths fail verification."]}
    machos = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            relative = str(path.relative_to(root))
            try:
                target = path.resolve(strict=True)
                valid = within(root, target)
            except (OSError, RuntimeError):
                target = None
                valid = False
            report["installation_links"].append({"file": relative, "target": str(target) if target else None})
            if not valid:
                report["findings"].append({"file": relative, "error": "installation link leaves archive or is unresolved"})
            continue
        if not path.is_file():
            continue
        file_result = run("file", "-b", str(path))
        if file_result.returncode:
            report["findings"].append({"file": str(path.relative_to(root)), "error": "file command failed"})
            continue
        if "Mach-O" not in file_result.stdout:
            continue
        relative = str(path.relative_to(root))
        entry = {"file": relative, "file_type": file_result.stdout.strip()}
        report["inspected_files"].append(entry)
        machos.append((path, entry))
        archs = run("lipo", "-archs", str(path))
        if archs.returncode:
            entry["error"] = "lipo could not inspect Mach-O architecture"
            report["findings"].append({"file": relative, "error": entry["error"]})
            continue
        entry["architectures"] = archs.stdout.strip().split()
        if architecture not in entry["architectures"]:
            report["findings"].append({"file": relative, "error": "required architecture missing", "actual": entry["architectures"]})
        load = run("otool", "-l", str(path))
        linked = run("otool", "-L", str(path))
        if load.returncode or linked.returncode:
            report["findings"].append({"file": relative, "error": "otool failed to inspect load commands"})
            continue
        entry["dependencies"] = [line.strip().split(" (compatibility version", 1)[0]
                                  for line in linked.stdout.splitlines()[1:] if line.strip()]
        parsed = commands(load.stdout)
        entry["install_id"] = next((item["value"] for item in parsed if item["cmd"] == "LC_ID_DYLIB" and "value" in item), None)
        entry["rpaths"] = [item["value"] for item in parsed if item["cmd"] == "LC_RPATH" and "value" in item]
        minos = next((item["value"] for item in parsed if item["cmd"] == "LC_BUILD_VERSION" and "value" in item), None)
        if minos is None:
            minos = next((item["value"] for item in parsed if item["cmd"] == "LC_VERSION_MIN_MACOSX" and "value" in item), None)
        entry["minimum_os"] = minos
        if minos is None:
            report["findings"].append({"file": relative, "error": "minimum macOS target metadata missing"})
        elif version_tuple(minos) is None or version_tuple(minos)[:2] > MINIMUM_OS:
            report["findings"].append({"file": relative, "error": "minimum macOS target exceeds 11.0", "actual": minos})
        for rpath in entry["rpaths"]:
            if rpath.startswith("/") and not is_system(rpath):
                report["findings"].append({"file": relative, "error": "forbidden absolute LC_RPATH", "path": rpath})
            elif not (rpath.startswith(("@loader_path", "@executable_path", "/"))):
                report["findings"].append({"file": relative, "error": "unsupported LC_RPATH token", "path": rpath})

    executables = [path for path, entry in machos if "executable" in entry["file_type"].lower()]
    # Resolve only after the complete executable set is known.
    for binary, entry in machos:
        for dependency in entry.get("dependencies", []):
            if dependency == entry.get("install_id"):
                continue
            if is_system(dependency):
                continue
            if dependency.startswith("/") and not is_system(dependency):
                report["findings"].append({"file": entry["file"], "error": "forbidden absolute dependency", "path": dependency})
                continue
            if not resolve_token(dependency, binary, entry.get("rpaths", []), executables or [binary], root):
                report["findings"].append({"file": entry["file"], "error": "unresolved dependency", "path": dependency})
    report["passed"] = not report["findings"] and bool(report["inspected_files"])
    if not report["inspected_files"]:
        report["findings"].append({"error": "no Mach-O files found"})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("installation", type=pathlib.Path)
    parser.add_argument("architecture", choices=("x86_64", "arm64"))
    parser.add_argument("--report", type=pathlib.Path)
    parser.add_argument("--archive", type=pathlib.Path, action="append", default=[])
    args = parser.parse_args(argv)
    report = inspect(args.installation, args.architecture)
    try:
        report["archives"] = archive_evidence(args.archive)
    except (OSError, ValueError) as exc:
        report["findings"].append({"error": str(exc)})
        report["passed"] = False
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded)
    print(f"Inspected {len(report['inspected_files'])} Mach-O files; {len(report['findings'])} finding(s).")
    for finding in report["findings"][:20]:
        print(json.dumps(finding, sort_keys=True))
    if len(report["findings"]) > 20:
        print(f"... {len(report['findings']) - 20} more finding(s) in {args.report}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
