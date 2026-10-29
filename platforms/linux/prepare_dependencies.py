#!/usr/bin/env python3
"""Install the system packages needed by a Linux build job."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from build_support.metadata import load_package


def requirements(component: str) -> list[str]:
    names = list(load_package(component).get("linux_apt_packages", []))
    path = ROOT / "platforms/linux/base-build-requirements.txt"
    for line in path.read_text(encoding="utf-8").splitlines():
        names.extend(line.split("#", 1)[0].split())
    return sorted(set(names))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component")
    parser.add_argument("--print", action="store_true", dest="print_only")
    args = parser.parse_args()
    names = requirements(args.component)
    if args.print_only:
        print(" ".join(names))
        return
    prefix = [] if os.geteuid() == 0 else ["sudo"]
    subprocess.run([*prefix, "apt-get", "update"], check=True)
    subprocess.run([*prefix, "apt-get", "install", "-y", "--no-install-recommends", *names], check=True)


if __name__ == "__main__":
    main()
