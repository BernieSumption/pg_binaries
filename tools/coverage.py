#!/usr/bin/env python3
"""Reconcile declared PostgreSQL and extension support with inventory.json."""

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:[-+].*)?$")
PRERELEASE = re.compile(r"^\d+(?:\.\d+)?(?:beta|alpha|rc|dev)\d*", re.IGNORECASE)
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
REVISION = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
VERIFICATION_OUTCOMES = {"passed", "failed", "skipped"}
VERIFICATION_SCOPES = {"pilot-smoke", "publication"}


class CoverageError(Exception):
    pass


def archive_project_name(project):
    if not isinstance(project, str):
        raise CoverageError("extension project name must be a string")
    name = re.sub(r"[^a-z0-9]+", "_", project.lower()).strip("_")
    if not name:
        raise CoverageError(f"extension project has no archive name: {project!r}")
    return name


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
    minimum = int(support["postgresql"]["minimum_major"])
    status = data.get("support_status")
    if not isinstance(status, dict) or not isinstance(status.get("supported_majors"), list):
        raise CoverageError("release snapshot must include upstream support_status and supported_majors")
    try:
        dt.date.fromisoformat(status["as_of"])
    except (KeyError, TypeError, ValueError):
        raise CoverageError("release snapshot support_status as_of must be YYYY-MM-DD")
    if not isinstance(status.get("source"), str) or not status["source"].startswith("https://"):
        raise CoverageError("release snapshot support_status source must be an https URL")
    supported = status["supported_majors"]
    if (not supported
            or any(not isinstance(v, int) or isinstance(v, bool) or v < minimum for v in supported)
            or len(supported) != len(set(supported))):
        raise CoverageError("release snapshot supported_majors must list distinct supported major numbers")
    found, latest = set(), {}
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
        if parts[0] in supported:
            previous = latest.get(parts[0])
            if previous is None or parts[1] > version_parts(previous, "snapshot")[1]:
                latest[parts[0]] = version
    missing = set(supported) - set(latest)
    if missing:
        raise CoverageError(f"release snapshot lacks a stable release for supported PostgreSQL majors {sorted(missing)}")
    return [latest[major] for major in sorted(latest)]


