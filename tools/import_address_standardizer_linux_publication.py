#!/usr/bin/env python3
"""Validate and retain Address Standardizer Linux candidate evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import coverage
import emit_address_standardizer_linux_publication as publication
import linux_core_resolution

MAX_FILE_BYTES = 8 * 1024 * 1024


def read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"invalid or missing JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"expected a JSON object in {path}")
    return value


def retain(source, destination, copies):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
        raise coverage.CoverageError(f"evidence must be a regular file no larger than {MAX_FILE_BYTES} bytes: {source}")
    if destination.exists() and (destination.is_symlink() or destination.read_bytes() != source.read_bytes()):
        raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    copies.append((source, destination))


def copy(copies, root):
    root = Path(root).resolve()
    for source, destination in copies:
        if not destination.parent.resolve().is_relative_to(root):
            raise coverage.CoverageError(f"retained evidence path escapes repository root: {destination}")
        ancestor = destination.parent
        while ancestor != root and ancestor != ancestor.parent:
            if ancestor.is_symlink():
                raise coverage.CoverageError(f"retained evidence path crosses a symbolic link: {ancestor}")
            ancestor = ancestor.parent
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def import_run(root, core_archives, archives, run_id):
    root, core_archives, archives = map(Path, (root, core_archives, archives))
    root, run_id = root.resolve(), str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    attempt_path = archives / "publication" / "attempt.json"
    attempt = read_json(attempt_path)
    architecture = attempt.get("architecture")
    pg_version = attempt.get("postgresql_version")
    if architecture not in {"x86_64", "arm64"}:
        raise coverage.CoverageError("attempt architecture is unsupported")
    selected = publication.profile_id(architecture, pg_version)
    extension_version = attempt.get("version")
    profile = publication.validate_target(root, architecture, pg_version, extension_version)
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("profile_id") != selected or attempt.get("postgresql_version") != pg_version
            or attempt.get("release_eligible") is not False
            or attempt.get("redistribution_status") != publication.BLOCK
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("raw attempt identity does not match this run and profile")
    workflow = attempt.get("workflow_steps")
    if not isinstance(workflow, dict) or set(workflow) != {"build", "verify", "core_resolution"}:
        raise coverage.CoverageError("raw attempt must retain build, verify and core resolution outcomes")
    if workflow["core_resolution"] not in {"success", "failure", "skipped", "cancelled", "timed_out"}:
        raise coverage.CoverageError("raw attempt core resolution outcome is invalid")
    results = publication._case_results(workflow["verify"],
        "passed" if attempt.get("steps", {}).get("elf-closure") == "success" else
        "failed" if attempt.get("steps", {}).get("elf-closure") == "failure" else None)
    expected_steps = {case: ("success" if result == "passed" else "failure" if result == "failed" else "skipped")
                      for case, result in results.items()}
    if attempt.get("steps") != expected_steps:
        raise coverage.CoverageError("raw attempt case outcomes do not match workflow outcomes")

    platform = f"linux-{architecture}"
    archive_name = f"address-standardizer-{extension_version}-postgresql-{pg_version}-{platform}.tar.gz"
    core_name = f"postgresql-{pg_version}-{platform}.tar.gz"
    archive, core = archives / archive_name, core_archives / core_name
    if attempt.get("archives_present") != {core_name: core.is_file(), archive_name: archive.is_file()}:
        raise coverage.CoverageError("raw attempt archive presence differs from downloaded files")
    resolution_path = core_archives / "core-resolution.json"
    resolution = None
    if workflow["core_resolution"] == "success":
        if resolution_path.is_file():
            try:
                resolution = linux_core_resolution.validate_resolution(
                    resolution_path, core, pg_version, architecture)
            except (OSError, ValueError) as exc:
                raise coverage.CoverageError(f"invalid resolved PostgreSQL core provenance: {exc}") from exc
            if (workflow["core_resolution"] != "success"
                    or attempt.get("core_run_id") != resolution["provenance"]["run_id"]):
                raise coverage.CoverageError("raw attempt core provenance differs from resolution outcome")
        else:
            raise coverage.CoverageError("selected attempt lacks required PostgreSQL core provenance")
    elif attempt.get("core_run_id") is not None:
        raise coverage.CoverageError("unresolved core attempt must not claim core provenance")
    evidence = root / "support/evidence" / f"address-standardizer-linux-publication-{run_id}"
    if pg_version != "18.6":
        evidence /= pg_version
    evidence /= architecture
    copies = []
    retain(attempt_path, evidence / "attempt.json", copies)
    if resolution is None:
        if ((archives / "publication/current-receipt.json").exists()
                or (archives / "publication/verification-record.json").exists()):
            raise coverage.CoverageError("archive-bound evidence exists without resolved core provenance")
        copy(copies, root)
        return [str(destination.relative_to(root)) for _, destination in copies]
    if archive.is_symlink() or core.is_symlink():
        raise coverage.CoverageError("archives must not be symbolic links")
    if not archive.is_file() or not core.is_file():
        if (archives / "publication/current-receipt.json").exists() or (archives / "publication/verification-record.json").exists():
            raise coverage.CoverageError("receipt or record exists without both archives")
        copy(copies, root)
        return [str(destination.relative_to(root)) for _, destination in copies]
    if extension_version != publication.VERSION:
        raise coverage.CoverageError("unsupported Address Standardizer recipe must not produce a candidate archive")

    checksums = {archive_name: publication.digest(archive), core_name: publication.digest(core)}
    for path in (archive, core):
        publication._sidecar(path, checksums[path.name])
    if attempt.get("archives") != checksums:
        raise coverage.CoverageError("archive bytes differ from the raw attempt hashes")
    retain(Path(str(archive) + ".sha256"), evidence / f"{archive_name}.sha256", copies)
    retain(Path(str(core) + ".sha256"), evidence / f"{core_name}.sha256", copies)

    report_names = {"elf_closure": (archives / "static-analysis/address-standardizer.json", "elf-closure.json"),
                    "build_evidence": (archives / "build-evidence.txt", "build-evidence.txt"),
                    "address_standardizer_license": (archives / "Address-Standardizer-COPYING.txt", "Address-Standardizer-COPYING.txt"),
                    "pcre2_license": (archives / "PCRE2-LICENCE.md", "PCRE2-LICENCE.md"),
                    "sljit_license": (archives / "SLJIT-LICENSE.txt", "SLJIT-LICENSE.txt"),
                    "probe_output": (archives / "probe-output.txt", "probe-output.txt")}
    if resolution is not None:
        report_names["core_resolution"] = (resolution_path, "core-resolution.json")
    reports = {}
    for key, (source, name) in report_names.items():
        if source.is_file():
            reports[key] = publication.digest(source)
            retain(source, evidence / name, copies)
    if attempt.get("reports") != reports:
        raise coverage.CoverageError("raw report hashes differ from retained report files")
    if "elf_closure" in reports:
        static = read_json(report_names["elf_closure"][0])
        if (static.get("architecture") != architecture
                or static.get("outcome") != ("passed" if results["elf-closure"] == "passed" else "failed")
                or static.get("archives") != [
                    {"basename": core_name, "sha256": checksums[core_name]},
                    {"basename": archive_name, "sha256": checksums[archive_name]},
                ]):
            raise coverage.CoverageError("ELF report is not bound to both final archives")
    if results["archive-suite"] == "passed":
        probe = report_names["probe_output"][0]
        if not probe.is_file() or f"PASS: Address Standardizer {publication.VERSION} with PostgreSQL {pg_version}" not in probe.read_text(encoding="utf-8"):
            raise coverage.CoverageError("passed archive suite lacks relocated Alpine probe output")

    receipt_path = archives / "publication/current-receipt.json"
    record_path = archives / "publication/verification-record.json"
    if receipt_path.exists() != record_path.exists():
        raise coverage.CoverageError("receipt and verification record must be retained together")
    if not receipt_path.exists():
        copy(copies, root)
        return [str(destination.relative_to(root)) for _, destination in copies]
    receipt, record = read_json(receipt_path), read_json(record_path)
    if (receipt.get("profile_id") != selected or receipt.get("profile_revision") != profile["profile_revision"]
            or receipt.get("project") != "Address Standardizer" or receipt.get("version") != publication.VERSION
            or receipt.get("architecture") != architecture or receipt.get("platform") != platform
            or receipt.get("postgresql_version") != pg_version or receipt.get("case_results") != results
            or receipt.get("archives") != checksums or receipt.get("extension_archive") != archive_name
            or receipt.get("release_eligible") is not False or receipt.get("redistribution_status") != publication.BLOCK
            or receipt.get("reports") != {key: value for key, value in reports.items() if key != "probe_output"}
            or receipt.get("environment") != record.get("environment")):
        raise coverage.CoverageError("receipt identity, archive or report hashes differ from raw evidence")
    ci = receipt.get("ci")
    if (not isinstance(ci, dict) or str(ci.get("run_id")) != run_id
            or any(ci.get(key) != attempt["source_revision"] for key in ("source_revision", "build_revision", "test_revision"))
            or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")):
        raise coverage.CoverageError("receipt CI provenance differs from raw attempt")
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    expected_outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    if (record.get("profile_revision") != profile["profile_revision"] or record.get("test_cases") != profile["case_ids"]
            or record.get("case_results") != results or record.get("outcome") != expected_outcome
            or record.get("ci") != ci or record.get("test_revision") != attempt["source_revision"]
            or record.get("sha256") != checksums[archive_name]
            or record.get("assembled_core") != {"archive": core_name, "sha256": checksums[core_name], "version": pg_version}
            or record.get("release_eligible") is not False or record.get("redistribution_status") != publication.BLOCK):
        raise coverage.CoverageError("verification record identity or checksums differ from receipt")
    retain(receipt_path, evidence / "current-receipt.json", copies)
    retain(record_path, evidence / "verification-record.json", copies)
    retain(record_path, root / "support/verification" /
           f"address-standardizer-{publication.VERSION}-postgresql-{pg_version}-{platform}-current-{run_id}.json", copies)
    copy(copies, root)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_archives, args.archives, args.run_id)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Address Standardizer Linux evidence import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
