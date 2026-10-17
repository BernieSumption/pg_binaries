# Unmodified OpenSSL source at the macOS 11 target

[Run 39055374951](https://github.com/BernieSumption/pg_binaries/actions/runs/39055374951) built OpenSSL 3.5.8 from its upstream release tarball on standard macOS 15 Intel and Apple Silicon runners. Both jobs confirmed SHA-256 `a8f84a39918ec6415ce765d9b429d313ba97b8143169c172e734b9514464f5b2` against the official sidecar and computed source digest. The retained `inspection.txt` and `source.sha256` files came from the CI artifacts for each architecture.

The installed libcrypto, libssl, provider and engine dylibs have the expected architecture and declare macOS 11.0 as their minimum. Their load paths point to the temporary CI installation prefix. This probe establishes source-build feasibility for OpenSSL; relocation, transitive closure and final PostgreSQL archive verification remain open.
