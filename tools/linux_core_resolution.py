#!/usr/bin/env python3
"""Write a compact provenance record for a resolved Linux PostgreSQL core."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile


SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
BUILD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def _text(value, pattern, field):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def _core_manifest(archive_path):
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            info = archive.getmember("postgresql/manifest.json")
            member = archive.extractfile("postgresql/manifest.json")
            if member is None or not info.isfile() or info.size > 1024 * 1024:
                raise ValueError("archive lacks a bounded PostgreSQL manifest")
            value = json.load(member)
    except (OSError, tarfile.TarError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read PostgreSQL core manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("PostgreSQL core manifest must be an object")
    return value


def create_record(archive_path, version, architecture, origin, candidate=None, environ=None,
                  artifact_name=None):
    archive_path = Path(archive_path)
    environ = os.environ if environ is None else environ
    manifest = _core_manifest(archive_path)
    if (manifest.get("component") != "postgresql" or manifest.get("version") != version
            or manifest.get("platform") != "linux" or manifest.get("architecture") != architecture):
        raise ValueError("archive manifest target does not match resolution target")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    provenance = {
        "source_revision": _text(manifest.get("source_revision"), SHA, "source revision"),
        "build_id": _text(manifest.get("build_id"), BUILD_ID, "build ID"),
    }
    inputs = manifest.get("builder_inputs")
    if not isinstance(inputs, dict) or inputs.get("base_image") != "ubuntu:22.04":
        raise ValueError("archive manifest lacks checked builder inputs")
    provenance["build_inputs"] = {
        "base_image": "ubuntu:22.04",
        "base_image_digest": _text(inputs.get("base_image_digest"), re.compile(r"sha256:[0-9a-f]{64}"), "base image digest"),
        "packages_sha256": _text(inputs.get("packages_sha256"), HEX_SHA256, "builder packages digest"),
    }
    if origin == "reused":
        if not isinstance(candidate, dict):
            raise ValueError("reused origin requires validated candidate provenance")
        run_id = _text(str(candidate.get("run_id", "")), re.compile(r"[1-9][0-9]*"), "producer run ID")
        attempt = candidate.get("run_attempt")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise ValueError("invalid producer run attempt")
        artifact_revision = _text(candidate.get("artifact_revision"), SHA, "artifact revision")
        artifact_name = _text(artifact_name or candidate.get("artifact_name"),
                              re.compile(r"[A-Za-z0-9_.-]{1,255}"), "artifact name")
        candidate_digest = _text(candidate.get("sha256"), HEX_SHA256, "candidate archive digest")
        if digest != candidate_digest:
            raise ValueError("candidate provenance digest differs from resolved archive")
        provenance.update({"provider": "github-actions", "run_id": run_id,
                           "run_attempt": attempt, "artifact_name": artifact_name,
                           "head_sha": artifact_revision})
    elif origin == "built":
        provenance.update({
            "provider": "github-actions",
            "run_id": _text(environ.get("GITHUB_RUN_ID", ""), re.compile(r"[1-9][0-9]*"), "current run ID"),
            "run_attempt": int(_text(environ.get("GITHUB_RUN_ATTEMPT", "1"), re.compile(r"[1-9][0-9]*"), "current run attempt")),
            "repository": _text(environ.get("GITHUB_REPOSITORY", ""), re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"), "repository"),
            "workflow_ref": _text(environ.get("GITHUB_WORKFLOW_REF", ""), re.compile(r"[A-Za-z0-9_./@{}-]{1,512}"), "workflow reference"),
        })
        provenance["run_sha"] = _text(environ.get("GITHUB_SHA", ""), SHA, "current run SHA")
    else:
        raise ValueError("origin must be reused or built")
    return {"schema_version": 1, "archive": archive_path.name, "sha256": digest,
            "postgresql_version": version, "architecture": architecture,
            "origin": origin, "provenance": provenance}


def validate_resolution(record_path, archive_path, version, architecture, root=None):
    """Validate a transferred resolution record against its archive without external tools."""
    del root
    try:
        record = json.loads(Path(record_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read core resolution record: {exc}") from exc
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ValueError("unsupported core resolution record schema")
    archive_path = Path(archive_path)
    if (record.get("archive") != archive_path.name or record.get("postgresql_version") != version
            or record.get("architecture") != architecture):
        raise ValueError("core resolution target or archive name does not match")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if record.get("sha256") != digest:
        raise ValueError("core resolution archive digest does not match")
    origin, provenance = record.get("origin"), record.get("provenance")
    if origin not in {"built", "reused"} or not isinstance(provenance, dict):
        raise ValueError("core resolution origin or provenance is invalid")
    inputs = provenance.get("build_inputs")
    if (not isinstance(inputs, dict) or inputs.get("base_image") != "ubuntu:22.04"
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(inputs.get("base_image_digest", "")))
            or not HEX_SHA256.fullmatch(str(inputs.get("packages_sha256", "")))):
        raise ValueError("core resolution build inputs are invalid")
    _text(provenance.get("source_revision"), SHA, "source revision")
    _text(provenance.get("build_id"), BUILD_ID, "build ID")
    if provenance.get("provider") != "github-actions":
        raise ValueError("core resolution provider is invalid")
    _text(provenance.get("run_id"), re.compile(r"[1-9][0-9]*"), "run ID")
    attempt = provenance.get("run_attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise ValueError("core resolution run attempt is invalid")
    if origin == "reused":
        _text(provenance.get("artifact_name"), re.compile(r"[A-Za-z0-9_.-]{1,255}"), "artifact name")
        _text(provenance.get("head_sha"), SHA, "artifact head SHA")
    else:
        _text(provenance.get("run_sha"), SHA, "current run SHA")
        _text(provenance.get("repository"), re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"), "repository")
        _text(provenance.get("workflow_ref"), re.compile(r"[A-Za-z0-9_./@{}-]{1,512}"), "workflow reference")
    manifest = _core_manifest(archive_path)
    if (manifest.get("component") != "postgresql" or manifest.get("version") != version
            or manifest.get("platform") != "linux" or manifest.get("architecture") != architecture
            or manifest.get("source_revision") != provenance["source_revision"]
            or manifest.get("build_id") != provenance["build_id"]
            or manifest.get("builder_inputs") != inputs):
        raise ValueError("resolution provenance differs from embedded core manifest")
    return copy.deepcopy(record)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    parser.add_argument("--origin", choices=("reused", "built"))
    parser.add_argument("--candidate-json")
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--validate-record", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.validate_record:
            validate_resolution(args.validate_record, args.archive, args.postgresql_version,
                                args.architecture)
            return 0
        if args.output is None or args.origin is None:
            parser.error("--output and --origin are required when writing a resolution record")
        candidate = json.loads(args.candidate_json) if args.candidate_json is not None else None
        artifact_name = None
        if args.candidate_manifest:
            discovery = json.loads(args.candidate_manifest.read_text(encoding="utf-8"))
            artifact_name = discovery["archives"][0]["source"]["artifact_name"]
        record = create_record(args.archive, args.postgresql_version, args.architecture,
                               args.origin, candidate, artifact_name=artifact_name)
        args.output.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
                               encoding="utf-8")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
