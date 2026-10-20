# Windows PostGIS toolchain smoke test

On 2026-10-20, [run 39480171231](https://github.com/BernieSumption/pg_binaries/actions/runs/39480171231) tested MSYS2 MINGW64 GCC before downloading or building PostgreSQL. A trivial `int main(void) { return 0; }` program failed to compile. GCC 16.2.0 printed its invocation of `cc1.exe`, then exited with status 1 and no further diagnostic. This explains why PostgreSQL's earlier configure probe failed, but it does not identify why `cc1.exe` could not compile on this runner.

No PostgreSQL or PostGIS source was built, and no module-load or ABI result exists from this trial. Diagnose the compiler subprocess in isolation before rerunning the full source build. The [earlier configure log](../postgis-windows-abi-39479049259/README.md) and this job's log retain the failure boundary.
