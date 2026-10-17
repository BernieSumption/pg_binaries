# Unmodified Zstandard source at the macOS 11 target

[Run 39055344195](https://github.com/BernieSumption/pg_binaries/actions/runs/39055344195) built Zstandard 1.5.7 from its pinned upstream tarball on standard macOS 15 Intel and Apple Silicon runners. Both jobs verified the source SHA-256, and their dylibs have the expected architecture and declare macOS 11.0 as the minimum. The retained `inspection.txt` and `source.sha256` files came from the CI artifacts for each architecture.

The installed dylibs name `/usr/local/lib/libzstd.1.dylib`. This probe establishes source-build feasibility for Zstandard only; relocation, transitive closure and final PostgreSQL archive verification remain open.
