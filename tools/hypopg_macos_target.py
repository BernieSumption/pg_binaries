"""Load the pinned target identity for a HypoPG macOS publication run."""

from dataclasses import dataclass
import json
from pathlib import Path
import re


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
    core_run_id: str
    core_sha256: str
    core_build_id: str
    core_source_revision: str

    @property
    def extension_basename(self):
        return f"hypopg-{HYPOPG_VERSION}-postgresql-{self.postgresql_version}-{self.platform}.tar.gz"

    def shell_values(self):
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


def load_target_config(path):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read HypoPG target config {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) != EXPECTED_KEYS:
        raise ValueError("HypoPG target config has an unexpected field set")
    core, source = value.get("core_archive"), value.get("source")
    if not isinstance(core, dict) or set(core) != {"basename", "run_id", "sha256", "build_id", "source_revision"}:
        raise ValueError("HypoPG target core_archive has an unexpected field set")
    if not isinstance(source, dict) or set(source) != {"url", "sha256"}:
        raise ValueError("HypoPG target source has an unexpected field set")

    version = value.get("postgresql_version")
    architecture = value.get("architecture")
    if value.get("schema_version") != 1 or version not in {"17.11", "18.6"}:
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
    if (not isinstance(run_id, str) or not run_id.isdigit()
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or build_id != f"github-{run_id}-1"
            or not isinstance(source_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", source_revision)):
        raise ValueError("HypoPG target core identity is invalid")
    if source != {"url": SOURCE_URL, "sha256": SOURCE_SHA256}:
        raise ValueError("HypoPG target source must match the pinned 1.4.3 source archive")
    return HypoPGMacosTarget(profile_id, version, architecture, platform, core_basename,
                             run_id, digest, build_id, source_revision)