def validate_support(support):
    if not isinstance(support, dict) or support.get("schema_version") != 1:
        raise CoverageError("support schema_version must be 1")
    pg = support.get("postgresql")
    if not isinstance(pg, dict):
        raise CoverageError("support postgresql must be an object")
    if pg.get("minimum_major") != 15 or "stable_release_cutoff" in pg:
        raise CoverageError("support postgresql must select supported majors from 15 without a release-date cutoff")
    try:
        dt.date.fromisoformat(support["version_selection_as_of"])
    except (KeyError, TypeError, ValueError):
        raise CoverageError("support version_selection_as_of must be YYYY-MM-DD")
    if not isinstance(support.get("os_support"), dict) or set(support["os_support"]) != {"macos", "windows", "linux"}:
        raise CoverageError("support os_support must declare exactly macos, windows, and linux")
    for name, details in support["os_support"].items():
        if not isinstance(details, dict) or not isinstance(details.get("minimum_version"), str) or not details["minimum_version"]:
            raise CoverageError(f"support {name} must declare minimum_version")
    if support.get("architectures") != ["x86_64", "arm64"]:
        raise CoverageError("support architectures must be [x86_64, arm64]")
    platform_architectures = support.get("platform_architectures")
    if (not isinstance(platform_architectures, dict)
            or set(platform_architectures) != set(support["os_support"])
            or any(not isinstance(values, list) or not values or len(values) != len(set(values))
                   or any(value not in support["architectures"] for value in values)
                   for values in platform_architectures.values())
            or platform_architectures != {"macos": ["x86_64", "arm64"],
                                          "windows": ["x86_64"],
                                          "linux": ["x86_64", "arm64"]}):
        raise CoverageError("support platform_architectures must declare macOS and Linux x86_64/arm64 and Windows x86_64")
    extensions = support.get("extensions")
    if not isinstance(extensions, dict) or not extensions:
        raise CoverageError("support extensions must be a nonempty object")
    declared_sql_names = set()
    archive_names = set()
    for project, ext in extensions.items():
        archive_name = archive_project_name(project)
        if archive_name in archive_names:
            raise CoverageError(f"duplicate extension archive project name: {archive_name}")
        archive_names.add(archive_name)
        if not isinstance(ext, dict) or not isinstance(ext.get("sql_names"), list) or not ext["sql_names"]:
            raise CoverageError(f"support extension {project} must declare sql_names")
        names = ext["sql_names"]
        if (any(not isinstance(name, str) or not name for name in names)
                or len(names) != len(set(names)) or declared_sql_names.intersection(names)):
            raise CoverageError(f"support extension {project}: duplicate or invalid SQL extension name")
        declared_sql_names.update(names)
        required_projects = ext.get("requires", [])
        if (not isinstance(required_projects, list)
                or any(not isinstance(name, str) or not name for name in required_projects)
                or len(required_projects) != len(set(required_projects))
                or any(name not in extensions for name in required_projects)):
            raise CoverageError(f"support extension {project}: requires must list declared projects uniquely")
        required_versions = ext.get("requires_versions", {})
        if (not isinstance(required_versions, dict)
                or any(name not in required_projects for name in required_versions)):
            raise CoverageError(f"support extension {project}: requires_versions keys must name required projects")
        for required_project, constraint in required_versions.items():
            if (not isinstance(constraint, dict) or set(constraint) != {"minimum_version"}
                    or not isinstance(constraint.get("minimum_version"), str)):
                raise CoverageError(
                    f"support extension {project}: {required_project} requires a minimum_version constraint")
            version_parts(constraint["minimum_version"],
                          f"support extension {project} {required_project} minimum_version")
            eligible = support["extensions"][required_project].get("versions", {})
            if not any(version_parts(candidate, f"support extension {required_project} version")
                       >= version_parts(constraint["minimum_version"],
                                        f"support extension {project} {required_project} minimum_version")
                       for candidate in eligible):
                raise CoverageError(
                    f"support extension {project}: no declared {required_project} version meets minimum "
                    f"{constraint['minimum_version']}")
        versions = ext.get("versions")
        if not isinstance(versions, dict) or not versions:
            raise CoverageError(f"support extension {project} must declare versions")
        first_releases = ext.get("major_first_releases", {})
        if not isinstance(first_releases, dict):
            raise CoverageError(f"support extension {project}: major_first_releases must be an object")
        for major, record in first_releases.items():
            if not major.isdigit() or not isinstance(record, dict):
                raise CoverageError(f"support extension {project}: invalid major-first-release record")
            try:
                dt.date.fromisoformat(record["date"])
            except (KeyError, TypeError, ValueError):
                raise CoverageError(f"support extension {project}: invalid first release date for major {major}")
            if not isinstance(record.get("source"), str) or not record["source"].startswith("https://"):
                raise CoverageError(f"support extension {project}: missing source for major {major}")
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


