# Architecture migration baseline, 18 October 2026

This inventory describes the `spike` implementation at commit `76661d5`, before the architecture trial. It records where migration starts; it does not establish that any archive is eligible for release.

## Build and verification paths

The repository has 89 GitHub Actions workflow files: 47 publication candidates, 40 investigations and two infrastructure workflows. Only `profile-change-scope.yml` is a reusable workflow. The publication workflows are candidate build or verification paths, not permanent GitHub Release publishers. They often duplicate a project and platform path for several PostgreSQL releases. pgTAP, collection and pg_jsonschema on macOS, and HypoPG on Windows, have both generic and release-specific wrappers. These paths need case-by-case comparison before one replaces another. `tools/architecture_inventory.py` produces a current workflow-to-profile inventory for migration and cleanup reviews.

Forty-four workflows contain a fixed upstream artifact run ID. The IDs provide exact inputs while the corresponding Actions artifacts exist, but they are embedded in target configuration and expire. The selected-target planner in `tools/extension_work_queue.py` already models core builds, project archive candidates, verification and prerequisites. Its optional candidate manifest checks local archive bytes and embedded target metadata. It does not retrieve missing candidate bytes or dispatch work to CI. It also does not yet establish whether a candidate was built with the currently intended source, dependencies, configuration and recipe.

The active platform code is under `scripts/linux/`, `scripts/macos/` and `scripts/windows/`. Project code is under `scripts/<project>/`. Linux has a shared publication workflow and project-specific build and verify scripts. macOS and Windows have more project-specific workflows and evidence writers. HypoPG's PostgreSQL 17.11 macOS arm64 and Windows x86-64 publication paths already verify downloaded final archives in separate jobs. Several other macOS and Windows extension paths still run their archive suites on the build runner and need migration to the fresh-runner requirement.

The publication workflow migration groups are:

- The one `linux-publication.yml` combines PostgreSQL core with several extensions on both Linux architectures. Its selected-target replacement must preserve core and per-extension profiles while allowing a bounded project retry.
- Two Address Standardizer Linux workflows cover PostgreSQL 18.6 and 15.19–17.11. They use `scripts/address_standardizer/linux-build.sh` and `linux-verify.sh`, with the matching Linux evidence emitter and importer.
- Eight collection macOS workflows cover two architectures and four PostgreSQL releases. They share `scripts/collection/macos-feasibility.sh` and `tools/import_collection_macos_publication.py`.
- Six HypoPG macOS and Windows workflows have separate platform recipes and importers; the Linux path is inside `linux-publication.yml`. The PostgreSQL 17.11 macOS arm64 and Windows x86-64 workflows are already fresh-runner references.
- Twelve pg_jsonschema workflows cover Linux, macOS and Windows. They use `scripts/pg_jsonschema/` platform recipes and three platform evidence importers.
- Two pg_cron and four pg_ivm macOS workflows use their project recipes and evidence importers; their Linux paths are inside `linux-publication.yml`.
- Twelve pgTAP macOS and Windows workflows cover two Mac architectures, Windows x86-64 and four PostgreSQL releases. They share project recipes and one importer per operating system; their Linux path is inside `linux-publication.yml`.

The generic workflow names usually select PostgreSQL 18.6, while release-suffixed names select another currently supported PostgreSQL release. None of these 47 files can be retired based on its name alone. Compare selected targets, required profile cases and archive-bound evidence before replacing each group. Feasibility and probe workflows remain investigation paths until their results and next use are reviewed.

`tools/coverage.py`, `support/verification-profiles.json`, the platform dependency inspectors and the archive staging tools provide shared checks. Project and platform emitters and importers repeat receipt construction, archive binding and evidence retention. Existing SQL probes are partly reused across platforms; differences must be reviewed against required behaviour before consolidation. The retained archive-bound records under `support/evidence/` remain historical evidence when their producing workflow is retired.

## Investigation paths

Feasibility, pilot, probe, QEMU and agent-trial workflows support investigations. Some still have push triggers, so file changes can start optional work. `scripts/dependency_probes/`, older project feasibility scripts and the pg_repack, pg_partman, pg_squeeze and pg_stat_monitor trials require the cleanup review in `policies/architecture.md`. An investigation that remains useful belongs under `experiments/<name>/` with its creation date, question, inputs and exit condition; useful results remain under `support/evidence/`.

Before deleting any path, the migration must identify its selected targets, profile cases, successor path and evidence impact. The first proof targets and completion checks are in `GOAL_BACKLOG.md` under Architecture migration.
