#!/usr/bin/env python3
"""Build a structural draft of a future inventory from proposed assets.

This helper does not establish publication eligibility or validate all inventory
metadata, including OS support and archive contents.
"""

from copy import deepcopy
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

_BUILTINS_SPEC = importlib.util.spec_from_file_location(
    "candidate_builtins", Path(__file__).with_name("discover_builtins.py"))
_builtins = importlib.util.module_from_spec(_BUILTINS_SPEC)
_BUILTINS_SPEC.loader.exec_module(_builtins)

_COVERAGE_SPEC = importlib.util.spec_from_file_location("candidate_coverage", Path(__file__).with_name("coverage.py"))
_coverage = importlib.util.module_from_spec(_COVERAGE_SPEC)
_COVERAGE_SPEC.loader.exec_module(_coverage)
CoverageError = _coverage.CoverageError
expected_targets = _coverage.expected_targets
inventory_targets = _coverage.inventory_targets
release_snapshot = _coverage.release_snapshot
validate_download = _coverage.validate_download
version_parts = _coverage.version_parts


class CandidateError(ValueError):
    """The proposed candidate cannot safely be represented in the inventory."""


TAG = re.compile(r"^catalog-\d{8}-\d+$")
FILENAME = re.compile(r"^[A-Za-z0-9._+-]+\.tar\.gz$")


