# Unmodified libxslt source at the macOS 11 target

[Run 39056557533](https://github.com/BernieSumption/pg_binaries/actions/runs/39056557533) built libxslt 1.1.45 against source-built libxml2 2.15.4 on standard macOS 15 Intel and Apple Silicon runners. Both jobs checked the libxslt source SHA-256 against its official sidecar and the libxml2 source against its pinned digest. The built dylibs have the expected architectures and declare macOS 11.0 as their minimum. The retained inspection and checksum files came from the CI artifacts for each architecture.

The installed dylibs name temporary build prefixes. This probe establishes source-build feasibility for libxslt with libxml2 only; relocation, transitive closure and final PostgreSQL archive verification remain open.
