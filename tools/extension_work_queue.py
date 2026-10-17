#!/usr/bin/env python3
"""Plan a bounded, deterministic batch of archive and current-OS verification work."""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coverage = _load("work_queue_coverage", "coverage.py")
archive_plan = _load("work_queue_archive_plan", "extension_archive_plan.py")


def _id(kind, *key):
    digest = hashlib.sha256(json.dumps([kind, *key], separators=(",", ":")).encode()).hexdigest()[:16]
    return f"{kind}:{digest}"


def build_queue(root):
    """Build project-level archive candidates and exact endpoint verification tasks."""
    root = Path(root)
    support = coverage.load_json(root / "support.json")
    coverage.validate_support(support)
    coverage.validate_extension_policy(root, support)
    snapshot = coverage.load_json(root / "support/postgresql-releases.json")
    inventory = coverage.load_json(root / "inventory.json", required=False) or {"postgresql": {}, "extensions": {}}
    releases = coverage.release_snapshot(snapshot, support)
    core_targets, _ = coverage.expected_targets(support, releases)
    core_downloads, extension_downloads = coverage.inventory_targets(inventory)
    records = coverage.verification_records(root, support)
    groups = archive_plan.plan(support, snapshot)["candidate_archives"]
    items = {}
    unresolved = []

    def add(item):
        items[item["id"]] = item

    def observed(component, version, pg, platform, endpoint):
        return [{"record": row["_record_file"], "outcome": row["outcome"]}
                for row in records if row.get("_profile_current") is True
                and row.get("component") == component and str(row.get("version")) == str(version)
                and row.get("postgresql_version") == pg and row.get("platform") == platform
                and row.get("environment", {}).get("endpoint") == endpoint]

    # Core work exists for each exact selected PostgreSQL target used by an extension group.
    core_verify_ids = {}
    for group in groups:
        pg = group["postgresql_version"]
        key = (pg, group["platform"])
        if key not in core_targets:
            continue
        download = core_downloads.get(key)
        build_id = _id("build-core", pg, group["platform"])
        if build_id not in items:
            add({"id": build_id, "kind": "build-core", "component": "postgresql", "version": pg,
                 "postgresql_version": pg, "platform": group["platform"], "status": "complete" if download else "needed",
                 "evidence": "inventory" if download else None, "depends_on": []})
        os_endpoint = "current"
        verify_id = _id("verify-core", pg, group["platform"], os_endpoint)
        core_verify_ids[(pg, group["platform"], os_endpoint)] = verify_id
        verified = bool(download and coverage.verified(records, download, "postgresql", pg,
                                                         group["platform"], pg, os_endpoint))
        seen = observed("postgresql", pg, pg, group["platform"], os_endpoint)
        if verify_id not in items:
            add({"id": verify_id, "kind": "verify-core", "component": "postgresql", "version": pg,
                 "postgresql_version": pg, "platform": group["platform"], "endpoint": os_endpoint,
                 "status": "complete" if verified else "needed",
                 "evidence": "current-passing-record" if verified else
                 ("retained-record-unbound-to-inventory" if seen else None),
                 "observed_records": [] if verified else seen, "depends_on": [build_id]})

    for group in groups:
        project, version = group["project"], group["selected_version"]
        platform = group["platform"]
        pg = group["postgresql_version"]
        pg_versions = [pg]
        sql_names = group["sql_names"]
        # Bind one project archive only when every declared SQL name maps to the same exact download.
        downloads_by_name = {}
        for name in sql_names:
            matching = [(key, dl) for key, dl in extension_downloads.items()
                        if key[0] == name and key[1] == version and key[4] == platform
                        and all(coverage.version_parts(key[2], "archive range") <= coverage.version_parts(pg, "target")
                                <= coverage.version_parts(key[3], "archive range") for pg in pg_versions)]
            downloads_by_name[name] = matching
        signatures = {(dl["url"], dl["sha256"].lower()) for matches in downloads_by_name.values()
                      for _, dl in matches}
        archive_bound = (all(len(downloads_by_name[name]) == 1 for name in sql_names)
                         and len(signatures) == 1)
        archive_download = next(iter(next(iter(downloads_by_name.values()))))[1] if archive_bound else None
        group_id = _id("build-extension", project, version, platform, group["postgresql_major"])
        build_pg = pg
        core_deps = [_id("build-core", build_pg, platform)]
        add({"id": group_id, "kind": "build-extension", "component": project, "project": project,
             "version": version, "platform": platform, "postgresql_major": group["postgresql_major"],
             "postgresql_version": pg,
             "postgresql_range": {"from": pg, "to": pg},
             "build_postgresql_version": build_pg,
             "sql_names": sql_names,
             "status": "complete" if archive_bound else "needed",
             "evidence": "inventory-project-archive-bound" if archive_bound else None,
             "range_status": "unverified",
             "depends_on": sorted(set(core_deps))})

        # Each SQL name is checked at each distinct PostgreSQL boundary and OS endpoint.
        for name in sql_names:
            exact_download = downloads_by_name[name][0][1] if archive_bound else None
            os_endpoint = "current"
            verify_id = _id("verify-extension", project, version, platform, group["postgresql_major"],
                            name, pg, os_endpoint)
            core_dl = core_downloads.get((pg, platform))
            prereqs = coverage.expected_prerequisite_archives(
                support, extension_downloads, project, pg, platform)
            verified = bool(exact_download and core_dl and prereqs is not None and coverage.verified(
                records, exact_download, name, version, platform, pg, os_endpoint,
                assembled_core_sha256=core_dl["sha256"], prerequisite_archives=prereqs))
            seen = observed(name, version, pg, platform, os_endpoint)
            deps = [group_id, core_verify_ids[(pg, platform, os_endpoint)]]
            add({"id": verify_id, "kind": "verify-extension", "component": name, "project": project,
                 "version": version, "postgresql_version": pg, "platform": platform,
                 "postgresql_major": group["postgresql_major"], "endpoint": os_endpoint,
                 "status": "complete" if verified else "needed",
                 "evidence": "current-passing-record" if verified else
                 ("retained-record-unbound-to-inventory" if seen else None),
                 "observed_records": [] if verified else seen, "depends_on": deps})

        prerequisite_groups = []
        prerequisite_ambiguous = False
        for required_project in support["extensions"][project].get("requires", []):
            constraint = support["extensions"][project].get("requires_versions", {}).get(required_project, {})
            candidates = [candidate for candidate in groups
                          if candidate["project"] == required_project
                          and candidate["platform"] == platform
                          and candidate["postgresql_major"] == group["postgresql_major"]
                          and coverage.prerequisite_version_allowed(
                              support, project, required_project, candidate["selected_version"])]
            candidate_ids = sorted({_id("build-extension", candidate["project"], candidate["selected_version"],
                                        candidate["platform"], candidate["postgresql_major"])
                                    for candidate in candidates})
            if len(candidate_ids) == 1:
                prerequisite_groups.append(candidate_ids[0])
                items[group_id]["depends_on"] = sorted(set(items[group_id]["depends_on"] + candidate_ids))
            else:
                prerequisite_ambiguous = True
                unresolved.append({"item_id": group_id, "project": project, "required_project": required_project,
                                   "postgresql_major": group["postgresql_major"], "platform": platform,
                                   "candidate_group_ids": candidate_ids,
                                   "status": "version-selection-unresolved",
                                   "reason": ("no declared prerequisite version meets the constraint" if not candidates
                                              else "multiple declared prerequisite versions meet the constraint"),
                                   "candidate_selection_source": "support.json" if constraint else None})
        items[group_id]["prerequisite_candidate_groups"] = prerequisite_groups
        items[group_id]["blocked_by_unresolved_prerequisite"] = prerequisite_ambiguous
        for item in items.values():
            if (item.get("kind") == "verify-extension" and item.get("project") == project
                    and item.get("version") == version and item.get("platform") == platform
                    and item.get("postgresql_major") == group["postgresql_major"]):
                item["blocked_by_unresolved_prerequisite"] = prerequisite_ambiguous

        for candidate_id in prerequisite_groups:
            candidate_group = next(row for row in groups
                                   if _id("build-extension", row["project"], row["selected_version"],
                                          row["platform"], row["postgresql_major"]) == candidate_id)
            pg = candidate_group["postgresql_version"]
            os_endpoint = "current"
            for name in candidate_group["sql_names"]:
                prerequisite_verify = _id("verify-extension", candidate_group["project"],
                                          candidate_group["selected_version"], candidate_group["platform"],
                                          candidate_group["postgresql_major"], name, pg, os_endpoint)
                for item in items.values():
                    if (item.get("kind") == "verify-extension" and item.get("project") == project
                            and item.get("version") == version and item.get("platform") == platform
                            and item.get("postgresql_major") == group["postgresql_major"]
                            and item.get("postgresql_version") == pg and item.get("endpoint") == os_endpoint):
                        item["depends_on"] = sorted(set(item["depends_on"] + [prerequisite_verify]))

        checks = [item for item in items.values() if item.get("project") == project
                  and item.get("version") == version and item.get("platform") == platform
                  and item.get("postgresql_major") == group["postgresql_major"]
                  and item.get("kind") == "verify-extension"]
        items[group_id]["range_status"] = ("complete" if archive_bound and not prerequisite_ambiguous and checks
                                            and all(item["status"] == "complete" for item in checks)
                                            else "unverified")

    platform_order = {f"{os}-{arch}": i for i, (os, arch) in enumerate(
        (os_name, arch) for os_name, arches in support["platform_architectures"].items() for arch in arches)}
    ordered = sorted(items.values(), key=lambda item: (
        coverage.version_parts(item.get("postgresql_version") or
                               item.get("postgresql_range", {}).get("from") or item["version"], "queue order"),
        platform_order[item["platform"]], item["kind"], item.get("component", ""), item.get("version", ""),
        item.get("endpoint", ""), item["id"]))
    return {"snapshot_as_of": snapshot["as_of"], "work_items": ordered,
            "unresolved_prerequisites": unresolved,
            "scope": "project archive groups target exact selected PostgreSQL minors; routine verification uses the current OS endpoint"}


