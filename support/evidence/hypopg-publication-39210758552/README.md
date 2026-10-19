# HypoPG selected Linux publication verification

[GitHub Actions run 39210758552](https://github.com/BernieSumption/pg_binaries/actions/runs/39210758552) tested source revision `80c23e1ba5087bb79f90ffdab64ec46c2cedaa5d` on 2026-10-19. It built and verified HypoPG 1.4.3 against PostgreSQL 15.19, 16.15, 17.11 and 18.6 on Linux x86-64 and arm64. All eight archive-suite records passed.

The core resolution manifests report `origin: built` for all eight targets, with `build_id: github-39210758552-1`; none reused a prior core. SHA-256 values below were calculated from the downloaded selected artifacts. The independent importer checked each archive against its sidecar, receipt and verification record, then confirmed that retained evidence did not conflict with the downloaded bytes.

- PostgreSQL 15.19 arm64: core `963060811cbae8e28eb7e83d7ec8d5f2be839556ba016d93792c965efd4e5b60`; HypoPG `3c2d1912e2d354c64cb4d87fc6c3a537db85122765c24a3436abb7129e3b246e`.
- PostgreSQL 15.19 x86-64: core `9a1baf17d45a729d844b8f9b690ff88714f4bdb4f9077e539ec4ea4abbd1f928`; HypoPG `d1c343e48c196ccfb851446dc3a1c6b0f89344802ab2ac1b2189842e47d7f0b4`.
- PostgreSQL 16.15 arm64: core `723de0a08a7f8ed0eaffce881144143d824ccae8ce1fd3305dd569670bdee144`; HypoPG `1c4ed6c5d6841213cc5c35d66308ad50e12325e9a8354f4f2ecc9cc21d8bc6a6`.
- PostgreSQL 16.15 x86-64: core `4c272a01ac12db39b379c9d2c311989f9a46ece376ad1a2873f269958260c4da`; HypoPG `87e10c027ad5882f12bbab3e6487d71a15166bdef8c49880572d7d44ff2e84ce`.
- PostgreSQL 17.11 arm64: core `7a37b9a01173f7211d9cef28b713ee49bb7154135e12cb7400353cc47618e775`; HypoPG `f414ab12ca7d5fed378dae10b99462ca6d860e1f644e3046dc423652d1a4e3e3`.
- PostgreSQL 17.11 x86-64: core `6d3b2d74a4024726b444be9668ed063773ad6216fdf79e26e77f822ab9694fac`; HypoPG `dddc63b1df2cf72fd84e2399448668c5fbbfdf441ebf34705df147a60788b4a3`.
- PostgreSQL 18.6 arm64: core `b0a8219ae31511e30f1fafb6b4cbcf4fd7ce7bcd6e8a19b363646bf119326266`; HypoPG `c974aa11d46b3b0be5e8c1558f354d8026bd2c0dee7b16cb56916e1fa82ee043`.
- PostgreSQL 18.6 x86-64: core `8939ccb59a8c38b5f56446fd2f42784bb1df4eacd0a41d0544e78486d08be2d9`; HypoPG `8b27b6671db5d30d0d5376f640f0ea02733272f7fa11afb2c0ab9a4479702ad8`.

The eight verification records are under `support/verification/`; receipts, step outcomes and static-analysis reports are retained under this directory by architecture and PostgreSQL version.
