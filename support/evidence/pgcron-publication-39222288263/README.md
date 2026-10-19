# pg_cron Linux publication, run 39222288263

The selected `pg_cron` 1.6.8 archives passed their publication profiles for PostgreSQL 15.19, 16.15, 17.11 and 18.6 on x86_64 and arm64. All eight attempts report successful core, extension build and verification steps. Receipts identify Alpine Linux 3.22.6, a clean system, and passing dependency checks. The importer checked the selected profile, receipt and record identities, archive sidecar hashes, and the matching core archive hash before retaining the evidence under this directory and `support/verification/`.

All attempts use source revision `de32190cc638fa45cc8b56f779a0e760be4b2f2e`. Each PostgreSQL core archive was reused from the verified `pgtap-linux-core` artifacts produced by run 39210758552. Core archives were not rebuilt for this run.

The following entries give PostgreSQL version, architecture, `pg_cron` archive SHA-256, then core archive SHA-256:

- 15.19 x86_64: `4f1797caf42529aaaec3a66eadb7e0945b540eec2b4d31b615d2c2756d247f37`; `49a1cd9e5a668ec1aa21fd00644613fbcd030cd5091c670909be01d4d1558b31`.
- 15.19 arm64: `99a90423ca63a6051e9832ad8a5ce53727a60915ce1e570a0cf7e9c298e9b8a9`; `eee5b48bb34614b759ab89db4525941451bc208616dedbbd89e9e67b9941bd0c`.
- 16.15 x86_64: `1ae159891ef2daf0229405c56784d22c8579181230f12a0d316eddd685ea70c7`; `a6e8cd1920a4e40e06f3cddcf2896a8e0c84655d449e9bc20a65249e0da1bbc5`.
- 16.15 arm64: `d25eeef8fa207facccb90b16312edce964dc539ba9a94f3baf222febea2937bc`; `64e8def6065bd2bec063e010b7c097b253d782cb16726f1b96e22be1ccbfe41f`.
- 17.11 x86_64: `d76e3057341a0e4b6ac20b4b69e23c0c1496e0e7bb312e4279b9e44c14d5cd78`; `1b724cce9953bd65a4463d651812ee7d0537df7dc8cd346e4d90c95874f3f79c`.
- 17.11 arm64: `eb4ba373dd9f03484db0bf0388d1f026f34ac3b369680806406f3a67af535a60`; `68f2df1c55d356c1c2d7963cc83a8cad178c7b84116260ecdf4a5852ae84a57f`.
- 18.6 x86_64: `4b34b045c413b3801bad200c46009f2f0bf516f1521ec7e863481b4194ec8803`; `e817abe99aea45047d198528934cc3c3ce1d714bc5304ada937deeeacd4c099f`.
- 18.6 arm64: `fffbaac49af50960936a39a417788e5f55309b1fbea89b5d07fb6be1913bf574`; `00b4963c4ad6e2c04dfe04b07ce9c8998d874cc3746f1b522414022f90840842`.
