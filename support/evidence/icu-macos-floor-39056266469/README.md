# Unmodified ICU source at the macOS 11 target

[Run 39056266469](https://github.com/BernieSumption/pg_binaries/actions/runs/39056266469) built ICU 78.3 from its pinned upstream tarball on standard macOS 15 Intel and Apple Silicon runners. Both jobs verified the source SHA-256. The built dylibs have the expected architecture, declare macOS 11.0 as their minimum and list only relative ICU dylib names and system libraries in their load commands. The retained inspection and checksum files came from the CI artifacts for each architecture.

This probe establishes source-build feasibility for ICU only. Final archive dependency closure and PostgreSQL verification remain open.
