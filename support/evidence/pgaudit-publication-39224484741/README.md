# pgAudit Linux publication evidence, run 39224484741

All eight pgAudit targets passed their build, relocated archive verification, receipt and record emission steps for PostgreSQL 15.19, 16.15, 17.11 and 18.6 on x86_64 and arm64. The aggregate run still concluded with failure: each verifier job failed only at the final `Require build, provenance, verification and import to pass` step because the CI importer expected the archive at the artifact root while this workflow placed it in `_temp/pgaudit/`.

The artifacts were independently imported after the importer fix using the current repository importer and the producer-revision support tree. These records describe the successful underlying archive verification at producer revision `b7798e14fcf12d2670e8abf7711f73fda5bb36e4`; they are historical evidence created after the importer fix and do not change the recorded aggregate run conclusion. Receipts identify Alpine Linux 3.22.6, a clean system, and passing dependency checks. PostgreSQL core archives were reused from `pgtap-linux-core` run 39210758552.

Each entry gives PostgreSQL version, architecture, pgAudit archive SHA-256, then core archive SHA-256:

- 15.19 x86_64: `69bdddf927ee71ed0dfbe5787b98b74d99e5f415d0b459491be3d9dd126154f1`; `49a1cd9e5a668ec1aa21fd00644613fbcd030cd5091c670909be01d4d1558b31`.
- 15.19 arm64: `b1be0fe7834dcd1dec6530bf967821bd298dfd969733c3878f6c615a64f979fa`; `eee5b48bb34614b759ab89db4525941451bc208616dedbbd89e9e67b9941bd0c`.
- 16.15 x86_64: `7cbc391a0e06bbc9555dd0228d2d985020d712e1ab7fd53ae98f358b5682c269`; `a6e8cd1920a4e40e06f3cddcf2896a8e0c84655d449e9bc20a65249e0da1bbc5`.
- 16.15 arm64: `996512c5be3d22be77bac1acbe67d7bfdfd32db2c38b928ee97b4c1351e3ca8b`; `64e8def6065bd2bec063e010b7c097b253d782cb16726f1b96e22be1ccbfe41f`.
- 17.11 x86_64: `61e2af838eb928c8194239bcd02e8d84c3a89d90d2555eafb71d8260ad54d663`; `1b724cce9953bd65a4463d651812ee7d0537df7dc8cd346e4d90c95874f3f79c`.
- 17.11 arm64: `8ed889be50796e15a8c0c6e9de19539b950a1e0257f4e85d5127ed1b64ea39d5`; `68f2df1c55d356c1c2d7963cc83a8cad178c7b84116260ecdf4a5852ae84a57f`.
- 18.6 x86_64: `f3943e04a8b1da62b37b190b0d65203f7ba3e1cd26fd9642cad5f12fc7821274`; `e817abe99aea45047d198528934cc3c3ce1d714bc5304ada937deeeacd4c099f`.
- 18.6 arm64: `1f5f86c5fabaf06027f2e6b50e476724393fb0529d24b432f04ff6e7ecff94be`; `00b4963c4ad6e2c04dfe04b07ce9c8998d874cc3746f1b522414022f90840842`.
