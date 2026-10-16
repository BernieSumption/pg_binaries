#!/usr/bin/env python3
"""Best-effort reuse of a verified PostgreSQL Linux core archive from Actions."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request
import zipfile

import coverage


API = "https://api.github.com"
ARTIFACT_NAME = "linux-pilot-core-archives"
WORKFLOW_NAME = "Linux x86-64 pilot"
TARGETS = {
    "x86_64": (WORKFLOW_NAME, ".github/workflows/linux-pilot.yml", ARTIFACT_NAME),
    "arm64": ("Linux arm64 PostgreSQL 18.6 pilot", ".github/workflows/linux-arm64-pilot.yml",
              "linux-arm64-pilot-archives"),
}


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        # GitHub redirects artifact downloads to a separate blob host.
        return urllib.request.Request(new_url, headers={"Accept": "application/octet-stream"})


def request(url, token, accept="application/vnd.github+json"):
    opener = urllib.request.build_opener(SafeRedirect)
    req = urllib.request.Request(url, headers={
        "Accept": accept,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "pg-binaries-postgis-core-reuse",
    })
    with opener.open(req, timeout=45) as response:
        return response.read()


def api_json(url, token):
    return json.loads(request(url, token).decode("utf-8"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def select_run(runs, sha, architecture="x86_64"):
    workflow_name, workflow_path, _ = TARGETS[architecture]
    candidates = [run for run in runs
                  if run.get("name") == workflow_name
                  and run.get("path") == workflow_path
                  and run.get("head_sha") == sha
                  and run.get("conclusion") == "success"]
    candidates.sort(key=lambda item: item.get("run_number", 0), reverse=True)
    return candidates[0] if candidates else None


def validate_and_extract(zip_data, root, sha, pg_version, run_id, output, architecture="x86_64"):
    expected_archive = f"postgresql-{pg_version}-linux-{architecture}.tar.gz"
    expected_profile = coverage.verification_profile(root, f"linux-pilot-{architecture}")
    record_name = f"postgresql-{pg_version}-linux-{architecture}-{run_id}.json"
    required = {expected_archive, expected_archive + ".sha256", record_name}
    with zipfile.ZipFile(io.BytesIO(zip_data)) as archive:
        entries = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            base = Path(info.filename).name
            if base not in required:
                continue
            if base in entries:
                raise ValueError(f"artifact contains duplicate {base}")
            entries[base] = archive.read(info)

    record_candidates = [value for name, value in entries.items()
                         if name == record_name]
    if len(record_candidates) != 1:
        raise ValueError("artifact must contain one PostgreSQL verification record")
    record = json.loads(record_candidates[0].decode("utf-8"))
    if (record.get("outcome") != "passed"
            or record.get("component") != "postgresql"
            or record.get("version") != pg_version
            or record.get("postgresql_version") != pg_version
            or record.get("platform") != f"linux-{architecture}"
            or record.get("test_revision") != sha
            or record.get("profile_id") != expected_profile["profile_id"]
            or record.get("profile_revision") != expected_profile["profile_revision"]):
        raise ValueError("verification record does not match commit, PostgreSQL version, platform, or profile")
    ci = record.get("ci", {})
    if any(ci.get(key) != sha for key in ("source_revision", "build_revision", "test_revision")):
        raise ValueError("verification record source or build revision differs")
    if str(ci.get("run_id")) != str(run_id):
        raise ValueError("verification record belongs to a different Actions run")

    try:
        data = entries[expected_archive]
        checksum_text = entries[expected_archive + ".sha256"].decode("ascii").split()
    except (KeyError, UnicodeDecodeError, IndexError) as exc:
        raise ValueError("core archive or checksum is missing") from exc
    if not checksum_text or not re.fullmatch(r"[0-9a-fA-F]{64}", checksum_text[0]):
        raise ValueError("core archive checksum file is malformed")
    actual = digest(data)
    if actual != checksum_text[0].lower() or actual != str(record.get("sha256", "")).lower():
        raise ValueError("core archive checksum does not match verification record")
    output.mkdir(parents=True, exist_ok=True)
    (output / expected_archive).write_bytes(data)
    (output / (expected_archive + ".sha256")).write_bytes(entries[expected_archive + ".sha256"])


def reuse(repo, sha, pg_version, root, output, token, architecture="x86_64"):
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
        raise ValueError("source commit must be a full lowercase Git SHA")
    owner_repo = urllib.parse.quote(repo, safe="/")
    runs_url = f"{API}/repos/{owner_repo}/actions/runs?head_sha={sha}&per_page=100"
    run = select_run(api_json(runs_url, token).get("workflow_runs", []), sha, architecture)
    if not run:
        raise ValueError("no successful matching Linux run exists for this commit")
    run_id = run["id"]
    artifacts = api_json(f"{API}/repos/{owner_repo}/actions/runs/{run_id}/artifacts?per_page=100", token)
    matches = [item for item in artifacts.get("artifacts", [])
               if item.get("name") == TARGETS[architecture][2] and not item.get("expired")]
    if len(matches) != 1:
        raise ValueError("expected core archive artifact is missing or ambiguous")
    blob = request(f"{API}/repos/{owner_repo}/actions/artifacts/{matches[0]['id']}/zip",
                   token, "application/vnd.github+json")
    validate_and_extract(blob, root, sha, pg_version, run_id, output, architecture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=sorted(TARGETS), default="x86_64")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--postgresql-version", default="18.6")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-output", type=Path, default=None)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN", "")
    success = False
    try:
        if not args.repo or not token:
            raise ValueError("repository or read-only GitHub token is unavailable")
        reuse(args.repo, args.sha, args.postgresql_version, args.root, args.output, token, args.architecture)
        success = True
        print("Reused verified PostgreSQL core archive from this commit")
    except Exception as exc:
        print(f"Core archive reuse unavailable; PostGIS job will build independently: {exc}")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"reused={'true' if success else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
