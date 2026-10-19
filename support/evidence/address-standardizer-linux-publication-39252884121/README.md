# Address Standardizer selected Linux trial, run 39252884121

The [selected-target CI run](https://github.com/BernieSumption/pg_binaries/actions/runs/39252884121) passed PostgreSQL 18.6 on Linux x86-64 through the final evidence gate. It built PostgreSQL in the same run after core resolution found no reusable candidate, then built Address Standardizer 3.7.0 and PCRE2 against that core. The relocated Alpine 3.22 archive suite and ELF closure check both passed.

The imported record uses source and test revision `8bfdb74957b3f22f5d9df7571011b1b8e63aa944` and current profile revision `ade7cca6a155f1f87b622c3284e6d90a6ccd7c5c9ed1442e056392e5e57a8be5`. The final Address Standardizer archive SHA-256 is `89486647342dc876bc1bfaf7f2142956c6b6dbc826957b4e46ea1c8abd625998`; the PostgreSQL archive SHA-256 is `32761bc640abcd3341aead972863bcac0193d47eef7c38c20c89f98fcfad2aa4`. Retained evidence and the verification record match the CI artifact byte-for-byte.

This candidate remains release-ineligible pending the dependency provenance and redistribution review recorded in `GOAL_BACKLOG.md`.
