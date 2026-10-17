# Unmodified e2fsprogs libuuid at the macOS 11 target

[Run 39057581114](https://github.com/BernieSumption/pg_binaries/actions/runs/39057581114) built the libuuid shared library from unmodified e2fsprogs 1.47.3 source on standard macOS 15 Intel and Apple Silicon runners. Both jobs checked the source SHA-256 against the digest published by [the upstream project download page](https://sourceforge.net/projects/e2fsprogs/files/e2fsprogs/v1.47.3/e2fsprogs-1.47.3.tar.gz/download). The library has the expected architecture and declares macOS 11.0 as its minimum. The retained inspection and checksum files came from the CI artifacts for each architecture.

Its install name points to the temporary build prefix. This establishes source-build feasibility for libuuid only; integration, relocation and final PostgreSQL archive verification remain open.
