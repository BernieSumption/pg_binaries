#!/usr/bin/env python3
"""Create the selected PostGIS macOS archive's dependency and data inventory."""

import hashlib
import csv
import json
from pathlib import Path
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

expected_formulae = {
    "boost": ("1.92.0", "BSL-1.0"),
    "geos": ("3.15.0", "LGPL-2.1-or-later"),
    "gmp": ("6.3.0", "LGPL-3.0-or-later OR GPL-2.0-or-later"),
    "jpeg-turbo": ("3.2.0", "IJG AND Zlib AND BSD-3-Clause"),
    "json-c": ("0.19", "MIT"),
    "libtiff": ("4.7.2", "libtiff"),
    "mpfr": ("4.2.2", "LGPL-3.0-or-later"),
    "proj": ("9.8.1", "MIT"),
    "protobuf-c": ("1.5.2_19", "BSD-2-Clause"),
    "sfcgal": ("2.3.0_1", "LGPL-2.0-or-later"),
    "webp": ("1.6.0", "BSD-3-Clause"),
    "xz": ("5.8.3", "0BSD AND GPL-2.0-or-later"),
    "zstd": ("1.5.7_1", "(BSD-3-Clause OR GPL-2.0-only) AND BSD-2-Clause AND MIT"),
}


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def formula_path(name, source, formula):
    value = formula.get("ruby_source_path") or source.get("path")
    if not isinstance(value, str) or not value.startswith("Formula/") or not value.endswith(".rb"):
        value = f"Formula/{name[0]}/{name}.rb"
    path = Path(value)
    if not path.is_relative_to("Formula") or path.suffix != ".rb":
        raise SystemExit(f"invalid Homebrew formula path for {name}: {value}")
    return path.as_posix()


def formula_url(name, source, formula):
    return f"https://github.com/Homebrew/homebrew-core/blob/{source['tap_git_head']}/{formula_path(name, source, formula)}"


def proj_data_source(formula, source):
    for resource in formula.get("resources", []):
        identity = (resource.get("name", "") + resource.get("url", "")).lower()
        if "proj-data" in identity:
            return resource.get("url"), resource.get("checksum")
    path = formula_path("proj", source, formula)
    url = f"https://raw.githubusercontent.com/Homebrew/homebrew-core/{source['tap_git_head']}/{path}"
    with urlopen(url, timeout=30) as response:
        content = response.read().decode("utf-8")
    for match in re.finditer(r"^\s{2}resource\s+['\"](?P<name>[^'\"]+)['\"]\s+do(?P<body>.*?)(?=^\s{2}end\s*$)", content, re.M | re.S):
        body = match.group("body")
        source_url = re.search(r"^\s{4}url\s+['\"]([^'\"]+)['\"]", body, re.M)
        source_sha = re.search(r"^\s{4}sha256\s+['\"]([0-9a-f]{64})['\"]", body, re.M)
        if "proj-data" in (match.group("name") + (source_url.group(1) if source_url else "")).lower():
            return (source_url.group(1) if source_url else None,
                    source_sha.group(1) if source_sha else None)
    return None, None


def formula_package_version(formula):
    stable = formula.get("versions", {}).get("stable")
    revision = formula.get("revision", 0)
    if not isinstance(stable, str) or not isinstance(revision, int):
        return None
    return stable if revision == 0 else f"{stable}_{revision}"


