# Windows PostGIS selected-core configure result

On 2026-10-20, [run 39495924217](https://github.com/BernieSumption/pg_binaries/actions/runs/39495924217) downloaded the checked PostgreSQL 18.6 Windows x86-64 archive and attempted to configure unmodified PostGIS 3.6.4 in MSYS2 MINGW64. A previous selected-core run failed the `libpq` link check; this trial supplied `.a` copies of the selected core's `.lib` import libraries inside the disposable extraction.

The retained `postgis-3.6.4/config.log` shows that the link check invoked `cl -o conftest.exe ... /wd4018 ... -lpq` and failed with `cl: command not found`. PostGIS obtained this compiler and its flags from the selected core's `pg_config` despite the command's `CC=gcc` setting. This attempt therefore did not test whether GCC can link the MSVC import library or load the resulting module. The next trial substitutes build-tool answers from a disposable `pg_config` wrapper while preserving the selected core's paths and version.
