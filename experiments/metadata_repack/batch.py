"""Batch the fixed first-release metadata-only archive corrections."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools import coverage
from experiments.metadata_repack.repack import RepackError, _identity, _members, repack


EXPECTED_COUNT = 22
EVIDENCE_DIR = "support/evidence/metadata-repack-2026-10-22"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _known_missing(filename, metadata):
    project, _, expected = _identity(filename, _core_name(filename))
    if metadata.get("project") != project:
        return False
    return all(field not in metadata for field in expected)


def _core_name(filename):
    match = re.fullmatch(
        r"(?:pgvector|hypopg|pg_jsonschema)-[^/]+-postgresql-(\d+\.\d+)-(linux|windows|macos)-(x86_64|arm64)\.tar\.gz",
        filename,
    )
    if not match:
        raise RepackError(f"unsupported archive filename {filename!r}")
    version, platform, arch = match.groups()
    return f"postgresql-{version}-{platform}-{arch}.tar.gz"


def _expected_delta(metadata, additions):
    return {key: {"before": metadata.get(key, "<missing>"), "after": value}
            for key, value in additions.items()}


def _member_proof(path):
    members, payloads = _members(path)
    proof = []
    for member in members:
        entry = {"path": member.name, "type": member.type.decode("ascii", "replace"),
                 "mode": member.mode, "link_target": member.linkname,
                 "uid": member.uid, "gid": member.gid, "uname": member.uname,
                 "gname": member.gname, "mtime": member.mtime,
                 "devmajor": member.devmajor, "devminor": member.devminor,
                 "sparse": member.sparse, "pax_headers": member.pax_headers}
        if member.isfile():
            entry["size"] = member.size
            entry["content_sha256"] = hashlib.sha256(payloads[member.name]).hexdigest()
        proof.append(entry)
    return proof


def _proof_document(source, filename, input_sha, output_sha, delta):
    return {"archive": filename, "original_sha256": input_sha,
            "patched_sha256": output_sha, "expected_metadata_delta": delta,
            "unchanged_non_metadata_members": [m for m in _member_proof(source)
                                                  if m["path"] != "metadata.json"]}


def _read_metadata(path):
    with tarfile.open(path, "r:gz") as archive:
        return json.load(archive.extractfile("metadata.json"))


def _select_defects(candidate, archive_dir):
    selected, names = [], set()
    for entry in candidate:
        filename = entry.get("filename") if isinstance(entry, dict) else None
        if not isinstance(filename, str) or not filename.startswith(("pgvector-", "hypopg-", "pg_jsonschema-")):
            continue
        archive = Path(archive_dir) / filename
        if not archive.is_file():
            continue
        metadata = _read_metadata(archive)
        try:
            defect = _known_missing(filename, metadata)
        except RepackError:
            defect = False
        if defect:
            if filename in names:
                raise RepackError(f"duplicate candidate filename: {filename}")
            names.add(filename)
            selected.append((entry, archive, metadata))
    return selected


def _derive_record(original, input_sha, output_sha, additions, proof_path, support, root):
    if not isinstance(original, dict) or original.get("sha256") != input_sha:
        raise RepackError("verification record does not bind original archive")
    if coverage.validate_verification_record(original, support, root) is not True:
        raise coverage.CoverageError("verification profile is stale")
    derived = copy.deepcopy(original)
    derived["sha256"] = output_sha
    derived["noncode_patch"] = {"kind": "metadata-only", "original_sha256": input_sha,
                                 "patched_sha256": output_sha, "metadata_delta": additions,
                                 "original_record_sha256": hashlib.sha256(
                                     json.dumps(original, sort_keys=True, separators=(",", ":")).encode()
                                 ).hexdigest(), "proof": proof_path}
    if coverage.validate_verification_record(derived, support, root) is not True:
        raise coverage.CoverageError("derived verification profile is stale")
    return derived


def run_batch(root=ROOT, output=None):
    root = Path(root)
    archive_dir = root / "dist/first-release/archives"
    candidate_path = root / "dist/first-release/candidate/proposed-entries.json"
    output = Path(output) if output else root / "dist/first-release/metadata-repack-batch"
    if output.exists() and any(output.iterdir()):
        raise RepackError(f"output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    archive_out, proof_out, verification_out = (output / name for name in ("archives", "proofs", "verification"))
    for directory in (archive_out, proof_out, verification_out):
        directory.mkdir(parents=True, exist_ok=True)
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    if not isinstance(candidate, list):
        raise RepackError("proposed entries must be an array")
    support = coverage.load_json(root / "support.json")
    selected = _select_defects(candidate, archive_dir)
    if len(selected) != EXPECTED_COUNT:
        raise RepackError(f"expected exactly {EXPECTED_COUNT} known metadata defects, found {len(selected)}")

    report = {"schema_version": 1, "selected_count": len(selected), "patched": [], "stale_records": []}
    for entry, source, original_metadata in selected:
        filename = source.name
        input_sha = _sha256(source)
        if entry.get("sha256") != input_sha:
            raise RepackError(f"candidate checksum does not match archive: {filename}")
        core_name = _core_name(filename)
        patched = archive_out / filename
        summary = repack(source, core_name, patched)
        delta = _expected_delta(original_metadata, summary["added"])
        proof = _proof_document(source, filename, input_sha, summary["output_sha256"], delta)
        proof_name = f"{filename}.proof.json"
        (proof_out / proof_name).write_text(
            json.dumps(proof, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
        record_files = []
        records = entry.get("verification", [])
        if not isinstance(records, list):
            raise RepackError(f"candidate verification must be an array: {filename}")
        for index, original in enumerate(records, 1):
            try:
                derived = _derive_record(original, input_sha, summary["output_sha256"],
                                         summary["added"], f"{EVIDENCE_DIR}/proofs/{proof_name}",
                                         support, root)
            except coverage.CoverageError as exc:
                report["stale_records"].append({"archive": filename, "profile_id": original.get("profile_id"),
                                                 "reason": str(exc)})
                continue
            record_name = f"{filename}.verification-{index}.json"
            (verification_out / record_name).write_text(
                json.dumps(derived, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            record_files.append(record_name)
        report["patched"].append({"archive": filename, "original_sha256": input_sha,
                                  "patched_sha256": summary["output_sha256"],
                                  "proof": f"proofs/{proof_name}",
                                  "derived_verification_records": record_files})
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_batch(args.root, args.output)
    print(json.dumps({"selected": report["selected_count"], "patched": len(report["patched"]),
                      "derived_records": sum(len(item["derived_verification_records"]) for item in report["patched"]),
                      "stale_records": report["stale_records"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RepackError, coverage.CoverageError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc))
