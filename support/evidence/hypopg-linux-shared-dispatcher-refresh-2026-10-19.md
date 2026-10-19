# Linux HypoPG shared-dispatcher refresh, 2026-10-19

[x86-64 run 39196689245](https://github.com/BernieSumption/pg_binaries/actions/runs/39196689245) and [arm64 run 39196690111](https://github.com/BernieSumption/pg_binaries/actions/runs/39196690111) passed the shared dispatcher at revision `26848cf` for PostgreSQL 17.11 and HypoPG 1.4.3. Each selected and verified its target, and retained a record binding the extension archive to the exact PostgreSQL archive and current Linux profile revision.

The artifacts were downloaded after CI. The importer independently validated each core and extension archive and reproduced the four retained files for each architecture. All eight files match the corresponding CI artifact bytes. The scoped HypoPG-only planner trial and its temporary request have been removed; the selected Linux workflow now gives preceding shared-dispatcher artifacts candidate precedence when called through that entry point.
