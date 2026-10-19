# Intel HypoPG profile refresh, 2026-10-19

[Run 39196052697](https://github.com/BernieSumption/pg_binaries/actions/runs/39196052697) passed the PostgreSQL 18.6 and HypoPG 1.4.3 selected Intel Mac build and fresh-runner verifier at revision `492c29e3f2e9253cfa240a52a5e581612812de22`. The shared macOS core-target helper change had invalidated the previous profile record.

The candidate and publication artifacts were downloaded. An independent import using the exact source revision reproduced all five retained files byte-for-byte, including the final-archive verification record. The record binds the HypoPG archive to the checked PostgreSQL archive and current profile revision.