def prerequisite_version_allowed(support, project, prerequisite, version):
    """Return whether a prerequisite release meets the consuming project's declared constraint."""
    constraint = (support.get("extensions", {}).get(project, {})
                  .get("requires_versions", {}).get(prerequisite, {}))
    minimum = constraint.get("minimum_version")
    return minimum is None or version_parts(version, f"{prerequisite} version") >= version_parts(
        minimum, f"{project} prerequisite minimum_version")


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
                      for arch in support["platform_architectures"][os])
    core = {(v, p) for v in releases for p in platforms}
    extensions = set()
    selected_versions = {}
    as_of = dt.date.fromisoformat(support["version_selection_as_of"])
    try:
        threshold = as_of.replace(year=as_of.year - 2)
    except ValueError:
        threshold = as_of.replace(year=as_of.year - 2, day=28)
    for project, ext in support.get("extensions", {}).items():
        for pg in releases:
            pg_major = version_parts(pg, "snapshot")[0]
            for platform in platforms:
                os = platform.split("-", 1)[0]
                compatible = {}
                for ext_version, policy in ext.get("versions", {}).items():
                    low = int(policy.get("postgresql_minimum_major", support["postgresql"]["minimum_major"]))
                    high = int(policy.get("postgresql_maximum_major", 999))
                    if low > high:
                        raise CoverageError(f"{project} {ext_version}: PostgreSQL range is reversed")
                    if not low <= pg_major <= high or os not in policy.get("operating_systems", list(support["os_support"])):
                        continue
                    major = version_parts(ext_version, f"{project} version")[0]
                    previous = compatible.get(major)
                    if previous is None or version_parts(ext_version, f"{project} version") > version_parts(previous, f"{project} version"):
                        compatible[major] = ext_version
                if not compatible:
                    continue
                latest = max(compatible.values(), key=lambda version: version_parts(version, f"{project} version"))
                selected = {latest}
                for major, version in compatible.items():
                    if version == latest:
                        continue
                    record = ext.get("major_first_releases", {}).get(str(major))
                    if record is None:
                        raise CoverageError(f"{project}: first release date required for eligible major {major}")
                    if dt.date.fromisoformat(record["date"]) >= threshold:
                        selected.add(version)
                for sql_name in ext.get("sql_names", []):
                    extensions.update((sql_name, version, pg, platform) for version in selected)
                selected_versions[(project, pg, platform)] = selected
    for (project, pg, platform), versions in selected_versions.items():
        for prerequisite in support["extensions"][project].get("requires", []):
            prerequisite_versions = selected_versions.get((prerequisite, pg, platform), set())
            if not any(prerequisite_version_allowed(support, project, prerequisite, version)
                       for version in prerequisite_versions):
                raise CoverageError(
                    f"{project} target PostgreSQL {pg} {platform} has no selected "
                    f"{prerequisite} prerequisite meeting its version constraint")
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


