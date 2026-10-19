"""Validate current-profile pgvector records in a retrieved candidate bundle."""

import hashlib
import json
import re
from pathlib import Path

import coverage


class CandidateRecordError(ValueError):
    pass


def _fail(message):
    raise CandidateRecordError(message)


def _digest(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def validate_candidate_records(manifest, root):
    """Return the core and extension records after binding them to this bundle and run."""
    root = Path(root)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        _fail("candidate manifest schema_version must be 1")
    target, source = manifest.get("target"), manifest.get("source")
    files, listed_hashes = manifest.get("files"), manifest.get("sha256")
    if not isinstance(target, dict) or not isinstance(source, dict):
        _fail("candidate manifest must include target and source objects")
    if not isinstance(files, dict) or not isinstance(listed_hashes, dict):
        _fail("candidate manifest must include files and sha256 objects")

    version = target.get("pgvector_version")
    pg_version = target.get("postgresql_version")
    platform = target.get("platform")
    run_id = str(source.get("run_id", ""))
    head_sha = source.get("head_sha")
    repository = source.get("repository")
    if (not isinstance(version, str) or not re.fullmatch(r"\d+(?:\.\d+)+", version)
            or not isinstance(pg_version, str) or not re.fullmatch(r"\d+\.\d+", pg_version)
            or not isinstance(platform, str) or not re.fullmatch(r"linux-(?:x86_64|arm64)", platform)):
        _fail("candidate manifest target is invalid")
    if (not re.fullmatch(r"[1-9][0-9]*", run_id)
            or not isinstance(head_sha, str)
            or not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", head_sha)
            or not isinstance(repository, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)):
        _fail("candidate manifest producer identity is invalid")

    architecture = platform.removeprefix("linux-")
    core_archive = f"postgresql-{pg_version}-{platform}.tar.gz"
    extension_archive = f"pgvector-{version}-postgresql-{pg_version}-{platform}.tar.gz"
    record_names = {
        "core": f"postgresql-{pg_version}-{platform}-current-{run_id}.json",
        "extension": f"pgvector-{version}-postgresql-{pg_version}-{platform}-current-{run_id}.json",
    }
    required_names = [core_archive, core_archive + ".sha256", extension_archive,
                      extension_archive + ".sha256", *record_names.values()]
    actual_hashes = {}
    loaded_records = {}
    for name in required_names:
        path = files.get(name)
        if not isinstance(path, str):
            _fail(f"candidate manifest is missing {name}")
        try:
            content = Path(path).read_bytes()
        except OSError as exc:
            _fail(f"cannot read candidate file {name}: {exc}")
        actual = hashlib.sha256(content).hexdigest()
        if _digest(listed_hashes.get(name), f"manifest sha256 for {name}") != actual:
            _fail(f"candidate file {name} does not match manifest sha256")
        actual_hashes[name] = actual
        if name.endswith(".json"):
            try:
                data = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                _fail(f"cannot parse candidate record {name}: {exc}")
            if not isinstance(data, dict):
                _fail(f"candidate record {name} must be an object")
            loaded_records[name] = data

    for archive in (core_archive, extension_archive):
        sidecar = Path(files[archive + ".sha256"]).read_text(encoding="utf-8").strip()
        if sidecar != f"{actual_hashes[archive]}  {archive}":
            _fail(f"candidate checksum sidecar does not match {archive}")

    support = coverage.load_json(root / "support.json")
    coverage.validate_support(support)
    validated = {}
    for kind, name in record_names.items():
        record = loaded_records[name]
        label = f"{kind} candidate record {name}"
        try:
            current = coverage.validate_verification_record(record, support, root, label)
        except coverage.CoverageError as exc:
            raise CandidateRecordError(str(exc)) from exc
        if not current:
            _fail(f"{label}: profile is not current")
        expected_component = "postgresql" if kind == "core" else "vector"
        expected_version = pg_version if kind == "core" else version
        if (record.get("outcome") != "passed" or record.get("scope") != "publication"
                or record.get("component") != expected_component
                or str(record.get("version")) != expected_version
                or record.get("postgresql_version") != pg_version
                or record.get("platform") != platform
                or record.get("environment", {}).get("endpoint") != "current"):
            _fail(f"{label}: record target or outcome does not match the candidate")
        cases = record.get("test_cases")
        results = record.get("case_results")
        if (not isinstance(results, dict) or not cases or set(results) != set(cases)
                or any(result != "passed" for result in results.values())):
            _fail(f"{label}: all registered publication cases must have passed")
        ci = record.get("ci")
        if (not isinstance(ci, dict) or ci.get("provider") != "github-actions"
                or str(ci.get("run_id")) != run_id
                or ci.get("run_url") != f"https://github.com/{repository}/actions/runs/{run_id}"
                or any(not isinstance(ci.get(field), str)
                       or ci[field].lower() != head_sha.lower()
                       for field in ("source_revision", "build_revision", "test_revision"))):
            _fail(f"{label}: CI run and source identity do not match the producer")
        if record.get("sha256", "").lower() != actual_hashes[
                core_archive if kind == "core" else extension_archive]:
            _fail(f"{label}: archive SHA-256 does not match the candidate archive")
        validated[kind] = record

    core_sha = actual_hashes[core_archive]
    assembled = validated["extension"].get("assembled_core")
    if (not isinstance(assembled, dict) or assembled.get("archive") != core_archive
            or assembled.get("version") != pg_version
            or assembled.get("sha256", "").lower() != core_sha):
        _fail("extension candidate record assembled_core does not match the core archive")
    return validated
