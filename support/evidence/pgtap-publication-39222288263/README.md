# pgTAP Linux publication, run 39222288263

The selected pgTAP 1.3.4 archives passed their publication profiles for PostgreSQL 15.19, 16.15, 17.11 and 18.6 on x86_64 and arm64. All eight receipts identify Alpine Linux 3.22.6, a clean system and passing dependency checks. The importer validated each current profile, receipt, verification record and exact archive hash before retaining evidence under this directory and `support/verification/`.

All targets use source revision `de32190cc638fa45cc8b56f779a0e760be4b2f2e`. PostgreSQL core archives were reused from the verified `pgtap-linux-core` artifacts produced by run 39210758552; none were rebuilt for this run.

Each entry gives PostgreSQL version, architecture, pgTAP archive SHA-256, then core archive SHA-256:

- 15.19 x86_64: `062b4a73ea85ef8e2ea4323e9faf86e06e08161fed86c4e4f7779d249d64e015`; `49a1cd9e5a668ec1aa21fd00644613fbcd030cd5091c670909be01d4d1558b31`.
- 15.19 arm64: `ca87993f84120fb4adea8c49955ed4802857d6345baef19e2d2043264918d64c`; `eee5b48bb34614b759ab89db4525941451bc208616dedbbd89e9e67b9941bd0c`.
- 16.15 x86_64: `3f690eac53290128fc3ae3628b204face763e9ccc4b8b02a764357b7863c9815`; `a6e8cd1920a4e40e06f3cddcf2896a8e0c84655d449e9bc20a65249e0da1bbc5`.
- 16.15 arm64: `e07e4940942b1c8fb8383791399745b97b19bd0fe7f1e4b18126005395cea063`; `64e8def6065bd2bec063e010b7c097b253d782cb16726f1b96e22be1ccbfe41f`.
- 17.11 x86_64: `201529083e1e2ff8c8aa59cfe0da0969c4f11119fe91437d4a3f8145829d3bc9`; `1b724cce9953bd65a4463d651812ee7d0537df7dc8cd346e4d90c95874f3f79c`.
- 17.11 arm64: `06a4f40763105c25d24cf6a53c7c3e01817614023ba25b04b414ed9c48879d21`; `68f2df1c55d356c1c2d7963cc83a8cad178c7b84116260ecdf4a5852ae84a57f`.
- 18.6 x86_64: `4b66d447449a9579125ae834291e00005bcfbbbc3ee9b114aa68c353eb32d07b`; `e817abe99aea45047d198528934cc3c3ce1d714bc5304ada937deeeacd4c099f`.
- 18.6 arm64: `76d382308c767c4f69f54e6f237fc9d81d6479c8f9d65ca062fdb8ba57989587`; `00b4963c4ad6e2c04dfe04b07ce9c8998d874cc3746f1b522414022f90840842`.