def merge_candidate(base_inventory, proposed_entries, support, snapshot, root=None):
    """Return an unpublished structural draft containing base entries and proposals.

    Each proposal has ``component`` (``postgresql``, an inventory SQL name, or
    a declared extension project name),
    ``version``, ``platform``, ``tag``, ``filename``, ``sha256``, and
    ``verification``. Extension proposals also have ``postgresql_support``.
    Verification is a list of coverage-style records, with one passed current
    publication record for each selected target.
    """
    try:
        root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
        releases = release_snapshot(snapshot, support)
        _coverage.validate_support(support)
        expected_core, expected_extensions = expected_targets(support, releases)
        base_core, base_extensions = inventory_targets(base_inventory)
    except (CoverageError, KeyError, TypeError) as exc:
        raise CandidateError(str(exc)) from exc

    if not isinstance(proposed_entries, list):
        raise CandidateError("proposed entries must be an array")
    candidate = deepcopy(base_inventory)
    _retire_unselected(candidate, expected_core, expected_extensions)
    candidate.setdefault("schema_version", 1)
    candidate.setdefault("postgresql", {})
    candidate.setdefault("extensions", {})
    if ("os_support" in candidate
            and candidate["os_support"] != support.get("os_support")):
        raise CandidateError("base inventory os_support differs from declared support")
    candidate["os_support"] = deepcopy(support["os_support"])
    candidate["candidate_status"] = "structural-draft"
    candidate_evidence = candidate["verification_evidence"] = {}
    seen_targets, seen_urls = set(), set()
    base_urls = {entry["url"] for entry in list(base_core.values()) + list(base_extensions.values())}
    pending_extension_evidence = []

    for item in proposed_entries:
        if not isinstance(item, dict):
            raise CandidateError("each proposed entry must be an object")
        component, version, platform = item.get("component"), item.get("version"), item.get("platform")
        if not all(isinstance(v, str) and v for v in (component, version, platform)):
            raise CandidateError("entry component, version and platform are required strings")
        os_name, separator, arch = platform.partition("-")
        if (not separator or os_name not in support.get("os_support", {})
                or arch not in support.get("architectures", [])):
            raise CandidateError(f"unsupported platform {platform!r}")
        tag, filename = item.get("tag"), item.get("filename")
        if not isinstance(tag, str) or not TAG.fullmatch(tag):
            raise CandidateError("tag must be an immutable catalog-YYYYMMDD-N release tag")
        if not isinstance(filename, str) or not FILENAME.fullmatch(filename):
            raise CandidateError("filename must be a simple .tar.gz asset name")
        if component == "postgresql":
            expected = f"postgresql-{version}-{platform}.tar.gz"
            if filename != expected:
                raise CandidateError(f"PostgreSQL filename must be {expected}")
        else:
            suffix = f"-{version}-postgresql-"
            marker = filename.find(suffix)
            if marker <= 0 or not filename.endswith(f"-{platform}.tar.gz"):
                raise CandidateError("extension filename must identify project, version, PostgreSQL target and platform")
            pg_target = filename[marker + len(suffix):-len(f"-{platform}.tar.gz")]
            if not re.fullmatch(r"\d+\.\d+(?:-to-\d+\.\d+)?", pg_target):
                raise CandidateError("extension filename must identify a PostgreSQL build version or support range")
        url = f"https://github.com/BernieSumption/pg_binaries/releases/download/{tag}/{filename}"
        download = {"url": url, "sha256": item.get("sha256")}
        try:
            validate_download(download, "candidate")
        except CoverageError as exc:
            raise CandidateError(str(exc)) from exc

        if component == "postgresql":
            target = (version, platform)
            if target not in expected_core:
                raise CandidateError(f"unsupported PostgreSQL target {target}")
            target_key = ("postgresql", version, platform)
            included_extensions = item.get("included_extensions")
            if (not isinstance(included_extensions, list)
                    or any(not isinstance(name, str) or not _builtins.EXTENSION_NAME.fullmatch(name)
                           for name in included_extensions)
                    or included_extensions != sorted(set(included_extensions))):
                raise CandidateError("included_extensions must be a sorted unique array of names")
            existing_version = candidate["postgresql"].get(version, {})
            existing_names = existing_version.get("included_extensions")
            if existing_names is not None and existing_names != included_extensions:
                raise CandidateError(f"inconsistent included_extensions for PostgreSQL {version}")
        else:
            target = None
            ext_versions = support.get("extensions", {})
            if component in ext_versions:
                project = component
                extension = ext_versions[project]
                sql_names = extension.get("sql_names", [])
                policy = extension.get("versions", {}).get(version)
            else:
                selected = next(((project_name, ext, policy) for project_name, ext in ext_versions.items()
                                 for name in ext.get("sql_names", []) if name == component
                                 for policy in [ext.get("versions", {}).get(version)] if policy), None)
                if selected is None:
                    raise CandidateError(f"unsupported extension target {component} {version}")
                project, extension, policy = selected
                sql_names = [component]
            if not policy:
                raise CandidateError(f"unsupported extension target {component} {version}")
            if filename[:marker] != _coverage.archive_project_name(project):
                raise CandidateError("extension filename must identify the declared project")
            pg_range = item.get("postgresql_support")
            try:
                low, high = pg_range["from"], pg_range["to"]
                if version_parts(low, "candidate range") > version_parts(high, "candidate range"):
                    raise CandidateError("PostgreSQL support range is reversed")
            except (TypeError, KeyError, CoverageError) as exc:
                raise CandidateError("malformed PostgreSQL support range") from exc
            if "-to-" in pg_target:
                if pg_target != f"{low}-to-{high}":
                    raise CandidateError("filename support range differs from the inventory claim")
            elif not (version_parts(low, "candidate range")
                      <= version_parts(pg_target, "filename PostgreSQL build version")
                      <= version_parts(high, "candidate range")):
                raise CandidateError("filename PostgreSQL build version falls outside the inventory claim")
            minimum_major = policy.get("postgresql_minimum_major", support["postgresql"]["minimum_major"])
            maximum_major = policy.get("postgresql_maximum_major")
            if (version_parts(low, "candidate range")[0] < minimum_major
                    or (maximum_major is not None and version_parts(high, "candidate range")[0] > maximum_major)):
                raise CandidateError("extension range exceeds declared PostgreSQL compatibility")
            download["postgresql_support"] = {"from": low, "to": high}
            relevant = [pg for pg in releases
                        if version_parts(low, "candidate range") <= version_parts(pg, "candidate range")
                        <= version_parts(high, "candidate range")]
            if (not relevant or any((sql_name, version, pg, platform) not in expected_extensions
                                    for sql_name in sql_names for pg in relevant)):
                raise CandidateError("extension range includes unsupported PostgreSQL targets")
            target_keys = [("extension", sql_name, version, platform, low, high)
                           for sql_name in sql_names]
        if url in base_urls:
            raise CandidateError("candidate asset URL must be new")
        if url in seen_urls:
            raise CandidateError("candidate asset URL is reused")
        if component == "postgresql":
            target_keys = [target_key]
        elif low == high and pg_target == low and url not in base_urls:
            _replace_selected_range_targets(
                candidate, sql_names, version, platform, low, expected_extensions, base_urls)
        for target_key in target_keys:
            if target_key in seen_targets:
                raise CandidateError(f"duplicate target {target_key}")
            seen_targets.add(target_key)
        seen_urls.add(url)

        records = item.get("verification")
        if not isinstance(records, list):
            raise CandidateError("missing verification evidence")
        evidence_components = [component] if component == "postgresql" else sql_names
        if component == "postgresql":
            endpoint = "current"
            if not any(_evidence_matches(r, download, component, version, platform, version,
                                         endpoint, support, root) for r in records):
                raise CandidateError(
                    f"missing passed {endpoint} verification for {component} {version} {platform}")
        else:
            pending_extension_evidence.append(
                (download, evidence_components, version, platform, records))

        candidate_evidence[url] = deepcopy(records)

        if component == "postgresql":
            version_entry = candidate["postgresql"].setdefault(version, {})
            version_entry["included_extensions"] = included_extensions
            downloads = version_entry.setdefault("downloads", {})
            downloads[platform] = download
        else:
            for sql_name in sql_names:
                extension_entry = candidate["extensions"].setdefault(sql_name, {}).setdefault(version, {})
                requires = extension.get("requires", [])
                if "requires" in extension_entry and extension_entry["requires"] != requires:
                    raise CandidateError(f"inconsistent extension requirements for {sql_name} {version}")
                extension_entry["requires"] = deepcopy(requires)
                downloads = extension_entry.setdefault("downloads", {})
                ranges = downloads.setdefault(platform, [])
                for existing in ranges:
                    a, b = existing["postgresql_support"]["from"], existing["postgresql_support"]["to"]
                    if (version_parts(low, "candidate range") <= version_parts(b, "candidate range")
                            and version_parts(a, "candidate range") <= version_parts(high, "candidate range")):
                        raise CandidateError(f"overlapping extension range for {sql_name} {version} {platform}")
                ranges.append(download)

    for download, evidence_components, version, platform, records in pending_extension_evidence:
        selected_pg = [pg for pg in releases
                       if version_parts(download["postgresql_support"]["from"], "candidate range")
                       <= version_parts(pg, "candidate range")
                       <= version_parts(download["postgresql_support"]["to"], "candidate range")]
        for pg in selected_pg:
            core = candidate.get("postgresql", {}).get(pg, {}).get("downloads", {}).get(platform)
            expected_name = f"postgresql-{pg}-{platform}.tar.gz"
            if (not isinstance(core, dict) or not isinstance(core.get("url"), str)
                    or core.get("url", "").rsplit("/", 1)[-1] != expected_name):
                raise CandidateError(f"candidate has no canonical PostgreSQL archive for {pg} {platform}")
            expected_core = {"archive": expected_name, "version": pg,
                             "sha256": str(core.get("sha256", "")).lower()}
            _candidate_core, candidate_extensions = _coverage.inventory_targets(candidate)
            project = next(project for project, details in support["extensions"].items()
                           if any(name in details["sql_names"] for name in evidence_components))
            expected_prerequisites = _coverage.expected_prerequisite_archives(
                support, candidate_extensions, project, pg, platform)
            if expected_prerequisites is None:
                raise CandidateError(f"candidate has no consistent prerequisite archives for {project} PostgreSQL {pg} {platform}")
            for evidence_component in evidence_components:
                endpoint = "current"
                if not any(_evidence_matches(
                        record, download, evidence_component, version, platform, pg,
                        endpoint, support, root, expected_core=expected_core,
                        expected_prerequisites=expected_prerequisites)
                        for record in records):
                    raise CandidateError(
                        f"missing passed {endpoint} verification for {evidence_component} {version} {pg} {platform} "
                        "bound to candidate PostgreSQL archive")
    return candidate


