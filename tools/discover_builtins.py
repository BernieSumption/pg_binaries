#!/usr/bin/env python3
"""List built-in PostgreSQL SQL extensions from an extracted core prefix."""

import argparse
import json
from pathlib import Path
import re
import sys


class DiscoveryError(ValueError):
    """The extracted PostgreSQL prefix does not contain a valid extension directory."""


EXTENSION_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def discover_builtins(prefix):
    """Return SQL extension names advertised by ``share/extension/*.control``.

    ``prefix`` must contain only the core PostgreSQL build output; separately
    installed extensions must be merged after this discovery step.
    """
    directory = Path(prefix) / "share" / "extension"
    if not directory.is_dir():
        raise DiscoveryError(f"PostgreSQL extension directory does not exist: {directory}")

    names = []
    for path in directory.glob("*.control"):
        name = path.name[:-len(".control")]
        if not EXTENSION_NAME.fullmatch(name) or not path.is_file():
            raise DiscoveryError(f"malformed PostgreSQL extension control file: {path}")
        names.append(name)
    if not names:
        raise DiscoveryError(f"no PostgreSQL extension control files found in {directory}")
    return sorted(names)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path, help="extracted core PostgreSQL installation prefix")
    args = parser.parse_args()
    try:
        print(json.dumps(discover_builtins(args.prefix)))
        return 0
    except (OSError, DiscoveryError) as exc:
        print(f"discover_builtins: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
