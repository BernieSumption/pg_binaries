"""Check that a macOS static-analysis report covers the target's final archives."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from pg_jsonschema_macos_target import load_target


def _read_report(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read static-analysis report {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("static-analysis report must be a JSON object")
    return value


def validate(target_path, core_archive, extension_archive, report_path):
    target = load_target(target_path)
    core_archive, extension_archive = Path(core_archive), Path(extension_archive)
    for archive in (core_archive, extension_archive):
        if not archive.is_file():
            raise ValueError(f"archive is missing: {archive}")
    if core_archive.name != target.core_basename:
        raise ValueError("core archive basename does not match target")
    if extension_archive.name != target.extension_basename:
        raise ValueError("extension archive basename does not match target")

    report = _read_report(report_path)
    expected = {
        core_archive.name: hashlib.sha256(core_archive.read_bytes()).hexdigest(),
        extension_archive.name: hashlib.sha256(extension_archive.read_bytes()).hexdigest(),
    }
    actual = report.get("archives")
    if isinstance(actual, list):
        try:
            actual = {item["basename"]: item["sha256"] for item in actual}
        except (KeyError, TypeError):
            actual = None
    module_path = f"lib/{target.module_filename}"
    files = report.get("inspected_files", [])
    if (report.get("passed") is not True
            or report.get("architecture") != target.architecture
            or actual != expected
            or not isinstance(files, list)
            or not any(isinstance(item, dict) and item.get("file") == module_path
                       for item in files)):
        raise ValueError("Mach-O analysis did not pass for the target's final archives")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="validated macOS target JSON")
    parser.add_argument("--core-archive", required=True)
    parser.add_argument("--extension-archive", required=True)
    parser.add_argument("--report", required=True, help="static-analysis.json")
    args = parser.parse_args(argv)
    try:
        validate(args.target, args.core_archive, args.extension_archive, args.report)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("PASS: static analysis covers the target's final core and extension archives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