if sys.argv[1:] == ["--preflight"]:
    info = json.loads(command("brew", "info", "--json=v2", *sorted(expected_formulae)))
    formula_data = {item["name"]: item for item in info.get("formulae", [])}
    urls = []
    for name, (version, license_expr) in sorted(expected_formulae.items()):
        formula = formula_data.get(name)
        if not formula or (formula_package_version(formula), formula.get("license")) != (version, license_expr):
            raise SystemExit(f"unreviewed Homebrew formula {name}: expected {version} / {license_expr}")
        stable = formula.get("urls", {}).get("stable", {})
        if not stable.get("url") or not re.fullmatch(r"[0-9a-f]{64}", stable.get("checksum") or ""):
            raise SystemExit(f"incomplete Homebrew source identity for {name} {version}")
        prefix = Path(command("brew", "--prefix", name).strip()).resolve()
        if prefix.name != version:
            raise SystemExit(f"Homebrew keg version mismatch for {name}: expected {version}, found {prefix.name}")
        receipt_path = prefix / "INSTALL_RECEIPT.json"
        if not receipt_path.is_file(): raise SystemExit(f"missing Homebrew receipt for {name} {version}")
        receipt = json.loads(receipt_path.read_text()); source = receipt.get("source", {})
        if (source.get("tap") != "homebrew/core" or source.get("tap_git_head") != formula.get("tap_git_head")
                or not re.fullmatch(r"[0-9a-f]{40}", source.get("tap_git_head", ""))):
            raise SystemExit(f"Homebrew formula revision mismatch for {name} {version}")
        urls.append((name, formula_url(name, source, formula)))
        candidates = [path for path in prefix.rglob("*") if path.is_file()
            and (path.name.lower() in {"license", "license.txt", "license.md", "license_1_0.txt", "copying", "copyright"}
                 or path.name.lower().startswith(("copying.", "license.")))
            and len(path.relative_to(prefix).parts) <= 6]
        print(f"{name} {version}: {'notice text found' if candidates else 'no notice text; declaration evidence required'}")
        if name == "proj":
            data_url, data_sha = proj_data_source(formula, source)
            if not data_url or not re.fullmatch(r"[0-9a-f]{64}", data_sha or ""):
                raise SystemExit("receipt-pinned PROJ formula does not identify a checksum-pinned PROJ-data source")
            urls.append(("proj-data", data_url))
            data_dir = prefix / "share/proj"
            for filename in ("README.DATA", "copyright_and_licenses.csv", "proj.db"):
                if not (data_dir / filename).is_file():
                    raise SystemExit(f"installed PROJ data is missing {filename}")
            print(f"PROJ datum grids: checksum-pinned source metadata found ({data_sha})")
    def check_formula_url(item):
        name, url = item
        request = Request(url, method="HEAD", headers={"User-Agent": "pg_binaries-licence-preflight"})
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as error:
            raise RuntimeError(f"{name}: receipt-pinned formula URL returned {error.code}: {url}") from error
        with response:
            if response.status != 200: raise RuntimeError(f"Homebrew formula source URL returned {response.status}: {url}")
        return name
    with ThreadPoolExecutor(max_workers=8) as executor:
        for name in executor.map(check_formula_url, urls):
            print(f"{name}: receipt-pinned formula URL verified")
    raise SystemExit(0)

if len(sys.argv) != 6:
    raise SystemExit("usage: macos-license-inventory.py PACKAGE CORE_ROOT BREW_PREFIX POSTGIS_SOURCE GDAL_SOURCE")
