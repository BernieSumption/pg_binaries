# HypoPG Linux publication evidence from run 39271533561

[Linux changed-profile scheduler run 39271533561](https://github.com/BernieSumption/pg_binaries/actions/runs/39271533561) completed successfully at producer commit `0e7be7ff21129a84c7c80caa5c56a28f145e2da2`. Its final artifacts cover HypoPG 1.4.3 for PostgreSQL 15.19, 16.15, 17.11 and 18.6 on x86-64 and arm64.

The exact producer revision's `tools/import_linux_hypopg_publication.py` independently imported each selected-target artifact. It retained four files per target: the receipt, step outcomes, static analysis report and target-bound verification record. All 32 retained files matched the corresponding files embedded in the final CI artifacts byte for byte. The importer also checked each core and extension archive against its SHA-256 sidecar and bound those digests to its receipt and verification record. All eight records report `passed`.

Archive SHA-256 values from the downloaded final artifacts, independently checked by the importer against each sidecar and verification record:

- PostgreSQL 15.19, x86-64: HypoPG `2b4a7d5970e88d1f7cb15ff1d46113af1c8eac508938ff5deae812e45178cb07`; core `86d37fcf226ef4bbf47dca33f8ab10b4022fc68421fbd46e9151e41c9455aa69`.
- PostgreSQL 15.19, arm64: HypoPG `047d6a6cebe87ce39f484566d10f07502728d2e4d63c68fdcbe2db9270f3faf6`; core `2c299f83815797b50e5d97c1c4655bdbdb63d108e9150e0659d6f3df703a92c6`.
- PostgreSQL 16.15, x86-64: HypoPG `2363a79b38f042b0da572b087e1d12b6040cd3f603ff703210645195028658b4`; core `8af0d2e02cdbad8607014f5f4cddbc6e8282cdce8acd0b646b3689d8e152349`.
- PostgreSQL 16.15, arm64: HypoPG `a74c62db44d6bd054966c1f72c185d32e458784f215f869b340bde52df166a36`; core `b1df4aec7e3c86576bdf0b9becd5464752a98125d9a09ffa8e58b755973cc258`.
- PostgreSQL 17.11, x86-64: HypoPG `aeb0f06a6001dae1df41eaf0c4a76ba0a95f4ceb4a425667ef76ac6fb03c30cc`; core `d919cc90761f614ce6aff1694cb8bea7f445132f37b0d955f1fcfc1b90569916`.
- PostgreSQL 17.11, arm64: HypoPG `4df982978155bef536834458a7ee45e35f27091f81f4eee519fd130cd286cd4e`; core `9436bc7f10d2857d9e8565595573fa039e094c4dfb3c6ef03abdd4974a73622e`.
- PostgreSQL 18.6, x86-64: HypoPG `1b2eabf0ed0e2e800b1398971b490b26acf9a1ff2e4305ef2fcdc98e1a420a9f`; core `62528f99d68efe162e36bf0f28945d94daca3182cb95cc3e994c23577c3a4102`.
- PostgreSQL 18.6, arm64: HypoPG `94c4ecb3ce806657748e3f2f4c6a1d26c06098828f80754d35af31d9c489a25d`; core `1985357f3c2ed8a099ddcd3377a39a11a6ee651586d5117f081079fba836c464`.

Each record's `profile_revision` is accepted by that target profile's compatibility list in the current branch. This evidence covers only these eight PostgreSQL and architecture targets under the recorded Alpine Linux 3.22 verification environment; it does not establish compatibility for other profiles, distributions or operating systems.
