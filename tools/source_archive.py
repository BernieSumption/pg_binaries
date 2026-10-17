"""Look up validated upstream source archive identities from support metadata."""

import argparse
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SourceArchiveError(ValueError):
    """The requested source archive is unknown or its identity is invalid."""


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceArchiveError(f"cannot read source archive metadata {path}: {exc}") from exc


def _archive_record(record, component, version, archive_format):
    if not isinstance(record, dict):
        raise SourceArchiveError(f"no {archive_format} source archive for {component} {version}")
    url, digest = record.get("url"), record.get("sha256")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise SourceArchiveError(f"missing or invalid URL for {component} {version} {archive_format}")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise SourceArchiveError(f"missing or invalid SHA-256 for {component} {version} {archive_format}")
    return {"url": url, "sha256": digest}


def source_archive(component, version, archive_format, root=ROOT):
    """Return ``{"url", "sha256"}`` for a supported PostgreSQL or pgvector archive.

    PostgreSQL versions come from the release snapshot; extension versions come
    from support.json. The function intentionally rejects aliases and formats
    absent from the metadata.
    """
    root = Path(root)
    if component == "postgresql":
        snapshot = _read_json(root / "support" / "postgresql-releases.json")
        releases = snapshot.get("releases") if isinstance(snapshot, dict) else None
        row = next((item for item in releases or []
                    if isinstance(item, dict) and item.get("version") == version), None)
        if row is None:
            raise SourceArchiveError(f"unknown PostgreSQL release {version}")
        records = row.get("source_archives", {})
    elif component == "pgvector":
        support = _read_json(root / "support.json")
        try:
            records = support["extensions"]["pgvector"]["versions"][version]["source_archives"]
        except (KeyError, TypeError):
            raise SourceArchiveError(f"unknown pgvector release {version}") from None
    else:
        raise SourceArchiveError(f"unknown source component {component!r}")
    if not isinstance(records, dict) or archive_format not in records:
        raise SourceArchiveError(f"unsupported archive format {archive_format!r} for {component} {version}")
    return _archive_record(records[archive_format], component, version, archive_format)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=("postgresql", "pgvector"))
    parser.add_argument("version")
    parser.add_argument("archive_format")
    parser.add_argument("--field", choices=("url", "sha256"),
                        help="print one identity field; by default print both as JSON")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = source_archive(args.component, args.version, args.archive_format, args.root)
    except SourceArchiveError as exc:
        parser.error(str(exc))
    if args.field:
        print(result[args.field])
    else:
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
