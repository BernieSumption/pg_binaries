#!/usr/bin/env python3
"""Best-effort reuse of a passing macOS core archive with matching build inputs."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile

import coverage
import stage_macos_core_symbols as stage_symbols
import source_archive


WORKFLOW = "postgresql-macos-selected-publication.yml"
MAX_ZIP_BYTES = 1024 * 1024 * 1024
CORE_INPUTS = (
    "scripts/macos/build-source-dependencies.sh", "scripts/macos/build.sh",
    "scripts/macos/bundle.py", "scripts/macos/licenses.py",
    "tools/create_macos_symbols.py", "tools/discover_builtins.py",
    "tools/source_archive.py", "tools/check_source_identity.py",
)
CORE_WORKFLOW = ".github/workflows/postgresql-macos-selected-publication.yml"


def gh_json(endpoint: str):
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "gh api failed")
    return json.loads(result.stdout)


def artifact_zip(repo: str, artifact: dict) -> bytes:
    result = subprocess.run(["gh", "api", f"repos/{repo}/actions/artifacts/{artifact['id']}/zip"],
                            capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "artifact download failed")
    data = result.stdout
    if len(data) > MAX_ZIP_BYTES:
        raise RuntimeError("candidate artifact exceeds size limit")
    claimed = str(artifact.get("digest", ""))
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", claimed):
        raise RuntimeError("candidate artifact has no SHA-256 ZIP digest")
    if hashlib.sha256(data).hexdigest() != claimed.split(":", 1)[1].lower():
        raise RuntimeError("candidate artifact ZIP digest mismatch")
    return data


def extract_zip(data: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if len(archive.infolist()) > 20000:
            raise RuntimeError("candidate artifact has too many entries")
        seen = set()
        for item in archive.infolist():
            name = item.filename
            relative = PurePosixPath(name)
            mode = item.external_attr >> 16
            canonical_name = relative.as_posix() + ("/" if item.is_dir() else "")
            if (not name or relative.is_absolute() or "\\" in name or ":" in name
                    or any(part in {"", ".", ".."} for part in relative.parts)
                    or name != canonical_name
                    or name in seen or (mode & 0o170000) == 0o120000):
                raise RuntimeError(f"unsafe or ambiguous candidate ZIP path: {name!r}")
            seen.add(name)
            target = destination.joinpath(*relative.parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if item.file_size > MAX_ZIP_BYTES:
                raise RuntimeError("candidate artifact member exceeds size limit")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open("xb") as output:
                output.write(source.read(MAX_ZIP_BYTES + 1))
            if target.stat().st_size != item.file_size:
                raise RuntimeError("candidate artifact member size mismatch")


def _matches(run: dict, repository: str, branch: str, current_run: str, workflow_path: str) -> bool:
    repo = run.get("repository")
    head_repo = run.get("head_repository")
    return (str(run.get("id")) != current_run and run.get("status") == "completed"
            and run.get("conclusion") == "success" and run.get("head_branch") == branch
            and isinstance(repo, dict) and repo.get("full_name", "").casefold() == repository.casefold()
            and isinstance(head_repo, dict) and head_repo.get("full_name", "").casefold() == repository.casefold()
            and run.get("event") in {"push", "workflow_dispatch", "workflow_call"}
            and str(run.get("path", "")).endswith(workflow_path))


def relevant_inputs_match(revision: str, root: Path) -> bool:
    present = subprocess.run(["git", "cat-file", "-e", f"{revision}^{{commit}}"],
                             cwd=root, check=False, capture_output=True)
    if present.returncode:
        fetched = subprocess.run(["git", "fetch", "--no-tags", "--depth=1", "origin", revision],
                                 cwd=root, check=False, capture_output=True)
        if fetched.returncode:
            raise RuntimeError("cannot retrieve candidate macOS core source revision")
    result = subprocess.run(["git", "diff", "--quiet", revision, "--", *CORE_INPUTS],
                            cwd=root, check=False, capture_output=True)
    if result.returncode == 1:
        return False
    if result.returncode:
        raise RuntimeError("git diff could not verify macOS core recipe inputs")
    historical = subprocess.run(["git", "show", f"{revision}:{CORE_WORKFLOW}"], cwd=root,
                                check=False, capture_output=True)
    if historical.returncode:
        raise RuntimeError("cannot retrieve candidate macOS core build workflow")
    try:
        old_build = _workflow_build_job(historical.stdout.decode("utf-8"))
        new_build = _workflow_build_job((root / CORE_WORKFLOW).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError("cannot verify macOS core build workflow inputs") from exc
    return old_build == new_build


def _workflow_build_job(workflow: str) -> str:
    lines = workflow.splitlines(keepends=True)
    try:
        start = next(index for index, line in enumerate(lines) if line.rstrip("\r\n") == "  build:")
    except StopIteration as exc:
        raise ValueError("workflow lacks a build job") from exc
    end = next((index for index in range(start + 1, len(lines))
                if re.fullmatch(r"  [A-Za-z_][A-Za-z0-9_-]*:\s*\r?\n?", lines[index])), len(lines))
    return "".join(lines[start:end])


def validate_passing_record(record: dict, *, profile_id: str, version: str,
                            architecture: str, run_id: str, revision: str,
                            archive_sha256: str) -> tuple[str, ...]:
    cases = record.get("test_cases")
    case_results = record.get("case_results")
    profile_revision = record.get("profile_revision")
    if (record.get("schema_version") != 2 or record.get("scope") != "publication"
            or record.get("component") != "postgresql" or record.get("outcome") != "passed"
            or record.get("profile_id") != profile_id
            or not isinstance(profile_revision, str)
            or not re.fullmatch(r"[0-9a-f]{64}", profile_revision)
            or not isinstance(cases, list) or not cases
            or any(not isinstance(case, str) or not case for case in cases)
            or cases != sorted(set(cases))
            or not isinstance(case_results, dict) or set(case_results) != set(cases)
            or any(value != "passed" for value in case_results.values())
            or record.get("postgresql_version") != version
            or record.get("platform") != f"macos-{architecture}"
            or record.get("sha256") != archive_sha256
            or record.get("test_revision") != revision):
        raise RuntimeError("publication record is not a passed record bound to this archive")
    ci = record.get("ci") if isinstance(record.get("ci"), dict) else {}
    environment = record.get("environment") if isinstance(record.get("environment"), dict) else {}
    if (any(ci.get(key) != revision for key in ("source_revision", "build_revision", "test_revision"))
            or str(ci.get("run_id")) != run_id
            or environment.get("os") != "macos"
            or environment.get("architecture") != architecture
            or environment.get("endpoint") != "current"
            or environment.get("clean_system") is not True
            or environment.get("dependency_checks_passed") is not True):
        raise RuntimeError("publication record provenance does not bind this archive")
    return tuple(cases)


def _artifact_file(root: Path, filename: str, *, required: bool = True) -> bytes | None:
    allowed_parents = {"verification", "_temp/verification", "support/verification"}
    found = []
    for path in root.rglob(filename):
        relative = path.relative_to(root).parent.as_posix()
        retained_attempt = (filename == "publication-attempt.json" and re.search(
            r"(?:^|/)support/evidence/macos-core-publication-[1-9][0-9]*/"
            r"postgresql-[0-9]+\.[0-9]+/(?:arm64|x86_64)$", relative) is not None)
        if relative in allowed_parents or relative.endswith("/support/verification") or retained_attempt:
            found.append((relative, path.read_bytes()))
        else:
            raise RuntimeError(f"candidate has {filename} outside its verification layout")
    if not found:
        if required:
            raise RuntimeError(f"candidate verification artifact lacks {filename}")
        return None
    if len({data for _parent, data in found}) != 1:
        raise RuntimeError(f"candidate verification copies disagree for {filename}")
    return found[0][1]


def _artifact_suffix(root: Path, suffixes: tuple[str, ...]) -> bytes:
    found = []
    for path in root.rglob("index.json"):
        relative = path.relative_to(root).as_posix()
        if any(relative == suffix or relative.endswith("/" + suffix) for suffix in suffixes):
            found.append(path.read_bytes())
    if not found:
        raise RuntimeError("candidate verification artifact lacks its retained dSYM index")
    if len(set(found)) != 1:
        raise RuntimeError("candidate verification dSYM index copies disagree")
    return found[0]


def validate_core_manifest(archive: Path, version: str, architecture: str,
                           run_id: str, run_attempt: int, revision: str, root: Path) -> None:
    member_name = "postgresql/manifest.json"
    with tarfile.open(archive, "r:gz") as bundle:
        matches = [member for member in bundle.getmembers() if member.name == member_name]
        if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 1024 * 1024:
            raise RuntimeError("core archive lacks one bounded regular PostgreSQL manifest")
        stream = bundle.extractfile(matches[0])
        if stream is None:
            raise RuntimeError("cannot read PostgreSQL manifest from core archive")
        manifest = json.loads(stream.read(1024 * 1024 + 1).decode("utf-8"))
    expected_source = source_archive.source_archive("postgresql", version, "tar.bz2", root)
    expected_configuration = (
        f"postgresql-{version};mode=core-only;builder=native-macos;deployment-target=11.0;"
        "configure=icu,openssl,lz4,zstd,libxml,libxslt,zlib,uuid-e2fs-interface-apple-system,no-readline;"
        "dependencies=pinned-upstream-source;cflags=-O2,-g;runtime=bundled-dylibs"
    )
    expected_build_id = f"github-{run_id}-{run_attempt}"
    if (not isinstance(manifest, dict) or manifest.get("component") != "postgresql"
            or manifest.get("version") != version or manifest.get("postgresql_version") != version
            or manifest.get("platform") != "macos" or manifest.get("architecture") != architecture
            or manifest.get("build_id") != expected_build_id
            or manifest.get("source_revision") != revision
            or manifest.get("build_configuration") != expected_configuration
            or manifest.get("source_archive") != expected_source):
        raise RuntimeError("embedded PostgreSQL manifest does not match candidate run, core recipe, or source")


def stage_and_promote(build_root: Path, archive: Path, sidecar: Path,
                      archive_name: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        candidate_output = Path(temporary) / "archives"
        candidate_output.mkdir()
        shutil_copy(archive, candidate_output / archive_name)
        shutil_copy(sidecar, candidate_output / f"{archive_name}.sha256")
        stage_symbols.stage(build_root, candidate_output / "debug-symbols", archive_name)
        if destination.exists():
            if not destination.is_dir() or any(destination.iterdir()):
                raise RuntimeError("build output directory is not empty before candidate promotion")
            destination.rmdir()
        os.replace(candidate_output, destination)


def reuse(repo: str, revision: str, version: str, architecture: str, current_run: str,
          branch: str, destination: Path) -> None:
    if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise RuntimeError("revision must be a full Git SHA")
    workflow_path = f".github/workflows/{WORKFLOW}"
    runs = gh_json(f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?per_page=100").get("workflow_runs", [])
    candidates = sorted((run for run in runs if isinstance(run, dict)
                         and _matches(run, repo, branch, current_run, workflow_path)),
                        key=lambda run: run.get("run_number", 0), reverse=True)
    archive_name = f"postgresql-{version}-macos-{architecture}.tar.gz"
    profile = f"postgresql-publication-macos-{architecture}-{version}"
    coverage.verification_profile(Path(__file__).resolve().parents[1], profile)
    reasons = []
    for run in candidates:
        run_id = str(run["id"])
        artifacts = gh_json(f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100").get("artifacts", [])
        expected_build = f"postgresql-macos-selected-{version}-{architecture}-build-{run_id}"
        expected_verification = f"postgresql-macos-selected-{version}-{architecture}-verification-{run_id}"
        builds = [a for a in artifacts if a.get("name") == expected_build and not a.get("expired")]
        verifications = [a for a in artifacts if a.get("name") == expected_verification and not a.get("expired")]
        if len(builds) != 1 or len(verifications) != 1:
            reasons.append(f"run {run_id}: build or verification artifact missing/ambiguous")
            continue
        try:
            import tempfile
            with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
                root = Path(temporary)
                build_root, verify_root = root / "build", root / "verify"
                extract_zip(artifact_zip(repo, builds[0]), build_root)
                extract_zip(artifact_zip(repo, verifications[0]), verify_root)
                record_name = f"{archive_name[:-7]}-current-{run_id}.json"
                record = json.loads(_artifact_file(verify_root, record_name).decode("utf-8"))
                archive = build_root / archive_name
                sidecar = build_root / f"{archive_name}.sha256"
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                candidate_revision = str(run.get("head_sha", ""))
                run_attempt = run.get("run_attempt")
                if not re.fullmatch(r"[0-9a-f]{40,64}", candidate_revision):
                    raise RuntimeError("candidate run has an invalid source revision")
                if not isinstance(run_attempt, int) or isinstance(run_attempt, bool) or run_attempt < 1:
                    raise RuntimeError("candidate run has an invalid attempt number")
                if not relevant_inputs_match(candidate_revision, Path(__file__).resolve().parents[1]):
                    raise RuntimeError("macOS core recipe or source identity changed since candidate")
                validate_core_manifest(archive, version, architecture, run_id, run_attempt,
                                       candidate_revision, Path(__file__).resolve().parents[1])
                record_cases = validate_passing_record(
                    record, profile_id=profile, version=version, architecture=architecture,
                    run_id=run_id, revision=candidate_revision, archive_sha256=digest)
                if not sidecar.is_file():
                    raise RuntimeError("candidate archive checksum sidecar is missing")
                attempt_data = _artifact_file(verify_root, "publication-attempt.json")
                attempt = json.loads(attempt_data.decode("utf-8"))
                step_data = _artifact_file(verify_root, "step-results.json")
                step_results = json.loads(step_data.decode("utf-8"))
                expected_steps = {case: "success" for case in record_cases}
                if (str(attempt.get("run_id")) != run_id
                        or attempt.get("source_revision") != candidate_revision
                        or attempt.get("profile_id") != profile
                        or attempt.get("archive_present") is not True
                        or attempt.get("archives") != {archive_name: digest}
                        or step_results != expected_steps
                        or attempt.get("steps") != expected_steps):
                    raise RuntimeError("candidate attempt or step evidence does not support the passing record")
                checksum = sidecar.read_text(encoding="ascii").strip()
                checksum_match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", checksum)
                if (checksum_match is None or checksum_match.group(1).lower() != digest
                        or Path(checksum_match.group(2)).name != archive_name):
                    raise RuntimeError("archive checksum sidecar does not match")
                index = json.loads((build_root / "debug-symbols/index.json").read_text(encoding="utf-8"))
                retained_index = json.loads(_artifact_suffix(verify_root, (
                    "_temp/verification/debug-symbols/index.json",
                    "verification/debug-symbols/index.json")))
                if (index != retained_index
                        or index.get("schema_version") != 1
                        or not isinstance(index.get("files"), list) or not index["files"]
                        or any(item.get("archive") != archive_name or item.get("archive_sha256") != digest
                               for item in index["files"])):
                    raise RuntimeError("candidate dSYM index does not bind to core archive")
                stage_and_promote(build_root, archive, sidecar, archive_name, destination)
                return
        except Exception as exc:
            reasons.append(f"run {run_id}: {exc}")
    raise RuntimeError("no passing core candidate with matching build inputs; " + "; ".join(reasons[-5:]))


def shutil_copy(source: Path, target: Path) -> None:
    import shutil
    shutil.copyfile(source, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--revision", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", ""))
    parser.add_argument("--current-run", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", choices=("arm64", "x86_64"), required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        if not args.repository:
            raise RuntimeError("GitHub repository context is unavailable")
        reuse(args.repository, args.revision, args.postgresql_version, args.architecture,
              args.current_run, args.branch, args.destination)
        print("Reused passing macOS core archive and dSYMs with matching build inputs")
        reused = True
    except Exception as exc:
        print(f"macOS core reuse unavailable; building independently: {exc}", file=sys.stderr)
        reused = False
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"reused={'true' if reused else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