def select_batch(queue, limit, project=None, platform=None, postgresql_major=None):
    if limit < 1:
        raise ValueError("batch limit must be positive")
    items = {item["id"]: item for item in queue["work_items"]}
    roots = [item for item in queue["work_items"]
             if (project is None or item.get("project") == project or item.get("component") == project)
             and (platform is None or item["platform"] == platform)
             and (postgresql_major is None or item.get("postgresql_major") == postgresql_major)]
    if (project is not None or platform is not None or postgresql_major is not None) and not roots:
        raise ValueError("work selection matches no declared targets")
    # Keep dependency closure, including items outside the requested project filter.
    included = set()
    def include(item):
        if item["id"] in included:
            return
        included.add(item["id"])
        for dependency in item.get("depends_on", []):
            if dependency in items:
                include(items[dependency])
    for root_item in roots:
        include(root_item)
    pending = {key for key in included if items[key]["status"] != "complete"
               and not items[key].get("blocked_by_unresolved_prerequisite")}
    done = {key for key in included if items[key]["status"] == "complete"}
    selected = []
    direct_ids = {item["id"] for item in roots}
    while pending and len(selected) < limit:
        ready = sorted((key for key in pending if set(items[key].get("depends_on", [])) <= done),
                       key=lambda key: (
                           {"build-core": 0, "build-extension": 1 if key in direct_ids else 2,
                            "verify-core": 3, "verify-extension": 4 if key in direct_ids else 5}.get(
                                items[key]["kind"], 9),
                           queue["work_items"].index(items[key])))
        if not ready:
            break
        key = ready[0]
        selected.append(items[key])
        done.add(key)
        pending.remove(key)
    unresolved = [entry for entry in queue.get("unresolved_prerequisites", [])
                  if entry["item_id"] in included]
    return {"selected_items": selected, "unresolved_prerequisites": unresolved,
            "omitted_dependency_count": len(pending)}


