# PostGIS Windows core ABI trial

On 2026-10-20, [run 39474845275](https://github.com/BernieSumption/pg_binaries/actions/runs/39474845275) used the standard `windows-2022` runner and MSYS2 CLANG64 to configure unmodified PostGIS 3.6.4 against the checked MSVC-built PostgreSQL 18.6 core archive. It checked the exact core archive and PostGIS source hashes, then stopped during configure before compiling PostGIS.

The configure log shows that `pg_config` selected `CC='cl'` from the MSVC PostgreSQL build. The MSYS2 shell had no `cl` command, so the `PQserverVersion` link check failed with `./configure: line 1867: cl: command not found`. The core archive contains `libpq.a` and `libpq.lib`; the failure does not establish a missing libpq or an ABI incompatibility. The run artifact retains the configure log for its three-day lifetime.

The next investigation must choose an upstream-supported build environment that can use this exact core, or establish that a Windows core built in the upstream PostGIS toolchain is acceptable for all selected extensions. Do not expand dependency packaging or other PostgreSQL targets until a module loads into the selected core.
