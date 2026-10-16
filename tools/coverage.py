#!/usr/bin/env python3
"""Reconcile declared PostgreSQL and extension support with inventory.json."""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:[-+].*)?$")
PRERELEASE = re.compile(r"^\d+(?:\.\d+)?(?:beta|alpha|rc|dev)\d*", re.IGNORECASE)
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class CoverageError(Exception):
    pass


def load_json(path, required=True):
    if not path.exists():
        if required:
            raise CoverageError(f"missing {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageError(f"cannot read {path}: {exc}") from exc


def version_parts(value, label):
    match = VERSION.fullmatch(str(value))
    if not match:
        raise CoverageError(f"{label}: malformed PostgreSQL version {value!r}")
    return tuple(int(v or 0) for v in match.groups())


def release_snapshot(data, support):
    if not isinstance(data, dict) or not isinstance(data.get("releases"), list):
        raise CoverageError("release snapshot must contain a releases array")
    try:
        dt.date.fromisoformat(data["as_of"])
    except (KeyError, TypeError, ValueError):
        raise CoverageError("release snapshot as_of must be YYYY-MM-DD")
    if not isinstance(data.get("source"), str) or not data["source"].startswith("https://"):
        raise CoverageError("release snapshot source must be an https URL")
    cutoff = dt.date.fromisoformat(support["postgresql"]["stable_release_cutoff"])
    minimum = int(support["postgresql"]["minimum_major"])
    found, targets = set(), []
    for item in data["releases"]:
        if not isinstance(item, dict) or not isinstance(item.get("version"), str):
            raise CoverageError("each release must have a version and release_date")
        version = item["version"]
        if PRERELEASE.match(version):
            continue
        parts = version_parts(version, "release snapshot")
        if parts[2] or "-" in version or "+" in version:
            raise CoverageError(f"release snapshot contains prerelease or unsupported version {version}")
        if version in found:
            raise CoverageError(f"duplicate PostgreSQL release {version}")
        found.add(version)
        try:
            released = dt.date.fromisoformat(item["release_date"])
        except (KeyError, TypeError, ValueError):
            raise CoverageError(f"invalid release_date for PostgreSQL {version}")
        if parts[0] >= minimum and released >= cutoff:
            targets.append(version)
    if not targets:
        raise CoverageError("release snapshot has no qualifying stable PostgreSQL releases")
    return sorted(targets, key=lambda v: version_parts(v, "snapshot"))


def validate_support(support):
    if not isinstance(support, dict) or support.get("schema_version") != 1:
        raise CoverageError("support schema_version must be 1")
    pg = support.get("postgresql")
    if not isinstance(pg, dict):
        raise CoverageError("support postgresql must be an object")
    if pg.get("minimum_major") != 15 or pg.get("stable_release_cutoff") != "2025-09-25":
        raise CoverageError("support postgresql must retain the specification's major 15 and 2025-09-25 cutoff")
    if not isinstance(support.get("os_support"), dict) or set(support["os_support"]) != {"macos", "windows", "linux"}:
        raise CoverageError("support os_support must declare exactly macos, windows, and linux")
    for name, details in support["os_support"].items():
        if not isinstance(details, dict) or not isinstance(details.get("minimum_version"), str) or not details["minimum_version"]:
            raise CoverageError(f"support {name} must declare minimum_version")
    if support.get("architectures") != ["x86_64", "arm64"]:
        raise CoverageError("support architectures must be [x86_64, arm64]")
    extensions = support.get("extensions")
    if not isinstance(extensions, dict) or not extensions:
        raise CoverageError("support extensions must be a nonempty object")
    declared_sql_names = set()
    for project, ext in extensions.items():
        if not isinstance(ext, dict) or not isinstance(ext.get("sql_names"), list) or not ext["sql_names"]:
            raise CoverageError(f"support extension {project} must declare sql_names")
        names = ext["sql_names"]
        if (any(not isinstance(name, str) or not name for name in names)
                or len(names) != len(set(names)) or declared_sql_names.intersection(names)):
            raise CoverageError(f"support extension {project}: duplicate or invalid SQL extension name")
        declared_sql_names.update(names)
        versions = ext.get("versions")
        if not isinstance(versions, dict) or not versions:
            raise CoverageError(f"support extension {project} must declare versions")
        for version, policy in versions.items():
            if not isinstance(policy, dict):
                raise CoverageError(f"support extension {project} {version}: policy must be an object")
            for field in ("postgresql_minimum_major", "postgresql_maximum_major"):
                if field in policy and (not isinstance(policy[field], int) or isinstance(policy[field], bool)):
                    raise CoverageError(f"support extension {project} {version}: {field} must be an integer")
            systems = policy.get("operating_systems", list(support["os_support"]))
            if (not isinstance(systems, list) or not systems
                    or any(not isinstance(name, str) or name not in support["os_support"] for name in systems)
                    or len(systems) != len(set(systems))):
                raise CoverageError(f"support extension {project} {version}: invalid operating_systems")


def validate_extension_policy(root, support):
    path = root / "policies" / "extensions.md"
    try:
        policy = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CoverageError(f"cannot read extension policy {path}: {exc}") from exc
    included = re.findall(r"^## ([^\n]+?) — include\s*$", policy, re.MULTILINE)
    excluded = re.findall(r"^## ([^\n]+?) — exclude\s*$", policy, re.MULTILINE)
    if len(included) != len(set(included)):
        raise CoverageError("extension policy contains duplicate include headings")
    if len(excluded) != len(set(excluded)) or set(included) & set(excluded):
        raise CoverageError("extension policy contains conflicting or duplicate decisions")
    section = re.search(r"^## Unreviewed projects\s*\n(.*?)(?=^## |\Z)", policy,
                        re.MULTILINE | re.DOTALL)
    if section:
        unreviewed = [name.strip() for name in re.findall(r"^\|\s*([^|]+?)\s*\|", section[1], re.MULTILINE)
                      if name.strip() not in {"Project", "---"}]
        if len(unreviewed) != len(set(unreviewed)) or set(unreviewed) & (set(included) | set(excluded)):
            raise CoverageError("extension policy repeats a project in unreviewed and decision sections")
    declared = set(support["extensions"])
    if set(included) != declared:
        missing = sorted(declared - set(included))
        unlisted = sorted(set(included) - declared)
        raise CoverageError(f"extension policy include headings differ from support.json (missing={missing}, unlisted={unlisted})")


def expected_targets(support, releases):
    platforms = tuple(f"{os}-{arch}" for os in support["os_support"]
                      for arch in support["architectures"])
    core = {(v, p) for v in releases for p in platforms}
    extensions = set()
    for project, ext in support.get("extensions", {}).items():
        for sql_name in ext.get("sql_names", []):
            for ext_version, policy in ext.get("versions", {}).items():
                systems = policy.get("operating_systems", list(support["os_support"]))
                low = int(policy.get("postgresql_minimum_major", support["postgresql"]["minimum_major"]))
                high = int(policy.get("postgresql_maximum_major", 999))
                if low > high:
                    raise CoverageError(f"{project} {ext_version}: PostgreSQL range is reversed")
                for pg in releases:
                    major = version_parts(pg, "snapshot")[0]
                    if low <= major <= high:
                        for os in systems:
                            for arch in support["architectures"]:
                                extensions.add((sql_name, ext_version, pg, f"{os}-{arch}"))
    return core, extensions


def validate_download(entry, label):
    if not isinstance(entry, dict):
        raise CoverageError(f"{label}: download must be an object")
    url, checksum = entry.get("url"), entry.get("sha256")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise CoverageError(f"{label}: malformed download URL")
    if not isinstance(checksum, str) or not SHA256.fullmatch(checksum):
        raise CoverageError(f"{label}: malformed SHA-256 checksum")


def inventory_targets(inventory):
    if not isinstance(inventory, dict):
        raise CoverageError("inventory must be an object")
    if "schema_version" in inventory and inventory["schema_version"] != 1:
        raise CoverageError("inventory schema_version must be 1")
    if not isinstance(inventory.get("postgresql", {}), dict) or not isinstance(inventory.get("extensions", {}), dict):
        raise CoverageError("inventory postgresql and extensions must be objects")
    core, extensions = {}, {}
    for pg, record in inventory.get("postgresql", {}).items():
        version_parts(pg, "inventory")
        if not isinstance(record, dict):
            raise CoverageError(f"PostgreSQL {pg}: record must be an object")
        if not isinstance(record.get("downloads"), dict):
            raise CoverageError(f"PostgreSQL {pg}: downloads must be an object")
        for platform, download in record["downloads"].items():
            validate_download(download, f"PostgreSQL {pg} {platform}")
            core[(pg, platform)] = download
    for name, versions in inventory.get("extensions", {}).items():
        if not isinstance(versions, dict):
            raise CoverageError(f"extension {name}: versions must be an object")
        for ext_version, record in versions.items():
            if not isinstance(record, dict) or not isinstance(record.get("downloads", {}), dict):
                raise CoverageError(f"extension {name} {ext_version}: record and downloads must be objects")
            for platform, downloads in record.get("downloads", {}).items():
                if not isinstance(downloads, list):
                    raise CoverageError(f"extension {name} {ext_version} {platform}: downloads must be an array")
                ranges = []
                for download in downloads:
                    validate_download(download, f"extension {name} {ext_version} {platform}")
                    pg_range = download.get("postgresql_support")
                    try:
                        low, high = pg_range["from"], pg_range["to"]
                        lo, hi = version_parts(low, "inventory range"), version_parts(high, "inventory range")
                    except (TypeError, KeyError):
                        raise CoverageError(f"extension {name} {ext_version}: malformed PostgreSQL range")
                    if lo > hi:
                        raise CoverageError(f"extension {name} {ext_version}: PostgreSQL range is reversed")
                    for old_low, old_high in ranges:
                        if lo <= old_high and old_low <= hi:
                            raise CoverageError(f"extension {name} {ext_version} {platform}: overlapping PostgreSQL ranges")
                    ranges.append((lo, hi))
                    extensions[(name, ext_version, low, high, platform)] = download
    return core, extensions


def _os_version_parts(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+)*", value):
        raise CoverageError(f"{label}: OS version must be numeric dotted version")
    parts = [int(part) for part in value.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def verification_records(root, support):
    records = []
    directory = root / "support" / "verification"
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.json")):
        data = load_json(path)
        if not isinstance(data, dict):
            raise CoverageError(f"verification record {path} must be an object")
        if data.get("schema_version") != 1:
            raise CoverageError(f"verification record {path}: schema_version must be 1")
        platform = data.get("platform")
        os_name, separator, architecture = platform.partition("-") if isinstance(platform, str) else ("", "", "")
        if (not separator or os_name not in support["os_support"]
                or architecture not in support["architectures"]):
            raise CoverageError(f"verification record {path}: invalid platform")
        environment = data.get("environment")
        if (not isinstance(environment, dict)
                or not isinstance(environment.get("os_version"), str) or not environment["os_version"]
                or environment.get("os") != os_name
                or environment.get("architecture") != architecture
                or environment.get("clean_system") is not True
                or environment.get("endpoint") not in {"minimum", "current"}):
            raise CoverageError(f"verification record {path}: invalid environment")
        actual = _os_version_parts(environment["os_version"], f"verification record {path}")
        minimum = _os_version_parts(support["os_support"][os_name]["minimum_version"],
                                    f"support {os_name} minimum_version")
        endpoint = environment["endpoint"]
        if ((endpoint == "minimum" and actual != minimum)
                or (endpoint == "current" and actual <= minimum)):
            raise CoverageError(f"verification record {path}: OS version does not match {endpoint} endpoint")
        if (not isinstance(data.get("test_cases"), list) or not data["test_cases"]
                or any(not isinstance(case, str) or not case for case in data["test_cases"])
                or not isinstance(data.get("test_revision"), str) or not data["test_revision"]):
            raise CoverageError(f"verification record {path}: invalid test evidence")
        required = ("outcome", "sha256", "component", "version", "platform", "postgresql_version")
        if any(key not in data for key in required):
            raise CoverageError(f"verification record {path}: missing required fields")
        records.append(data)
    return records


def verified(records, download, component, version, platform, pg_version, endpoint):
    return any(r.get("outcome") == "passed"
               and r.get("sha256", "").lower() == download["sha256"].lower()
               and r.get("component") == component and str(r.get("version")) == str(version)
               and r.get("platform") == platform and r.get("postgresql_version") == pg_version
               and r["environment"].get("endpoint") == endpoint
               for r in records)


def classify_extension_targets(targets, downloads, records):
    without_download, awaiting_verification = [], []
    for name, version, pg, platform in sorted(targets):
        matching = [(key, download) for key, download in downloads.items()
                    if key[0] == name and key[1] == version and key[4] == platform
                    and version_parts(key[2], "inventory range") <= version_parts(pg, "target")
                    <= version_parts(key[3], "inventory range")]
        if not matching:
            without_download.append((name, version, pg, platform))
            continue
        (_, _, low, high, _), download = matching[0]
        endpoints = {low, high}
        verified_endpoints = [(pg_endpoint, os_endpoint) for pg_endpoint in endpoints
                              for os_endpoint in ("minimum", "current") if verified(
            records, download, name, version, platform, pg_endpoint, os_endpoint)]
        if len(verified_endpoints) != len(endpoints) * 2:
            awaiting_verification.append((name, version, pg, platform))
    return without_download, awaiting_verification


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="write machine-readable coverage")
    args = parser.parse_args()
    try:
        root = args.root
        support = load_json(root / "support.json")
        validate_support(support)
        validate_extension_policy(root, support)
        snapshot = load_json(root / "support/postgresql-releases.json")
        inventory = load_json(root / "inventory.json", required=False) or {"postgresql": {}, "extensions": {}}
        releases = release_snapshot(snapshot, support)
        want_core, want_ext = expected_targets(support, releases)
        have_core, have_ext = inventory_targets(inventory)
        records = verification_records(root, support)
        core_without_download = sorted(t for t in want_core if t not in have_core)
        core_awaiting_verification = sorted(
            t for t in want_core if t in have_core and any(not verified(
                records, have_core[t], "postgresql", t[0], t[1], t[0], endpoint)
                for endpoint in ("minimum", "current")))
        missing_core = sorted(core_without_download + core_awaiting_verification)
        extension_without_download, extension_awaiting_verification = classify_extension_targets(
            want_ext, have_ext, records)
        missing_ext = sorted(extension_without_download + extension_awaiting_verification)
        result = {"snapshot_as_of": snapshot["as_of"], "postgresql_releases": len(releases),
                  "required_core": len(want_core), "missing_core": [list(x) for x in missing_core],
                  "core_without_download": [list(x) for x in core_without_download],
                  "core_awaiting_verification": [list(x) for x in core_awaiting_verification],
                  "required_extension_targets": len(want_ext),
                  "missing_extension": [list(x) for x in missing_ext],
                  "extension_without_download": [list(x) for x in extension_without_download],
                  "extension_awaiting_verification": [list(x) for x in extension_awaiting_verification],
                  "verification": "structural-only" if not missing_core and not missing_ext else
                  ("unverified" if not records else "incomplete"),
                  "coverage_scope": "structural coverage only; publication eligibility is not established"}
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"PostgreSQL releases: {len(releases)}; core targets: {len(want_core)} ({len(missing_core)} missing)")
            print(f"Extension SQL targets: {len(want_ext)} ({len(missing_ext)} missing); verification: {result['verification']}")
            print(f"  core: {len(core_without_download)} without download, {len(core_awaiting_verification)} awaiting verification")
            print(f"  extensions: {len(extension_without_download)} without download, {len(extension_awaiting_verification)} awaiting verification")
            for version, platform in missing_core[:20]:
                print(f"missing core {version} {platform}")
            for name, version, pg, platform in missing_ext[:20]:
                print(f"missing extension {name} {version} PostgreSQL {pg} {platform}")
            if len(missing_core) + len(missing_ext) > 40:
                print("additional missing targets omitted")
        return 1 if missing_core or missing_ext else 0
    except (CoverageError, KeyError, TypeError, ValueError) as exc:
        print(f"coverage: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
