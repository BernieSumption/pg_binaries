"""Validate common identities in one retrieved Linux extension candidate bundle."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

import build_input_identity
import coverage


class CandidateError(ValueError):
    pass


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RUN_ID = re.compile(r"[1-9][0-9]*\Z")
_REVISION = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


def _fail(message):
    raise CandidateError(message)


def _hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value, label):
    if (not isinstance(value, str) or not value or "\\" in value
            or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts
            or PurePosixPath(value).as_posix() != value):
        _fail(f"{label} must be a safe relative POSIX path")
    return value


def _metadata(archive_path, member_name):
    """Read one bounded regular JSON metadata member without extracting it."""
    member_name = _safe_name(member_name, "metadata member")
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            matches = [item for item in members if item.name == member_name]
            if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 1024 * 1024:
                _fail(f"candidate metadata {member_name} must be one bounded regular file")
            stream = archive.extractfile(matches[0])
            value = json.load(stream)
    except (OSError, tarfile.TarError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise CandidateError(f"cannot read candidate metadata {member_name}: {exc}") from exc
    if not isinstance(value, dict):
        _fail(f"candidate metadata {member_name} must be an object")
    return value


def validate_candidate(manifest, *, root, core_name, extension_name,
                       core_component, core_version, extension_component,
                       extension_version, extension_project, extension_display_name,
                       expected_build_inputs,
                       metadata_member="metadata.json",
                       core_metadata_member="postgresql/manifest.json"):
    """Check archive/record identities for a single selected Linux extension bundle.

    ``manifest`` contains ``target``, ``source``, ``files`` (name to extracted path),
    and ``sha256`` (name to digest). Producer discovery and core recipe validation
    intentionally remain caller responsibilities. No core verification record is
    required or synthesized.
    """
    if isinstance(manifest, (str, Path)):
        try:
            manifest = json.loads(Path(manifest).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CandidateError(f"cannot read candidate manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        _fail("candidate manifest has unsupported schema")
    target, source = manifest.get("target"), manifest.get("source")
    files, hashes = manifest.get("files"), manifest.get("sha256")
    if not all(isinstance(value, dict) for value in (target, source, files, hashes)):
        _fail("candidate manifest must contain target, source, files and sha256 objects")
    pg_version, platform = target.get("postgresql_version"), target.get("platform")
    if (not isinstance(pg_version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", pg_version)
            or not isinstance(platform, str) or not re.fullmatch(r"linux-(?:x86_64|arm64)", platform)):
        _fail("candidate target must identify an exact Linux PostgreSQL release and architecture")
    if str(core_version) != pg_version:
        _fail("candidate core version differs from the selected PostgreSQL release")
    architecture = platform.removeprefix("linux-")
    run_id = str(source.get("run_id", ""))
    run_attempt = source.get("run_attempt")
    head_sha, repository = source.get("head_sha"), source.get("repository")
    if (not _RUN_ID.fullmatch(run_id)
            or not isinstance(run_attempt, int) or isinstance(run_attempt, bool) or run_attempt < 1
            or not isinstance(head_sha, str) or not _REVISION.fullmatch(head_sha)
            or not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository)):
        _fail("candidate producer identity is invalid")

    names = (core_name, core_name + ".sha256", extension_name,
             extension_name + ".sha256")
    actual_hashes = {}
    for name in names:
        path = files.get(name)
        if not isinstance(path, (str, Path)):
            _fail(f"candidate manifest is missing {name}")
        try:
            actual = _hash_file(path)
        except OSError as exc:
            raise CandidateError(f"cannot read candidate file {name}: {exc}") from exc
        claimed = hashes.get(name)
        if not isinstance(claimed, str) or not _SHA256.fullmatch(claimed) or claimed != actual:
            _fail(f"candidate file {name} differs from its manifest SHA-256")
        actual_hashes[name] = actual
    for name in (core_name, extension_name):
        sidecar_path = Path(files[name + ".sha256"])
        try:
            if sidecar_path.stat().st_size > 4096:
                _fail(f"candidate checksum sidecar for {name} is too large")
            sidecar = sidecar_path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError) as exc:
            raise CandidateError(f"cannot read checksum sidecar for {name}: {exc}") from exc
        if sidecar != f"{actual_hashes[name]}  {name}":
            _fail(f"candidate checksum sidecar does not match {name}")

    record_name = manifest.get("extension_record")
    if not isinstance(record_name, str) or record_name not in files:
        _fail("candidate manifest must name its extension verification record")
    record_path = Path(files[record_name])
    try:
        if record_path.stat().st_size > 1024 * 1024:
            _fail("extension verification record exceeds size limit")
        record_bytes = record_path.read_bytes()
        record = json.loads(record_bytes)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CandidateError(f"cannot read extension verification record: {exc}") from exc
    if not isinstance(record, dict):
        _fail("extension verification record must be an object")
    record_digest = hashes.get(record_name)
    if not isinstance(record_digest, str) or _hash_file(record_path) != record_digest:
        _fail("extension verification record differs from its manifest SHA-256")
    support = coverage.load_json(Path(root) / "support.json")
    try:
        current = coverage.validate_verification_record(record, support, root)
    except coverage.CoverageError as exc:
        raise CandidateError(str(exc)) from exc
    if not current:
        _fail("extension verification profile is not current")
    if (record.get("outcome") != "passed" or record.get("scope") != "publication"
            or record.get("component") != extension_component
            or record.get("version") != extension_version
            or record.get("project") != extension_display_name
            or record.get("postgresql_version") != pg_version
            or record.get("platform") != platform
            or record.get("environment", {}).get("endpoint") != "current"):
        _fail("extension verification record target or outcome differs from candidate")
    cases, results = record.get("test_cases"), record.get("case_results")
    if not isinstance(cases, list) or not cases or not isinstance(results, dict) \
            or set(results) != set(cases) or any(value != "passed" for value in results.values()):
        _fail("all registered extension publication cases must have passed")
    ci = record.get("ci")
    if (not isinstance(ci, dict) or ci.get("provider") != "github-actions"
            or str(ci.get("run_id")) != run_id
            or ci.get("run_url") != f"https://github.com/{repository}/actions/runs/{run_id}"
            or any(not isinstance(ci.get(field), str) or ci[field].lower() != head_sha.lower()
                   for field in ("source_revision", "build_revision", "test_revision"))):
        _fail("extension record CI identity differs from candidate producer")
    if record.get("sha256", "").lower() != actual_hashes[extension_name]:
        _fail("extension record archive SHA-256 differs from candidate archive")
    assembled = record.get("assembled_core")
    if (not isinstance(assembled, dict) or assembled.get("archive") != core_name
            or assembled.get("version") != core_version
            or assembled.get("sha256", "").lower() != actual_hashes[core_name]):
        _fail("extension record assembled_core differs from candidate core archive")

    core_metadata = _metadata(files[core_name], core_metadata_member)
    if (core_metadata.get("component") != core_component
            or str(core_metadata.get("version")) != str(core_version)
            or core_metadata.get("platform") != "linux"
            or core_metadata.get("architecture") != architecture):
        _fail("core archive metadata target differs from candidate")
    metadata = _metadata(files[extension_name], metadata_member)
    if (metadata.get("project") != extension_project
            or str(metadata.get("version")) != str(extension_version)
            or metadata.get("platform") != "linux"
            or metadata.get("architecture") != architecture
            or str(metadata.get("postgresql_version")) != pg_version):
        _fail("extension archive metadata target differs from candidate")
    assessment = build_input_identity.assess_reuse(
        expected_build_inputs, metadata.get("build_inputs"))
    if not assessment["reusable"]:
        _fail(f"extension build inputs differ: {assessment['reason']}")
    return {"core": {"component": core_component, "version": core_version,
                      "postgresql_version": pg_version, "platform": platform,
                      "path": str(Path(files[core_name]).resolve()),
                      "archive_name": core_name, "sha256": actual_hashes[core_name]},
            "extension": {"component": extension_component, "project": extension_display_name,
                          "version": extension_version,
                          "postgresql_version": pg_version, "platform": platform,
                          "path": str(Path(files[extension_name]).resolve()),
                          "archive_name": extension_name,
                          "sha256": actual_hashes[extension_name]},
            "verification_records": [record],
            "extension_build_input_identity": expected_build_inputs}
