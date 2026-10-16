#!/usr/bin/env python3
"""Check a structural candidate and staged files before any release operation.

Passing this check is not a publication eligibility decision. It validates
candidate structure, support coverage, retained checksums, and local staged
archive bytes, including PostgreSQL built-in extension declarations. It does
checks declared redistribution reviews and their archive-local evidence; it does
not establish legal correctness, behavioral evidence, or public URL availability.
"""

import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from urllib.parse import urlsplit

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



def _archive_redistribution(path):
    """Check declared reviews and evidence without interpreting licence terms."""
    def relative(value):
        if (not isinstance(value, str) or not value or "\\" in value
                or PurePosixPath(value).is_absolute()
                or any(part in ("", ".", "..") for part in value.split("/"))):
            raise PreflightError(f"invalid licence inventory path: {value!r}")
        return value

    try:
        with tarfile.open(path, "r:gz") as archive:
            members = {}
            for member in archive.getmembers():
                name = member.name.rstrip("/")
                relative(name)
                if name in members:
                    raise PreflightError(f"duplicate archive member: {name}")
                members[name] = member
            inventories = [name for name in members
                           if len(name.split("/")) == 3
                           and name.endswith("/LICENSES/inventory.json")]
            if len(inventories) != 1:
                raise PreflightError("staged archive requires one root/LICENSES/inventory.json")
            inventory_path = inventories[0]
            root = inventory_path.split("/")[0]
            if any(name.split("/")[0] != root for name in members):
                raise PreflightError("licence inventory must describe the archive single root")

            def text_file(name):
                member = members.get(name)
                if member is None or not member.isfile() or member.size <= 0:
                    raise PreflightError(f"missing non-empty licence evidence file: {name}")
                if member.size > 8 * 1024 * 1024:
                    raise PreflightError(f"licence evidence file exceeds 8 MiB: {name}")
                return archive.extractfile(member).read().decode("utf-8")

            inventory = json.loads(text_file(inventory_path))
            if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
                raise PreflightError("licence inventory schema_version must be 1")
            components = inventory.get("components")
            if not isinstance(components, list) or not components:
                raise PreflightError("licence inventory requires components")
            for entry in components:
                if not isinstance(entry, dict) or not all(
                        isinstance(entry.get(key), str) and entry[key].strip()
                        for key in ("component", "version")):
                    raise PreflightError("licence component requires component and version")
                paths = entry.get("payload_paths")
                if not isinstance(paths, list) or not paths:
                    raise PreflightError("licence component requires payload_paths")
                for payload in paths:
                    prefix = root + "/" + relative(payload)
                    if not any(name == prefix or name.startswith(prefix + "/") for name in members):
                        raise PreflightError(f"missing mapped licence payload: {payload}")
                files = entry.get("additional_license_files", [])
                if not isinstance(files, list):
                    raise PreflightError("additional_license_files must be a list")

                def licence_file(value):
                    name = relative(value)
                    if not name.startswith("LICENSES/"):
                        name = "LICENSES/" + name
                    return text_file(root + "/" + name)

                for filename in [entry.get("license_file"), *files]:
                    licence_file(filename)
                review = entry.get("redistribution_review")
                if (not isinstance(review, dict) or review.get("status") != "resolved"
                        or not isinstance(review.get("basis"), str) or not review["basis"].strip()):
                    raise PreflightError("licence component requires resolved redistribution_review and basis")
                obligation = review.get("source_obligation")
                if obligation == "source-links":
                    links = review.get("source_links")
                    if not isinstance(links, list) or not links:
                        raise PreflightError("source-links review requires source_links")
                    for link in links:
                        if not isinstance(link, str):
                            raise PreflightError("source_links requires public HTTPS URLs")
                        parsed = urlsplit(link)
                        if (parsed.scheme != "https" or not parsed.hostname
                                or parsed.username or parsed.password or any(c.isspace() for c in link)):
                            raise PreflightError("source_links requires public HTTPS URLs")
                elif obligation == "source-offer":
                    licence_file(review.get("source_offer_file"))
                elif obligation != "none":
                    raise PreflightError("review requires source_obligation none, source-links or source-offer")
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, PreflightError):
            raise
        raise PreflightError(f"cannot read staged archive licence evidence: {exc}") from exc


def preflight_candidate(base_inventory, candidate, support, snapshot, staged_assets):
    """Validate candidate references and staged bytes without contacting GitHub.

    ``staged_assets`` maps each new immutable download URL to an object with
    ``path`` and ``sha256`` fields. Each new archive must carry the licence
    inventory and review declarations defined in policies/releases.md. The result describes only this local
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

        _archive_redistribution(path)

    return {
        "preflight_status": "passed",
        "new_asset_count": len(new_urls),
        "redistribution_review_status": "declarations-checked",
        "postgresql_target_count": len(expected_core),
        "extension_target_count": len(expected_extensions),
    }
