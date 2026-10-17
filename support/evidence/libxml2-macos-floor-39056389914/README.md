# Unmodified libxml2 source at the macOS 11 target

[Run 39056389914](https://github.com/BernieSumption/pg_binaries/actions/runs/39056389914) built libxml2 2.15.4 from its pinned upstream tarball on standard macOS 15 Intel and Apple Silicon runners. Both jobs checked the source SHA-256 against the official sidecar. The built dylibs have the expected architecture and declare macOS 11.0 as their minimum. The retained inspection and checksum files came from the CI artifacts for each architecture.

The installed dylib names its temporary build prefix. This probe establishes source-build feasibility for libxml2 only; relocation, transitive closure and final PostgreSQL archive verification remain open.
