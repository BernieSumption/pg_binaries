"""Load a pinned macOS pg_jsonschema publication target."""

from dataclasses import dataclass
import json
from pathlib import Path
import re


SOURCE_URL = "https://github.com/supabase/pg_jsonschema.git"
SOURCE_COMMIT = "cbe74b570d38aa0c4d42914e7a118bcb3adaee7a"
CARGO_LOCK_SHA256 = "ab865dc25d9eea4bf7dbfaf8fae13283e5c0bce4bca460fe10464c6716e67028"
BLOCKERS = ["seahash-4.1.0-notice-unresolved", "postgresql-core-redistribution-review-pending"]
EXPECTED_KEYS = {"schema_version", "profile_id", "postgresql_version", "pg_jsonschema_version",
                 "architecture", "platform", "core_archive", "source"}
CORE_KEYS = {"basename", "run_id", "sha256", "build_id", "source_revision"}


@dataclass(frozen=True)
class Target:
    profile_id: str
    postgresql_version: str
    extension_version: str
    architecture: str
    platform: str
    core_basename: str
    core_run_id: str
    core_sha256: str
    core_build_id: str
    core_source_revision: str
    source_url: str
    source_commit: str
    cargo_lock_sha256: str

    @property
    def pg_major(self):
        return self.postgresql_version.split(".", 1)[0]

    @property
    def feature(self):
        return f"pg{self.pg_major}"

    @property
    def module_filename(self):
        suffix = ".so" if self.postgresql_version == "15.19" else ".dylib"
        return f"pg_jsonschema{suffix}"

    @property
    def cargo_target(self):
        return "aarch64-apple-darwin" if self.architecture == "arm64" else "x86_64-apple-darwin"

    @property
    def extension_basename(self):
        return (f"pg_jsonschema-{self.extension_version}-postgresql-{self.postgresql_version}-"
                f"{self.platform}.tar.gz")

    def shell_values(self):
        return (self.postgresql_version, self.extension_version, self.architecture, self.platform,
                self.profile_id, self.core_basename, self.core_run_id, self.core_sha256,
                self.core_build_id, self.core_source_revision, self.source_url,
                self.source_commit, self.cargo_lock_sha256, self.module_filename)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate target key: {key}")
        result[key] = value
    return result


def load_target(path):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read pg_jsonschema target {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) != EXPECTED_KEYS:
        raise ValueError("pg_jsonschema target has an unexpected field set")
    core, source = value.get("core_archive"), value.get("source")
    if not isinstance(core, dict) or set(core) != CORE_KEYS:
        raise ValueError("pg_jsonschema core_archive has an unexpected field set")
    if not isinstance(source, dict) or set(source) != {"url", "commit", "cargo_lock_sha256"}:
        raise ValueError("pg_jsonschema source has an unexpected field set")
    pg_version = value.get("postgresql_version")
    version = value.get("pg_jsonschema_version")
    architecture = value.get("architecture")
    if value.get("schema_version") != 1 or pg_version not in {"15.19", "16.15", "17.11", "18.6"} or version != "0.3.4":
        raise ValueError("unsupported pg_jsonschema macOS target version")
    if architecture not in {"arm64", "x86_64"}:
        raise ValueError("unsupported macOS architecture")
    platform = f"macos-{architecture}"
    profile = f"pg-jsonschema-publication-macos-{architecture}-{pg_version}"
    basename = f"postgresql-{pg_version}-{platform}.tar.gz"
    run_id, digest, build_id, revision = (core.get(key) for key in
                                          ("run_id", "sha256", "build_id", "source_revision"))
    if (value.get("profile_id") != profile or value.get("platform") != platform
            or core.get("basename") != basename):
        raise ValueError("pg_jsonschema target profile or archive identity is inconsistent")
    if (not isinstance(run_id, str) or not run_id.isdigit()
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or build_id != f"github-{run_id}-1"
            or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision)):
        raise ValueError("pg_jsonschema core identity is invalid")
    if (source.get("url") != SOURCE_URL or source.get("commit") != SOURCE_COMMIT
            or source.get("cargo_lock_sha256") != CARGO_LOCK_SHA256):
        raise ValueError("pg_jsonschema source must match pinned 0.3.4 inputs")
    return Target(profile, pg_version, version, architecture, platform, basename, run_id,
                  digest, build_id, revision, source["url"], source["commit"],
                  source["cargo_lock_sha256"])
