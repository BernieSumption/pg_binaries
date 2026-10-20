# Windows PostGIS same-toolchain trial, run 39478214213

Run: https://github.com/BernieSumption/pg_binaries/actions/runs/39478214213

The Windows Server 2022 job installed MSYS2 MINGW64 dependencies and verified the PostgreSQL 18.6 source archive checksum. With `CC=gcc`, PostgreSQL configure selected `gcc` for `x86_64-w64-mingw32` but its compiler check failed: `checking whether the C compiler works... no` and `C compiler cannot create executables`. The uploaded build log does not include `config.log`, so the lower-level compiler error is unavailable.

The run stopped before PostgreSQL compiled and before PostGIS or the SQL probe ran. Together with [the CLANG64 build failure](../postgis-windows-abi-39476749270/README.md) and [the initial MINGW64 configure failure](../postgis-windows-abi-39477479928/README.md), it leaves Windows PostGIS ABI compatibility untested.
