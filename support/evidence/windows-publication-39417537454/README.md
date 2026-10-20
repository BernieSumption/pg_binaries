# Windows PostgreSQL 18.6 and pgvector 0.8.7

[Run 39417537454](https://github.com/BernieSumption/pg_binaries/actions/runs/39417537454) built pgvector against the checked PostgreSQL core from run 39291561227. A separate Windows runner passed relocation and SQL use, PE dependency inspection, PDB matching, and representative loader and server-log diagnostics. The importer checked both downloaded final archives and retained the archive-bound reports and records here and in `support/verification/`.

The core SHA-256 is `6c98dc1177ff11006009ee5a4f732c9d48db24f6da40551f63cdee0dfe9951d2`; pgvector is `6f8a119f362dc7d9206eecc73f3f0923a81a2effb18e660d143d4a84331e3015`. The core came from revision `9ac66ca5bac4e16233c813077bf9f1763e54c249`; pgvector and verification used revision `5a7cbd8e95ffa89f107931237a4f75f46a166dc7`.

The later pgcollection support-matrix correction changed this profile's whole-file `support.json` hash. These passing records remain historical until the profile fingerprint is narrowed or a current-profile verification is run. The archives are temporary Actions artifacts, not published releases.