def _retire_unselected(candidate, expected_core, expected_extensions):
    """Keep base downloads that serve at least one currently selected target."""
    postgresql = candidate.get("postgresql", {})
    for version, record in list(postgresql.items()):
        downloads = record.get("downloads", {})
        for platform in list(downloads):
            if (version, platform) not in expected_core:
                del downloads[platform]
        if not downloads:
            del postgresql[version]

    extensions = candidate.get("extensions", {})
    for name, versions in list(extensions.items()):
        for version, record in list(versions.items()):
            downloads = record.get("downloads", {})
            for platform, ranges in list(downloads.items()):
                kept = []
                for download in ranges:
                    pg_range = download["postgresql_support"]
                    low = version_parts(pg_range["from"], "inventory range")
                    high = version_parts(pg_range["to"], "inventory range")
                    selected_pg = (target[2] for target in expected_extensions
                                   if target[0] == name and target[1] == version and target[3] == platform)
                    if any(low <= version_parts(pg, "selected PostgreSQL") <= high
                           for pg in selected_pg):
                        kept.append(download)
                if kept:
                    downloads[platform] = kept
                else:
                    del downloads[platform]
            if not downloads:
                del versions[version]
        if not versions:
            del extensions[name]


def _replace_selected_range_targets(candidate, sql_names, version, platform, pg,
                                    expected_extensions, base_urls):
    """Move a selected target from a retained range URL to a new exact archive.

    Historical bytes keep their URL. Their inventory claim is reduced to the
    other selected PostgreSQL releases they still serve.
    """
    pg_parts = version_parts(pg, "replacement PostgreSQL target")
    for name in sql_names:
        record = candidate.get("extensions", {}).get(name, {}).get(version, {})
        ranges = record.get("downloads", {}).get(platform, [])
        rebuilt = []
        for download in ranges:
            support = download["postgresql_support"]
            low, high = (version_parts(support[key], "retained extension range")
                         for key in ("from", "to"))
            if (download.get("url") not in base_urls or not low <= pg_parts <= high):
                rebuilt.append(download)
                continue
            remaining = sorted({target[2] for target in expected_extensions
                                if target[0] == name and target[1] == version
                                and target[3] == platform
                                and target[2] != pg
                                and low <= version_parts(target[2], "selected PostgreSQL") <= high},
                               key=lambda value: version_parts(value, "selected PostgreSQL"))
            for selected_pg in remaining:
                narrowed = deepcopy(download)
                narrowed["postgresql_support"] = {"from": selected_pg, "to": selected_pg}
                rebuilt.append(narrowed)
        if record and ranges:
            if rebuilt:
                record["downloads"][platform] = rebuilt
            else:
                del record["downloads"][platform]
                if not record["downloads"]:
                    del candidate["extensions"][name][version]
                if not candidate["extensions"][name]:
                    del candidate["extensions"][name]


