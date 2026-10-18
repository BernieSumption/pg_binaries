"""Load the immutable target identity used by pgTAP macOS publication tools."""

from dataclasses import dataclass
import json
from pathlib import Path
import re


SOURCE_URL = "https://github.com/theory/pgtap/archive/refs/tags/v1.3.4.tar.gz"
SOURCE_SHA256 = "d2c951afb296a001d21785611a8e966e3f8fa3f5bfbd929396a5130c0152f314"
EXPECTED_KEYS = {
    "schema_version", "profile_id", "postgresql_version", "pgtap_version",
    "architecture", "platform", "core_archive", "source",
}
CORE_KEYS = {"basename", "run_id", "sha256", "build_id", "source_revision"}


@dataclass(frozen=True)
class PgtapMacosTarget:
    profile_id: str
    postgresql_version: str
    pgtap_version: str
    architecture: str
    platform: str
    core_basename: str
    core_run_id: str
    core_sha256: str
    core_build_id: str
    core_source_revision: str
    source_url: str
    source_sha256: str

    @property
    def extension_basename(self):
        return (f"pgtap-{self.pgtap_version}-postgresql-{self.postgresql_version}-"
                f"{self.platform}.tar.gz")

    def shell_values(self):
        return (
            self.postgresql_version, self.pgtap_version, self.architecture, self.platform,
            self.profile_id, self.core_basename, self.core_run_id, self.core_sha256,
            self.core_build_id, self.core_source_revision, self.source_url, self.source_sha256,
        )


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate target config key: {key}")
        value[key] = item
    return value


def load_target_config(path):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read pgTAP target config {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) != EXPECTED_KEYS:
        raise ValueError("pgTAP target config has an unexpected field set")
    core = value.get("core_archive")
    source = value.get("source")
    if not isinstance(core, dict) or set(core) != CORE_KEYS:
        raise ValueError("pgTAP target core_archive has an unexpected field set")
    if not isinstance(source, dict) or set(source) != {"url", "sha256"}:
        raise ValueError("pgTAP target source has an unexpected field set")

    pg_version = value.get("postgresql_version")
    version = value.get("pgtap_version")
    architecture = value.get("architecture")
    if value.get("schema_version") != 1 or pg_version not in {"15.19", "16.15", "17.11", "18.6"} or version != "1.3.4":
        raise ValueError("unsupported pgTAP PostgreSQL target version")
    if architecture not in {"arm64", "x86_64"}:
        raise ValueError("unsupported pgTAP macOS architecture")
    platform = f"macos-{architecture}"
    profile_id = f"pgtap-publication-macos-{architecture}-{pg_version}"
    core_basename = f"postgresql-{pg_version}-{platform}.tar.gz"
    if (value.get("profile_id") != profile_id or value.get("platform") != platform
            or core.get("basename") != core_basename):
        raise ValueError("pgTAP target profile or archive identity is inconsistent")
    run_id = core.get("run_id")
    digest = core.get("sha256")
    build_id = core.get("build_id")
    source_revision = core.get("source_revision")
    if (not isinstance(run_id, str) or not run_id.isdigit()
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or build_id != f"github-{run_id}-1"
            or not isinstance(source_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", source_revision)):
        raise ValueError("pgTAP target core identity is invalid")
    if (source.get("url") != SOURCE_URL or source.get("sha256") != SOURCE_SHA256):
        raise ValueError("pgTAP target source must match the pinned 1.3.4 source archive")
    return PgtapMacosTarget(
        profile_id, pg_version, version, architecture, platform, core_basename,
        run_id, digest, build_id, source_revision, source["url"], source["sha256"],
    )
