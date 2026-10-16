#!/usr/bin/env python3
"""Discover stable PostgreSQL source releases and reconcile the support snapshot."""

import argparse
import datetime as dt
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


SOURCE = "https://ftp.postgresql.org/pub/source/"
RELEASE_NOTES = "https://www.postgresql.org/docs/release/{version}/"
VERSION_DIR = re.compile(r"^v(\d+)\.(\d+)/$")
RELEASE_DATE = re.compile(r"\bRelease date:\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
MAX_RESPONSE_BYTES = 1_000_000


class DiscoveryError(Exception):
    pass


class IndexParser(HTMLParser):
    """Read source-directory links independently of the server's index layout."""

    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            href = attrs.get("href")
            if href:
                self.hrefs.append(href)


def parse_index(html, minimum_major):
    parser = IndexParser()
    parser.feed(html)
    versions = []
    saw_release_directory = False
    for candidate in parser.hrefs:
        if not VERSION_DIR.fullmatch(candidate):
            continue
        saw_release_directory = True
        version_match = VERSION_DIR.fullmatch(candidate)
        major, minor = map(int, version_match.groups())
        if major < minimum_major:
            continue
        version = f"{major}.{minor}"
        if version in versions:
            raise DiscoveryError(f"FTP index contains duplicate release directory {candidate}")
        versions.append(version)
    if not saw_release_directory:
        raise DiscoveryError("FTP index contains no stable vMAJOR.MINOR directory rows")
    if not versions:
        raise DiscoveryError("FTP index has no stable release directories at or above the declared major")
    return sorted(versions, key=lambda value: tuple(map(int, value.split("."))))


def parse_release_date(html, version):
    class TextParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)
    parser = TextParser()
    parser.feed(html)
    match = RELEASE_DATE.search(" ".join(parser.parts))
    if match is None:
        raise DiscoveryError(f"official release notes for PostgreSQL {version} have no release date")
    try:
        return dt.date.fromisoformat(match.group(1))
    except ValueError as exc:
        raise DiscoveryError(f"official release notes for PostgreSQL {version} have an invalid release date") from exc


def fetch_index(url=SOURCE):
    request = Request(url, headers={"User-Agent": "pg-binaries-release-discovery/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise DiscoveryError(f"PostgreSQL FTP index exceeds {MAX_RESPONSE_BYTES} bytes: {url}")
        return payload.decode("utf-8")
    except DiscoveryError:
        raise
    except (OSError, UnicodeDecodeError, URLError) as exc:
        raise DiscoveryError(f"cannot fetch PostgreSQL FTP index {url}: {exc}") from exc


def fetch_release_notes(version):
    url = RELEASE_NOTES.format(version=version)
    request = Request(url, headers={"User-Agent": "pg-binaries-release-discovery/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise DiscoveryError(f"official release notes exceed {MAX_RESPONSE_BYTES} bytes: {url}")
        return payload.decode("utf-8")
    except DiscoveryError:
        raise
    except (OSError, UnicodeDecodeError, URLError) as exc:
        raise DiscoveryError(f"cannot fetch official release notes for PostgreSQL {version}: {exc}") from exc


def discover_releases(index_html, minimum_major, cutoff, release_notes_fetcher=fetch_release_notes):
    releases = []
    for version in parse_index(index_html, minimum_major):
        published = parse_release_date(release_notes_fetcher(version), version)
        if published >= cutoff:
            releases.append({"version": version, "release_date": published.isoformat()})
    if not releases:
        raise DiscoveryError("official release dates contain no releases matching the declared date cutoff")
    return releases


def compare_releases(discovered, snapshot):
    stored = snapshot.get("releases")
    if not isinstance(stored, list):
        raise DiscoveryError("release snapshot must contain a releases array")
    def keyed(items):
        result = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("version"), str) or not isinstance(item.get("release_date"), str):
                raise DiscoveryError("each snapshot release must have a version and release_date")
            if item["version"] in result:
                raise DiscoveryError(f"duplicate release {item['version']} in snapshot")
            result[item["version"]] = item["release_date"]
        return result
    actual, expected = keyed(discovered), keyed(stored)
    missing = sorted(set(actual) - set(expected), key=lambda value: tuple(map(int, value.split("."))))
    extra = sorted(set(expected) - set(actual), key=lambda value: tuple(map(int, value.split("."))))
    changed = sorted(version for version in actual.keys() & expected.keys()
                     if actual[version] != expected[version])
    return missing, extra, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="compare the live release list with the stored snapshot")
    mode.add_argument("--write", action="store_true", help="replace the stored snapshot with the live release list")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        root = args.root
        support = json.loads((root / "support.json").read_text(encoding="utf-8"))
        pg = support["postgresql"]
        minimum = int(pg["minimum_major"])
        cutoff = dt.date.fromisoformat(pg["stable_release_cutoff"])
        discovered = discover_releases(fetch_index(), minimum, cutoff)
        path = root / "support" / "postgresql-releases.json"
        if args.write:
            snapshot = {"as_of": dt.datetime.now(dt.timezone.utc).date().isoformat(),
                        "source": SOURCE, "release_date_source": RELEASE_NOTES,
                        "releases": discovered}
            path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {len(discovered)} PostgreSQL releases to {path}")
            return 0

        stored = json.loads(path.read_text(encoding="utf-8"))
        missing, extra, changed = compare_releases(discovered, stored)
        if not missing and not extra and not changed:
            print(f"release snapshot matches {len(discovered)} qualifying PostgreSQL releases")
            return 0
        for version in missing:
            print(f"missing from snapshot: PostgreSQL {version} ({dict((item['version'], item['release_date']) for item in discovered)[version]})")
        for version in extra:
            print(f"extra in snapshot: PostgreSQL {version}")
        actual_dates = {item["version"]: item["release_date"] for item in discovered}
        expected_dates = {item["version"]: item["release_date"] for item in stored["releases"]}
        for version in changed:
            print(f"date changed: PostgreSQL {version}: snapshot {expected_dates[version]}, official release notes {actual_dates[version]}")
        return 1
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, DiscoveryError) as exc:
        print(f"discover_postgresql: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
