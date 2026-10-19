# Address Standardizer selected Linux post-cleanup matrix

After the pinned publication workflows and core-run lists were removed, the shared dispatcher built and verified Address Standardizer 3.7.0 against every selected PostgreSQL release on both Linux architectures:

- PostgreSQL 15.19: [x86-64 run 39258732080](address-standardizer-linux-publication-39258732080/README.md) and [arm64 run 39258736054](address-standardizer-linux-publication-39258736054/README.md).
- PostgreSQL 16.15: [x86-64 run 39258737088](address-standardizer-linux-publication-39258737088/README.md) and [arm64 run 39258735375](address-standardizer-linux-publication-39258735375/README.md).
- PostgreSQL 17.11: [x86-64 run 39258734639](address-standardizer-linux-publication-39258734639/README.md) and [arm64 run 39258735757](address-standardizer-linux-publication-39258735757/README.md).
- PostgreSQL 18.6: [x86-64 run 39257708823](address-standardizer-linux-publication-39257708823/README.md) and [arm64 run 39258735498](address-standardizer-linux-publication-39258735498/README.md).

Every run passed `archive-suite` and `elf-closure`. The importer retained all 11 evidence files and the verification record from each run; independent comparison found them byte-identical to the CI artifacts. All eight records match the registered current profiles. They remain release-ineligible pending dependency provenance and redistribution review.
