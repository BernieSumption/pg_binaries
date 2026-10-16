#!/usr/bin/env python3
"""Collect license texts for Homebrew libraries embedded in a pilot archive."""

import json
import pathlib
import shutil
import subprocess
import sys
import urllib.request


root = pathlib.Path(sys.argv[1]).resolve()
licenses = root / "LICENSES"
licenses.mkdir(exist_ok=True)
sources = json.loads((root / "bundled-dependencies.json").read_text())
formulas = {}
for library, source in sources.items():
    parts = pathlib.Path(source).parts
    if "Cellar" not in parts:
        raise SystemExit(f"cannot identify package owning {source}")
    index = parts.index("Cellar")
    name, version = parts[index + 1 : index + 3]
    formulas.setdefault((name, version), []).append(library)

known_urls = {
    "icu4c@78": "https://raw.githubusercontent.com/unicode-org/icu/main/LICENSE",
    "openssl@3": "https://raw.githubusercontent.com/openssl/openssl/master/LICENSE.txt",
    "lz4": "https://raw.githubusercontent.com/lz4/lz4/dev/lib/LICENSE",
    "zstd": "https://raw.githubusercontent.com/facebook/zstd/dev/LICENSE",
    "libxml2": "https://raw.githubusercontent.com/GNOME/libxml2/master/Copyright",
    "libxslt": "https://raw.githubusercontent.com/GNOME/libxslt/master/Copyright",
    "libgcrypt": "https://raw.githubusercontent.com/gpg/libgcrypt/master/COPYING.LIB",
    "libgpg-error": "https://raw.githubusercontent.com/gpg/libgpg-error/master/COPYING.LIB",
}
inventory = []
for (name, version), libraries in sorted(formulas.items()):
    prefix = pathlib.Path("/usr/local/Cellar") / name / version
    if not prefix.exists():
        prefix = pathlib.Path("/opt/homebrew/Cellar") / name / version
    candidates = sorted(
        p for p in prefix.rglob("*")
        if p.is_file() and p.name.lower() in {"license", "license.txt", "copying", "copyright"}
        and len(p.relative_to(prefix).parts) <= 5
    )
    target = licenses / f"{name.replace('@', '-')}-{version}.txt"
    if name == "e2fsprogs":
        if not all(library.startswith("libuuid") for library in libraries):
            raise SystemExit(f"e2fsprogs libraries need separate license review: {libraries}")
        origin = f"https://raw.githubusercontent.com/tytso/e2fsprogs/v{version}/lib/uuid/COPYING"
        urllib.request.urlretrieve(origin, target)
    elif candidates:
        shutil.copyfile(candidates[0], target)
        origin = str(candidates[0])
    elif name in known_urls:
        urllib.request.urlretrieve(known_urls[name], target)
        origin = known_urls[name]
    else:
        raise SystemExit(f"missing license text for bundled package {name} {version}")
    inventory.append({"package": name, "version": version, "libraries": libraries, "license_file": target.name, "license_source": origin})
(licenses / "inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
print(f"Collected {len(inventory)} dependency license texts")
