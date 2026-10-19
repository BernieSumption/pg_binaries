"""Validate a selected collection macOS target and its resolved core identity."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Optional


VERSIONS = {
    "1.1.1": "ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e",
    "2.1.3": "a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4",
}
PG_VERSIONS = {"15.19", "16.15", "17.11", "18.6"}
ARCHITECTURES = {"arm64", "x86_64"}


@dataclass(frozen=True)
class Target:
    postgresql_version: str
    architecture: str
    core_basename: str
    core_sha256: Optional[str]
    core_run_id: Optional[str]
    core_build_id: Optional[str]
    core_source_revision: Optional[str]

    @property
    def platform(self):
        return f"macos-{self.architecture}"

    @property
    def profile_id(self):
        return f"collection-publication-macos-{self.architecture}-{self.postgresql_version}"

    def extension_basename(self, version):
        return f"collection-{version}-postgresql-{self.postgresql_version}-{self.platform}.tar.gz"


def load_target(path, require_resolved=False):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read collection macOS target {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {"schema_version", "project", "postgresql_version", "architecture", "platform", "profile_id", "core_archive", "sources"}:
        raise ValueError("collection target has an unexpected field set")
    pg, arch = value["postgresql_version"], value["architecture"]
    if value["schema_version"] != 1 or value["project"] != "collection" or pg not in PG_VERSIONS or arch not in ARCHITECTURES:
        raise ValueError("unsupported collection macOS target")
    platform = f"macos-{arch}"
    core = value["core_archive"]
    if not isinstance(core, dict) or core.get("basename") != f"postgresql-{pg}-{platform}.tar.gz":
        raise ValueError("collection target core archive name is inconsistent")
    resolved_keys = {"basename", "sha256", "run_id", "build_id", "source_revision"}
    if set(core) not in ({"basename"}, resolved_keys):
        raise ValueError("collection core identity must be a base or resolved target")
    resolved = set(core) == resolved_keys
    if require_resolved and not resolved:
        raise ValueError("collection macOS target requires a resolved core identity")
    if resolved:
        if (not re.fullmatch(r"[0-9a-f]{64}", str(core["sha256"]))
                or not str(core["run_id"]).isdigit()
                or not re.fullmatch(r"github-[0-9]+-[1-9][0-9]*", str(core["build_id"]))
                or not re.fullmatch(r"[0-9a-f]{40}", str(core["source_revision"]))):
            raise ValueError("resolved collection core identity is invalid")
    sources = value["sources"]
    if not isinstance(sources, dict) or sources != VERSIONS:
        raise ValueError("collection source hashes must match both supported upstream releases")
    if value["platform"] != platform or value["profile_id"] != f"collection-publication-macos-{arch}-{pg}":
        raise ValueError("collection target profile identity is inconsistent")
    return Target(pg, arch, core["basename"], core.get("sha256"), core.get("run_id"),
                  core.get("build_id"), core.get("source_revision"))


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate target key: {key}")
        result[key] = value
    return result
