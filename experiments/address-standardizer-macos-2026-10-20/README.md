# Address Standardizer macOS archive trial

Created 2026-10-20.

## Question

Can unmodified Address Standardizer 3.7.0 and PCRE2 10.48 be packaged against the selected PostgreSQL 17.11 arm64 macOS core, then pass Mach-O dependency inspection and both SQL extension probes on a fresh macOS runner?

## Inputs

- The selected `postgresql-17.11-macos-arm64.tar.gz` archive and its resolver-generated `target.json`.
- Address Standardizer tag `v3.7.0`, commit `fa11ff53eb49b863d9ffff37f6afd5ff9299c581`.
- PCRE2 10.48 archive, checked against SHA-256 `b6c68fdf6f3ac31388b50aa89ff0fc49c00c987c16e7b5146491d12003f2c8ed`.
- Standard `macos-15` arm64 GitHub-hosted runners for separate build and verification jobs.

`workflow.yml` is a local trial definition. It is not installed under `.github/workflows` and has no selected dispatcher route. It retains raw archive hashes and probe/static-analysis output; it does not produce a validated repository archive-bound verification record.

The manual trial uses the registered `.github/workflows/address-standardizer-macos-probe.yml` path on `spike`. [Run 39447215667](https://github.com/BernieSumption/pg_binaries/actions/runs/39447215667) failed before compilation because the runner's Bash rejected process substitution around a here-document while reading the selected target. The recipe now captures the Python output before reading its fields; the archive and SQL checks still need a fresh run.

[Run 39447704128](https://github.com/BernieSumption/pg_binaries/actions/runs/39447704128) built PCRE2 and Address Standardizer, then failed while calculating staged paths because `pg_config` has no `--prefix` option. Final packaging and verification remained untested.

[Run 39448268625](https://github.com/BernieSumption/pg_binaries/actions/runs/39448268625) reached installation but showed that relocated `pg_config` reports paths under the extracted core, while its build-time configure prefix is only restored as a symlink. The staging check now uses the extracted core root that PGXS actually selected.

[Run 39448850741](https://github.com/BernieSumption/pg_binaries/actions/runs/39448850741) built and installed the extension, then failed the staging path guard: `pg_config` returned install paths through the restored original-prefix symlink, so the lexical paths appeared outside the extracted core. The recipe now resolves those paths for package-relative names and reads staged files under the original prefix used by PGXS. Archive packaging and verification still need a fresh run.

[Run 39449470691](https://github.com/BernieSumption/pg_binaries/actions/runs/39449470691) built and installed upstream sources but failed a silent staged-file assertion. The next trial will print the expected and actual staged paths before changing the recipe further.

## Completion and cleanup

The trial question is answered when the build produces the final extension archive and the fresh-runner job passes the archive suite and Mach-O closure inspection. If either fails, retain the logs and correct only concrete recipe errors before retrying.

After a passing trial, either migrate the path with standard archive-bound evidence emission/import and review its redistribution status, or remove this experiment. Remove it if the build cannot package the upstream sources without modifying them, or if the required evidence work is not justified. Recheck this experiment by 2027-01-20 if it remains open.
