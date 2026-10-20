# pg_cron Windows feasibility

Created 2026-10-20 to check whether upstream pg_cron 1.6.8 builds and runs against the checked PostgreSQL 18.6 Windows archive without source changes. The [trial workflow](../../.github/workflows/pgcron-windows-feasibility.yml) transfers final archives to a separate runner, checks matching PDBs and PE dependencies, and exercises a scheduled background-worker job. Its inputs are the pinned upstream source and `support/windows-core-pins/18.6-x86_64.json`.

When this target passes, move the tested recipe and probe into a selected publication profile, retain compact archive-bound evidence, and remove the trial workflow and this note. If it fails for a reason requiring an upstream source change, record the finding and follow the no-project-patches rule.
