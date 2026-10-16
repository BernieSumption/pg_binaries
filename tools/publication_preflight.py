#!/usr/bin/env python3
"""Check a structural candidate and staged files before any release operation.

Passing this check is not a publication eligibility decision. It validates
candidate structure, support coverage, retained checksums, and local staged
archive bytes, including PostgreSQL built-in extension declarations. It does
not validate package metadata, licensing, behavioral evidence, or public URL
availability.
"""

import hashlib
import importlib.util
from pathlib import Path
import re
import tarfile

_COVERAGE_SPEC = importlib.util.spec_from_file_location(
    "preflight_coverage", Path(__file__).with_name("coverage.py"))
_coverage = importlib.util.module_from_spec(_COVERAGE_SPEC)
_COVERAGE_SPEC.loader.exec_module(_coverage)
_BUILTINS_SPEC = importlib.util.spec_from_file_location(
    "preflight_builtins", Path(__file__).with_name("discover_builtins.py"))
_builtins = importlib.util.module_from_spec(_BUILTINS_SPEC)
_BUILTINS_SPEC.loader.exec_module(_builtins)
NEW_ASSET_URL = re.compile(
    r"^https://github\.com/BernieSumption/pg_binaries/releases/download/"
    r"catalog-\d{8}-\d+/[A-Za-z0-9._+-]+\.tar\.gz$")


class PreflightError(ValueError):
    """The candidate or its staged assets fail local preflight checks."""


def _asset_references(inventory):
    """Return URL to checksum references, preserving extension range entries."""
    references = {}
    try:
        core, extensions = _coverage.inventory_targets(inventory)
    except _coverage.CoverageError as exc:
        raise PreflightError(f"invalid inventory structure: {exc}") from exc
    for key, entry in [*core.items(), *extensions.items()]:
        url, checksum = entry["url"], entry["sha256"].lower()
        previous = references.get(url)
        if previous is not None and previous != checksum:
            raise PreflightError(f"inventory URL has conflicting checksums: {url}")
        references[url] = checksum
    return references


def _candidate_targets(inventory):
    try:
        core, extensions = _coverage.inventory_targets(inventory)
    except _coverage.CoverageError as exc:
        raise PreflightError(f"invalid candidate inventory: {exc}") from exc
    return core, extensions


def _covers_extension(target, extension_ranges):
    name, version, pg, platform = target
    pg_version = _coverage.version_parts(pg, "required target")
    for (candidate_name, candidate_version, low, high, candidate_platform) in extension_ranges:
        if (candidate_name == name and candidate_version == version
                and candidate_platform == platform
                and _coverage.version_parts(low, "candidate range") <= pg_version
                <= _coverage.version_parts(high, "candidate range")):
            return True
    return False


def _archive_builtins(path):
    """Read built-in SQL names from PostgreSQL control-file members."""
    try:
        with tarfile.open(path, "r:gz") as archive:
            names = []
            for member in archive.getmembers():
                parts = Path(member.name).parts
                if parts and parts[-1].endswith(".control"):
                    if (len(parts) != 4 or parts[0] != "postgresql"
                            or parts[1:3] != ("share", "extension")):
                        raise PreflightError(
                            f"PostgreSQL extension control is outside postgresql/share/extension: {member.name}")
                    name = parts[-1][:-len(".control")]
                    if not member.isfile() or not _builtins.EXTENSION_NAME.fullmatch(name):
                        raise PreflightError(f"malformed PostgreSQL extension control in staged archive: {member.name}")
                    names.append(name)
            if not names or len(names) != len(set(names)):
                raise PreflightError(f"missing or duplicate PostgreSQL extension controls in staged archive: {path}")
            return sorted(names)
    except (OSError, tarfile.TarError) as exc:
        raise PreflightError(f"cannot read PostgreSQL archive controls from {path}: {exc}") from exc


