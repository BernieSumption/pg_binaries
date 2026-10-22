#!/usr/bin/env python3
"""Prepare candidate proposal and local asset manifests from staged archives.

This helper only joins files already on disk with current publication records.
It does not download, build, publish, or decide release eligibility.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

_COVERAGE_SPEC = importlib.util.spec_from_file_location(
    "stage_coverage", Path(__file__).with_name("coverage.py"))
_coverage = importlib.util.module_from_spec(_COVERAGE_SPEC)
_COVERAGE_SPEC.loader.exec_module(_coverage)
_PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "stage_preflight", Path(__file__).with_name("publication_preflight.py"))
_preflight = importlib.util.module_from_spec(_PREFLIGHT_SPEC)
_PREFLIGHT_SPEC.loader.exec_module(_preflight)

TAG = re.compile(r"^catalog-\d{8}-\d+$")


class StagingError(ValueError):
    """Staged files and current verification records cannot form manifests."""


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_files(paths):
    files = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.json")))
        elif path.is_file() and path.suffix == ".json":
            files.append(path)
    return sorted(set(files))


def _archive_identity(path, support, platforms):
    filename = path.name
    for platform in platforms:
        core = re.fullmatch(rf"postgresql-(\d+\.\d+)-{re.escape(platform)}\.tar\.gz", filename)
        if core:
            return "postgresql", core[1], platform, None
    for project, details in support.get("extensions", {}).items():
        archive_project = _coverage.archive_project_name(project)
        for version in details.get("versions", {}):
            for platform in platforms:
                pattern = (rf"{re.escape(archive_project)}-{re.escape(version)}-postgresql-"
                           rf"(\d+\.\d+(?:-to-\d+\.\d+)?)-{re.escape(platform)}\.tar\.gz")
                match = re.fullmatch(pattern, filename)
                if match:
                    return project, version, platform, match[1]
    return None


def prepare_manifests(archives, verification_files, support, snapshot, tag, root=None):
    """Return ``(proposals, staged_assets, missing)`` for exact staged bytes."""
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    if not isinstance(tag, str) or not TAG.fullmatch(tag):
        raise StagingError("tag must be an immutable catalog-YYYYMMDD-N release tag")
    try:
        _coverage.validate_support(support)
        releases = _coverage.release_snapshot(snapshot, support)
        expected_core, expected_extensions = _coverage.expected_targets(support, releases)
    except (KeyError, TypeError, _coverage.CoverageError) as exc:
        raise StagingError(f"invalid support or release snapshot: {exc}") from exc
    platforms = [f"{os_name}-{arch}" for os_name, arches in support["platform_architectures"].items()
                 for arch in arches]

    records = []
    for path in _record_files(verification_files):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            _coverage.validate_verification_record(record, support, root, f"verification record {path}")
        except (OSError, UnicodeError, json.JSONDecodeError, _coverage.CoverageError):
            continue
        env = record.get("environment", {})
        if (record.get("scope") == "publication" and record.get("outcome") == "passed"
                and env.get("endpoint") == "current"):
            records.append(record)

    assets = []
    for value in archives:
        path = Path(value)
        if not path.is_file() or path.suffixes[-2:] != [".tar", ".gz"]:
            continue
        identity = _archive_identity(path, support, platforms)
        if identity is None:
            continue
        project, version, platform, build_claim = identity
        checksum = _digest(path)
        filename = path.name
        url = (f"https://github.com/BernieSumption/pg_binaries/releases/download/"
               f"{tag}/{filename}")
        existing = next((asset for asset in assets if asset["url"] == url), None)
        if existing:
            if existing["sha256"] != checksum:
                raise StagingError(f"staged copies of {filename} have different bytes")
            continue
        assets.append({"path": path.resolve(), "url": url, "sha256": checksum,
                       "identity": (project, version, platform), "build_claim": build_claim})

    sql_names_by_project = {project: details["sql_names"]
                            for project, details in support.get("extensions", {}).items()}
    core_target_to_asset = {}
    ext_target_to_asset = {}
    target_records = {}
    missing = []

    for asset in assets:
        project, version, platform = asset["identity"]
        target = (version, platform)
        if project != "postgresql" or target not in expected_core:
            continue
        if target in core_target_to_asset:
            raise StagingError(f"multiple staged PostgreSQL archives match {version} {platform}")
        core_target_to_asset[target] = asset

    for asset in assets:
        project, version, platform = asset["identity"]
        if project == "postgresql":
            target = (version, platform)
            if target not in expected_core:
                continue
            if core_target_to_asset[target] is not asset:
                raise StagingError(f"multiple staged PostgreSQL archives match {version} {platform}")
            matching = [r for r in records if r.get("sha256", "").lower() == asset["sha256"]
                        and r.get("component") == "postgresql" and str(r.get("version")) == version
                        and r.get("platform") == platform and r.get("postgresql_version") == version]
            if matching:
                target_records[asset["url"]] = matching
            else:
                missing.append(f"verification: postgresql {version} {platform} (sha256 {asset['sha256']})")
        else:
            sql_names = sql_names_by_project[project]
            build_claim = asset["build_claim"]
            build_low, build_high = (build_claim.split("-to-") if "-to-" in build_claim
                                     else (build_claim, build_claim))
            for sql_name, ext_version, pg_version, ext_platform in expected_extensions:
                if (ext_version != version or ext_platform != platform or sql_name not in sql_names):
                    continue
                if not (_coverage.version_parts(build_low, "archive build range")
                        <= _coverage.version_parts(pg_version, "selected PostgreSQL version")
                        <= _coverage.version_parts(build_high, "archive build range")):
                    continue
                selected_core = core_target_to_asset.get((pg_version, platform))
                if selected_core is None:
                    continue
                matching = [r for r in records if r.get("sha256", "").lower() == asset["sha256"]
                            and r.get("component") in sql_names and str(r.get("version")) == version
                            and r.get("platform") == platform and r.get("postgresql_version") == pg_version
                            and r.get("assembled_core", {}).get("sha256", "").lower() == selected_core["sha256"]]
                if all(any(r.get("component") == name for r in matching) for name in sql_names):
                    key = (sql_name, version, pg_version, platform)
                    prior = ext_target_to_asset.get(key)
                    if prior is not None and prior is not asset:
                        raise StagingError(f"multiple staged extension archives match {sql_name} {version} PostgreSQL {pg_version} {platform}")
                    ext_target_to_asset[key] = asset
                    target_records.setdefault(asset["url"], {})[pg_version] = matching

    proposals = []
    for version, platform in sorted(expected_core):
        if (version, platform) not in core_target_to_asset:
            missing.append(f"target: PostgreSQL {version} {platform} (no staged archive)")
    for target, asset in core_target_to_asset.items():
        if asset["url"] not in target_records:
            continue
        try:
            included = _preflight._archive_builtins(asset["path"], target[0], target[1])
        except _preflight.PreflightError as exc:
            raise StagingError(f"invalid staged PostgreSQL archive {asset['path']}: {exc}") from exc
        proposals.append({"component": "postgresql", "version": target[0], "platform": target[1],
                          "tag": tag, "filename": asset["path"].name, "sha256": asset["sha256"],
                          "included_extensions": included, "verification": target_records[asset["url"]]})

    extension_groups = {}
    for target in sorted(expected_extensions):
        asset = ext_target_to_asset.get(target)
        sql_name, version, pg_version, platform = target
        if asset is None:
            matching_file = next((candidate for candidate in assets
                                  if candidate["identity"] == (next((project for project, names in sql_names_by_project.items()
                                                                       if sql_name in names), ""), version, platform)
                                  and _coverage.version_parts(candidate["build_claim"].split("-to-")[0], "archive build range")
                                  <= _coverage.version_parts(pg_version, "selected PostgreSQL version")
                                  <= _coverage.version_parts(candidate["build_claim"].split("-to-")[-1], "archive build range")), None)
            suffix = f" (archive {matching_file['path'].name} lacks matching current-profile SHA evidence)" if matching_file else " (no staged archive)"
            missing.append(f"target: extension {sql_name} {version} PostgreSQL {pg_version} {platform}{suffix}")
            continue
        extension_groups.setdefault(asset["url"], {"asset": asset, "targets": set(), "records": []})["targets"].add(pg_version)
        for record in target_records[asset["url"]][pg_version]:
            if record not in extension_groups[asset["url"]]["records"]:
                extension_groups[asset["url"]]["records"].append(record)

    selected_versions = sorted(releases, key=lambda v: _coverage.version_parts(v, "release snapshot"))
    for group in extension_groups.values():
        asset = group["asset"]
        project, version, platform = asset["identity"]
        covered = sorted(group["targets"], key=lambda v: _coverage.version_parts(v, "selected target"))
        first, last = covered[0], covered[-1]
        between = {pg for pg in selected_versions
                   if _coverage.version_parts(first, "selected target") <= _coverage.version_parts(pg, "release")
                   <= _coverage.version_parts(last, "selected target")
                   and any(t[1] == version and t[2] == pg and t[3] == platform and t[0] in sql_names_by_project[project]
                           for t in expected_extensions)}
        if between != set(covered):
            absent = sorted(between - set(covered), key=lambda v: _coverage.version_parts(v, "selected target"))
            missing.append(f"archive {asset['path'].name} cannot claim one continuous range; missing current-profile evidence for PostgreSQL {', '.join(absent)} {platform}")
            continue
        build_claim = asset["build_claim"]
        if "-to-" in build_claim:
            build_low, build_high = build_claim.split("-to-", 1)
            if (build_low, build_high) != (first, last):
                missing.append(f"archive {asset['path'].name} range must exactly match its verified selected PostgreSQL range {first}-to-{last}")
                continue
        elif not (_coverage.version_parts(first, "support range") <= _coverage.version_parts(build_claim, "archive build version")
                  <= _coverage.version_parts(last, "support range")):
            missing.append(f"archive {asset['path'].name} build version falls outside its verified selected PostgreSQL range {first}-to-{last}")
            continue
        proposals.append({"component": project, "version": version, "platform": platform,
                          "tag": tag, "filename": asset["path"].name, "sha256": asset["sha256"],
                          "postgresql_support": {"from": first, "to": last},
                          "verification": group["records"]})

    proposal_urls = {f"https://github.com/BernieSumption/pg_binaries/releases/download/{tag}/{p['filename']}"
                     for p in proposals}
    staged = {asset["url"]: {"path": str(asset["path"]), "sha256": asset["sha256"]}
              for asset in assets if asset["url"] in proposal_urls}
    return sorted(proposals, key=lambda p: (p["component"], p["version"], p["platform"], p["filename"])), staged, missing


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", required=True, type=Path,
                        help="directory containing final .tar.gz files (searched recursively)")
    parser.add_argument("--verification-dir", action="append", required=True, type=Path,
                        help="directory or JSON record file; may be repeated")
    parser.add_argument("--support", type=Path, default=Path("support.json"))
    parser.add_argument("--release-snapshot", type=Path, default=Path("support/postgresql-releases.json"))
    parser.add_argument("--tag", required=True, help="new immutable catalog-YYYYMMDD-N tag")
    parser.add_argument("--root", type=Path, help="repository root containing current verification profiles")
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        archives = sorted(args.archive_dir.rglob("*.tar.gz"))
        support = json.loads(args.support.read_text(encoding="utf-8"))
        snapshot = json.loads(args.release_snapshot.read_text(encoding="utf-8"))
        proposals, staged, missing = prepare_manifests(
            archives, args.verification_dir, support, snapshot, args.tag, root=args.root)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "proposed-entries.json").write_text(
            json.dumps(proposals, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (args.output_dir / "staged-assets.json").write_text(
            json.dumps(staged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, StagingError) as exc:
        parser.exit(2, f"stage first release: {exc}\n")
    if missing:
        for item in sorted(set(missing)):
            print(f"missing: {item}", file=sys.stderr)
        print(f"wrote {len(proposals)} proposals and {len(staged)} staged assets with missing targets", file=sys.stderr)
        return 1
    print(f"wrote {len(proposals)} proposals and {len(staged)} staged assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
