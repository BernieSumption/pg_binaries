"""Validate local copies of unpublished GitHub Actions archive candidates."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tarfile
import importlib.util

_identity_spec = importlib.util.spec_from_file_location(
    "candidate_build_input_identity", Path(__file__).with_name("build_input_identity.py"))
_identity = importlib.util.module_from_spec(_identity_spec)
_identity_spec.loader.exec_module(_identity)


def _version_key(value):
    return tuple(int(part) for part in value.split("."))


def load_candidates(manifest_path, support, expected_build_inputs=None):
    """Return retrieved candidates keyed by project, version, platform and PG major.

    Source run, artifact and expiry values are manifest claims. Expiry describes
    whether the source may still be fetched; cached bytes remain usable after it
    when the embedded and current checked build-input identities match.
    """
    try:
        manifest_path = Path(manifest_path)
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return {}, [{"entry": None, "reason": f"cannot read candidate manifest: {exc}"}]
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or not isinstance(data.get("archives"), list)):
        return {}, [{"entry": None,
                     "reason": "candidate manifest must have schema_version 1 and an archives array"}]

    now = datetime.now(timezone.utc)
    valid, rejected = {}, []
    for index, row in enumerate(data["archives"]):
        try:
            if not isinstance(row, dict):
                raise ValueError("entry must be an object")
            component = row.get("component")
            is_core = component == "postgresql"
            project, version, platform, pg = (row.get(k) for k in
                                               ("project", "version", "platform", "postgresql_version"))
            if is_core:
                version, platform, pg = row.get("version"), row.get("platform"), row.get("postgresql_version")
                if not all(isinstance(v, str) and v for v in (version, platform, pg)):
                    raise ValueError("core version, platform and postgresql_version are required")
                if version != pg:
                    raise ValueError("core version and postgresql_version must identify the same release")
            elif not all(isinstance(v, str) and v for v in (project, version, platform, pg)):
                raise ValueError("extension project, version, platform and postgresql_version are required")
            source = row.get("source")
            if (not isinstance(source, dict) or source.get("provider") != "github-actions"
                    or not re.fullmatch(r"[1-9][0-9]*", str(source.get("run_id", "")))
                    or not isinstance(source.get("artifact_name"), str) or not source["artifact_name"]):
                raise ValueError("source must identify a GitHub Actions run and artifact")
            expiry_status = "unknown"
            try:
                expiry = datetime.fromisoformat(str(source.get("expires_at", "")).replace("Z", "+00:00"))
                if expiry.tzinfo is not None:
                    expiry_status = "expired" if expiry <= now else "unexpired"
            except (ValueError, OverflowError):
                pass
            path_value = row.get("path")
            if not isinstance(path_value, str) or not path_value:
                raise ValueError("path is required")
            archive_path = Path(path_value)
            if not archive_path.is_absolute():
                archive_path = manifest_path.parent / archive_path
            if not archive_path.is_file():
                raise ValueError("retrieved archive bytes are unavailable")
            expected = row.get("sha256")
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
            hasher = hashlib.sha256()
            with archive_path.open("rb") as source_file:
                for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
            if digest != expected:
                raise ValueError("retrieved archive checksum differs from the manifest")

            os_name, separator, architecture = platform.partition("-")
            if not separator or platform not in {
                    f"{os}-{arch}" for os, arches in support["platform_architectures"].items()
                    for arch in arches}:
                raise ValueError("platform is not declared in support.json")
            if not re.fullmatch(r"\d+\.\d+", pg):
                raise ValueError("postgresql_version must be an exact major.minor release")
            with tarfile.open(archive_path, "r:gz") as archive:
                member_name = "postgresql/manifest.json" if is_core else "metadata.json"
                member = next((m for m in archive.getmembers()
                               if m.name == member_name and m.isfile() and m.size < 1024 * 1024), None)
                if member is None:
                    raise ValueError(f"archive has no regular {member_name}")
                stream = archive.extractfile(member)
                metadata = json.load(stream)
            if not isinstance(metadata, dict):
                raise ValueError("archive metadata must be a JSON object")
            if is_core:
                if (metadata.get("schema_version") != 1 or metadata.get("component") != "postgresql"
                        or metadata.get("version") != version or metadata.get("postgresql_version") != pg
                        or metadata.get("platform") != os_name
                        or metadata.get("architecture") != architecture):
                    raise ValueError("embedded PostgreSQL manifest does not match the candidate target")
                if archive_path.name != f"postgresql-{pg}-{platform}.tar.gz":
                    raise ValueError("core archive filename does not identify the candidate target")
                key = ("postgresql", version, platform)
            else:
                if version not in support["extensions"].get(project, {}).get("versions", {}):
                    raise ValueError("extension release is not declared in support.json")
                extension = support["extensions"][project]
                expected_project = re.sub(r"[^a-z0-9]+", "_", project.lower()).strip("_")
                if archive_path.name != f"{expected_project}-{version}-postgresql-{pg}-{platform}.tar.gz":
                    raise ValueError("extension archive filename does not identify the candidate target")
                if (metadata.get("project") != expected_project or metadata.get("version") != version
                        or metadata.get("platform") != os_name
                        or metadata.get("architecture") != architecture
                        or metadata.get("postgresql_version", pg) != pg
                        or metadata.get("sql_names") != extension["sql_names"]):
                    raise ValueError("embedded extension metadata does not match the candidate target")
                key = (project, version, platform, int(pg.split(".", 1)[0]))
            expected_identity = (expected_build_inputs or {}).get(key)
            if expected_identity is None:
                raise ValueError("expected current build input identity is missing")
            assessment = _identity.assess_reuse(expected_identity, metadata.get("build_inputs"))
            if not assessment["reusable"]:
                raise ValueError(assessment["reason"])
            candidate = {"path": str(archive_path), "sha256": digest, "postgresql_version": pg,
                         "source_claims": source, "source_expiry_status": expiry_status,
                         "archive_name": archive_path.name,
                         "build_input_sha256": expected_identity["sha256"]}
            previous = valid.get(key)
            if previous is None or _version_key(pg) > _version_key(previous["postgresql_version"]) or (
                    pg == previous["postgresql_version"] and digest < previous["sha256"]):
                valid[key] = candidate
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError,
                json.JSONDecodeError, tarfile.TarError) as exc:
            rejected.append({"entry": index, "reason": str(exc)})
    return valid, rejected
