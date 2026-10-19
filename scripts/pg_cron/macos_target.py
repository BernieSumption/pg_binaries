"""Validate the selected and resolved targets used by pg_cron macOS recipes."""

import argparse
import json
from pathlib import Path
import re
import sys

SOURCE_URL = "https://github.com/citusdata/pg_cron/archive/refs/tags/v1.6.8.tar.gz"
SOURCE_SHA256 = "c19ab9bb35406c60fb51ecda993737c083850abe424acb6c1030439d00a1f8e4"
TARGET_KEYS = {
    "schema_version", "profile_id", "postgresql_version", "pg_cron_version",
    "architecture", "platform", "core_archive", "source",
}
CORE_BASE_KEYS = {"basename"}
CORE_RESOLVED_KEYS = CORE_BASE_KEYS | {"run_id", "sha256", "build_id", "source_revision"}


def _selected_postgresql_target(version, architecture):
    root = Path(__file__).resolve().parents[2]
    tools = root / "tools"
    sys.path.insert(0, str(tools))
    try:
        import extension_archive_plan
    finally:
        sys.path.remove(str(tools))
    try:
        support = json.loads((root / "support.json").read_text(encoding="utf-8"))
        releases = json.loads(
            (root / "support" / "postgresql-releases.json").read_text(encoding="utf-8"))
        selection = extension_archive_plan.plan(support, releases)
        return extension_archive_plan.select_target(
            selection, "pg_cron", f"macos-{architecture}", version, "1.6.8")
    except (OSError, ValueError, TypeError, extension_archive_plan._coverage.CoverageError) as exc:
        raise ValueError(f"PostgreSQL target is not selected for pg_cron macOS: {exc}") from exc


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate target key: {key}")
        value[key] = item
    return value


def load_target(path, require_resolved=False):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read pg_cron target {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) != TARGET_KEYS:
        raise ValueError("pg_cron target has an unexpected field set")
    version = value.get("postgresql_version")
    cron_version = value.get("pg_cron_version")
    architecture = value.get("architecture")
    platform = value.get("platform")
    if (value.get("schema_version") != 1 or cron_version != "1.6.8"
            or architecture not in {"arm64", "x86_64"} or platform != f"macos-{architecture}"):
        raise ValueError("unsupported pg_cron macOS target")
    _selected_postgresql_target(version, architecture)
    profile_id = f"pgcron-publication-macos-{architecture}-{version}"
    if value.get("profile_id") != profile_id:
        raise ValueError("pg_cron target profile does not match selected architecture")
    source = value.get("source")
    if (not isinstance(source, dict) or set(source) != {"url", "sha256"}
            or source.get("url") != SOURCE_URL or source.get("sha256") != SOURCE_SHA256):
        raise ValueError("target source identity does not match pg_cron 1.6.8")
    core = value.get("core_archive")
    expected_name = f"postgresql-{version}-{platform}.tar.gz"
    if not isinstance(core, dict) or core.get("basename") != expected_name:
        raise ValueError("target core archive name does not match PostgreSQL target")
    if set(core) not in (CORE_BASE_KEYS, CORE_RESOLVED_KEYS):
        raise ValueError("target core archive has an unexpected field set")
    resolved = set(core) == CORE_RESOLVED_KEYS
    if require_resolved and not resolved:
        raise ValueError("target core archive has not been resolved")
    if resolved:
        digest, run_id = core.get("sha256"), core.get("run_id")
        build_id, revision = core.get("build_id"), core.get("source_revision")
        build_match = re.fullmatch(r"github-([0-9]+)-[1-9][0-9]*", build_id or "")
        if (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or not isinstance(run_id, str) or not re.fullmatch(r"[0-9]+", run_id)
                or build_match is None or build_match.group(1) != run_id
                or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision)):
            raise ValueError("target core archive identity is invalid")
    else:
        digest = build_id = revision = ""
    return {
        "profile_id": profile_id, "postgresql_version": version,
        "pg_cron_version": cron_version, "architecture": architecture, "platform": platform,
        "core_basename": expected_name, "core_sha256": digest, "core_build_id": build_id,
        "core_source_revision": revision, "source_url": SOURCE_URL,
        "source_sha256": SOURCE_SHA256,
        "extension_basename": f"pg_cron-{cron_version}-postgresql-{version}-{platform}.tar.gz",
        "resolved": resolved,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--require-resolved", action="store_true")
    args = parser.parse_args()
    try:
        target = load_target(args.target, require_resolved=args.require_resolved)
        print("\t".join(target[key] for key in (
            "postgresql_version", "architecture", "platform", "core_basename", "core_sha256",
            "core_build_id", "core_source_revision", "source_url", "source_sha256", "extension_basename")))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"pg_cron macOS target: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
