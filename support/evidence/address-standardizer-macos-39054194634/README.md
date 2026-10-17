# Address Standardizer macOS source feasibility

[GitHub Actions run 39054194634](https://github.com/BernieSumption/pg_binaries/actions/runs/39054194634) checks the unmodified Address Standardizer v3.7.0 tag against PostgreSQL 18.6, with PCRE2 10.48 built from its upstream release tarball. The workflow revision is `ee72e1f2f5de97d14d80516cd9d2c6aa7bc24154`; the extension tag resolves to `fa11ff53eb49b863d9ffff37f6afd5ff9299c581`.

Both Apple Silicon and Intel jobs passed `CREATE EXTENSION` and representative parsing and standardization DDL for `address_standardizer` and `address_standardizer_data_us`. Mach-O inspection found the expected architecture and macOS 11.0 minimum-target metadata on each extension library and bundled PCRE2 library. The output files in `arm64/` and `x86_64/` came from the respective CI artifacts.

This establishes source-build feasibility only. Each extension's PCRE2 load command names an absolute CI build path, and no relocatable archives or final-byte publication verification were produced. A release build must resolve the load path under the upstream-only rule before this can count as support coverage.