root, core_root, brew_prefix, postgis_archive, gdal_archive = map(Path, sys.argv[1:])
root = root.resolve(); core_root = core_root.resolve()
dependencies = json.loads((root / "bundled-dependencies.json").read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
if set(name for name, _ in formula_libs) != set(expected_formulae):
    raise SystemExit(f"incremental Homebrew closure changed: {sorted(formula_libs)}")
components = []
for (name, version), libraries in sorted(formula_libs.items()):
    formula = formula_data.get(name)
    if not formula or formula_package_version(formula) != version:
        raise SystemExit(f"Homebrew metadata does not match bundled {name} {version}")
    prefix = Path(command("brew", "--prefix", name).strip())
    keg = prefix.resolve()
    receipt_path = keg / "INSTALL_RECEIPT.json"
    if not receipt_path.is_file(): raise SystemExit(f"Homebrew install receipt is missing for {name} {version}")
    receipt = json.loads(receipt_path.read_text())
    source_identity = receipt.get("source", {})
    formula_revision = source_identity.get("tap_git_head")
    if (source_identity.get("tap") != "homebrew/core" or not formula_revision
            or not re.fullmatch(r"[0-9a-f]{40}", formula_revision)):
        raise SystemExit(f"installed Homebrew formula revision is missing for {name} {version}")
    if formula.get("tap_git_head") != formula_revision:
        raise SystemExit(f"Homebrew API metadata does not match installed formula revision for {name} {version}")
    formula_url = f"https://github.com/Homebrew/homebrew-core/blob/{formula_revision}/{formula_path(name, source_identity, formula)}"
    stable = formula.get("urls", {}).get("stable", {})
    source_url, source_sha = stable.get("url"), stable.get("checksum")
    if not source_url or not re.fullmatch(r"[0-9a-f]{64}", source_sha or ""):
        raise SystemExit(f"Homebrew source identity is incomplete for {name} {version}")
    license_expr = formula.get("license")
    if not license_expr:
        raise SystemExit(f"Homebrew licence expression missing for {name} {version}")
    candidates = sorted(path for path in prefix.rglob("*") if path.is_file()
        and (path.name.lower() in {"license", "license.txt", "license.md", "license_1_0.txt", "copying", "copyright"}
             or path.name.lower().startswith(("copying.", "license.")))
        and len(path.relative_to(prefix).parts) <= 6)
    license_names = []
    for index, candidate in enumerate(candidates):
        license_name = f"{name}-{version}-license-{index + 1}.txt"
        (root / "LICENSES" / license_name).write_bytes(candidate.read_bytes())
        license_names.append(license_name)
    if not candidates:
        evidence_name = f"{name}-{version}-licence-declaration.txt"
        evidence = (f"Package: {name} {version}\nSource: {source_url}\nSource SHA-256: {source_sha}\n"
                    f"Declared licence: {license_expr}\nUpstream declaration: {formula_url}\n")
        (root / "LICENSES" / evidence_name).write_text(evidence)
        license_names.append(evidence_name)
    paths = [f"lib/{lib}" for lib in sorted(libraries)]
    if (version, license_expr) != expected_formulae[name]:
        raise SystemExit(f"unreviewed Homebrew version or licence for {name}: {version}, {license_expr}")
    primary = candidates[0] if candidates else None
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
    elif name == "zstd" and all("libzstd" in library.lower() for library in libraries):
        library_expression = "BSD-3-Clause"
        review_note = "Only libzstd is included. Zstandard offers BSD-3-Clause or GPL-2.0-only terms; this distribution uses the included BSD-3-Clause notice. The other formula terms cover excluded package files."
        primary = next((path for path in candidates if path.name.lower() == "license"), None)
        if primary is None: raise SystemExit("zstd BSD-3-Clause licence text is missing")
    if primary is None:
        primary_index = 0
        license_source = formula_url
    else:
        primary_index = candidates.index(primary)
        license_source = str(primary)
    copyleft = "LGPL" in library_expression or "GPL" in library_expression
    source_links = [source_url, formula_url,
                    f"https://github.com/BernieSumption/pg_binaries/blob/{__import__('os').environ['GITHUB_SHA']}/scripts/postgis/macos-build-publication.sh"]
    notice_basis = ("The archive includes the applicable notice texts." if candidates else
                    "The package contains no licence text; the archive includes declaration evidence identifying this exact source and formula licence.")
    review_basis = (f"Homebrew {name} {version} formula at {formula_url} identifies the source archive and package terms. {review_note} "
                    f"{notice_basis} No source modifications are made.")
    if copyleft:
        review_basis += " The shared LGPL library is dynamically linked and can be replaced by users; corresponding source and build material are linked for the LGPL source and relinking requirements."
    else:
        review_basis += " The applied library terms require notices but no source delivery for this binary distribution."
    components.append({
        "component": f"homebrew-library-{name}", "package": name, "version": version,
        "license_expression": library_expression, "package_license_expression": license_expr,
        "payload_paths": paths,
        "license_file": f"LICENSES/{license_names[primary_index]}",
        "additional_license_files": [f"LICENSES/{filename}" for index, filename in enumerate(license_names)
                                      if index != primary_index],
        "source_url": source_url, "source_sha256": source_sha, "source_revision": formula_revision,
        "license_source": license_source,
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
proj_source_receipt = json.loads((Path(command("brew", "--prefix", "proj").strip()).resolve() / "INSTALL_RECEIPT.json").read_text()).get("source", {})
resource_url, resource_sha = proj_data_source(proj_formula, proj_source_receipt)
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
pending=list((root/"lib").glob("*")); scanned=set(); needed_core=set()
while pending:
    binary=pending.pop()
    if not binary.is_file() or binary in scanned: continue
    scanned.add(binary)
    inspected=subprocess.run(("lipo","-archs",str(binary)),capture_output=True)
    if inspected.returncode: continue
    lines=command("otool","-L",str(binary)).splitlines()[1:]
    for line in lines:
        dependency=line.strip().split(" ",1)[0]
        if dependency.startswith(("/usr/lib/","/System/Library/","@executable_path/")): continue
        if dependency.startswith("@loader_path/"):
            candidate=(binary.parent/dependency.removeprefix("@loader_path/")).resolve()
            if not candidate.is_file(): candidate=core_root/"lib"/Path(dependency.removeprefix("@loader_path/")).name
        elif dependency.startswith("@rpath/"):
            name=Path(dependency.removeprefix("@rpath/")).name
            candidate=next((path for path in (root/"lib"/name,core_root/"lib"/name) if path.is_file()),Path())
        elif dependency.startswith("/"):
            candidate=Path(dependency)
        else: continue
        if candidate.is_file() and candidate.is_relative_to(core_root):
            if candidate not in needed_core:
                needed_core.add(candidate); pending.append(candidate)
for core_file in sorted(needed_core):
    library=core_file.name
    owner=next((item for item in core_inventory["components"] if library in item.get("libraries",[])),None)
    if owner is None or owner.get("redistribution_review",{}).get("status")!="resolved":
        raise SystemExit(f"checked core has no resolved licence record for {library}")
    reused.append({"library":library,"sha256":sha(core_file),"core_component":owner["component"],
                   "core_version":owner["version"],"license_file":"LICENSES/"+owner["license_file"]})
if not any(item["library"] == "libxml2.16.dylib" for item in reused):
    raise SystemExit("PostGIS does not resolve libxml2 to the checked PostgreSQL core library")
inventory={"schema_version":1,"reused_core_dependencies":reused,"components":components}
(root/"LICENSES/postgis-inventory.json").write_text(json.dumps(inventory,indent=2,sort_keys=True)+"\n")
print(f"Recorded {len(components)} PostGIS macOS redistribution components")
