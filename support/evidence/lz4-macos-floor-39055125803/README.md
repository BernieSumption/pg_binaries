# Corrected LZ4 macOS 11 source-build inspection

[Run 39055125803](https://github.com/BernieSumption/pg_binaries/actions/runs/39055125803) built unmodified upstream LZ4 1.10.0 on standard macOS 15 Intel and Apple Silicon runners with the deployment target set to macOS 11.0. Both jobs checked the source tarball against its upstream SHA-256 sidecar and inspected the resulting dylib. The retained `inspection.txt` and `source.sha256` files came from the CI artifacts for each architecture.

Both dylibs have the expected architecture and declare macOS 11.0 as their minimum. Their install name remains `/usr/local/lib/liblz4.1.dylib`, so this probe does not establish relocation or suitability of a final PostgreSQL archive. This run corrects the earlier inspection that also reported the temporary `otool` filename as a host path.
