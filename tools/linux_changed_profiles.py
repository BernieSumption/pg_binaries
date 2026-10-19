#!/usr/bin/env python3
"""Select routed Linux extension targets whose publication profiles changed."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys


def _load_tool(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coverage = _load_tool("linux_changed_profiles_coverage", "coverage.py")
extension_archive_plan = _load_tool("linux_changed_profiles_plan", "extension_archive_plan.py")

# These are projects with a Linux route in selected-extension-publication.yml.
# Add a project here when its reusable selected Linux workflow is ready.
LINUX_ROUTES = {"hypopg": "HypoPG", "pg-jsonschema": "pg_jsonschema", "pgtap": "pgtap"}
MAX_TARGETS = 128


def _profile_id(route_name, architecture, postgresql_version):
    return f"{route_name}-publication-linux-{architecture}-{postgresql_version}"


def changed_targets(before_root, current_root):
    """Return a bounded matrix of changed targets, selecting all if base is absent."""
    current_root = Path(current_root)
    support = coverage.load_json(current_root / "support.json")
    releases = coverage.load_json(current_root / "support" / "postgresql-releases.json")
    plan = extension_archive_plan.plan(support, releases)
    registry = coverage.load_json(current_root / "support" / "verification-profiles.json")
    profiles = registry.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("verification profile registry must contain profiles")

    candidates = []
    seen_profiles = set()
    for route_name, project in LINUX_ROUTES.items():
        project_candidates = [target for target in plan["candidate_archives"]
                              if target["project"] == project
                              and target["platform"].startswith("linux-")]
        for target in project_candidates:
            architecture = target["platform"].removeprefix("linux-")
            profile_id = _profile_id(route_name, architecture, target["postgresql_version"])
            if profile_id in seen_profiles:
                raise ValueError(f"multiple selected releases require distinct profiles for {profile_id!r}")
            seen_profiles.add(profile_id)
            current = coverage.verification_profile(current_root, profile_id)
            if current["scope"] != "publication" or current["platforms"] != [target["platform"]]:
                raise ValueError(f"profile {profile_id!r} does not match its Linux publication target")
            candidates.append({
                "project": project,
                "extension_version": target["selected_version"],
                "postgresql_version": target["postgresql_version"],
                "platform": target["platform"],
                "profile_id": profile_id,
                "profile_revision": current["profile_revision"],
            })

    registered = {name for name, profile in profiles.items()
                  if profile.get("scope") == "publication"
                  and any(name.startswith(f"{route}-publication-linux-") for route in LINUX_ROUTES)}
    declared = {target["profile_id"] for target in candidates}
    if registered != declared:
        raise ValueError("routed Linux publication profiles and support-derived targets differ")
    if len(candidates) > MAX_TARGETS:
        raise ValueError(f"Linux changed-profile matrix exceeds the {MAX_TARGETS}-target limit")

    selected = before_root is None
    before_root = Path(before_root) if before_root is not None else None
    changed = []
    for target in candidates:
        should_select = selected
        if before_root is not None:
            try:
                previous = coverage.verification_profile(before_root, target["profile_id"])
            except Exception as exc:
                print(f"Cannot resolve base profile {target['profile_id']!r}; selecting all routed targets: {exc}",
                      file=sys.stderr)
                selected = True
                should_select = True
            else:
                should_select = (previous["profile_revision"] != target["profile_revision"])
        if should_select:
            changed.append({key: target[key] for key in
                            ("project", "extension_version", "postgresql_version", "platform")})
    if selected:
        changed = [{key: target[key] for key in
                    ("project", "extension_version", "postgresql_version", "platform")}
                   for target in candidates]
    return sorted(changed, key=lambda item: (item["project"], item["postgresql_version"], item["platform"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-root", type=Path)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        before = args.before_root if args.before_root and args.before_root.exists() else None
        selected = changed_targets(before, args.current_root)
    except Exception as exc:
        parser.exit(2, f"Linux profile selection failed: {exc}\n")
    rendered = json.dumps(selected, separators=(",", ":"))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"targets={rendered}\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
