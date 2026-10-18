# PostGIS and TIGER selected Linux trial

Created 18 October 2026 to check PostGIS 3.6.4 and TIGER 2025.2 together with PostgreSQL 18.6 on Linux x86_64. The trial asks whether the existing combined Alpine verifier can validate the final archives from one historical publication run.

The workflow downloads the PostgreSQL, PostGIS, and TIGER evidence artifacts from run 39075939610. It requires exact archive names and SHA-256 values: PostgreSQL `e532b07c29904db82d1681f1a4ab815364b769a4e1f277c9de9bcd45d0cdc7c6`, PostGIS `8afe3bb3e27e483e8b54943eec89c65737b32a57b58f4fdf14abfa7ee67f6465`, and TIGER `208c0e68f10d44d4b5e764627be488464329573907efcd346f167e2c7f9ef149`.

The existing combined verifier's core phase also checks pgvector 0.8.7. The historical PostgreSQL artifact includes that archive; the workflow pins it to SHA-256 `c94c26bb5eb07fe479d182e2b02c823bd8674698c8a3629d7fcc15b9fba67ccb`, recorded in the run's retained PostgreSQL publication receipt. The PostGIS and TIGER phases use their pinned archive inputs and preserve phase logs and static analysis reports in a seven-day Actions artifact.

The trial ends when a clean run completes the combined verifier. Review it after that result, after changes to the target, or within three months. Remove the workflow and this experiment when no further investigation is needed; retain useful verification results under `support/evidence/`.
