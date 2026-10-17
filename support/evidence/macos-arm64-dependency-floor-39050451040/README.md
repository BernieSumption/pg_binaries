# macOS 11 dependency-floor probe

[Apple Silicon run 39050451040](https://github.com/BernieSumption/pg_binaries/actions/runs/39050451040) used vcpkg commit `bf19794383e8fb95eba5aa553235bc8ec2271688` on a standard macOS 15 runner with `VCPKG_OSX_DEPLOYMENT_TARGET=11.0`. Its [retained report](floors.json) records 70 dylib paths, all with Mach-O minimum-version metadata of 11.0. This is a dependency build probe; it did not build or test a PostgreSQL archive.

The run log shows vcpkg applying source patches to these libraries, including `cxx-for-icu.diff` to libxml2, `target-lz4-lz4.diff` to LZ4 and `cmake-config.patch` to OpenSSL. The repository's [upstream-only specification](../../../specs/functional.md#never-patch-or-modify-extensions-or-dependencies) prohibits this route for release assets. The result shows that source-built dependencies can carry the intended Mach-O target; a production build still needs unmodified upstream source and final-archive verification.
