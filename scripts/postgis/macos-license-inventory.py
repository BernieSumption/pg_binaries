#!/usr/bin/env python3
"""Create the selected PostGIS macOS archive's dependency and data inventory."""

import hashlib
import csv
from urllib.request import urlopen
import json
from pathlib import Path
import re
import subprocess
import sys

root, core_root, brew_prefix, postgis_archive, gdal_archive = map(Path, sys.argv[1:])
root = root.resolve(); core_root = core_root.resolve()
dependencies = json.loads((root / "bundled-dependencies.json").read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


formula_libs = {}
for library, source in dependencies.items():
    parts = Path(source).parts
    if "Cellar" not in parts:
        if Path(source).name.startswith("libgdal"):
            continue
        raise SystemExit(f"unmapped bundled library source: {source}")
    index = parts.index("Cellar")
    if len(parts) <= index + 2:
        raise SystemExit(f"cannot identify Homebrew formula for {source}")
    name, version = parts[index + 1:index + 3]
    formula_libs.setdefault((name, version), set()).add(library)

info = json.loads(command("brew", "info", "--json=v2", *sorted({name for name, _ in formula_libs})))
formula_data = {item["name"]: item for item in info.get("formulae", [])}
expected_formulae = {
    "boost": ("1.92.0", "BSL-1.0"),
    "geos": ("3.15.0", "LGPL-2.1-or-later"),
    "gmp": ("6.3.0", "LGPL-3.0-or-later OR GPL-2.0-or-later"),
    "jpeg-turbo": ("3.2.0", "IJG AND Zlib AND BSD-3-Clause"),
    "json-c": ("0.19", "MIT"),
    "libxml2": ("2.15.4", "MIT"),
    "libtiff": ("4.7.2", "libtiff"),
    "mpfr": ("4.2.2", "LGPL-3.0-or-later"),
    "pcre2": ("10.48", "BSD-3-Clause"),
    "proj": ("9.8.1", "MIT"),
    "protobuf-c": ("1.5.2_19", "BSD-2-Clause"),
    "sfcgal": ("2.3.0_1", "LGPL-2.0-or-later"),
    "webp": ("1.6.0", "BSD-3-Clause"),
    "xz": ("5.8.3", "0BSD AND GPL-2.0-or-later"),
}
if set(name for name, _ in formula_libs) != set(expected_formulae):
    raise SystemExit(f"incremental Homebrew closure changed: {sorted(formula_libs)}")
components = []
for (name, version), libraries in sorted(formula_libs.items()):
    formula = formula_data.get(name)
    if not formula or formula.get("versions", {}).get("stable") != version:
        raise SystemExit(f"Homebrew metadata does not match bundled {name} {version}")
    prefix = Path(command("brew", "--prefix", name).strip())
    candidates = sorted(path for path in prefix.rglob("*") if path.is_file()
        and (path.name.lower() in {"license", "license.txt", "license.md", "license_1_0.txt", "copying", "copyright"}
             or path.name.lower().startswith(("copying.", "license.")))
        and len(path.relative_to(prefix).parts) <= 6)
    if not candidates:
        raise SystemExit(f"no licence text found in Homebrew package {name} {version}")
    license_names = []
    for index, candidate in enumerate(candidates):
        license_name = f"{name}-{version}-license-{index + 1}.txt"
        (root / "LICENSES" / license_name).write_bytes(candidate.read_bytes())
        license_names.append(license_name)
    stable = formula.get("urls", {}).get("stable", {})
    source_url, source_sha = stable.get("url"), stable.get("checksum")
    if not source_url or not re.fullmatch(r"[0-9a-f]{64}", source_sha or ""):
        raise SystemExit(f"Homebrew source identity is incomplete for {name} {version}")
    paths = [f"lib/{lib}" for lib in sorted(libraries)]
    license_expr = formula.get("license")
    if not license_expr:
        raise SystemExit(f"Homebrew licence expression missing for {name} {version}")
    if (version, license_expr) != expected_formulae[name]:
        raise SystemExit(f"unreviewed Homebrew version or licence for {name}: {version}, {license_expr}")
    primary = candidates[0]
    # Homebrew describes the whole source package; narrow mixed package terms
    # to the exact shared libraries included in this archive.
    library_expression = license_expr
    review_note = "The exact dynamically linked libraries are listed by payload path."
    if name == "gmp":
        library_expression = "LGPL-3.0-or-later"
        review_note = "GMP's shared libraries use the LGPL-3.0-or-later alternative; GPL-2.0-or-later applies to other package uses."
        primary = next((path for path in candidates if "lesser" in path.name.lower()), None)
        if primary is None: raise SystemExit("GMP shared-library LGPL text is missing")
    elif name == "xz" and all("liblzma" in library.lower() for library in libraries):
        library_expression = "0BSD"
        review_note = "Only liblzma is included; the package's GPL-2.0-or-later term applies to the xz utilities, which are excluded."
        primary = next((path for path in candidates if "0bsd" in path.name.lower()), None)
        if primary is None: raise SystemExit("xz liblzma 0BSD text is missing")
    copyleft = "LGPL" in library_expression or "GPL" in library_expression
    formula_revision = command("git", "-C", command("brew", "--repository", "homebrew/core").strip(),
                               "rev-parse", "HEAD").strip()
    if not formula_revision or not re.fullmatch(r"[0-9a-f]{40}", formula_revision):
        raise SystemExit(f"Homebrew formula revision is missing for {name}")
    formula_url = f"https://github.com/Homebrew/homebrew-core/blob/{formula_revision}/Formula/{name[0]}/{name}.rb"
    source_links = [source_url, formula_url,
                    f"https://github.com/BernieSumption/pg_binaries/blob/{__import__('os').environ['GITHUB_SHA']}/scripts/postgis/macos-build-publication.sh"]
    review_basis = (f"Homebrew {name} {version} formula at {formula_url} identifies the source archive and package terms. {review_note} "
                    "The archive includes the applicable notice texts. No source modifications are made.")
    if copyleft:
        review_basis += " The shared LGPL library is dynamically linked and can be replaced by users; corresponding source and build material are linked for the LGPL source and relinking requirements."
    else:
        review_basis += " The applied library terms require notices but no source delivery for this binary distribution."
    components.append({
        "component": f"homebrew-library-{name}", "package": name, "version": version,
        "license_expression": library_expression, "package_license_expression": license_expr,
        "payload_paths": paths,
        "license_file": f"LICENSES/{license_names[candidates.index(primary)]}",
        "additional_license_files": [f"LICENSES/{filename}" for filename in license_names[1:]],
        "source_url": source_url, "source_sha256": source_sha, "source_revision": formula_revision,
        "license_source": str(primary),
        "redistribution_review": {
            "status": "resolved",
            "basis": review_basis,
            "source_obligation": "source-links" if copyleft else "none",
            **({"source_links": source_links} if copyleft else {}),
        },
    })

postgis_sha = sha(postgis_archive)
gdal_sha = sha(gdal_archive)
postgis_license = root / "LICENSES/PostGIS.txt"
gdal_license = root / "LICENSES/GDAL.txt"
components.insert(0, {
    "component": "postgis", "version": "3.6.4", "source_url": "https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz",
    "source_sha256": postgis_sha,
    "payload_paths": sorted([p.relative_to(root).as_posix() for p in (root / "lib").glob("postgis*.*")]
                            + ["share/extension"]),
    "license_file": "LICENSES/PostGIS.txt",
    "license_source": "https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz",
    "license_expression": "GPL-2.0-or-later",
    "redistribution_review": {"status":"resolved", "basis":"PostGIS 3.6.4 COPYING declares GPL-2.0-or-later. This archive distributes unmodified upstream source-built binaries and includes the complete license text. The corresponding source is the exact checksum-pinned 3.6.4 source archive; GDAL's source and the public build recipe cover the combined build. No source modifications are made.", "source_obligation":"source-links",
                               "source_links":["https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz",
                                               "https://download.osgeo.org/gdal/3.13.3/gdal-3.13.3.tar.gz",
                                               f"https://github.com/BernieSumption/pg_binaries/blob/{__import__('os').environ['GITHUB_SHA']}/scripts/postgis/macos-build-publication.sh"]},
})
gdal_libs = sorted(p.name for p in (root / "lib").glob("libgdal*.dylib"))
if len(gdal_libs) != 1:
    raise SystemExit(f"expected one source-built GDAL library, found {gdal_libs}")
components.append({
    "component":"gdal", "version":"3.13.3", "source_url":"https://download.osgeo.org/gdal/3.13.3/gdal-3.13.3.tar.gz",
    "source_sha256":gdal_sha, "payload_paths":[f"lib/{gdal_libs[0]}", "share/gdal"],
    "license_file":"LICENSES/GDAL.txt", "license_source":"https://gdal.org/en/stable/license.html",
    "redistribution_review":{"status":"resolved", "basis":"GDAL 3.13.3 LICENSE.TXT includes its MIT-style terms and bundled third-party notices; the build disables optional drivers and retains its full licence file.", "source_obligation":"none"},
})
proj_license = next((Path(command("brew", "--prefix", "proj").strip()) / name
                     for name in ("COPYING", "share/doc/proj/COPYING")
                     if (Path(command("brew", "--prefix", "proj").strip()) / name).is_file()), None)
if proj_license is None:
    raise SystemExit("PROJ licence text is missing")
proj_formula = formula_data.get("proj", {})
proj_resource = next((resource for resource in proj_formula.get("resources", [])
                      if "proj-data" in (resource.get("name", "").lower()
                                          + resource.get("url", "").lower())), None)
if proj_resource is None:
    raise SystemExit("Homebrew PROJ metadata does not identify its installed datum-grid source")
resource_url, resource_sha = proj_resource.get("url"), proj_resource.get("checksum")
if not resource_url or not re.fullmatch(r"[0-9a-f]{64}", resource_sha or ""):
    raise SystemExit("PROJ-data source URL or checksum is missing")
proj_data_dir = Path(command("brew", "--prefix", "proj").strip()) / "share/proj"
for name in ("README.DATA", "copyright_and_licenses.csv"):
    source = proj_data_dir / name
    if not source.is_file() or not source.stat().st_size:
        raise SystemExit(f"installed PROJ data is missing {name}")
    (root / "LICENSES" / f"PROJ-data-{name}").write_bytes(source.read_bytes())
with (proj_data_dir / "copyright_and_licenses.csv").open(newline="", encoding="utf-8") as stream:
    rows = list(csv.reader(stream))
rows_by_name = {row[0].strip(): row for row in rows if row and row[0].strip().lower() not in {"filename", "file"}}
listed = set(rows_by_name)
data_files = {path.name for path in proj_data_dir.iterdir() if path.is_file()
              and path.name not in {"copyright_and_licenses.csv", "proj.db", "proj.ini"}}
if not data_files or not data_files.issubset(listed):
    raise SystemExit(f"PROJ copyright data does not cover installed files: {sorted(data_files-listed)[:10]}")
(root / "LICENSES/PROJ-data.txt").write_bytes(proj_license.read_bytes())
license_urls = {
    "CC-BY-3.0": "https://raw.githubusercontent.com/spdx/license-list-data/v3.25/text/CC-BY-3.0.txt",
    "CC-BY-4.0": "https://raw.githubusercontent.com/spdx/license-list-data/v3.25/text/CC-BY-4.0.txt",
    "CC-BY-SA-3.0": "https://raw.githubusercontent.com/spdx/license-list-data/v3.25/text/CC-BY-SA-3.0.txt",
    "CC-BY-SA-4.0": "https://raw.githubusercontent.com/spdx/license-list-data/v3.25/text/CC-BY-SA-4.0.txt",
    "CC0-1.0": "https://raw.githubusercontent.com/spdx/license-list-data/v3.25/text/CC0-1.0.txt",
    "BSD-2-Clause": "https://raw.githubusercontent.com/spdx/license-list-data/v3.25/text/BSD-2-Clause.txt",
    "OGL-Canada-2.0": "https://open.canada.ca/en/open-government-licence-canada",
    "Data licence Germany - attribution - version 2.0": "https://www.govdata.de/dl-de/by-2-0",
}
license_sources = {}
for row in rows_by_name.values():
    if len(row) < 3: raise SystemExit("malformed PROJ copyright and licence row")
    expression = row[2].strip()
    if expression in {"Public domain", "Free redistribution is allowed and welcome", "BSD-2-Clause", "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-3.0", "CC-BY-SA-4.0", "CC0-1.0", "OGL-Canada-2.0", "Data licence Germany - attribution - version 2.0"}:
        if expression == "BSD-2-Clause" or expression.startswith("CC-") or expression == "OGL-Canada-2.0" or expression.startswith("Data licence Germany"):
            license_sources[expression] = license_urls[expression]
        continue
    if expression.startswith("Open License France - "):
        license_sources[expression] = expression.removeprefix("Open License France - ").strip()
        continue
    raise SystemExit(f"unreviewed PROJ-data licence: {expression}")
license_records=[]
for index,(expression,url) in enumerate(sorted(license_sources.items()),1):
    with urlopen(url,timeout=30) as response: text=response.read()
    if not text: raise SystemExit(f"empty PROJ data licence text for {expression}")
    filename=f"PROJ-data-license-{index}.txt"
    (root/"LICENSES"/filename).write_bytes(text)
    license_records.append({"expression":expression,"url":url,"file":f"LICENSES/{filename}","sha256":hashlib.sha256(text).hexdigest()})
components.append({
    "component":"proj-data", "version":proj_formula.get("versions",{}).get("stable"),
    "payload_paths":["share/proj"], "license_file":"LICENSES/PROJ-data.txt",
    "source_url":resource_url, "source_sha256":resource_sha,
    "source_components":[{"component":"PROJ","version":proj_formula.get("versions",{}).get("stable"),
                           "source_url":proj_formula.get("urls",{}).get("stable",{}).get("url"),
                           "source_sha256":proj_formula.get("urls",{}).get("stable",{}).get("checksum")}],
    "additional_license_files":["LICENSES/PROJ-data-README.DATA", "LICENSES/PROJ-data-copyright_and_licenses.csv", *[item["file"] for item in license_records]],
    "data_licence_texts":license_records,
    "license_source":"https://github.com/OSGeo/PROJ-data/blob/master/README.DATA",
    "redistribution_review":{"status":"resolved", "basis":"The exact PROJ-data source archive is checksum-verified. Its upstream README and per-file copyright/licence mapping accompany the grids, along with the applicable licence texts and attribution records. The included data terms require notices and attribution but no source delivery.", "source_obligation":"none"},
})
reused=[]
core_inventory=json.loads((core_root/"LICENSES/inventory.json").read_text())
for library in ("libxml2.16.dylib","libzstd.1.5.7.dylib"):
    core_file=core_root/"lib"/library
    if not core_file.is_file(): raise SystemExit(f"checked core lacks expected reusable {library}")
    owner=next((item for item in core_inventory["components"] if library in item.get("libraries",[])),None)
    if owner is None or owner.get("redistribution_review",{}).get("status")!="resolved":
        raise SystemExit(f"checked core has no resolved licence record for {library}")
    reused.append({"library":library,"sha256":sha(core_file),"core_component":owner["component"],
                   "core_version":owner["version"],"license_file":"LICENSES/"+owner["license_file"]})
inventory={"schema_version":1,"reused_core_dependencies":reused,"components":components}
(root/"LICENSES/postgis-inventory.json").write_text(json.dumps(inventory,indent=2,sort_keys=True)+"\n")
print(f"Recorded {len(components)} PostGIS macOS redistribution components")
