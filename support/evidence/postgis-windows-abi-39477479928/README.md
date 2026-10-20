# Windows PostGIS same-toolchain trial, run 39477479928

Run: https://github.com/BernieSumption/pg_binaries/actions/runs/39477479928

The Windows Server 2022 job installed MSYS2 MINGW64 dependencies and verified the PostgreSQL 18.6 source archive checksum. PostgreSQL configure selected `x86_64-w64-mingw32-gcc` from `--host=x86_64-w64-mingw32`, then reported that the C compiler could not create executables. The build stopped before PostgreSQL compiled and before PostGIS or the SQL probe ran.

This run provides no ABI conclusion. It follows the [CLANG64 trial](../postgis-windows-abi-39476749270/README.md), which also stopped in PostgreSQL compilation before PostGIS. Further build work would need to make PostgreSQL configure use the MINGW64 compiler while keeping the PostgreSQL and PostGIS toolchains aligned.
