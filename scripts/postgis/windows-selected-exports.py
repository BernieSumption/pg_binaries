#!/usr/bin/env python3
"""Write a MinGW module-definition file from the selected PostgreSQL executable."""

import argparse
from pathlib import Path
import re
import subprocess


EXPORT = re.compile(r"^\s*\[\s*\d+\s*\]\s+\+base\[\s*\d+\s*\]\s+[0-9a-fA-F]+\s+(\S+)\s*$")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = subprocess.run(["objdump", "-p", str(args.executable)], capture_output=True,
                            text=True, check=True)
    section = result.stdout.split("[Ordinal/Name Pointer] Table", 1)
    if len(section) != 2:
        parser.error("selected PostgreSQL executable has no readable export table")
    exports = sorted({match.group(1) for line in section[1].splitlines()
                      if (match := EXPORT.match(line))})
    required = {"GetNumConfigOptions", "MemoryContextContains"}
    if not required <= set(exports):
        parser.error("selected PostgreSQL executable does not export required PostGIS symbols")
    args.output.write_text("EXPORTS\n" + "\n".join(exports) + "\n", encoding="utf-8")
    print(f"Selected PostgreSQL executable exports {len(exports)} symbols")


if __name__ == "__main__":
    main()