def _evidence_matches(record, download, component, version, platform, pg, endpoint, support, root,
                      expected_core=None, expected_prerequisites=None):
    if not isinstance(record, dict):
        return False
    try:
        _coverage.validate_verification_record(record, support, root, "candidate evidence")
    except CoverageError:
        return False
    environment = record.get("environment")
    os_name, _, architecture = platform.partition("-")
    if not isinstance(environment, dict):
        return False
    assembled_core = record.get("assembled_core")
    core_matches = (expected_core is None or (
        isinstance(assembled_core, dict)
        and assembled_core.get("archive") == expected_core["archive"]
        and assembled_core.get("version") == expected_core["version"]
        and isinstance(assembled_core.get("sha256"), str)
        and assembled_core["sha256"].lower() == expected_core["sha256"]
    ))
    prerequisite_matches = (expected_prerequisites is None or
                            record.get("prerequisite_archives", []) == expected_prerequisites)
    try:
        actual = _coverage._os_version_parts(environment.get("os_version"), "candidate evidence")
        minimum = _coverage._os_version_parts(support["os_support"][os_name]["minimum_version"], "support")
    except (CoverageError, KeyError, TypeError):
        return False
    return (record.get("schema_version") == 2 and record.get("scope") == "publication"
            and record.get("outcome") == "passed"
            and str(record.get("sha256", "")).lower() == str(download["sha256"]).lower()
            and record.get("component") == component and str(record.get("version")) == str(version)
            and record.get("platform") == platform and record.get("postgresql_version") == pg
            and core_matches
            and prerequisite_matches
            and isinstance(record.get("test_revision"), str) and bool(record["test_revision"])
            and isinstance(record.get("test_cases"), list) and bool(record["test_cases"])
            and environment.get("endpoint") == endpoint
            and environment.get("os") == os_name and environment.get("architecture") == architecture
            and environment.get("clean_system") is True
            and endpoint == "current" and actual >= minimum)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-inventory", required=True, type=Path)
    parser.add_argument("--proposed-entries", required=True, type=Path)
    parser.add_argument("--support", required=True, type=Path)
    parser.add_argument("--release-snapshot", required=True, type=Path)
    parser.add_argument("--root", type=Path,
                        help="repository root containing verification profile sources")
    parser.add_argument("--output", type=Path,
                        help="write the candidate JSON here; stdout is used when omitted")
    args = parser.parse_args(argv)

    def read_json(path):
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)

    try:
        result = merge_candidate(read_json(args.base_inventory),
                                 read_json(args.proposed_entries),
                                 read_json(args.support),
                                 read_json(args.release_snapshot), root=args.root)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, json.JSONDecodeError, CandidateError) as exc:
        parser.exit(2, f"candidate inventory: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
