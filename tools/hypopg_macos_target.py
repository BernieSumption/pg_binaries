"""Create and load target identities for a HypoPG macOS publication run."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Optional

import coverage


HYPOPG_VERSION = "1.4.3"
SOURCE_URL = "https://github.com/HypoPG/hypopg/archive/refs/tags/1.4.3.tar.gz"
SOURCE_SHA256 = "498a961d88cf37057fd9e98027d06fe805c8959d51895c3d9b94c9eb4e14f706"
EXPECTED_KEYS = {"schema_version", "profile_id", "postgresql_version", "architecture", "platform",
                 "core_archive", "source"}


@dataclass(frozen=True)
class HypoPGMacosTarget:
    profile_id: str
    postgresql_version: str
    architecture: str
    platform: str
    core_basename: str
    core_run_id: Optional[str]
    core_sha256: str
    core_build_id: Optional[str]
    core_source_revision: Optional[str]

    @property
    def extension_basename(self):
        return f"hypopg-{HYPOPG_VERSION}-postgresql-{self.postgresql_version}-{self.platform}.tar.gz"

    def shell_values(self):
        if not all((self.core_run_id, self.core_build_id, self.core_source_revision)):
            raise ValueError("HypoPG runtime target requires complete core build provenance")
        return (self.postgresql_version, self.architecture, self.platform, self.profile_id,
                self.core_basename, self.core_run_id, self.core_sha256, self.core_build_id,
                self.core_source_revision, SOURCE_URL, SOURCE_SHA256)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate target config key: {key}")
        result[key] = value
    return result


def base_target(postgresql_version, architecture, root=None):
    """Create an unresolved target for one support-selected macOS release."""
    if (not isinstance(postgresql_version, str)
            or re.fullmatch(r"[1-9][0-9]*\.[0-9]+", postgresql_version) is None
            or architecture not in {"arm64", "x86_64"}):
        raise ValueError("invalid HypoPG macOS target")
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    support = coverage.load_json(root / "support.json")
    releases = coverage.release_snapshot(
        coverage.load_json(root / "support/postgresql-releases.json"), support)
    selected_core_targets, _ = coverage.expected_targets(support, releases)
    platform = f"macos-{architecture}"
    if (postgresql_version, platform) not in selected_core_targets:
        raise ValueError(f"PostgreSQL {postgresql_version} {platform} is not selected")
    profile_id = f"hypopg-publication-{platform}-{postgresql_version}"
    profile = coverage.verification_profile(root, profile_id)
    if profile["scope"] != "publication" or profile["platforms"] != [platform]:
        raise ValueError(f"HypoPG PostgreSQL {postgresql_version} {platform} publication is not registered")
    return {
        "schema_version": 1,
        "profile_id": profile_id,
        "postgresql_version": postgresql_version,
        "architecture": architecture,
        "platform": platform,
        "core_archive": {"basename": f"postgresql-{postgresql_version}-{platform}.tar.gz"},
        "source": {"url": SOURCE_URL, "sha256": SOURCE_SHA256},
    }


def load_target_config(path, allow_base=False):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read HypoPG target config {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) != EXPECTED_KEYS:
        raise ValueError("HypoPG target config has an unexpected field set")
    core, source = value.get("core_archive"), value.get("source")
    stable_fields = {"basename", "sha256"}
    provenance_fields = stable_fields | {"run_id", "build_id", "source_revision"}
    allowed_core_fields = (stable_fields, provenance_fields) if allow_base else (provenance_fields,)
    if not isinstance(core, dict) or set(core) not in allowed_core_fields:
        raise ValueError("HypoPG target core_archive has an unexpected field set")
    if not isinstance(source, dict) or set(source) != {"url", "sha256"}:
        raise ValueError("HypoPG target source has an unexpected field set")

    version = value.get("postgresql_version")
    architecture = value.get("architecture")
    if (value.get("schema_version") != 1 or not isinstance(version, str)
            or re.fullmatch(r"[1-9][0-9]*\.[0-9]+", version) is None):
        raise ValueError("unsupported HypoPG macOS PostgreSQL target version")
    if architecture not in {"arm64", "x86_64"}:
        raise ValueError("unsupported HypoPG macOS architecture")
    platform = f"macos-{architecture}"
    profile_id = f"hypopg-publication-macos-{architecture}-{version}"
    core_basename = f"postgresql-{version}-{platform}.tar.gz"
    if (value.get("profile_id") != profile_id or value.get("platform") != platform
            or core.get("basename") != core_basename):
        raise ValueError("HypoPG target profile or archive identity is inconsistent")
    run_id, digest = core.get("run_id"), core.get("sha256")
    build_id, source_revision = core.get("build_id"), core.get("source_revision")
    if allow_base and set(core) == stable_fields:
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("HypoPG target core checksum is invalid")
        if source != {"url": SOURCE_URL, "sha256": SOURCE_SHA256}:
            raise ValueError("HypoPG target source must match the pinned 1.4.3 source archive")
        return HypoPGMacosTarget(profile_id, version, architecture, platform, core_basename,
                                 None, digest, None, None)
    if (not isinstance(run_id, str) or not run_id.isdigit()
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not isinstance(build_id, str)
            or not re.fullmatch(rf"github-{re.escape(run_id)}-[1-9][0-9]*", build_id)
            or not isinstance(source_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", source_revision)):
        raise ValueError("HypoPG target core identity is invalid")
    if source != {"url": SOURCE_URL, "sha256": SOURCE_SHA256}:
        raise ValueError("HypoPG target source must match the pinned 1.4.3 source archive")
    return HypoPGMacosTarget(profile_id, version, architecture, platform, core_basename,
                             run_id, digest, build_id, source_revision)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", choices=("arm64", "x86_64"), required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        target = base_target(args.postgresql_version, args.architecture, args.root)
    except (coverage.CoverageError, OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