def preflight_candidate(base_inventory, candidate, support, snapshot, staged_assets):
    """Validate candidate references and staged bytes without contacting GitHub.

    ``staged_assets`` maps each new immutable download URL to an object with
    ``path`` and ``sha256`` fields. The result describes only this local
    preflight; it never represents publication eligibility.
    """
    if not isinstance(candidate, dict) or candidate.get("candidate_status") != "structural-draft":
        raise PreflightError("candidate must have candidate_status 'structural-draft'")
    if candidate.get("schema_version") != 1:
        raise PreflightError("candidate schema_version must be 1")
    if not isinstance(staged_assets, dict):
        raise PreflightError("staged-assets manifest must be an object keyed by URL")
    try:
        _coverage.validate_support(support)
        releases = _coverage.release_snapshot(snapshot, support)
        expected_core, expected_extensions = _coverage.expected_targets(support, releases)
    except (KeyError, TypeError, _coverage.CoverageError) as exc:
        raise PreflightError(f"invalid support or release snapshot: {exc}") from exc
    if candidate.get("os_support") != support["os_support"]:
        raise PreflightError("candidate os_support does not match declared OS minima")

    base_refs = _asset_references(base_inventory)
    candidate_refs = _asset_references(candidate)
    dropped_refs = sorted(set(base_refs) - set(candidate_refs))
    if dropped_refs:
        raise PreflightError(f"candidate dropped retained URL: {dropped_refs[0]}")
    candidate_core, candidate_extensions = _candidate_targets(candidate)
    core_by_url = {}
    for target, entry in candidate_core.items():
        url = entry["url"]
        if url in core_by_url:
            raise PreflightError(f"PostgreSQL archive URL is reused across targets: {url}")
        core_by_url[url] = target[0]
    missing_core = sorted(expected_core - set(candidate_core))
    if missing_core:
        version, platform = missing_core[0]
        raise PreflightError(f"candidate is missing PostgreSQL target {version} {platform}")

    missing_extensions = sorted(target for target in expected_extensions
                                if not _covers_extension(target, candidate_extensions))
    if missing_extensions:
        name, version, pg, platform = missing_extensions[0]
        raise PreflightError(
            f"candidate is missing extension target {name} {version} PostgreSQL {pg} {platform}")

    new_urls = set(candidate_refs) - set(base_refs)
    manifest_urls = set(staged_assets)
    missing_assets = sorted(new_urls - manifest_urls)
    if missing_assets:
        raise PreflightError(f"candidate URL has no staged asset: {missing_assets[0]}")
    extra_assets = sorted(manifest_urls - new_urls)
    if extra_assets:
        raise PreflightError(f"staged asset is not referenced by candidate: {extra_assets[0]}")

    for url, checksum in candidate_refs.items():
        if url in base_refs and checksum != base_refs[url]:
            raise PreflightError(f"retained URL checksum changed: {url}")

    for url in sorted(new_urls):
        if not NEW_ASSET_URL.fullmatch(url):
            raise PreflightError(f"new asset URL is not an immutable catalog release URL: {url}")
        asset = staged_assets[url]
        if not isinstance(asset, dict) or not isinstance(asset.get("path"), (str, Path)):
            raise PreflightError(f"staged asset requires a local path: {url}")
        expected = asset.get("sha256")
        candidate_checksum = candidate_refs[url]
        if not isinstance(expected, str) or expected.lower() != candidate_checksum:
            raise PreflightError(f"staged manifest checksum does not match candidate: {url}")
        path = Path(asset["path"])
        try:
            hasher = hashlib.sha256()
            with path.open("rb") as archive:
                for chunk in iter(lambda: archive.read(1024 * 1024), b""):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
        except OSError as exc:
            raise PreflightError(f"cannot read staged asset for {url}: {exc}") from exc
        if digest != candidate_checksum:
            raise PreflightError(f"staged asset bytes do not match candidate checksum: {url}")
        if url in core_by_url:
            version = core_by_url[url]
            declared = candidate["postgresql"][version].get("included_extensions")
            if not isinstance(declared, list):
                raise PreflightError(f"PostgreSQL {version} requires included_extensions")
            actual = _archive_builtins(path)
            if declared != actual:
                raise PreflightError(
                    f"PostgreSQL {version} included_extensions do not match staged archive controls")

    return {
        "preflight_status": "passed",
        "new_asset_count": len(new_urls),
        "postgresql_target_count": len(expected_core),
        "extension_target_count": len(expected_extensions),
    }
