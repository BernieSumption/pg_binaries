"""Write machine-readable evidence for the checked pgvector planner route."""

import argparse
import json
from pathlib import Path


def build_evidence(request, candidate_manifest=None, dispatch_plan=None, *,
                   retrieval_outcome="not_attempted", validation_outcome="not_attempted",
                   dispatch_outcome="not_written", exit_code=None, errors=None):
    """Return one compact record describing candidate checks and the final plan."""
    manifest = candidate_manifest if isinstance(candidate_manifest, dict) else {}
    target = manifest.get("target", {})
    source = manifest.get("source", {})
    hashes = manifest.get("sha256", {})
    archives = {}
    if isinstance(hashes, dict):
        for name, digest in hashes.items():
            if (isinstance(name, str) and name.endswith(".tar.gz")
                    and (name.startswith("postgresql-") or name.startswith("pgvector-"))):
                archives[name] = digest
    return {
        "schema_version": 1,
        "request": request,
        "candidate": {
            "retrieval_outcome": retrieval_outcome,
            "validation_outcome": validation_outcome,
            "target": target,
            "source": source,
            "archive_sha256": archives,
        },
        "dispatch": {
            "outcome": dispatch_outcome,
            "exit_code": exit_code,
            "plan": dispatch_plan,
        },
        "errors": errors or {"retrieval": None, "validation": None, "dispatch": None},
    }


def _read_json(path):
    if path is None or not Path(path).is_file():
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--dispatch-plan", type=Path)
    parser.add_argument("--retrieval-outcome", required=True)
    parser.add_argument("--validation-outcome", required=True)
    parser.add_argument("--dispatch-outcome", required=True)
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--retrieval-error-file", type=Path)
    parser.add_argument("--validation-error-file", type=Path)
    parser.add_argument("--dispatch-error-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    errors = {}
    for key in ("retrieval", "validation", "dispatch"):
        path = getattr(args, key + "_error_file")
        message = (path.read_text(encoding="utf-8", errors="replace")[-4000:].strip()
                   if path and path.is_file() else "")
        errors[key] = message or None
    record = build_evidence(
        _read_json(args.request), _read_json(args.candidate_manifest), _read_json(args.dispatch_plan),
        retrieval_outcome=args.retrieval_outcome, validation_outcome=args.validation_outcome,
        dispatch_outcome=args.dispatch_outcome, exit_code=args.exit_code, errors=errors)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
