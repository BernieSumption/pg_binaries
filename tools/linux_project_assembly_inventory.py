"""Write an exact-hash, temporary inventory for selected Linux project archives."""

import argparse
import hashlib
import json
from pathlib import Path
import re


class ProjectAssemblyInventoryError(ValueError):
    pass


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(values, label):
    result = {}
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key or not item or key in result:
            raise ProjectAssemblyInventoryError(f"invalid or duplicate {label}: {value!r}")
        result[key] = item
    return result


def write_inventory(support, postgresql_version, platform, project_archives,
                    project_versions, output):
    if not re.fullmatch(r"\d+\.\d+", postgresql_version):
        raise ProjectAssemblyInventoryError("PostgreSQL version must be major.minor")
    if platform not in {"linux-x86_64", "linux-arm64"}:
        raise ProjectAssemblyInventoryError("platform must be linux-x86_64 or linux-arm64")
    if not project_archives or set(project_archives) != set(project_versions):
        raise ProjectAssemblyInventoryError("each selected project needs exactly one archive and version")

    extensions = {}
    for project, archive_value in project_archives.items():
        details = support.get("extensions", {}).get(project)
        version = project_versions[project]
        if not isinstance(details, dict) or version not in details.get("versions", {}):
            raise ProjectAssemblyInventoryError(f"unknown project/version: {project} {version}")
        archive = Path(archive_value)
        slug = project.lower().replace(" ", "_")
        expected_name = f"{slug}-{version}-postgresql-{postgresql_version}-{platform}.tar.gz"
        if archive.name != expected_name or not archive.is_file():
            raise ProjectAssemblyInventoryError(f"archive must exist and be named {expected_name}")
        download = {
            "url": f"https://assembly.invalid/{expected_name}",
            "sha256": _sha256(archive),
            "postgresql_support": {"from": postgresql_version, "to": postgresql_version},
        }
        for sql_name in details["sql_names"]:
            extensions.setdefault(sql_name, {})[version] = {
                "downloads": {platform: [download]}}

    inventory = {"schema_version": 1, "candidate_status": "assembly-only",
                 "extensions": extensions}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    return inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--support", type=Path, required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--project-archive", action="append", default=[], metavar="PROJECT=PATH")
    parser.add_argument("--project-version", action="append", default=[], metavar="PROJECT=VERSION")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        support = json.loads(args.support.read_text(encoding="utf-8"))
        write_inventory(support, args.postgresql_version, args.platform,
                        _mapping(args.project_archive, "project archive"),
                        _mapping(args.project_version, "project version"), args.output)
    except (OSError, json.JSONDecodeError, ProjectAssemblyInventoryError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
