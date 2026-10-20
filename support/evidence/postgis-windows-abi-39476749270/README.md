# Windows PostGIS same-toolchain trial, run 39476749270

Run: https://github.com/BernieSumption/pg_binaries/actions/runs/39476749270

The Windows Server 2022 job installed the MSYS2 CLANG64 dependencies, verified the PostgreSQL 18.6 source archive checksum, and configured the upstream PostgreSQL source build. It failed while compiling PostgreSQL itself in `src/common/pg_get_line.c`, before PostGIS was built or any extension load was attempted.

The failing expression passes PostgreSQL's MinGW `sigjmp_buf` (`long long[5]`) to Clang's `__builtin_setjmp`, which expects `void **`. The compiler reported incompatible pointer types and stopped `make`. This run therefore provides no PostGIS ABI conclusion. The follow-up trial uses the upstream-supported MSYS2 MINGW64/GCC environment to determine whether that compiler-specific blocker is avoided.
