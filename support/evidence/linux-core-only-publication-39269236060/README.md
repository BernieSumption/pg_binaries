# Linux PostgreSQL core-only evidence from run 39269236060

[Linux changed-profile scheduler run 39269236060](https://github.com/BernieSumption/pg_binaries/actions/runs/39269236060) produced passing core-only jobs at commit `df414ccfa0a5352a0801a9f9d0017b31673db36d` for PostgreSQL 15.19, 16.15, 17.11 and 18.6 on x86-64 and arm64. The overall scheduler run was still in progress on unrelated targets when these records were imported.

The importer at the exact producer revision checked the eight final selected artifacts and retained ten evidence files plus one verification record per target. All eight core archives matched their corresponding core build artifacts byte for byte, their SHA-256 sidecars matched, and all eight records report `passed`. The record profile revisions equal the current profile revisions at both the producer commit and the importing workspace revision.

This evidence covers the selected core-only publication profiles on the recorded Linux runners. Reuse of a temporary artifact as a planner candidate still requires a successful producer run and current recipe and builder-input checks.
