#!/usr/bin/env python3
"""Write archive-local provenance for Linux PostgreSQL pilot license texts."""

import argparse
import hashlib
import json
import pathlib
import subprocess


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("root", type=pathlib.Path)
parser.add_argument("postgresql_version")
parser.add_argument("runtime_map", type=pathlib.Path)
parser.add_argument("--reviews", type=pathlib.Path,
                    help="explicit redistribution decisions for every packaged component")
args = parser.parse_args()

root = args.root.resolve()
postgresql_version = args.postgresql_version
runtime_map = args.runtime_map
components = [{
    "component": "postgresql",
    "version": postgresql_version,
    "payload_paths": ["bin", "include", "lib", "libexec", "share"],
    "license_file": "PostgreSQL.txt",
    "license_source": (
        f"https://ftp.postgresql.org/pub/source/v{postgresql_version}/"
        f"postgresql-{postgresql_version}.tar.bz2"
    ),
}]

packages = {}
for line in runtime_map.read_text(encoding="utf-8").splitlines():
    package, payload_path = line.split("\t", 1)
    packages.setdefault(package, set()).add(payload_path)

for package, payload_paths in sorted(packages.items()):
    package_metadata = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}\t${source:Package}\t${source:Version}", package],
        check=True, capture_output=True, text=True,
    ).stdout.rstrip("\n").split("\t")
    if len(package_metadata) != 3:
        raise SystemExit(f"incomplete installed package metadata: {package}")
    version, source_package, source_version = package_metadata
    if not version:
        raise SystemExit(f"missing installed package version: {package}")
    if not source_package:
        raise SystemExit(f"missing source package name: {package}")
    if not source_version:
        raise SystemExit(f"missing source package version: {package}")
    license_file = f"{package}.copyright"
    license_path = root / "LICENSES" / license_file
    if not license_path.is_file() or not license_path.stat().st_size:
        raise SystemExit(f"missing non-empty license text: {license_path}")
    for payload_path in sorted(payload_paths):
        payload = root / payload_path
        if not payload.is_file() or not payload.stat().st_size:
            raise SystemExit(f"missing non-empty runtime payload: {payload}")
    entry = {
        "component": "runtime-package",
        "package": package,
        "version": version,
        "source_package": source_package,
        "source_version": source_version,
        "payload_paths": sorted(payload_paths),
        "license_file": license_file,
        "license_source": f"https://packages.ubuntu.com/jammy/{package}",
    }
    if package == "libc6":
        if source_package != "glibc":
            raise SystemExit(f"unexpected libc6 source package: {source_package}")
        if source_version != version:
            raise SystemExit(f"unexpected libc6 source version: {source_version}")
        source_base = "https://archive.ubuntu.com/ubuntu/pool/main/g/glibc/"
        upstream_version = version.split("-", 1)[0]
        entry["source_urls"] = [
            f"{source_base}glibc_{source_version}.dsc",
            f"{source_base}glibc_{upstream_version}.orig.tar.xz",
            f"{source_base}glibc_{source_version}.debian.tar.xz",
        ]
        entry["additional_license_files"] = [
            "libc6-GFDL-1.3.txt", "libc6-GPL-2.txt", "libc6-LGPL-2.1.txt"
        ]
        for additional in entry["additional_license_files"]:
            path = root / "LICENSES" / additional
            if not path.is_file() or not path.stat().st_size:
                raise SystemExit(f"missing glibc license text: {path}")
    elif package == "libicu70":
        if (version, source_package, source_version) != ("70.1-2", "icu", "70.1-2"):
            raise SystemExit(
                "unexpected libicu70 source identity: "
                f"{version} {source_package} {source_version}"
            )
        additional = "libicu70-icu-70.1-LICENSE.txt"
        path = root / "LICENSES" / additional
        if not path.is_file() or not path.stat().st_size:
            raise SystemExit(f"missing ICU third-party notices: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != "861671f8c712aa046f8f5ac89239e6c33821636516c5d0cc8c4e1973085f27a6":
            raise SystemExit(f"unexpected ICU third-party notices: {path}")
        entry["additional_license_files"] = [additional]
    elif package == "libssl3":
        if (version, source_package, source_version) != (
                "3.0.2-0ubuntu1.30", "openssl", "3.0.2-0ubuntu1.30"):
            raise SystemExit(
                "unexpected libssl3 source identity: "
                f"{version} {source_package} {source_version}"
            )
        additional = "common-licenses/Apache-2.0"
        path = root / "LICENSES" / additional
        if not path.is_file() or not path.stat().st_size:
            raise SystemExit(f"missing OpenSSL Apache-2.0 license text: {path}")
        entry["additional_license_files"] = [additional]
    elif package == "libxml2":
        if (version, source_package, source_version) != (
                "2.9.13+dfsg-1ubuntu0.14", "libxml2", "2.9.13+dfsg-1ubuntu0.14"):
            raise SystemExit(
                "unexpected libxml2 source identity: "
                f"{version} {source_package} {source_version}"
            )
        additional = "libxml2-2.9.13-dict-notice.txt"
        path = root / "LICENSES" / additional
        if not path.is_file() or not path.stat().st_size:
            raise SystemExit(f"missing libxml2 dict.c notice: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != "5e67dfcf4fbeb9e1a224e1001ad7cd4cab6cadb7383cc173ccd09315f89b0d9a":
            raise SystemExit(f"unexpected libxml2 dict.c notice: {path}")
        entry["additional_license_files"] = [additional]
    elif package == "musl":
        if source_package != "musl":
            raise SystemExit(f"unexpected musl source package: {source_package}")
        if source_version != version:
            raise SystemExit(f"unexpected musl source version: {source_version}")
        source_base = "https://archive.ubuntu.com/ubuntu/pool/universe/m/musl/"
        upstream_version = version.split("-", 1)[0]
        entry["source_urls"] = [
            f"{source_base}musl_{source_version}.dsc",
            f"{source_base}musl_{upstream_version}.orig.tar.gz",
            f"{source_base}musl_{source_version}.debian.tar.xz",
        ]
    components.append(entry)

postgres_license = root / "LICENSES" / "PostgreSQL.txt"
if not postgresql_version or not postgresql_version[0].isdigit():
    raise SystemExit(f"invalid PostgreSQL version: {postgresql_version}")
if not postgres_license.is_file() or not postgres_license.stat().st_size:
    raise SystemExit(f"missing non-empty license text: {postgres_license}")

if args.reviews is not None:
    try:
        review_data = json.loads(args.reviews.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read redistribution reviews: {exc}") from exc
    if not isinstance(review_data, dict) or review_data.get("schema_version") != 1:
        raise SystemExit("redistribution reviews require schema_version 1")
    entries = review_data.get("components")
    if not isinstance(entries, list):
        raise SystemExit("redistribution reviews require a components array")

    def identity(entry):
        if not isinstance(entry, dict):
            raise SystemExit("redistribution review component must be an object")
        component, package, version = (entry.get("component"), entry.get("package"),
                                       entry.get("version"))
        if (not isinstance(component, str) or not component
                or (package is not None and (not isinstance(package, str) or not package))
                or not isinstance(version, str) or not version):
            raise SystemExit("redistribution review requires component, package and version identity")
        return component, package, version

    reviews = {}
    for entry in entries:
        key = identity(entry)
        if key in reviews:
            raise SystemExit(f"duplicate redistribution review: {key}")
        review = entry.get("redistribution_review")
        if (not isinstance(review, dict) or review.get("status") != "resolved"
                or not isinstance(review.get("basis"), str) or not review["basis"].strip()
                or review.get("source_obligation") not in {"none", "source-links", "source-offer"}):
            raise SystemExit(f"unresolved redistribution review: {key}")
        reviews[key] = review
    expected = {identity(entry) for entry in components}
    if set(reviews) != expected:
        missing = sorted(expected - set(reviews), key=str)
        extra = sorted(set(reviews) - expected, key=str)
        raise SystemExit(f"redistribution reviews differ from packaged components: missing={missing}, extra={extra}")
    for entry in components:
        entry["redistribution_review"] = reviews[identity(entry)]

inventory = {"schema_version": 1, "components": components}
(root / "LICENSES" / "inventory.json").write_text(
    json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
