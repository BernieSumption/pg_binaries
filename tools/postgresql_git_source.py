"""Read the pinned upstream PostgreSQL Git source identity for Windows builds."""

import argparse
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
OID = re.compile(r"^[0-9a-f]{40}$")


def source_checkout(version, root=ROOT):
    data = json.loads((Path(root) / "support" / "windows-postgresql-source-identities.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported Windows PostgreSQL source identity schema")
    checkout = data.get("releases", {}).get(version)
    if not isinstance(checkout, dict):
        raise ValueError(f"no pinned PostgreSQL Git source for {version}")
    repository, ref = checkout.get("repository"), checkout.get("ref")
    commit, tree = checkout.get("commit"), checkout.get("tree")
    if repository != "https://github.com/postgres/postgres.git":
        raise ValueError("PostgreSQL Git source repository is not the approved upstream")
    if ref != f"refs/tags/REL_{version.replace('.', '_')}":
        raise ValueError("PostgreSQL Git source ref does not match the release version")
    if not isinstance(commit, str) or not OID.fullmatch(commit) or not isinstance(tree, str) or not OID.fullmatch(tree):
        raise ValueError("PostgreSQL Git source requires full commit and tree object IDs")
    return {"repository": repository, "ref": ref, "commit": commit, "tree": tree}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(source_checkout(args.version, args.root), sort_keys=True))


if __name__ == "__main__":
    main()