def profile_revision(profile_id, scope, cases, platforms, source_hashes):
    digest_input = {"profile_id": profile_id, "scope": scope, "case_ids": cases,
                    "platforms": platforms, "sources": source_hashes}
    return hashlib.sha256(json.dumps(digest_input, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def verification_profile(root, profile_id, allow_missing_sources=False):
    """Resolve a registered profile and hash its case list and current source files."""
    path = Path(root) / "support" / "verification-profiles.json"
    registry = load_json(path)
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        raise CoverageError("verification profile registry schema_version must be 1")
    profiles = registry.get("profiles")
    if not isinstance(profiles, dict) or profile_id not in profiles:
        raise CoverageError(f"unknown verification profile {profile_id!r}")
    profile = profiles[profile_id]
    if not isinstance(profile, dict):
        raise CoverageError(f"verification profile {profile_id}: expected an object")
    scope = profile.get("scope")
    cases = profile.get("case_ids")
    sources = profile.get("sources")
    platforms = profile.get("platforms")
    if scope not in VERIFICATION_SCOPES:
        raise CoverageError(f"verification profile {profile_id}: invalid scope")
    if (not isinstance(cases, list) or not cases
            or any(not isinstance(case, str) or not case.strip() for case in cases)
            or cases != sorted(set(cases))):
        raise CoverageError(f"verification profile {profile_id}: case_ids must be sorted unique strings")
    if (not isinstance(sources, list) or not sources
            or any(not isinstance(source, str) or not source for source in sources)
            or sources != sorted(set(sources))):
        raise CoverageError(f"verification profile {profile_id}: sources must be sorted unique paths")
    if (not isinstance(platforms, list) or not platforms
            or any(not isinstance(platform, str) or not platform for platform in platforms)
            or platforms != sorted(set(platforms))):
        raise CoverageError(f"verification profile {profile_id}: platforms must be sorted unique strings")
    source_hashes = {}
    crlf_source_hashes = {}
    sources_available = True
    root = Path(root)
    for source in sources:
        if "#" in source:
            raise CoverageError(f"verification profile {profile_id}: invalid source path {source!r}")
        source_path = Path(source)
        if source_path.is_absolute() or ".." in source_path.parts:
            raise CoverageError(f"verification profile {profile_id}: invalid source path {source!r}")
        try:
            content = (root / source_path).read_bytes()
            try:
                content.decode("utf-8")
                text_source = b"\0" not in content
            except UnicodeDecodeError:
                text_source = False
            normalized = content.replace(b"\r\n", b"\n") if text_source else content
            source_hashes[source] = hashlib.sha256(normalized).hexdigest()
            crlf = normalized.replace(b"\n", b"\r\n") if text_source else content
            crlf_source_hashes[source] = hashlib.sha256(crlf).hexdigest()
        except OSError as exc:
            if not allow_missing_sources:
                raise CoverageError(f"verification profile {profile_id}: cannot read source {source!r}: {exc}") from exc
            sources_available = False
            source_hashes[source] = None
            crlf_source_hashes[source] = None
    revision = profile_revision(profile_id, scope, cases, platforms, source_hashes)
    compatible = {revision, profile_revision(profile_id, scope, cases, platforms, crlf_source_hashes)}
    equivalences = registry.get("reviewed_equivalences", {})
    if not isinstance(equivalences, dict):
        raise CoverageError("reviewed_equivalences must be an object")
    for entry in equivalences.get(profile_id, []):
        if (not isinstance(entry, dict) or set(entry) != {"current", "previous", "reason"}
                or any(not isinstance(entry[key], str) or not entry[key]
                       for key in ("current", "previous", "reason"))
                or not SHA256.fullmatch(entry["current"])
                or not SHA256.fullmatch(entry["previous"])):
            raise CoverageError(f"verification profile {profile_id}: invalid reviewed equivalence")
        if entry["current"] == revision:
            compatible.add(entry["previous"])
    return {"profile_id": profile_id, "scope": scope, "case_ids": cases,
            "platforms": platforms, "profile_revision": revision,
            "compatible_profile_revisions": sorted(compatible),
            "sources_available": sources_available}


def verification_records(root, support):
    records = []
    directory = root / "support" / "verification"
    if not directory.exists():
        return records
    for path in sorted(directory.glob("*.json")):
        data = load_json(path)
        if not isinstance(data, dict):
            raise CoverageError(f"verification record {path} must be an object")
        if data.get("schema_version") != 2:
            raise CoverageError(f"verification record {path}: schema_version must be 2")
        platform = data.get("platform")
        os_name, separator, architecture = platform.partition("-") if isinstance(platform, str) else ("", "", "")
        if (not separator or os_name not in support["os_support"]
                or architecture not in support["platform_architectures"][os_name]):
            raise CoverageError(f"verification record {path}: invalid platform")
        current_profile = validate_verification_record(
            data, support, root, f"verification record {path}", allow_stale=True)
        data["_profile_current"] = current_profile
        data["_record_file"] = path.name
        required = ("outcome", "sha256", "component", "version", "platform", "postgresql_version")
        if any(key not in data for key in required):
            raise CoverageError(f"verification record {path}: missing required fields")
        records.append(data)
    return records


def validate_verification_record(data, support, root, label="verification record", allow_stale=False):
    """Validate the reusable evidence contract shared by coverage and candidates."""
    if data.get("schema_version") != 2:
        raise CoverageError(f"{label}: schema_version must be 2")
    profile_id = data.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id:
        raise CoverageError(f"{label}: missing or invalid profile_id")
    try:
        profile = verification_profile(root, profile_id, allow_missing_sources=allow_stale)
    except CoverageError as exc:
        if not (allow_stale and str(exc).startswith("unknown verification profile")):
            raise
        profile = None
    scope = data.get("scope")
    if profile is not None and scope != profile["scope"]:
        raise CoverageError(f"{label}: scope does not match registered profile")
    if profile is None and scope not in VERIFICATION_SCOPES:
        raise CoverageError(f"{label}: unknown historical profile scope")
    profile_revision = data.get("profile_revision")
    if not isinstance(profile_revision, str) or not SHA256.fullmatch(profile_revision):
        raise CoverageError(f"{label}: malformed profile_revision")
    if data.get("outcome") not in VERIFICATION_OUTCOMES:
        raise CoverageError(f"{label}: outcome must be passed, failed, or skipped")
    if not isinstance(data.get("sha256"), str) or not SHA256.fullmatch(data["sha256"]):
        raise CoverageError(f"{label}: malformed archive SHA-256")
    revision = data.get("test_revision")
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise CoverageError(f"{label}: test_revision must be a full Git commit hash")
    cases = data.get("test_cases")
    if (not isinstance(cases, list) or not cases
            or any(not isinstance(case, str) or not case.strip() for case in cases)
            or len(cases) != len(set(cases)) or cases != sorted(cases)):
        raise CoverageError(f"{label}: test_cases must be nonempty unique strings")
    current_profile = (profile is not None and profile["sources_available"]
                       and profile_revision in profile["compatible_profile_revisions"]
                       and cases == profile["case_ids"])
    if not current_profile and not allow_stale:
        raise CoverageError(f"{label}: test profile does not match current suite")
    if scope == "publication":
        case_results = data.get("case_results")
        if (not isinstance(case_results, dict)
                or set(case_results) != set(cases)
                or any(not isinstance(result, str) or result not in VERIFICATION_OUTCOMES
                       for result in case_results.values())):
            raise CoverageError(
                f"{label}: publication case_results must map every test case to passed, failed, or skipped")
        result_outcome = ("failed" if "failed" in case_results.values()
                          else "skipped" if "skipped" in case_results.values()
                          else "passed")
        if data["outcome"] != result_outcome:
            raise CoverageError(
                f"{label}: outcome must match publication case_results ({result_outcome})")
    environment = data.get("environment")
    if (not isinstance(environment, dict)
            or not all(isinstance(environment.get(field), str) and environment[field]
                       for field in ("image_id", "dependency_check_profile"))
            or not isinstance(environment.get("dependency_checks_passed"), bool)):
        raise CoverageError(f"{label}: environment must identify image and dependency checks")
    platform = data.get("platform")
    os_name, separator, architecture = platform.partition("-") if isinstance(platform, str) else ("", "", "")
    if (not separator or os_name not in support["os_support"]
            or architecture not in support["platform_architectures"][os_name]
            or environment.get("os") != os_name
            or environment.get("architecture") != architecture):
        raise CoverageError(f"{label}: environment identity does not match platform")
    if (not isinstance(environment.get("clean_system"), bool)
            or (data["outcome"] == "passed" and environment["clean_system"] is not True)
            or environment.get("endpoint") not in {"minimum", "current"}):
        raise CoverageError(f"{label}: invalid environment")
    actual = _os_version_parts(environment.get("os_version"), label)
    minimum = _os_version_parts(support["os_support"][os_name]["minimum_version"],
                                f"support {os_name} minimum_version")
    endpoint = environment["endpoint"]
    if ((endpoint == "minimum" and actual != minimum)
            or (endpoint == "current" and actual < minimum)):
        raise CoverageError(f"{label}: OS version does not match {endpoint} endpoint")
    if scope == "publication" and data.get("component") != "postgresql":
        pg_version = data.get("postgresql_version")
        assembled_core = data.get("assembled_core")
        expected_archive = f"postgresql-{pg_version}-{platform}.tar.gz"
        if (not isinstance(pg_version, str) or not isinstance(assembled_core, dict)
                or assembled_core.get("archive") != expected_archive
                or assembled_core.get("version") != pg_version
                or not isinstance(assembled_core.get("sha256"), str)
                or not SHA256.fullmatch(assembled_core["sha256"])):
            raise CoverageError(
                f"{label}: publication extension evidence requires assembled_core with canonical archive, version and SHA-256")
        project = data.get("project")
        selected = support.get("extensions", {}).get(project)
        selected_project = project
        if selected is None:
            selected_project, selected = next(((candidate, details)
                                               for candidate, details in support["extensions"].items()
                                               if data.get("component") in details.get("sql_names", [])),
                                              (None, None))
        if not isinstance(selected, dict):
            raise CoverageError(f"{label}: publication extension evidence names an undeclared project")
        if project is not None and support["extensions"].get(project) is not selected:
            raise CoverageError(f"{label}: publication extension project does not match its SQL name")
        required_projects = selected.get("requires", [])
        prerequisites = data.get("prerequisite_archives", [] if not required_projects else None)
        if not isinstance(prerequisites, list) or len(prerequisites) != len(required_projects):
            raise CoverageError(f"{label}: publication extension evidence must bind every prerequisite archive")
        seen_prerequisites = set()
        for item, required_project in zip(prerequisites, required_projects):
            if (not isinstance(item, dict)
                    or set(item) != {"project", "archive", "version", "sha256"}
                    or item.get("project") != required_project):
                raise CoverageError(f"{label}: prerequisite archive projects do not match declared requirements")
            prereq_version = item.get("version")
            archive = item.get("archive")
            checksum = item.get("sha256")
            target_match = (re.fullmatch(
                rf"{re.escape(archive_project_name(required_project))}-"
                rf"{re.escape(str(prereq_version))}-postgresql-(\d+\.\d+(?:-to-\d+\.\d+)?)-"
                rf"{re.escape(platform)}\.tar\.gz", archive)
                if isinstance(archive, str) and isinstance(prereq_version, str) else None)
            target_covers_pg = False
            if target_match:
                target = target_match.group(1)
                if "-to-" in target:
                    low, high = target.split("-to-", 1)
                    target_covers_pg = (version_parts(low, "prerequisite range")
                                        <= version_parts(pg_version, "target")
                                        <= version_parts(high, "prerequisite range"))
                else:
                    target_covers_pg = target == pg_version
            canonical = (isinstance(prereq_version, str)
                         and prereq_version in support["extensions"].get(required_project, {}).get("versions", {})
                         and prerequisite_version_allowed(support, selected_project, required_project, prereq_version)
                         and target_covers_pg)
            if (isinstance(prereq_version, str)
                    and prereq_version in support["extensions"].get(required_project, {}).get("versions", {})
                    and not prerequisite_version_allowed(support, selected_project, required_project, prereq_version)):
                minimum = (support["extensions"][selected_project].get("requires_versions", {})
                           .get(required_project, {}).get("minimum_version"))
                raise CoverageError(
                    f"{label}: prerequisite {required_project} {prereq_version} does not meet minimum {minimum}")
            if (not canonical or required_project in seen_prerequisites
                    or not isinstance(checksum, str) or not SHA256.fullmatch(checksum)):
                raise CoverageError(f"{label}: prerequisite archive reference is invalid for {required_project}")
            seen_prerequisites.add(required_project)
    if profile is not None and platform not in profile["platforms"]:
        raise CoverageError(f"{label}: platform is not supported by registered profile")
    if data["outcome"] == "passed":
        if environment.get("clean_system") is not True:
            raise CoverageError(f"{label}: passed outcome requires a clean system")
        if environment["dependency_checks_passed"] is not True:
            raise CoverageError(f"{label}: passed outcome requires successful dependency checks")
    return current_profile


def verified(records, download, component, version, platform, pg_version, endpoint,
             assembled_core_sha256=None, prerequisite_archives=None):
    return any(r.get("outcome") == "passed"
               and r.get("scope") == "publication"
               and r.get("_profile_current") is True
               and r.get("sha256", "").lower() == download["sha256"].lower()
               and r.get("component") == component and str(r.get("version")) == str(version)
               and r.get("platform") == platform and r.get("postgresql_version") == pg_version
               and r["environment"].get("endpoint") == endpoint
               and (assembled_core_sha256 is None or (
                   isinstance(r.get("assembled_core"), dict)
                   and isinstance(r["assembled_core"].get("sha256"), str)
                   and r["assembled_core"]["sha256"].lower() == assembled_core_sha256.lower()
               ))
               and (prerequisite_archives is None or r.get("prerequisite_archives", []) == prerequisite_archives)
               for r in records)


def expected_prerequisite_archives(support, extension_downloads, project, pg_version, platform):
    result = []
    selected = support.get("extensions", {}).get(project)
    if not isinstance(selected, dict):
        return None
    required_projects = selected.get("requires", [])
    if not isinstance(required_projects, list):
        return None
    for prerequisite in required_projects:
        if prerequisite not in support["extensions"]:
            return None
        candidates = []
        for sql_name in support["extensions"][prerequisite]["sql_names"]:
            matches = [(key, download) for key, download in extension_downloads.items()
                       if key[0] == sql_name and key[4] == platform
                       and prerequisite_version_allowed(support, project, prerequisite, key[1])
                       and version_parts(key[2], "prerequisite range") <= version_parts(pg_version, "target")
                       <= version_parts(key[3], "prerequisite range")]
            if len(matches) != 1:
                return None
            candidates.append(matches[0])
        references = {(key[1], download["url"], download["sha256"].lower())
                      for key, download in candidates}
        if len(references) != 1:
            return None
        version, url, checksum = references.pop()
        filename = url.rsplit("/", 1)[-1]
        result.append({"project": prerequisite, "archive": filename,
                       "version": version, "sha256": checksum})
    return result


def classify_extension_targets(targets, downloads, records, core_downloads, support=None):
    without_download, awaiting_verification = [], []
    for name, version, pg, platform in sorted(targets):
        matching = [(key, download) for key, download in downloads.items()
                    if key[0] == name and key[1] == version and key[4] == platform
                    and version_parts(key[2], "inventory range") <= version_parts(pg, "target")
                    <= version_parts(key[3], "inventory range")]
        if not matching:
            without_download.append((name, version, pg, platform))
            continue
        download = matching[0][1]
        core_download = core_downloads.get((pg, platform))
        project = next((project for project, details in support["extensions"].items()
                        if name in details["sql_names"]), None) if support else None
        prerequisites = (expected_prerequisite_archives(
            support, downloads, project, pg, platform) if project else [])
        if (core_download is None or prerequisites is None
                or not verified(records, download, name, version, platform, pg, "current",
                                assembled_core_sha256=core_download["sha256"],
                                prerequisite_archives=prerequisites)):
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
            t for t in want_core if t in have_core and not verified(
                records, have_core[t], "postgresql", t[0], t[1], t[0], "current"))
        missing_core = sorted(core_without_download + core_awaiting_verification)
        extension_without_download, extension_awaiting_verification = classify_extension_targets(
            want_ext, have_ext, records, have_core, support)
        missing_ext = sorted(extension_without_download + extension_awaiting_verification)
        outcome_records = {
            outcome: [{"record": r["_record_file"],
                      "target": {"component": r["component"], "version": r["version"],
                                 "postgresql_version": r["postgresql_version"],
                                 "platform": r["platform"]},
                      "checks": r["test_cases"], "scope": r["scope"],
                      "profile_current": r["_profile_current"],
                      **({"reason": r["reason"]} if isinstance(r.get("reason"), str) else {})}
                     for r in records if r["outcome"] == outcome]
            for outcome in ("failed", "skipped")
        }
        result = {"snapshot_as_of": snapshot["as_of"], "postgresql_releases": len(releases),
                  "required_core": len(want_core), "missing_core": [list(x) for x in missing_core],
                  "core_without_download": [list(x) for x in core_without_download],
                  "core_awaiting_verification": [list(x) for x in core_awaiting_verification],
                  "required_extension_targets": len(want_ext),
                  "stale_verification_records": sum(r.get("_profile_current") is False for r in records),
                  "missing_extension": [list(x) for x in missing_ext],
                  "extension_without_download": [list(x) for x in extension_without_download],
                  "extension_awaiting_verification": [list(x) for x in extension_awaiting_verification],
                  "verification_records_by_outcome": outcome_records,
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
            for outcome, items in outcome_records.items():
                for item in items:
                    target = item["target"]
                    label = (f"{target['component']} {target['version']} PostgreSQL "
                             f"{target['postgresql_version']} {target['platform']}")
                    print(f"verification {outcome}: {label}; checks: {', '.join(item['checks'])}; record: {item['record']}")
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
