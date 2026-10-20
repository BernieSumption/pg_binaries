"""Validate selected pgAudit macOS targets and resolved PostgreSQL archives."""

import argparse
import json
from pathlib import Path
import re
import sys

SOURCES = {
    "15.19": ("1.7.1", "https://api.github.com/repos/pgaudit/pgaudit/tarball/72da89c3fa02f3f2b9f3933214d91ad9c3428467", "1e52448238908a09e0e78b3375dcefbfca51509fdbb3a4d92eb710e380ed3567"),
    "16.15": ("16.1", "https://api.github.com/repos/pgaudit/pgaudit/tarball/a81792e8a4ea8f7aaf75bd610fcc4c2f96650bdc", "b0648fcebe5a67340c406126e6dddc703fd03821a9ace80390e128a0d1c91c73"),
    "17.11": ("17.1", "https://api.github.com/repos/pgaudit/pgaudit/tarball/538f89a93d8fd0d8913f3d740cacaea7b7eb66d9", "20e980bd0c22b4ae33305ec2b774bd846bf343642adad108b6c28b422a648312"),
    "18.6": ("18.0", "https://github.com/pgaudit/pgaudit/archive/refs/tags/18.0.tar.gz", "988e8afeda320ebe0a3e632ef6b6bce5d3a08346c2e100a173a585c9521d1fa5"),
}


def _selected(version, architecture):
    if version not in SOURCES:
        raise ValueError(f"unsupported pgAudit macOS target: {version}")
    if architecture not in {"arm64", "x86_64"}:
        raise ValueError(f"unsupported pgAudit macOS architecture: {architecture}")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tools"))
    try:
        import extension_archive_plan
        support = json.loads((root / "support.json").read_text(encoding="utf-8"))
        releases = json.loads((root / "support/postgresql-releases.json").read_text(encoding="utf-8"))
        plan = extension_archive_plan.plan(support, releases)
        extension_archive_plan.select_target(plan, "pgaudit", f"macos-{architecture}", version,
                                             SOURCES[version][0])
    except (OSError, ValueError, TypeError, KeyError, extension_archive_plan._coverage.CoverageError) as exc:
        raise ValueError(f"PostgreSQL target is not selected for pgAudit macOS: {exc}") from exc
    finally:
        sys.path.remove(str(root / "tools"))
    pgaudit_version, source_url, source_sha256 = SOURCES[version]
    platform = f"macos-{architecture}"
    return {
        "schema_version": 1,
        "profile_id": f"pgaudit-publication-macos-{architecture}-{version}",
        "postgresql_version": version,
        "pgaudit_version": pgaudit_version,
        "architecture": architecture,
        "platform": platform,
        "core_archive": {"basename": f"postgresql-{version}-{platform}.tar.gz"},
        "source": {"url": source_url, "sha256": source_sha256},
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate target key: {key}")
        result[key] = value
    return result


def target(version, architecture="arm64", target_config=None, require_resolved=False):
    expected = _selected(version, architecture)
    if target_config is None:
        if require_resolved:
            raise ValueError("a resolved pgAudit macOS target config is required")
        core = expected["core_archive"]
    else:
        try:
            value = json.loads(Path(target_config).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"cannot read pgAudit macOS target: {exc}") from exc
        if not isinstance(value, dict) or set(value) != set(expected) or any(
                value.get(key) != item for key, item in expected.items() if key != "core_archive"):
            raise ValueError("pgAudit target does not match the selected PostgreSQL release and architecture")
        core = value.get("core_archive")
        if not isinstance(core, dict) or core.get("basename") != expected["core_archive"]["basename"]:
            raise ValueError("pgAudit target core archive does not match selected PostgreSQL target")
        if set(core) not in ({"basename"}, {"basename", "run_id", "sha256", "build_id", "source_revision"}):
            raise ValueError("pgAudit target core archive has an unexpected field set")
    resolved = set(core) != {"basename"}
    if require_resolved and not resolved:
        raise ValueError("pgAudit target core archive has not been resolved")
    if resolved:
        run_id, digest = core.get("run_id"), core.get("sha256")
        build_id, revision = core.get("build_id"), core.get("source_revision")
        build = re.fullmatch(r"github-([0-9]+)-[1-9][0-9]*", build_id or "")
        if (not isinstance(run_id, str) or not re.fullmatch(r"[0-9]+", run_id)
                or build is None or build.group(1) != run_id
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision)):
            raise ValueError("pgAudit resolved core identity is invalid")
    else:
        run_id = digest = build_id = revision = ""
    return {
        **{key: value for key, value in expected.items() if key != "core_archive"},
        "core_basename": core["basename"], "core_sha256": digest, "core_run_id": run_id,
        "core_build_id": build_id, "core_source_revision": revision, "resolved": resolved,
        "source_url": expected["source"]["url"], "source_sha256": expected["source"]["sha256"],
        "extension_basename": f"pgaudit-{expected['pgaudit_version']}-postgresql-{version}-{expected['platform']}.tar.gz",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", choices=tuple(SOURCES))
    parser.add_argument("--architecture", choices=("arm64", "x86_64"), default="arm64")
    parser.add_argument("--target-config", type=Path)
    parser.add_argument("--require-resolved", action="store_true")
    parser.add_argument("--write-base", type=Path)
    parser.add_argument("--field", choices=("pgaudit_version", "core_basename", "core_sha256", "core_build_id", "core_source_revision", "source_url", "source_sha256"))
    parser.add_argument("--shell", action="store_true")
    args = parser.parse_args()
    try:
        base = _selected(args.version, args.architecture)
        if args.write_base:
            args.write_base.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
        selected = target(args.version, args.architecture, args.target_config, args.require_resolved)
        if args.shell:
            print("\t".join(str(selected[field]) for field in ("pgaudit_version", "core_sha256", "core_build_id", "core_source_revision", "source_url", "source_sha256")))
        elif args.field:
            print(selected[args.field])
        else:
            print(json.dumps(selected, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"pgAudit macOS target: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
