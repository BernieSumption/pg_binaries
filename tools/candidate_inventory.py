#!/usr/bin/env python3
"""Build a structural draft of a future inventory from proposed assets.

This helper does not establish publication eligibility or validate all inventory
metadata, including OS support and archive contents.
"""

from copy import deepcopy
import importlib.util
from pathlib import Path
import re

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

    Each proposal has ``component`` (``postgresql`` or an inventory SQL name),
    ``version``, ``platform``, ``tag``, ``filename``, ``sha256``, and
    ``verification``. Extension proposals also have ``postgresql_support``.
    Verification is a list of coverage-style records, with passed evidence for
    minimum and current OS endpoints crossed with the PostgreSQL range endpoints.
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
    candidate.setdefault("schema_version", 1)
    candidate.setdefault("postgresql", {})
    candidate.setdefault("extensions", {})
    candidate["candidate_status"] = "structural-draft"
    seen_targets, seen_urls = set(), set()
    base_urls = {entry["url"] for entry in list(base_core.values()) + list(base_extensions.values())}

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
        if platform not in filename:
            raise CandidateError("filename must identify its operating system and architecture")
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
            sql_name = component
            policy = next((policy for ext in ext_versions.values()
                          for name in ext.get("sql_names", []) if name == sql_name
                          for policy in [ext.get("versions", {}).get(version)] if policy), None)
            if policy is None:
                raise CandidateError(f"unsupported extension target {component} {version}")
            pg_range = item.get("postgresql_support")
            try:
                low, high = pg_range["from"], pg_range["to"]
                if version_parts(low, "candidate range") > version_parts(high, "candidate range"):
                    raise CandidateError("PostgreSQL support range is reversed")
            except (TypeError, KeyError, CoverageError) as exc:
                raise CandidateError("malformed PostgreSQL support range") from exc
            target_key = ("extension", component, version, platform, low, high)
            minimum_major = policy.get("postgresql_minimum_major", support["postgresql"]["minimum_major"])
            maximum_major = policy.get("postgresql_maximum_major")
            if (version_parts(low, "candidate range")[0] < minimum_major
                    or (maximum_major is not None and version_parts(high, "candidate range")[0] > maximum_major)):
                raise CandidateError("extension range exceeds declared PostgreSQL compatibility")
            download["postgresql_support"] = {"from": low, "to": high}
            relevant = [pg for pg in releases
                        if version_parts(low, "candidate range") <= version_parts(pg, "candidate range")
                        <= version_parts(high, "candidate range")]
            if not relevant or any((component, version, pg, platform) not in expected_extensions for pg in relevant):
                raise CandidateError("extension range includes unsupported PostgreSQL targets")
        if url in base_urls:
            raise CandidateError("candidate asset URL must be new")
        if url in seen_urls:
            raise CandidateError("candidate asset URL is reused")
        if target_key in seen_targets:
            raise CandidateError(f"duplicate target {target_key}")
        seen_targets.add(target_key)
        seen_urls.add(url)

        required_pg = [version] if component == "postgresql" else [low, high]
        records = item.get("verification")
        if not isinstance(records, list):
            raise CandidateError("missing verification evidence")
        for pg in required_pg:
            for endpoint in ("minimum", "current"):
                if not any(_evidence_matches(r, download, component, version, platform, pg, endpoint, support, root)
                           for r in records):
                    raise CandidateError(f"missing passed {endpoint} verification for {component} {version} {pg} {platform}")

        if component == "postgresql":
            version_entry = candidate["postgresql"].setdefault(version, {})
            version_entry["included_extensions"] = included_extensions
            downloads = version_entry.setdefault("downloads", {})
            downloads[platform] = download
        else:
            downloads = (candidate["extensions"].setdefault(component, {})
                         .setdefault(version, {}).setdefault("downloads", {}))
            ranges = downloads.setdefault(platform, [])
            for existing in ranges:
                a, b = existing["postgresql_support"]["from"], existing["postgresql_support"]["to"]
                if version_parts(low, "candidate range") <= version_parts(b, "candidate range") and version_parts(a, "candidate range") <= version_parts(high, "candidate range"):
                    raise CandidateError(f"overlapping extension range for {component} {version} {platform}")
            ranges.append(download)
    return candidate


def _evidence_matches(record, download, component, version, platform, pg, endpoint, support, root):
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
            and isinstance(record.get("test_revision"), str) and bool(record["test_revision"])
            and isinstance(record.get("test_cases"), list) and bool(record["test_cases"])
            and environment.get("endpoint") == endpoint
            and environment.get("os") == os_name and environment.get("architecture") == architecture
            and environment.get("clean_system") is True
            and ((endpoint == "minimum" and actual == minimum)
                 or (endpoint == "current" and actual > minimum)))
