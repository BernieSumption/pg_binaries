# Windows PostGIS same-toolchain diagnostic

On 2026-10-20, [run 39479049259](https://github.com/BernieSumption/pg_binaries/actions/runs/39479049259) retried the unmodified PostgreSQL 18.6 and PostGIS 3.6.4 source build in MSYS2 MINGW64. Its artifact retained PostgreSQL's `config.log`.

PostgreSQL configure selected MSYS2 GCC 16.2.0. `gcc --version` succeeded, but `gcc conftest.c` exited with status 1 and no compiler or linker diagnostic in `config.log`; configure stopped with “C compiler cannot create executables.” This run did not compile PostgreSQL or PostGIS and did not test whether a PostGIS module loads. The cause of the compiler-probe failure remains unknown. A subsequent investigation should first reproduce that minimal GCC command on the runner and capture its subprocess and linker diagnostics before attempting another full build.
