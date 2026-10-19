"""Bind a retrieved HypoPG bundle to current records and build inputs."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile

import linux_core_candidate
import linux_core_resolution
import linux_extension_candidate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/hypopg"))
import build_inputs as hypopg_build_inputs


class PlannerAdapterError(ValueError):
    pass


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_candidate_inputs(manifest, root=ROOT, *, core_base_image_digest,
                             core_builder_packages_sha256,
                             hypopg_builder_packages_sha256):
    """Return planner overlay after validating bundle, producer, core and recipe."""
    root = Path(root)
    if isinstance(manifest, (str, Path)):
        try:
            manifest = json.loads(Path(manifest).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PlannerAdapterError(f"cannot read candidate bundle manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise PlannerAdapterError("candidate bundle manifest must be an object")
    try:
        target = manifest["target"]
        pg, platform = target["postgresql_version"], target["platform"]
        architecture = platform.removeprefix("linux-")
        extension_version = hypopg_build_inputs.VERSION
        core_name = f"postgresql-{pg}-{platform}.tar.gz"
        extension_name = (f"hypopg-{extension_version}-postgresql-{pg}-{platform}.tar.gz")
        core_path = Path(manifest["files"][core_name])
        identity = hypopg_build_inputs.selected_identity(
            _sha256(core_path), hypopg_builder_packages_sha256, pg, architecture, root)
        validated = linux_extension_candidate.validate_candidate(
            manifest, root=root, core_name=core_name, extension_name=extension_name,
            core_component="postgresql", core_version=pg,
            extension_component="hypopg", extension_version=extension_version,
            extension_project="hypopg", extension_display_name="HypoPG",
            expected_build_inputs=identity,
        )
    except (ValueError, OSError, TypeError, KeyError) as exc:
        raise PlannerAdapterError(f"HypoPG candidate rejected: {exc}") from exc

    core_path = Path(validated["core"]["path"])
    files = manifest["files"]
    source = manifest["source"]
    resolution_path = Path(files["core-resolution.json"])
    if _sha256(resolution_path) != manifest.get("sha256", {}).get("core-resolution.json"):
        raise PlannerAdapterError("core resolution differs from candidate manifest SHA-256")
    try:
        resolution = linux_core_resolution.validate_resolution(
            resolution_path, core_path, pg, architecture, root=root)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        raise PlannerAdapterError(f"core resolution provenance rejected: {exc}") from exc
    provenance = resolution["provenance"]
    origin = resolution.get("origin")
    if origin == "built" and (
            provenance.get("run_id") != str(source["run_id"])
            or provenance.get("run_attempt") != source["run_attempt"]
            or provenance.get("run_sha", "").lower() != source["head_sha"].lower()
            or provenance.get("repository", "").casefold() != source["repository"].casefold()):
        raise PlannerAdapterError("built core resolution differs from candidate producer")
    if origin not in {"built", "reused"}:
        raise PlannerAdapterError("core resolution origin is invalid")

    discovery = {"schema_version": 1, "archives": [{
        "component": "postgresql", "version": pg, "postgresql_version": pg,
        "platform": platform, "path": str(core_path), "sha256": _sha256(core_path),
        "source": {"provider": "github-actions", "run_id": str(source["run_id"]),
                   "run_attempt": source["run_attempt"], "head_sha": source["head_sha"],
                   "artifact_name": source["artifact_name"]},
    }]}
    with tempfile.TemporaryDirectory(prefix="hypopg-planner-") as temporary:
        discovery_path = Path(temporary) / "core-discovery.json"
        discovery_path.write_text(json.dumps(discovery), encoding="utf-8")
        try:
            core_check = linux_core_candidate.validate_candidate(
                discovery_path, core_path, pg, core_base_image_digest,
                core_builder_packages_sha256, root=root, architecture=architecture,
                artifact_name_template=(f"hypopg-linux-selected-{pg}-{architecture}-{{run_id}}"))
        except (ValueError, OSError, TypeError, KeyError) as exc:
            raise PlannerAdapterError(f"core candidate rejected: {exc}") from exc

    record = validated["verification_records"][0]
    record_name = manifest["extension_record"]
    run_source = {"provider": "github-actions", "run_id": str(source["run_id"]),
                  "artifact_name": source["artifact_name"],
                  "expires_at": source["artifact_expires_at"]}
    checked_core = {
        **validated["core"], "source_claims": run_source,
        "source_revision": core_check["source_revision"],
        "build_inputs": linux_extension_candidate._metadata(
            core_path, "postgresql/manifest.json")["builder_inputs"],
        "validation": "linux-core-candidate-and-current-inputs",
    }
    checked_extension = {
        **validated["extension"], "source_claims": run_source,
        "build_input_identity": identity,
        "validation": "current-hypopg-build-input-identity",
    }
    current_record = {**record, "_profile_current": True, "_record_file": record_name}
    return {"planner_overlay": {"schema_version": 1,
                                 "candidate_archives": [checked_core, checked_extension],
                                 "verification_records": [current_record]}}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--core-base-image-digest", required=True)
    parser.add_argument("--core-builder-packages-sha256", required=True)
    parser.add_argument("--hypopg-builder-packages-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = checked_candidate_inputs(
            args.manifest, args.root, core_base_image_digest=args.core_base_image_digest,
            core_builder_packages_sha256=args.core_builder_packages_sha256,
            hypopg_builder_packages_sha256=args.hypopg_builder_packages_sha256)
    except PlannerAdapterError as exc:
        print(f"hypopg-planner-adapter: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
