# pg_ivm Linux publication evidence

GitHub Actions run [39074569076](https://github.com/BernieSumption/pg_binaries/actions/runs/39074569076) built and verified pg_ivm 1.16 with PostgreSQL 18.6 on x86_64 and arm64. Both publication cases passed on Alpine Linux 3.22.6. The retained receipts bind the verification to the exact core and extension archive digests:

- x86_64 core: `74bcee2fc09aaf25edd8a7a58e3ddb00f7d4bad1b6f3847c98646b361e2d7f20`; pg_ivm: `462a6a0e53ec1d9264d6fe7fa999c333a34e4d38cbe2767a4ec8c08e8360c2e1`.
- arm64 core: `0ff8c99e5106de0b3d34a5fbbbfc1675b83a6c50f0511841b3d8346318064c34`; pg_ivm: `ee5ce5136e87f2f1b811c8557714d2c77404239daa7dfc409d5dce9c47aff579`.

The raw attempts, step outcomes, receipts and static-analysis reports are retained by architecture in this directory. Archive-bound verification records are in `support/verification/`. They were validated against source revision `188268a9b7b21ee247123f94d363edbbbac281ae`. The publication profile and build inputs changed afterward for the PostgreSQL 15–18 matrix, so the current coverage view correctly treats these PG18 results as stale; they are historical evidence and do not count as current coverage.