def select_item_closure(queue, item_id, limit):
    """Return one exact work item and all of its prerequisites, or fail on the cap."""
    if limit < 1:
        raise ValueError("closure limit must be positive")
    items = {item["id"]: item for item in queue["work_items"]}
    if item_id not in items:
        raise ValueError(f"unknown work item: {item_id}")
    ordered = []
    visiting = set()
    visited = set()

    def visit(key):
        if key in visiting:
            raise ValueError(f"dependency cycle at {key}")
        if key in visited:
            return
        visiting.add(key)
        for dependency in sorted(items[key].get("depends_on", [])):
            if dependency not in items:
                raise ValueError(f"missing dependency {dependency} for {key}")
            visit(dependency)
        visiting.remove(key)
        visited.add(key)
        ordered.append(items[key])

    visit(item_id)
    if len(ordered) > limit:
        raise ValueError(f"work item closure has {len(ordered)} items, exceeding limit {limit}")
    unresolved = [entry for entry in queue.get("unresolved_prerequisites", [])
                  if entry["item_id"] in visited]
    if unresolved or any(item.get("blocked_by_unresolved_prerequisite") for item in ordered):
        raise ValueError(f"work item closure has unresolved prerequisite versions: {item_id}")
    return ordered


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--limit", type=int, default=8, help="maximum planned work items to display")
    parser.add_argument("--project", help="focus on one declared extension project or SQL name")
    parser.add_argument("--platform", help="focus on one declared platform, such as linux-x86_64")
    parser.add_argument("--postgresql-major", type=int, help="focus on one declared PostgreSQL major")
    parser.add_argument("--item-id", help="select one exact work item with its complete dependency closure")
    parser.add_argument("--all", action="store_true", help="display the full graph")
    args = parser.parse_args(argv)
    try:
        queue = build_queue(args.root)
        if args.item_id and (args.all or args.project or args.platform or args.postgresql_major):
            raise ValueError("--item-id cannot be combined with --all or target filters")
        if args.item_id:
            result = {"snapshot_as_of": queue["snapshot_as_of"], "item_id": args.item_id,
                      "planned_closure": select_item_closure(queue, args.item_id, args.limit),
                      "status": "planned; complete dependency closure within limit"}
        elif args.all:
            result = queue
        else:
            batch = select_batch(queue, args.limit, args.project, args.platform, args.postgresql_major)
            result = {"snapshot_as_of": queue["snapshot_as_of"],
                      "planned_batch": batch["selected_items"],
                      "unresolved_prerequisites": batch["unresolved_prerequisites"],
                      "omitted_dependency_count": batch["omitted_dependency_count"],
                      "limit": args.limit, "scope": queue["scope"],
                      "status": "preview; batch may omit later work items"}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (coverage.CoverageError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"extension-work-queue: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
